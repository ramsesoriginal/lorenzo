from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from lorenzo_cli.evalworker import (
    Engine,
    EvalError,
    EvalRequest,
    EvalResult,
    Limits,
    SourceFile,
    WorkerEngine,
    host,
    read_sources,
)
from lorenzo_cli.evalworker.tagged import function_text_of, is_plain, regex_of, stub_name_of


def run(
    *files: tuple[str, str], base: tuple[tuple[str, str], ...] = (), **limits: Any
) -> EvalResult:
    return WorkerEngine().evaluate(
        EvalRequest(
            base=[SourceFile(name=n, source=s) for n, s in base],
            files=[SourceFile(name=n, source=s) for n, s in files],
            limits=Limits(**limits),
        )
    )


def test_an_endless_loop_is_stopped_and_the_next_file_still_runs() -> None:
    result = run(
        ("loop.js", "while (true) {}"),
        ("after.js", 'WeaponsList["ok"] = {name: "Ok"};'),
        file_seconds=0.5,
    )

    assert [(f.name, f.status, f.error) for f in result.files] == [
        ("loop.js", "error", "JavaScript was terminated by timeout"),
        ("after.js", "ok", None),
    ]
    assert list(result.lists["WeaponsList"]) == ["ok"]


def test_a_script_that_eats_memory_is_stopped() -> None:
    result = run(
        ("hog.js", "var a = []; while (true) { a.push(new Array(100000).fill('x')); }"),
        max_memory_mb=32,
        file_seconds=20,
    )

    assert result.files[0].status == "error"
    assert "memory" in (result.files[0].error or "")


def test_the_wall_clock_kills_a_worker_that_outlives_its_budget() -> None:
    request = EvalRequest(
        files=[SourceFile(name="loop.js", source="while (true) {}")],
        limits=Limits(wall_seconds=2.0, file_seconds=60.0),
    )

    with pytest.raises(EvalError, match="stopped after 2s"):
        WorkerEngine().evaluate(request)


def test_too_many_unknown_names_gives_up_with_a_clear_error() -> None:
    result = run(("many.js", "a1(); a2(); a3(); a4();"), max_stub_retries=2)

    assert result.ok is False
    assert "Gave up after 2 restarts" in (result.error or "")


def test_the_worker_is_given_no_credentials() -> None:
    parent = {
        "LORENZO_TOKEN": "secret",
        "LORENZO_AUTHGEAR_CLIENT_ID": "id",
        "HOME": "/home/x",
        "PYTHONPATH": "/evil",
        "PATH": "/usr/bin",
        "LANG": "C.UTF-8",
    }

    assert host.worker_env(parent) == {"PATH": "/usr/bin", "LANG": "C.UTF-8"}


def test_the_subprocess_is_started_isolated_with_that_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        seen["command"] = command
        seen["env"] = kwargs["env"]
        return subprocess.CompletedProcess(
            command, 0, stdout=EvalResult(ok=True).model_dump_json().encode(), stderr=b""
        )

    monkeypatch.setenv("LORENZO_TOKEN", "secret")
    monkeypatch.setattr(subprocess, "run", fake_run)

    WorkerEngine(python="/py").evaluate(EvalRequest(files=[]))

    assert seen["command"] == ["/py", "-I", "-m", "lorenzo_cli.evalworker"]
    assert "LORENZO_TOKEN" not in seen["env"]


def test_a_crashed_worker_is_an_eval_error_with_its_last_stderr_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, b"", b"trace\nboom\n"),
    )

    with pytest.raises(EvalError, match=r"exit 1[)]: boom"):
        WorkerEngine().evaluate(EvalRequest(files=[]))


def test_a_garbled_answer_is_an_eval_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, b"not json", b""),
    )

    with pytest.raises(EvalError, match="unreadable"):
        WorkerEngine().evaluate(EvalRequest(files=[]))


def test_any_object_with_an_evaluate_method_is_an_engine() -> None:
    class Fake:
        def evaluate(self, request: EvalRequest) -> EvalResult:
            return EvalResult(ok=True, counts={"WeaponsList": len(request.files)})

    engine: Engine = Fake()

    assert engine.evaluate(EvalRequest(files=[SourceFile(name="a", source="")])).counts == {
        "WeaponsList": 1
    }


def test_files_are_read_in_order_and_a_byte_order_mark_is_dropped(tmp_path: Path) -> None:
    (tmp_path / "b.js").write_bytes(b"\xef\xbb\xbfvar b = 1;")
    (tmp_path / "a.js").write_text("var a = 1;")

    files = read_sources([tmp_path / "b.js", tmp_path / "a.js"])

    assert [(f.name, f.source) for f in files] == [("b.js", "var b = 1;"), ("a.js", "var a = 1;")]


def test_a_file_that_isnt_utf8_is_refused_by_name(tmp_path: Path) -> None:
    (tmp_path / "old.js").write_bytes(b"var x = '\xe9';")

    with pytest.raises(EvalError, match=r"old\.js isn't UTF-8"):
        read_sources([tmp_path / "old.js"])


def test_tagged_values_are_read_only_through_the_helpers() -> None:
    assert regex_of({"$re": ["a+", "gi"]}) == ("a+", "gi")
    assert regex_of("a+") is None
    assert function_text_of({"$fn": "function () {}"}) == "function () {}"
    assert function_text_of({"$fn": "x", "other": 1}) is None
    assert stub_name_of({"$stub": "What"}) == "What"
    assert stub_name_of({"name": "x"}) is None


def test_is_plain_looks_inside_nested_values() -> None:
    assert is_plain({"a": [1, "x", {"b": None}]})
    assert not is_plain({"a": [1, {"$re": ["x", ""]}]})
    assert not is_plain([{"$fn": "function () {}"}])
    assert not is_plain({"$num": "NaN"})
