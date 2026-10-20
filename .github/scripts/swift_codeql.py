"""Select Swift CodeQL without skipping build/scanner changes (ADR 0148)."""

import argparse
import subprocess
from pathlib import Path

BUILD_INPUTS = {
    "apps/inventory-ios/Package.resolved",
    "apps/inventory-ios/Info.plist",
    "apps/inventory-ios/Simulator.entitlements",
    "apps/inventory-ios/mise.toml",
    "apps/inventory-ios/version.txt",
    "apps/inventory-ios/scripts/project.py",
    "apps/inventory-ios/scripts/run.sh",
    ".github/workflows/security.yml",
    ".github/scripts/swift_codeql.py",
    "mise.toml",
}


def relevant(path: str) -> bool:
    return path.endswith(".swift") or path in BUILD_INPUTS or path.startswith(".github/codeql/")


def git_paths(root: Path, *args: str) -> list[str]:
    result = subprocess.check_output(["git", "-C", str(root), *args])
    return [p.decode("utf-8", errors="surrogateescape") for p in result.split(b"\0") if p]


def should_scan(root: Path, base: str | None = None) -> bool:
    tracked = git_paths(root, "ls-files", "-z")
    # CodeQL fails if the app no longer contains any source.
    if not any(p.startswith("apps/inventory-ios/Sources/") and p.endswith(".swift") for p in tracked):
        return False
    if base is None:
        return True  # main and scheduled scans always include the app
    # Compare tree snapshots: checkout is the PR merge commit, not its base tip.
    # No rename collapsing: removal of a Swift file must count too.
    changed = git_paths(root, "diff", "--no-renames", "--name-only", "-z", base, "HEAD", "--")
    return any(map(relevant, changed))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--base")
    args = parser.parse_args()
    print("true" if should_scan(args.root, args.base) else "false")
