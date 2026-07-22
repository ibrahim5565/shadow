import os

common_ini_path = r"C:\Users\mohamed ibrahim d\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\config\common.ini"
if os.path.exists(common_ini_path):
    with open(common_ini_path, "r", encoding="utf-16") as f:
        print(f.read())
else:
    print("common.ini not found")
