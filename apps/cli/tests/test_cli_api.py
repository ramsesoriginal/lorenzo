"""`lorenzo api METHOD PATH` (ADR 0161): one authenticated request, and the rules around it."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.main import Runtime, app

runner = CliRunner()


def runtime(
    tmp_path: Path, handler: httpx.MockTransport | None = None, *, stdin: str = ""
) -> Runtime:
    return Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok"},
        stdin=io.StringIO(stdin),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=handler,
    )


def serving(
    seen: list[httpx.Request], respond: httpx.Response | None = None
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return respond or httpx.Response(200, json={"ok": True, "n": [1, 2]})

    return httpx.MockTransport(handler)


def invoke(tmp_path: Path, args: list[str], transport: httpx.MockTransport, stdin: str = ""):  # noqa: ANN201
    return runner.invoke(app, ["api", *args], obj=runtime(tmp_path, transport, stdin=stdin))


# --- what it sends ------------------------------------------------------------------------


def test_a_get_sends_the_token_and_prints_the_body_indented(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = invoke(tmp_path, ["GET", "/tenants"], serving(seen))

    assert result.exit_code == 0, result.output
    assert seen[0].method == "GET"
    assert str(seen[0].url) == "https://api.example/tenants"
    assert seen[0].headers["Authorization"] == "Bearer tok"
    assert result.stdout == json.dumps({"ok": True, "n": [1, 2]}, indent=2) + "\n"


def test_the_method_can_be_written_in_any_case(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    invoke(tmp_path, ["delete", "/tenants/1/x"], serving(seen, httpx.Response(204)))

    assert seen[0].method == "DELETE"


@pytest.mark.parametrize(
    "path",
    [
        "https://evil.example/tenants",
        "http://evil.example/",
        "//evil.example/tenants",
        "tenants",
        "",
        "/ok\nHost: evil",
    ],
)
def test_a_full_address_or_a_non_path_is_refused_before_any_request(
    tmp_path: Path, path: str
) -> None:
    seen: list[httpx.Request] = []
    result = invoke(tmp_path, ["GET", path], serving(seen))

    assert result.exit_code == 2
    assert seen == []


def test_the_refusal_of_an_address_says_why(tmp_path: Path) -> None:
    result = invoke(tmp_path, ["GET", "https://evil.example/x"], serving([]))

    said = " ".join(re.sub(r"[│╭╮╰╯─]", " ", result.output).split())
    assert "only talks to the API you named" in said


@pytest.mark.parametrize("method", ["HEAD", "OPTIONS", "TRACE", "FETCH"])
def test_only_the_five_methods_are_accepted(tmp_path: Path, method: str) -> None:
    seen: list[httpx.Request] = []
    result = invoke(tmp_path, [method, "/tenants"], serving(seen))

    assert result.exit_code == 2
    assert seen == []


def test_query_pairs_are_added_to_the_ones_in_the_path_and_may_repeat(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    invoke(
        tmp_path,
        ["GET", "/tenants?kind=play", "-q", "tag=a", "-q", "tag=b", "--query", "q=x y"],
        serving(seen),
    )

    params = seen[0].url.params
    assert params["kind"] == "play"
    assert params.get_list("tag") == ["a", "b"]
    assert params["q"] == "x y"


def test_a_query_pair_without_an_equals_sign_is_refused(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = invoke(tmp_path, ["GET", "/tenants", "-q", "kind"], serving(seen))

    assert result.exit_code == 2
    assert seen == []


def test_if_match_is_sent_as_the_header(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    invoke(tmp_path, ["PATCH", "/x", "-d", "{}", "--if-match", '"abc"'], serving(seen))

    assert seen[0].headers["If-Match"] == '"abc"'


# --- the body ------------------------------------------------------------------------------


def test_data_is_sent_exactly_as_written_as_json(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    text = '{"name":  "Sunken Vale",\n "kind": "repository"}'
    result = invoke(tmp_path, ["POST", "/tenants", "-d", text], serving(seen))

    assert result.exit_code == 0, result.output
    assert seen[0].content == text.encode()
    assert seen[0].headers["Content-Type"] == "application/json"


def test_data_can_come_from_a_file(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    body = tmp_path / "body.json"
    body.write_text('{"a": 1}')
    invoke(tmp_path, ["PUT", "/x", "--data", f"@{body}"], serving(seen))

    assert seen[0].content == b'{"a": 1}'


def test_data_can_come_from_stdin(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    invoke(tmp_path, ["POST", "/x", "-d", "-"], serving(seen), stdin='{"from": "stdin"}')

    assert seen[0].content == b'{"from": "stdin"}'


@pytest.mark.parametrize("data", ["{not json", "", "@/definitely/not/here.json"])
def test_a_body_that_is_not_json_or_not_readable_is_refused_before_sending(
    tmp_path: Path, data: str
) -> None:
    seen: list[httpx.Request] = []
    result = invoke(tmp_path, ["POST", "/x", "-d", data], serving(seen))

    assert result.exit_code == 2
    assert seen == []


@pytest.mark.parametrize("method", ["GET", "DELETE"])
def test_a_body_is_only_for_post_put_and_patch(tmp_path: Path, method: str) -> None:
    seen: list[httpx.Request] = []
    result = invoke(tmp_path, [method, "/x", "-d", "{}"], serving(seen))

    assert result.exit_code == 2
    assert seen == []


# --- what it prints ---------------------------------------------------------------------------


def test_raw_leaves_the_body_as_it_came(tmp_path: Path) -> None:
    reply = httpx.Response(200, content=b'{"a":1}', headers={"content-type": "application/json"})
    result = invoke(tmp_path, ["GET", "/x", "--raw"], serving([], reply))

    assert result.stdout == '{"a":1}'


def test_include_prints_the_status_line_and_headers_then_the_body(tmp_path: Path) -> None:
    reply = httpx.Response(200, json={"a": 1}, headers={"ETag": '"v1"'})
    result = invoke(tmp_path, ["GET", "/x", "-i"], serving([], reply))

    head, _, body = result.stdout.partition("\n\n")
    assert head.splitlines()[0].endswith("200 OK")
    assert 'etag: "v1"' in head.lower()
    assert json.loads(body) == {"a": 1}


def test_an_empty_answer_prints_nothing(tmp_path: Path) -> None:
    result = invoke(tmp_path, ["DELETE", "/x"], serving([], httpx.Response(204)))

    assert result.exit_code == 0
    assert result.stdout == ""


def test_text_that_is_not_json_is_printed_as_it_is(tmp_path: Path) -> None:
    reply = httpx.Response(200, text="plain words", headers={"content-type": "text/plain"})
    result = invoke(tmp_path, ["GET", "/x"], serving([], reply))

    assert result.stdout == "plain words"


def test_bytes_are_written_untouched(tmp_path: Path) -> None:
    picture = bytes(range(256))
    reply = httpx.Response(200, content=picture, headers={"content-type": "image/png"})
    result = invoke(tmp_path, ["GET", "/me/picture"], serving([], reply))

    assert result.exit_code == 0
    assert result.stdout_bytes == picture


def test_a_refusal_is_printed_as_the_api_sent_it_with_its_status_on_stderr_and_exit_1(
    tmp_path: Path,
) -> None:
    problem = {"type": "repository-already-copied", "title": "Copied", "detail": "Copied already."}
    reply = httpx.Response(409, json=problem, headers={"content-type": "application/problem+json"})
    result = invoke(tmp_path, ["POST", "/x", "-d", "{}"], serving([], reply))

    assert result.exit_code == 1
    assert json.loads(result.stdout) == problem
    assert "HTTP 409: Copied already." in result.stderr


def test_a_refusal_without_a_body_still_says_its_status(tmp_path: Path) -> None:
    result = invoke(tmp_path, ["GET", "/x"], serving([], httpx.Response(502)))

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "HTTP 502" in result.stderr


def test_no_login_is_the_usual_one_line_error(tmp_path: Path) -> None:
    rt = runtime(tmp_path, serving([]))
    rt.env = {"LORENZO_API_URL": "https://api.example"}
    result = runner.invoke(app, ["api", "GET", "/tenants"], obj=rt)

    assert result.exit_code == 1
    assert "lorenzo login" in result.output


# --- paging -------------------------------------------------------------------------------------


def paged(seen: list[httpx.Request], pages: int = 3) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        page = int(request.url.params["page"])
        return httpx.Response(
            200,
            json={
                "items": [{"n": page * 10 + 1}, {"n": page * 10 + 2}],
                "total": pages * 2,
                "page": page,
                "size": 100,
                "pages": pages,
            },
        )

    return httpx.MockTransport(handler)


def test_paginate_walks_every_page_and_prints_one_array(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = invoke(tmp_path, ["GET", "/items", "--paginate", "-q", "kind=x"], paged(seen))

    assert result.exit_code == 0, result.output
    assert [row["n"] for row in json.loads(result.stdout)] == [11, 12, 21, 22, 31, 32]
    assert [r.url.params["page"] for r in seen] == ["1", "2", "3"]
    assert {r.url.params["size"] for r in seen} == {"100"}
    assert {r.url.params["kind"] for r in seen} == {"x"}


def test_paginate_on_something_that_is_not_a_page_prints_it_as_it_is(tmp_path: Path) -> None:
    result = invoke(tmp_path, ["GET", "/me", "--paginate"], serving([]))

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"ok": True, "n": [1, 2]}


def test_paginate_stops_at_a_refused_page_and_shows_the_refusal(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["page"] == "2":
            return httpx.Response(403, json={"title": "Forbidden", "detail": "Not yours."})
        return httpx.Response(
            200, json={"items": [{"n": 1}], "total": 2, "page": 1, "size": 100, "pages": 2}
        )

    result = invoke(tmp_path, ["GET", "/items", "--paginate"], httpx.MockTransport(handler))

    assert result.exit_code == 1
    assert "HTTP 403: Not yours." in result.stderr


@pytest.mark.parametrize("extra", [["--paginate", "-i"], ["--paginate"]])
def test_paginate_is_for_a_get_without_include(tmp_path: Path, extra: list[str]) -> None:
    seen: list[httpx.Request] = []
    method = "POST" if extra == ["--paginate"] else "GET"
    result = invoke(tmp_path, [method, "/items", *extra], serving(seen))

    assert result.exit_code == 2
    assert seen == []


# --- the rules every request gets ------------------------------------------------------


class Tokens:
    def __init__(self, fresh: str | None = None) -> None:
        self.fresh = fresh
        self.refreshed = 0

    def token(self) -> str:
        return "old"

    def refresh(self) -> str | None:
        self.refreshed += 1
        return self.fresh


def client_for(handler: httpx.MockTransport, tokens: Tokens) -> LorenzoClient:
    return LorenzoClient("https://api.example", tokens, transport=handler, sleep=lambda _: None)


def test_a_get_is_retried_after_a_bad_gateway_but_a_post_is_not() -> None:
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request.method)
        return httpx.Response(503) if len(attempts) % 2 else httpx.Response(200, json={})

    client = client_for(httpx.MockTransport(handler), Tokens())

    assert client.send("GET", "/x").status_code == 200
    attempts.clear()
    assert client.send("POST", "/x", content=b"{}").status_code == 503
    assert attempts == ["POST"]


def test_a_401_renews_the_token_once_and_retries_with_it() -> None:
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.headers["Authorization"])
        return (
            httpx.Response(401)
            if request.headers["Authorization"].endswith("old")
            else (httpx.Response(200, json={}))
        )

    tokens = Tokens(fresh="new")
    response = client_for(httpx.MockTransport(handler), tokens).send("GET", "/x")

    assert response.status_code == 200
    assert sent == ["Bearer old", "Bearer new"]
    assert tokens.refreshed == 1
