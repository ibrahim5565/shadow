import os

def search_files(directory, query):
    print(f"Searching for '{query}' in {directory}...")
    for root, dirs, files in os.walk(directory):
        if "venv" in root or "__pycache__" in root or ".git" in root or "scratch" in root:
            continue
        for file in files:
            if file.endswith(".py") or file.endswith(".ini") or file.endswith(".bat"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    for i, line in enumerate(lines):
                        if query.lower() in line.lower():
                            print(f"  {file}:{i+1} - {line.strip()}")
                except Exception as e:
                    pass

search_files("d:\\Trading\\Aegis_Gold", "cooldown")
search_files("d:\\Trading\\Aegis_Gold", "duplicate")
search_files("d:\\Trading\\Aegis_Gold", "minute")
