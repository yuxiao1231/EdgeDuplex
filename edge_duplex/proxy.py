import asyncio
import socket
from typing import Optional, Tuple, List
from .routing import RoutingManager, DuplexError
from .config import config, LOG_FILE
import time

def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")

def log(message: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{now()}] {message}\n")

async def read_exact(reader: asyncio.StreamReader, n: int) -> bytes:
    data = await reader.readexactly(n)
    return data

class SocksProxy:
    def __init__(self, bind_ip: str, gateway: str, proxy_interface: str, port: int, force_routes: bool, dns_server: str = "1.1.1.1") -> None:
        self.bind_ip = bind_ip
        self.gateway = gateway
        self.proxy_interface = proxy_interface
        self.port = port
        self.force_routes = force_routes
        self.dns_server = dns_server
        self.stopping = asyncio.Event()
        self.server: Optional[asyncio.AbstractServer] = None
        self.routed_ips: set[str] = set()
        self.if_index = 0

    async def start(self) -> None:
        try:
            info = RoutingManager.get_interface_info(self.proxy_interface)
            self.if_index = info.get("InterfaceIndex", 0)
        except Exception as e:
            log(f"Failed to get if_index for {self.proxy_interface}: {e}")

        self.server = await asyncio.start_server(
            self.handle_client, "127.0.0.1", self.port)
        log(f"SOCKS5 listening on 127.0.0.1:{self.port}, bind_ip={self.bind_ip}")

    async def stop(self) -> None:
        self.stopping.set()
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        try:
            ver_methods = await read_exact(reader, 2)
            if ver_methods[0] != 5:
                return
            nmethods = ver_methods[1]
            await read_exact(reader, nmethods)
            writer.write(b"\x05\x00")
            await writer.drain()

            hdr = await read_exact(reader, 4)
            ver, cmd, _rsv, atyp = hdr
            if ver != 5 or cmd != 1:
                await self.reply(writer, 7)
                return
            if atyp == 1:
                host = socket.inet_ntoa(await read_exact(reader, 4))
            elif atyp == 3:
                ln = (await read_exact(reader, 1))[0]
                host = (await read_exact(reader, ln)).decode("idna")
            elif atyp == 4:
                await self.reply(writer, 8)
                return
            else:
                await self.reply(writer, 8)
                return
            port = int.from_bytes(await read_exact(reader, 2), "big")

            out_reader, out_writer = await self.connect_out(host, port)
            await self.reply(writer, 0)
            await self.pipe_pair(reader, writer, out_reader, out_writer)
        except asyncio.IncompleteReadError:
            pass
        except Exception as exc:
            log(f"client {peer} error: {exc}")
            try:
                await self.reply(writer, 5)
            except Exception:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def resolve_dns_doh(self, domain: str, timeout: float = 5.0) -> List[str]:
        import ssl, json, urllib.parse
        loop = asyncio.get_running_loop()
        ctx = ssl.create_default_context()
        
        sni = "cloudflare-dns.com"
        if self.dns_server == "8.8.8.8" or self.dns_server == "8.8.4.4":
            sni = "dns.google"
        elif self.dns_server != "1.1.1.1" and self.dns_server != "1.0.0.1":
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        sock.bind((self.bind_ip, 0))
        
        if self.force_routes and self.dns_server not in self.routed_ips and self.if_index:
            try:
                RoutingManager.add_host_route_fast(self.dns_server, self.gateway, self.if_index)
                self.routed_ips.add(self.dns_server)
                from .state import runtime_state
                if self.dns_server not in runtime_state.added_routes:
                    runtime_state.added_routes.append(self.dns_server)
                    runtime_state.save()
            except Exception as route_exc:
                log(f"route add failed for DNS {self.dns_server}: {route_exc}")

        try:
            await asyncio.wait_for(loop.sock_connect(sock, (self.dns_server, 443)), timeout=timeout)
            reader, writer = await asyncio.open_connection(sock=sock, ssl=ctx, server_hostname=sni if ctx.check_hostname else None)
            
            host_header = sni if sni else self.dns_server
            req = f"GET /dns-query?name={urllib.parse.quote(domain)}&type=A HTTP/1.1\r\n"
            req += f"Host: {host_header}\r\n"
            req += "Accept: application/dns-json\r\n"
            req += "Connection: close\r\n\r\n"
            
            writer.write(req.encode("ascii"))
            await writer.drain()
            
            resp = await asyncio.wait_for(reader.read(), timeout=timeout)
            writer.close()
            await writer.wait_closed()
            
            header, body = resp.split(b"\r\n\r\n", 1)
            data = json.loads(body.decode("utf-8"))
            ips = []
            if "Answer" in data:
                for ans in data["Answer"]:
                    if ans["type"] == 1:
                        ips.append(ans["data"])
            return ips
        finally:
            try:
                sock.close()
            except Exception:
                pass

    async def connect_out(self, host: str, port: int) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        loop = asyncio.get_running_loop()
        is_ipv4 = False
        try:
            socket.inet_aton(host)
            is_ipv4 = True
        except OSError:
            pass

        ips = [host] if is_ipv4 else []
        if not is_ipv4:
            try:
                ips = await self.resolve_dns_doh(host)
            except Exception as exc:
                log(f"DNS resolution failed for {host}: {exc}")
                raise DuplexError(f"DNS resolution failed for {host}")
                
        if not ips:
            raise DuplexError(f"Could not resolve host {host}")
            
        last_exc: Optional[BaseException] = None
        for ip in ips:
            if self.force_routes and ip not in self.routed_ips and self.if_index:
                try:
                    RoutingManager.add_host_route_fast(ip, self.gateway, self.if_index)
                    self.routed_ips.add(ip)
                    from .state import runtime_state
                    if ip not in runtime_state.added_routes:
                        runtime_state.added_routes.append(ip)
                        runtime_state.save()
                except Exception as e:
                    log(f"Fast route add failed for {ip}: {e}")

            sockaddr = (ip, port)
            for attempt in (1, 2):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setblocking(False)
                try:
                    sock.bind((self.bind_ip, 0))
                    await asyncio.wait_for(loop.sock_connect(sock, sockaddr), timeout=12)
                    return await asyncio.open_connection(sock=sock)
                except Exception as exc:
                    last_exc = exc
                    sock.close()
                    if isinstance(exc, asyncio.TimeoutError) and attempt == 2:
                        raise DuplexError(f"connection to {ip}:{port} timed out")
                    if attempt == 2:
                        break
        raise DuplexError(f"connect failed for {host}:{port}: {last_exc}")

    async def reply(self, writer: asyncio.StreamWriter, rep: int) -> None:
        writer.write(b"\x05" + bytes([rep]) + b"\x00\x01\x00\x00\x00\x00\x00\x00")
        await writer.drain()

    async def pipe_pair(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        out_reader: asyncio.StreamReader,
        out_writer: asyncio.StreamWriter,
    ) -> None:
        async def pump(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
            try:
                while True:
                    data = await src.read(65536)
                    if not data:
                        break
                    dst.write(data)
                    await dst.drain()
            finally:
                try:
                    dst.close()
                except Exception:
                    pass

        t1 = asyncio.create_task(pump(client_reader, out_writer))
        t2 = asyncio.create_task(pump(out_reader, client_writer))
        done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
             task.cancel()
