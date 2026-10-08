"""Tests for affected.py (ADR 0148). Run: python3 -m unittest discover -s .github/scripts"""

import json
import tempfile
import unittest
from pathlib import Path

import affected

REPO = Path(__file__).resolve().parents[2]

GRAPH = """
[global]
run_everything = ["mise.toml", ".github/ci-graph.toml", ".github/scripts/*"]
pnpm_lockfile = "pnpm-lock.yaml"
openapi_source = "apps/api"

[nodes."apps/api"]
postgres = true
shards = 2

[nodes."apps/kt-app"]
depends_on = ["packages/kt-client"]

[nodes."packages/kt-client"]
generated_from = ["apps/api"]

[nodes."packages/ts-client"]
generated_from = ["apps/api"]

[suites.web-e2e]
node = "apps/web"
depends_on = ["apps/api"]
"""


def write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def js(root: Path, node: str, name: str, deps: dict[str, str] | None = None, check_schema: bool = False) -> None:
    write(root, f"{node}/package.json", json.dumps({"name": name, "dependencies": deps or {}}))
    write(root, f"{node}/mise.toml", "[tasks.check-schema]\nrun = 'true'\n" if check_schema else "")


def make_repo(graph: str = GRAPH) -> Path:
    root = Path(tempfile.mkdtemp())
    write(root, ".github/ci-graph.toml", graph)
    write(root, "apps/api/pyproject.toml", "[project]\nname='api'\n")
    write(root, "apps/api/mise.toml")
    js(root, "packages/ts-client", "@x/ts-client", check_schema=True)
    js(root, "packages/ui", "@x/ui")
    js(root, "apps/web", "@x/web", {"@x/ts-client": "workspace:*", "@x/ui": "workspace:*"})
    js(root, "apps/bot", "@x/bot", {"@x/ts-client": "workspace:*"})
    write(root, "apps/kt-app/mise.toml")
    write(root, "packages/kt-client/mise.toml", "[tasks.check-schema]\nrun = 'true'\n")
    # a python node with a uv path source onto another python node
    write(root, "packages/py-lib/pyproject.toml", "[project]\nname='py-lib'\n")
    write(root, "packages/py-lib/mise.toml")
    write(root, "apps/tool/pyproject.toml", "[project]\nname='tool'\n[tool.uv.sources]\npy-lib = { path = '../../packages/py-lib' }\n")
    write(root, "apps/tool/mise.toml")
    return root


def run(root: Path, *changed: str, everything: bool = False) -> affected.Result:
    return affected.affected(affected.load_graph(root), list(changed), everything=everything)


class Propagation(unittest.TestCase):
    def setUp(self) -> None:
        self.root = make_repo()

    def test_an_app_only_reaches_itself(self) -> None:
        self.assertEqual(run(self.root, "apps/bot/src/a.ts").tests, {"apps/bot"})

    def test_a_change_never_reaches_what_it_depends_on(self) -> None:
        result = run(self.root, "apps/web/src/a.ts")
        self.assertEqual(result.tests, {"apps/web"})
        self.assertNotIn("apps/api", result.tests)
        self.assertNotIn("packages/ts-client", result.tests)

    def test_a_package_reaches_every_dependent_app(self) -> None:
        self.assertEqual(
            run(self.root, "packages/ts-client/src/a.ts").tests,
            {"packages/ts-client", "apps/web", "apps/bot"},
        )

    def test_reaches_transitive_dependents(self) -> None:
        write(self.root, "apps/web2/mise.toml")
        js(self.root, "apps/web2", "@x/web2", {"@x/web": "workspace:*"})
        self.assertIn("apps/web2", run(self.root, "packages/ui/a.ts").tests)

    def test_uv_path_source_is_an_edge(self) -> None:
        self.assertEqual(run(self.root, "packages/py-lib/a.py").tests, {"packages/py-lib", "apps/tool"})
        self.assertEqual(run(self.root, "apps/tool/a.py").tests, {"apps/tool"})

    def test_docs_and_other_files_run_nothing(self) -> None:
        result = run(self.root, "docs/adr/0001.md", "README.md", ".github/workflows/docs.yml")
        self.assertEqual((result.tests, result.drift, result.suites, result.openapi_diff), (set(), set(), set(), False))


class ApiChanges(unittest.TestCase):
    def setUp(self) -> None:
        self.root = make_repo()
        self.result = run(self.root, "apps/api/src/a.py")

    def test_api_tests_and_openapi_diff_run(self) -> None:
        self.assertIn("apps/api", self.result.tests)
        self.assertTrue(self.result.openapi_diff)

    def test_generated_clients_are_drift_checked_but_not_tested(self) -> None:
        self.assertEqual(self.result.drift, {"packages/ts-client", "packages/kt-client"})
        self.assertNotIn("packages/ts-client", self.result.tests)
        self.assertNotIn("apps/web", self.result.tests)
        self.assertNotIn("apps/kt-app", self.result.tests)

    def test_a_suite_runs_against_the_api(self) -> None:
        self.assertEqual(self.result.suites, {"web-e2e"})

    def test_a_regenerated_client_reaches_its_consumers(self) -> None:
        result = run(self.root, "apps/api/src/a.py", "packages/ts-client/src/schema.d.ts")
        self.assertTrue({"apps/web", "apps/bot"} <= result.tests)

    def test_the_suite_also_runs_for_its_own_node(self) -> None:
        self.assertEqual(run(self.root, "apps/web/src/a.ts").suites, {"web-e2e"})
        self.assertEqual(run(self.root, "apps/bot/src/a.ts").suites, set())


class Everything(unittest.TestCase):
    def setUp(self) -> None:
        self.root = make_repo()

    def test_shared_files_run_every_node(self) -> None:
        graph = affected.load_graph(self.root)
        for path in ("mise.toml", ".github/ci-graph.toml", ".github/scripts/affected.py"):
            result = run(self.root, path)
            self.assertEqual(result.tests, set(graph.nodes), path)
            self.assertTrue(result.everything)

    def test_a_nodes_own_mise_toml_is_not_shared(self) -> None:
        self.assertEqual(run(self.root, "apps/bot/mise.toml").tests, {"apps/bot"})

    def test_push_marks_everything(self) -> None:
        result = run(self.root, everything=True)
        self.assertEqual(result.tests, set(affected.load_graph(self.root).nodes))

    def test_the_lockfile_runs_every_pnpm_node_only(self) -> None:
        result = run(self.root, "pnpm-lock.yaml")
        self.assertEqual(result.tests, {"packages/ts-client", "packages/ui", "apps/web", "apps/bot"})


class Registration(unittest.TestCase):
    def test_an_unreadable_node_must_be_declared(self) -> None:
        root = make_repo()
        write(root, "apps/mobile/mise.toml")
        with self.assertRaises(affected.GraphError) as caught:
            affected.load_graph(root)
        self.assertIn("apps/mobile", str(caught.exception))
        self.assertIn("ci-graph.toml", str(caught.exception))

    def test_declaring_it_fixes_that(self) -> None:
        root = make_repo(GRAPH + '\n[nodes."apps/mobile"]\ndepends_on = ["packages/kt-client"]\n')
        write(root, "apps/mobile/mise.toml")
        self.assertIn("apps/mobile", run(root, "packages/kt-client/a.kt").tests)

    def test_a_declared_node_that_does_not_exist_fails(self) -> None:
        with self.assertRaises(affected.GraphError):
            affected.load_graph(make_repo(GRAPH + '\n[nodes."apps/ghost"]\n'))

    def test_an_edge_to_an_unknown_node_fails(self) -> None:
        with self.assertRaises(affected.GraphError):
            affected.load_graph(make_repo(GRAPH.replace('["packages/kt-client"]', '["packages/nope"]')))

    def test_a_node_needs_a_mise_toml_to_exist(self) -> None:
        root = make_repo()
        write(root, "apps/not-an-app/README.md")
        self.assertNotIn("apps/not-an-app", affected.load_graph(root).nodes)


class Matrices(unittest.TestCase):
    def test_outputs_are_json_with_the_postgres_flag(self) -> None:
        root = make_repo()
        graph = affected.load_graph(root)
        out = affected.matrices(graph, affected.affected(graph, ["apps/api/a.py"]))
        self.assertIn(
            {"app": "apps/api", "label": "apps/api 1/2", "shard": "1/2", "postgres": True}, json.loads(out["test_matrix"])
        )
        self.assertIn({"app": "apps/bot", "label": "apps/bot", "shard": "", "postgres": False}, json.loads(affected.matrices(graph, affected.affected(graph, ["apps/bot/a.ts"]))["test_matrix"]))
        self.assertEqual(out["openapi_diff"], "true")
        self.assertEqual(json.loads(out["suites"]), ["web-e2e"])

    def test_nothing_affected_gives_empty_matrices(self) -> None:
        graph = affected.load_graph(make_repo())
        out = affected.matrices(graph, affected.affected(graph, ["docs/a.md"]))
        self.assertEqual((out["test_matrix"], out["drift_matrix"], out["suites"]), ("[]", "[]", "[]"))


class ThisRepository(unittest.TestCase):
    """The real graph loads, and the behavior ADR 0148 promises holds on it."""

    def setUp(self) -> None:
        self.graph = affected.load_graph(REPO)

    def test_every_node_is_placed(self) -> None:
        self.assertEqual(set(self.graph.nodes), set(affected.discover_nodes(REPO)))

    def test_a_loot_bot_change_runs_loot_bot_only(self) -> None:
        self.assertEqual(affected.affected(self.graph, ["apps/loot-bot/src/x.ts"]).tests, {"apps/loot-bot"})

    def test_api_client_reaches_the_three_apps(self) -> None:
        tests = affected.affected(self.graph, ["packages/api-client/src/index.ts"]).tests
        self.assertEqual(tests, {"packages/api-client", "apps/loot-bot", "apps/inventory-web", "apps/account-hub"})

    def test_an_api_change_does_not_retest_the_typescript_apps(self) -> None:
        result = affected.affected(self.graph, ["apps/api/src/lorenzo_api/main.py"])
        self.assertEqual(result.tests, {"apps/api"})
        self.assertEqual(result.drift, {"apps/cli", "packages/api-client"})
        self.assertEqual(result.suites, {"inventory-web-e2e", "cli-e2e", "account-hub-real-api"})
        self.assertTrue(result.openapi_diff)

    def test_a_hub_change_runs_the_hubs_real_api_suite(self) -> None:
        result = affected.affected(self.graph, ["apps/account-hub/src/lib/shelf.ts"])
        self.assertEqual(result.tests, {"apps/account-hub"})
        self.assertEqual(result.suites, {"account-hub-real-api"})

    def test_documentation_runs_nothing(self) -> None:
        self.assertEqual(affected.affected(self.graph, ["docs/adr/0148-dependency-aware-pr-ci.md"]).tests, set())

    def test_the_postgres_legs(self) -> None:
        self.assertEqual({n for n, v in self.graph.nodes.items() if v.postgres}, {"apps/api", "apps/loot-bot"})

    def test_the_api_suite_is_split_over_two_runners(self) -> None:
        self.assertEqual(self.graph.nodes["apps/api"].shards, 2)
        matrix = json.loads(affected.matrices(self.graph, affected.affected(self.graph, ["apps/api/a.py"]))["test_matrix"])
        self.assertEqual([(leg["app"], leg["shard"]) for leg in matrix], [("apps/api", "1/2"), ("apps/api", "2/2")])

    def test_cli_unit_tests_do_not_run_for_an_api_change_but_its_e2e_does(self) -> None:
        result = affected.affected(self.graph, ["apps/api/a.py"])
        self.assertNotIn("apps/cli", result.tests)
        self.assertIn("cli-e2e", result.suites)
        self.assertEqual(affected.affected(self.graph, ["apps/cli/src/x.py"]).suites, {"cli-e2e"})


if __name__ == "__main__":
    unittest.main()
