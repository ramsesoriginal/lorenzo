"""Swift security selection regressions; stdlib only, run by ci-tools."""

import subprocess
import tempfile
import unittest
from pathlib import Path

import swift_codeql


class SwiftSelectionTests(unittest.TestCase):
    def test_unrelated_changes_skip_swift(self):
        for path in ["README.md", "docs/adr/0148-dependency-aware-pr-ci.md",
                     "apps/cli/src/client.py", "apps/api/models.py", "pnpm-lock.yaml",
                     "apps/inventory-ios/README.md", "apps/inventory-ios/scripts/check_contract.py"]:
            with self.subTest(path=path):
                self.assertFalse(swift_codeql.relevant(path))

    def test_sources_and_build_inputs_scan(self):
        paths = ["apps/inventory-ios/Sources/App/Views.swift",
                 "apps/inventory-ios/Tests/ContractTests.swift",
                 "apps/inventory-ios/Package.swift",
                 ".github/codeql/codeql-config.yml", *swift_codeql.BUILD_INPUTS]
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(swift_codeql.relevant(path))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.write("apps/inventory-ios/Sources/App.swift", "// source")
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.root), "-c", "user.name=Test",
             "-c", "user.email=test@example.invalid", "-c", "core.hooksPath=", *args],
            stderr=subprocess.DEVNULL, text=True).strip()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "test")
        return self.git("rev-parse", "HEAD")

    def test_main_and_schedule_scan_even_without_changes(self):
        self.assertTrue(swift_codeql.should_scan(self.root))
        self.assertFalse(swift_codeql.should_scan(self.root, self.base))

    def test_docs_only_pr_skips(self):
        self.write("docs/note.md", "note")
        self.commit()
        self.assertFalse(swift_codeql.should_scan(self.root, self.base))

    def test_large_diff_includes_swift_without_api_file_limit(self):
        for n in range(350):
            self.write(f"docs/{n}.md", "note")
        self.write("apps/inventory-ios/Sources/App.swift", "// changed")
        self.commit()
        self.assertTrue(swift_codeql.should_scan(self.root, self.base))

    def test_rename_out_of_swift_counts_deleted_path(self):
        self.write("apps/inventory-ios/Sources/Other.swift", "// other")
        base = self.commit()
        self.git("mv", "apps/inventory-ios/Sources/App.swift", "apps/inventory-ios/Sources/App.txt")
        self.commit()
        self.assertTrue(swift_codeql.should_scan(self.root, base))

    def test_deleting_last_source_does_not_request_empty_database(self):
        self.git("rm", "apps/inventory-ios/Sources/App.swift")
        self.commit()
        self.assertFalse(swift_codeql.should_scan(self.root, self.base))

    def test_bad_base_fails_instead_of_skipping(self):
        with self.assertRaises(subprocess.CalledProcessError):
            swift_codeql.should_scan(self.root, "not-a-commit")

    def test_base_changes_are_not_mistaken_for_pr_changes(self):
        self.write("apps/inventory-ios/Sources/App.swift", "// base changed")
        base = self.commit()
        self.write("apps/cli/client.py", "# PR")
        self.commit()
        self.assertFalse(swift_codeql.should_scan(self.root, base))

    def test_new_source_with_spaces_is_seen(self):
        self.write("apps/inventory-ios/Sources/New name.swift", "// new")
        self.commit()
        self.assertTrue(swift_codeql.should_scan(self.root, self.base))
