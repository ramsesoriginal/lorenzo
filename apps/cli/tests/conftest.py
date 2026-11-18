"""Every test runs with a home of its own, so the completion cache (ADR 0507), which a command
writes under `~/.cache/lorenzo/` when nothing else is named, never lands in the real one."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _a_home_of_its_own(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
