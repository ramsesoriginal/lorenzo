#!/usr/bin/env python3
"""Which apps and packages can a change affect? (ADR 0148)

Every directory under apps/ or packages/ with a mise.toml is a node. A change
reaches its own node and everything that depends on it, never what it depends on.
Standard library only (3.11+: tomllib), because this runs in the job every other
job waits for.

    affected.py --root . --base <sha> [--github-output FILE] [--summary FILE]
    affected.py --root . --all       [...]      # push to main: everything

Edges come from three places:
  * derived: a package.json `workspace:` dependency, a pyproject.toml uv path source;
  * declared in .github/ci-graph.toml: `depends_on` (same strength as derived),
    `generated_from` (the node's generated code is drift-checked when the source
    changes; its tests run only if it changed itself or a code dependency did);
  * suites: slow integration jobs that run when their node or anything they run
    against is affected.
A node with neither a package.json nor a pyproject.toml cannot be read, so it
must be declared in the graph file; otherwise this script fails on purpose.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

GRAPH_FILE = ".github/ci-graph.toml"
DEP_SECTIONS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")


class GraphError(Exception):
    """The graph can't be built; the message says what to declare."""


@dataclass
class Node:
    name: str
    js: bool
    python: bool
    declared: bool = False
    postgres: bool = False
    check_schema: bool = False
    depends_on: set[str] = field(default_factory=set)
    generated_from: set[str] = field(default_factory=set)


@dataclass
class Suite:
    name: str
    node: str
    depends_on: set[str]


@dataclass
class Graph:
    nodes: dict[str, Node]
    suites: dict[str, Suite]
    run_everything: list[str]
    pnpm_lockfile: str
    openapi_source: str


@dataclass
class Result:
    tests: set[str]
    drift: set[str]
    suites: set[str]
    openapi_diff: bool
    reasons: dict[str, str]
    everything: bool


def discover_nodes(root: Path) -> list[str]:
    found = []
    for top in ("apps", "packages"):
        for mise in sorted((root / top).glob("*/mise.toml")):
            found.append(f"{top}/{mise.parent.name}")
    return found


def _load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _as_set(table: dict, key: str, where: str) -> set[str]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise GraphError(f"{where}: `{key}` must be a list of node names")
    return set(value)


def load_graph(root: Path) -> Graph:
    declared = _load_toml(root / GRAPH_FILE)
    node_names = discover_nodes(root)
    known = set(node_names)
    declared_nodes = declared.get("nodes", {})
    for name in declared_nodes:
        if name not in known:
            raise GraphError(f"{GRAPH_FILE}: [nodes.\"{name}\"] is not a directory with a mise.toml")

    nodes: dict[str, Node] = {}
    package_names: dict[str, str] = {}
    for name in node_names:
        base = root / name
        js = (base / "package.json").is_file()
        python = (base / "pyproject.toml").is_file()
        mise_text = (base / "mise.toml").read_text(encoding="utf-8")
        node = Node(
            name=name,
            js=js,
            python=python,
            declared=name in declared_nodes,
            check_schema=re.search(r"^\[tasks\.check-schema\]", mise_text, re.M) is not None,
        )
        if not (js or python or node.declared):
            raise GraphError(
                f"{name} has no package.json or pyproject.toml, so CI cannot read its "
                f"dependencies. Declare it in {GRAPH_FILE}: [nodes.\"{name}\"] with depends_on "
                f"(an empty list is fine). See docs/guides/adding-an-app.md."
            )
        nodes[name] = node
        if js:
            package_names[json.loads((base / "package.json").read_text(encoding="utf-8")).get("name", "")] = name

    # declared
    for name, table in declared_nodes.items():
        node = nodes[name]
        where = f'{GRAPH_FILE} [nodes."{name}"]'
        node.postgres = bool(table.get("postgres", False))
        node.depends_on |= _as_set(table, "depends_on", where)
        node.generated_from |= _as_set(table, "generated_from", where)

    # derived
    for name, node in nodes.items():
        base = root / name
        if node.js:
            package = json.loads((base / "package.json").read_text(encoding="utf-8"))
            for section in DEP_SECTIONS:
                for dep, spec in package.get(section, {}).items():
                    if isinstance(spec, str) and spec.startswith("workspace:") and dep in package_names:
                        node.depends_on.add(package_names[dep])
        if node.python:
            pyproject = _load_toml(base / "pyproject.toml")
            for source in pyproject.get("tool", {}).get("uv", {}).get("sources", {}).values():
                path = source.get("path") if isinstance(source, dict) else None
                if path:
                    target = (base / path).resolve()
                    for other in nodes:
                        if (root / other).resolve() == target:
                            node.depends_on.add(other)

    for node in nodes.values():
        node.depends_on.discard(node.name)
        for label, targets in (("depends_on", node.depends_on), ("generated_from", node.generated_from)):
            for target in targets:
                if target not in nodes:
                    raise GraphError(f"{node.name}: {label} names {target}, which is not a node")

    suites: dict[str, Suite] = {}
    for suite_name, table in declared.get("suites", {}).items():
        where = f"{GRAPH_FILE} [suites.{suite_name}]"
        node = table.get("node")
        if node not in nodes:
            raise GraphError(f"{where}: `node` must name a node")
        depends_on = _as_set(table, "depends_on", where)
        for target in depends_on:
            if target not in nodes:
                raise GraphError(f"{where}: depends_on names {target}, which is not a node")
        suites[suite_name] = Suite(suite_name, node, depends_on)

    glob = declared.get("global", {})
    openapi_source = glob.get("openapi_source", "")
    if openapi_source and openapi_source not in nodes:
        raise GraphError(f"{GRAPH_FILE}: openapi_source names {openapi_source}, which is not a node")
    return Graph(
        nodes=nodes,
        suites=suites,
        run_everything=list(glob.get("run_everything", [])),
        pnpm_lockfile=glob.get("pnpm_lockfile", ""),
        openapi_source=openapi_source,
    )


def owner(graph: Graph, path: str) -> str | None:
    for name in graph.nodes:
        if path.startswith(name + "/"):
            return name
    return None


def affected(graph: Graph, changed: list[str], everything: bool = False, why: str = "") -> Result:
    reasons: dict[str, str] = {}
    direct: set[str] = set()
    if not everything:
        for path in changed:
            if any(fnmatch.fnmatch(path, pattern) for pattern in graph.run_everything):
                everything, why = True, f"{path} is shared by every node"
                break
    if everything:
        direct = set(graph.nodes)
        for name in direct:
            reasons[name] = why or "everything"
    else:
        for path in changed:
            node = owner(graph, path)
            if node:
                direct.add(node)
                reasons.setdefault(node, f"{path} changed")
            elif graph.pnpm_lockfile and path == graph.pnpm_lockfile:
                for name, candidate in graph.nodes.items():
                    if candidate.js:
                        direct.add(name)
                        reasons.setdefault(name, f"{path} changed")

    dependents: dict[str, set[str]] = {name: set() for name in graph.nodes}
    for node in graph.nodes.values():
        for dep in node.depends_on:
            dependents[dep].add(node.name)
    tests = set(direct)
    queue = list(direct)
    while queue:
        current = queue.pop()
        for dependent in sorted(dependents[current]):
            if dependent not in tests:
                tests.add(dependent)
                reasons[dependent] = f"depends on {current}"
                queue.append(dependent)

    drift: set[str] = set()
    for node in graph.nodes.values():
        if not node.check_schema:
            continue
        if node.name in tests or node.generated_from & tests:
            drift.add(node.name)

    suites = {
        suite.name
        for suite in graph.suites.values()
        if suite.node in tests or suite.depends_on & tests
    }
    return Result(
        tests=tests,
        drift=drift,
        suites=suites,
        openapi_diff=bool(graph.openapi_source) and graph.openapi_source in tests,
        reasons=reasons,
        everything=everything,
    )


def matrices(graph: Graph, result: Result) -> dict[str, str]:
    test = [{"app": n, "postgres": graph.nodes[n].postgres} for n in sorted(result.tests)]
    drift = [{"app": n} for n in sorted(result.drift)]
    return {
        "test_matrix": json.dumps(test),
        "drift_matrix": json.dumps(drift),
        "suites": json.dumps(sorted(result.suites)),
        "openapi_diff": "true" if result.openapi_diff else "false",
    }


def summary(graph: Graph, result: Result, changed: list[str]) -> str:
    lines = ["### What this change affects (ADR 0148)", ""]
    lines.append(f"{len(changed)} changed file(s); " + ("**everything runs**." if result.everything else "affected nodes only."))
    lines += ["", "| Node | Tests | Why |", "| --- | --- | --- |"]
    for name in graph.nodes:
        ran = name in result.tests
        lines.append(f"| `{name}` | {'run' if ran else 'skipped'} | {result.reasons.get(name, '')} |")
    lines.append("")
    lines.append(f"Drift checks: {', '.join(sorted(result.drift)) or 'none'}. Suites: {', '.join(sorted(result.suites)) or 'none'}. "
                 f"OpenAPI diff: {'yes' if result.openapi_diff else 'no'}.")
    return "\n".join(lines) + "\n"


def changed_files(root: Path, base: str) -> list[str] | None:
    proc = subprocess.run(
        ["git", "diff", "--name-only", base, "HEAD"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return None
    return [line for line in proc.stdout.splitlines() if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".")
    parser.add_argument("--base", help="base commit of a pull request")
    parser.add_argument("--all", action="store_true", help="everything is affected (push to main)")
    parser.add_argument("--changed", nargs="*", help="changed paths instead of git diff (testing)")
    parser.add_argument("--github-output")
    parser.add_argument("--summary")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        graph = load_graph(root)
    except GraphError as err:
        print(f"::error::{err}")
        print(err, file=sys.stderr)
        return 1

    changed: list[str] = []
    everything, why = args.all, "push to main, or no base to compare with"
    if not args.all:
        if args.changed is not None:
            changed = args.changed
        elif args.base:
            diffed = changed_files(root, args.base)
            if diffed is None:
                everything, why = True, "the diff against the base could not be computed"
            else:
                changed = diffed
        else:
            everything = True
    result = affected(graph, changed, everything=everything, why=why)
    outputs = matrices(graph, result)
    text = summary(graph, result, changed)
    print(text)
    for key, value in outputs.items():
        print(f"{key}={value}")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
