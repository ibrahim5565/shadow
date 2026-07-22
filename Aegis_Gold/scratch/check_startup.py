import os

startup_path = os.path.join(
    os.environ["APPDATA"],
    r"Microsoft\Windows\Start Menu\Programs\Startup"
)

print(f"Startup folder path: {startup_path}")
if os.path.exists(startup_path):
    print("  [OK] Startup folder exists.")
    test_file = os.path.join(startup_path, "aegis_startup_test.txt")
    try:
        with open(test_file, "w") as f:
            f.write("Aegis Gold Startup Test")
        print("  [OK] Successfully wrote test file to Startup folder.")
        os.remove(test_file)
        print("  [OK] Successfully cleaned up test file.")
    except Exception as e:
        print(f"  [FAIL] Failed to write test file: {e}")
else:
    print("  [FAIL] Startup folder does not exist.")
