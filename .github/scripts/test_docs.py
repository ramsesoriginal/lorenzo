"""Checks that the lists in the docs name what is in the repository.

Run: python3 -m unittest discover -s .github/scripts

It catches three kinds of drift that a linter cannot see:
- an app or package that is missing from one of the lists every app and package must be in;
- an ADR or RFC file that is missing from, or out of order in, its index;
- a mention such as "ADR 0123" or "RFC 0042" that names a number with no file.
"""

import json
import re
import subprocess
import tomllib
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Text files whose ADR and RFC mentions are checked. Changelogs are generated, lockfiles are not prose.
TEXT_SUFFIXES = {
    ".md", ".py", ".ts", ".tsx", ".astro", ".toml", ".yml", ".yaml", ".kt", ".kts", ".swift",
    ".mjs", ".js", ".json", ".css", ".sh", ".txt", ".html",
}
SKIPPED_NAMES = {"CHANGELOG.md", "pnpm-lock.yaml", "package-lock.json", "uv.lock"}

# "ADR 0123", "ADRs 0123, 0124 and 0125", "RFC 0042 to 0044". Lorenzo's numbers are always four digits
# with a leading zero; an IETF RFC such as "RFC 7239" never matches.
MENTION = re.compile(r"\b(ADR|RFC)s?\s+((?:0\d{3}(?:\s*(?:,|and|to|–|-|/|&)\s*)?)+)")
INDEX_ENTRY = re.compile(r"^- \[(\d{4}) - .*?\]\(([^)\s]+)\)")


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True
    ).stdout.decode("utf-8")
    return [f for f in out.split("\0") if f]


def directories(parent: str, files: list[str]) -> set[str]:
    """The directories directly under `parent` that hold tracked files."""
    prefix = parent + "/"
    return {f[len(prefix):].split("/")[0] for f in files if f.startswith(prefix) and "/" in f[len(prefix):]}


def numbered_files(folder: str, files: list[str]) -> dict[str, str]:
    found = {}
    for f in files:
        m = re.fullmatch(rf"{folder}/(\d{{4}})-[^/]+\.md", f)
        if m:
            found[m.group(1)] = f.rsplit("/", 1)[1]
    return found


class ListsAreComplete(unittest.TestCase):
    """Every app and package is in every list that has to name it (docs/guides/adding-an-app.md)."""

    @classmethod
    def setUpClass(cls):
        cls.files = tracked_files()

    def table_names(self, readme: str) -> set[str]:
        text = (REPO / readme).read_text(encoding="utf-8")
        return set(re.findall(r"^\| \[`([^`]+)`\]", text, re.M))

    def check(self, parent: str, readme: str):
        on_disk = directories(parent, self.files)
        listed = self.table_names(readme)
        self.assertEqual(sorted(on_disk - listed), [], f"in {parent}/ but not in {readme}")
        self.assertEqual(sorted(listed - on_disk), [], f"in {readme} but not in {parent}/")

    def test_apps_readme(self):
        self.check("apps", "apps/README.md")

    def test_packages_readme(self):
        self.check("packages", "packages/README.md")

    def paths(self) -> set[str]:
        return {f"{p}/{d}" for p in ("apps", "packages") for d in directories(p, self.files)}

    def test_mise_config_roots(self):
        text = (REPO / "mise.toml").read_text(encoding="utf-8")
        roots = set(re.findall(r'"([^"]+)"', re.search(r"config_roots = \[(.*?)\]", text, re.S).group(1)))
        with_mise = {p for p in self.paths() if f"{p}/mise.toml" in self.files}
        self.assertEqual(sorted(with_mise - roots), [], "has a mise.toml but is not in config_roots")
        self.assertEqual(sorted(roots - self.paths()), [], "in config_roots but not a directory")

    def test_release_please(self):
        config = set(json.loads((REPO / "release-please-config.json").read_text())["packages"]) - {"."}
        manifest = set(json.loads((REPO / ".release-please-manifest.json").read_text())) - {"."}
        self.assertEqual(sorted(self.paths() - config), [], "missing from release-please-config.json")
        self.assertEqual(sorted(config - self.paths()), [], "in release-please-config.json but gone")
        self.assertEqual(sorted(self.paths() - manifest), [], "missing from .release-please-manifest.json")
        self.assertEqual(sorted(manifest - self.paths()), [], "in the manifest but gone")

    def test_ci_graph_nodes_exist(self):
        graph = tomllib.loads((REPO / ".github/ci-graph.toml").read_text(encoding="utf-8"))
        nodes = set(graph.get("nodes", {}))
        self.assertEqual(sorted(nodes - self.paths()), [], "a node in ci-graph.toml is not an app or package")


class IndexesAreComplete(unittest.TestCase):
    """docs/adr/README.md and docs/rfcs/README.md list every file once, in ascending order."""

    @classmethod
    def setUpClass(cls):
        cls.files = tracked_files()

    def check(self, folder: str):
        entries = []
        for line in (REPO / folder / "README.md").read_text(encoding="utf-8").splitlines():
            m = INDEX_ENTRY.match(line)
            if m:
                entries.append((m.group(1), m.group(2)))
        on_disk = numbered_files(folder, self.files)
        numbers = [n for n, _ in entries]
        self.assertEqual(sorted(on_disk.keys() - set(numbers)), [], f"{folder}: files with no index entry")
        self.assertEqual(sorted(set(numbers) - on_disk.keys()), [], f"{folder}: index entries with no file")
        self.assertEqual(len(numbers), len(set(numbers)), f"{folder}: a number is listed twice")
        self.assertEqual(numbers, sorted(numbers), f"{folder}: the index is not in ascending order")
        for number, target in entries:
            self.assertEqual(target, on_disk.get(number), f"{folder}: entry {number} links to the wrong file")

    def test_adr_index(self):
        self.check("docs/adr")

    def test_rfc_index(self):
        self.check("docs/rfcs")


class MentionsResolve(unittest.TestCase):
    """Every "ADR NNNN" and "RFC NNNN" in the repository names a file that exists."""

    def test_mentions(self):
        files = tracked_files()
        known = {
            "ADR": set(numbered_files("docs/adr", files)),
            "RFC": set(numbered_files("docs/rfcs", files)),
        }
        missing: dict[tuple[str, str], list[str]] = {}
        for f in files:
            name = f.rsplit("/", 1)[-1]
            suffix = "." + name.rsplit(".", 1)[-1] if "." in name else ""
            if suffix not in TEXT_SUFFIXES or name in SKIPPED_NAMES:
                continue
            try:
                text = (REPO / f).read_text(encoding="utf-8")
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for m in MENTION.finditer(line):
                    for number in re.findall(r"0\d{3}", m.group(2)):
                        if number not in known[m.group(1)]:
                            missing.setdefault((m.group(1), number), []).append(f"{f}:{lineno}")
        report = [f"{kind} {number}: {', '.join(where[:3])}" for (kind, number), where in sorted(missing.items())]
        self.assertEqual(report, [], "mentions of an ADR or RFC that has no file")


if __name__ == "__main__":
    unittest.main()
