import platform, subprocess
from pathlib import Path
root = Path(__file__).resolve().parent.parent
if platform.system() == "Darwin":
    subprocess.run(["swift", "format", "lint", "--strict", "--recursive", "Sources", "Tests", "StateTests", "UITests"], cwd=root, check=True)
    subprocess.run(["swiftc", "-parse", *map(str, root.glob("Sources/**/*.swift"))], check=True)
else:
    print("Swift parse runs on the required macOS CI job.")
