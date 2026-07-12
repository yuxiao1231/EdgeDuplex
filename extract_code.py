import os
from pathlib import Path

def extract_code(output_file="code_summary.txt", extensions=(".py", ".md", ".json", ".yml")):
    base_dir = Path(__file__).resolve().parent
    
    ignore_dirs = {"__pycache__", ".git", "build", "dist", ".github"}
    # Explicitly include .github/workflows if needed, but for now we skip standard ignores
    
    with open(output_file, "w", encoding="utf-8") as out:
        for root, dirs, files in os.walk(base_dir):
            # Filter ignored dirs
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                if file.endswith(extensions) and file != os.path.basename(__file__):
                    filepath = Path(root) / file
                    rel_path = filepath.relative_to(base_dir)
                    
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        out.write(f"\n{'='*60}\n")
                        out.write(f"File: {rel_path}\n")
                        out.write(f"{'='*60}\n\n")
                        out.write(content)
                        out.write("\n")
                    except Exception as e:
                        out.write(f"Error reading {rel_path}: {e}\n")

if __name__ == "__main__":
    extract_code()
    print("Code extracted to code_summary.txt")