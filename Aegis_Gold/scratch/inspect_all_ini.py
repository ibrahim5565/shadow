import os

config_dir = r"C:\Users\mohamed ibrahim d\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\config"
ini_files = ["common.ini", "settings.ini", "terminal.ini"]

for ini in ini_files:
    path = os.path.join(config_dir, ini)
    if os.path.exists(path):
        print(f"\n=================== {ini} ===================")
        # Try UTF-16-LE first, then UTF-8
        content = ""
        try:
            with open(path, "r", encoding="utf-16") as f:
                content = f.read()
        except Exception:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"Could not read {ini}: {e}")
                continue
        
        # Print sections and non-empty lines
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("[") or "=" in line:
                if any(x in line.lower() for x in ["expert", "dll", "webrequest", "allow", "confirm", "trade", "security", "url"]):
                    print(f"  {line}")
                elif line.startswith("["):
                    print(line)
    else:
        print(f"{ini} not found")
