"""Pictures under a Map and SVG as a picture (ADR 0360, 0361)."""

import hashlib
import uuid
from typing import Any

import pytest
from test_maps import SPHERE, entry, make_map, replace
from test_story_sessions import world

from lorenzo_api.svg_lint import SvgRefused, check_svg

_PNG = b"\x89PNG\r\n\x1a\n" + b"layer-one"
_PNG_TWO = b"\x89PNG\r\n\x1a\n" + b"layer-two"
_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    b'<title>Sea</title><rect width="10" height="10" fill="#2468"/></svg>'
)


async def picture_info(actor: Any, t: Any, chart: str, *, title: str = "Backdrop", public=False):
    """An Information of the Map with a picture in it: (information id, payload id)."""
    made = await actor.post(
        f"/tenants/{t}/entities/{chart}/information",
        json={"title": title, "type": "picture", "is_public": public, "content": ""},
    )
    assert made.status_code == 201, made.text
    info = made.json()["id"]
    return info, await add_picture(actor, t, info, _PNG)


async def add_picture(actor: Any, t: Any, info: str, data: bytes, kind: str = "image/png") -> str:
    uploaded = await actor.post(
        f"/tenants/{t}/information/{info}/payloads", files={"file": ("p", data, kind)}
    )
    assert uploaded.status_code == 201, uploaded.text
    return str(uploaded.json()["id"])


async def set_layers(actor: Any, t: Any, chart: str, layers: list[dict[str, Any]]):
    url = f"/tenants/{t}/maps/{chart}"
    current = await actor.get(url)
    return await actor.client.put(
        f"{url}/layers",
        headers={**actor.headers, "If-Match": current.headers["etag"]},
        json={"layers": layers},
    )


TWO = {
    "anchors": [
        {"image": [0.1, 0.2], "at": [100, 50]},
        {"image": [0.9, 0.8], "at": [900, 650]},
    ]
}


async def test_a_layer_is_set_read_and_follows_the_audience_of_its_picture(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        chart = (await make_map(gm, t, "Coast", is_public=True))["id"]
        info, payload = await picture_info(gm, t, chart)
        none = await set_layers(gm, t, chart, [])
        assert none.status_code == 200 and none.json()["layers"] == []
        done = await set_layers(
            gm, t, chart, [{"information_id": info, "calibration": TWO, "opacity": 0.5}]
        )
        assert done.status_code == 200, done.text
        (layer,) = done.json()["layers"]
        assert layer["position"] == 0 and layer["information_id"] == info
        assert layer["payload_id"] == payload and layer["content_type"] == "image/png"
        assert layer["sha256"] == hashlib.sha256(_PNG).hexdigest()
        assert layer["calibration"] == TWO and layer["opacity"] == 0.5
        assert layer["needs_review"] is False and layer["title"] == "Backdrop"
        assert done.headers["etag"] != ""
        # An opacity that no binary float holds exactly comes back as it went in.
        sixty = await set_layers(
            gm, t, chart, [{"information_id": info, "calibration": TWO, "opacity": 0.6}]
        )
        assert sixty.json()["layers"][0]["opacity"] == 0.6
        assert (
            await set_layers(
                gm, t, chart, [{"information_id": info, "calibration": TWO, "opacity": 0.5}]
            )
        ).status_code == 200
        # The picture is its Information's: a reader who cannot see it is not told it is there.
        assert (await player.get(f"/tenants/{t}/maps/{chart}")).json()["layers"] == []
        assert (await gm.get(f"/tenants/{t}/maps/{chart}")).json()["layers"] == [layer]
        made_public = await gm.client.patch(
            f"/tenants/{t}/information/{info}",
            json={"is_public": True},
            headers={
                **gm.headers,
                "If-Match": (await gm.get(f"/tenants/{t}/information/{info}")).headers["etag"],
            },
        )
        assert made_public.status_code == 200, made_public.text
        seen = (await player.get(f"/tenants/{t}/maps/{chart}")).json()["layers"]
        assert [row["information_id"] for row in seen] == [info]
        # A player cannot write layers.
        assert (await set_layers(player, t, chart, [{"information_id": info}])).status_code == 403
        # Deleting the Information takes the layer with it.
        gone = await gm.client.delete(
            f"/tenants/{t}/information/{info}",
            headers={
                **gm.headers,
                "If-Match": (await gm.get(f"/tenants/{t}/information/{info}")).headers["etag"],
            },
        )
        assert gone.status_code == 204, gone.text
        assert (await gm.get(f"/tenants/{t}/maps/{chart}")).json()["layers"] == []
    finally:
        await w.clean_up()


async def test_layers_are_ordered_limited_and_refuse_what_makes_no_sense(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        chart = (await make_map(gm, t, "Coast", is_public=True))["id"]
        other = (await make_map(gm, t, "Elsewhere", is_public=True))["id"]
        a, _ = await picture_info(gm, t, chart, title="Sea")
        b, _ = await picture_info(gm, t, chart, title="Roads")
        foreign, _ = await picture_info(gm, t, other, title="Not here")
        ok = await set_layers(gm, t, chart, [{"information_id": b}, {"information_id": a}])
        assert [x["title"] for x in ok.json()["layers"]] == ["Roads", "Sea"]
        assert [x["position"] for x in ok.json()["layers"]] == [0, 1]
        again = await set_layers(gm, t, chart, [{"information_id": a}, {"information_id": b}])
        assert [x["title"] for x in again.json()["layers"]] == ["Sea", "Roads"]
        # Another entry's Information, a missing one, a repeated one, and too many.
        assert (await set_layers(gm, t, chart, [{"information_id": foreign}])).status_code == 404
        missing = [{"information_id": str(uuid.uuid4())}]
        assert (await set_layers(gm, t, chart, missing)).status_code == 404
        assert (
            await set_layers(gm, t, chart, [{"information_id": a}, {"information_id": a}])
        ).status_code == 422
        nine = [{"information_id": a}] * 9
        assert (await set_layers(gm, t, chart, nine)).status_code == 422
        for bad in (
            {"information_id": a, "calibration": {"anchors": []}},
            {"information_id": a, "calibration": {"anchors": TWO["anchors"][:1]}},
            {"information_id": a, "opacity": 1.5},
        ):
            assert (await set_layers(gm, t, chart, [bad])).status_code == 422
        # A refusal changes nothing, and a missing If-Match asks for one.
        assert [
            x["title"] for x in (await gm.get(f"/tenants/{t}/maps/{chart}")).json()["layers"]
        ] == [
            "Sea",
            "Roads",
        ]
        assert (
            await gm.client.put(
                f"/tenants/{t}/maps/{chart}/layers", headers=gm.headers, json={"layers": []}
            )
        ).status_code == 428
        stale = await gm.client.put(
            f"/tenants/{t}/maps/{chart}/layers",
            headers={**gm.headers, "If-Match": '"stale"'},
            json={"layers": []},
        )
        assert stale.status_code == 412
        # A Map with pictures cannot become a sphere, and a sphere cannot have them.
        assert (await replace(gm, t, chart, SPHERE)).status_code == 409
        globe = (await make_map(gm, t, "Globe", is_public=True))["id"]
        made = await replace(gm, t, globe, SPHERE)
        assert made.status_code == 200
        sphere_info, _ = await picture_info(gm, t, globe)
        assert (
            await set_layers(gm, t, globe, [{"information_id": sphere_info}])
        ).status_code == 422
    finally:
        await w.clean_up()


async def test_a_replaced_picture_needs_review_until_it_is_marked_reviewed(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        chart = (await make_map(gm, t, "Coast", is_public=True))["id"]
        info, old = await picture_info(gm, t, chart)
        first = await set_layers(gm, t, chart, [{"information_id": info, "calibration": TWO}])
        assert first.json()["layers"][0]["needs_review"] is False
        # The picture is replaced: a new one is added and the old one removed.
        fresh = await add_picture(gm, t, info, _PNG_TWO)
        assert (
            await gm.client.delete(f"/tenants/{t}/payloads/{old}", headers=gm.headers)
        ).status_code == 204
        (changed,) = (await gm.get(f"/tenants/{t}/maps/{chart}")).json()["layers"]
        assert changed["payload_id"] == fresh and changed["needs_review"] is True
        assert changed["sha256"] == hashlib.sha256(_PNG_TWO).hexdigest()
        # Writing the same layers again does not clear it ...
        kept = await set_layers(gm, t, chart, [{"information_id": info, "calibration": TWO}])
        assert kept.json()["layers"][0]["needs_review"] is True
        # ... saying it was reviewed does.
        cleared = await set_layers(
            gm, t, chart, [{"information_id": info, "calibration": TWO, "reviewed": True}]
        )
        assert cleared.json()["layers"][0]["needs_review"] is False
        # A layer with no picture shows nothing and needs nothing.
        empty = await gm.post(
            f"/tenants/{t}/entities/{chart}/information",
            json={"title": "Empty", "type": "picture", "is_public": False, "content": ""},
        )
        bare = await set_layers(gm, t, chart, [{"information_id": empty.json()["id"]}])
        (nothing,) = bare.json()["layers"]
        assert nothing["payload_id"] is None and nothing["needs_review"] is False
    finally:
        await w.clean_up()


async def test_an_svg_is_a_picture_when_it_passes_the_lint_and_is_served_sandboxed(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        chart = (await make_map(gm, t, "Coast", is_public=True))["id"]
        info, png_payload = await picture_info(gm, t, chart)
        url = f"/tenants/{t}/information/{info}/payloads"
        good = await gm.post(url, files={"file": ("sea.svg", _SVG, "image/svg+xml")})
        assert good.status_code == 201, good.text
        served = await gm.get(f"/tenants/{t}/payloads/{good.json()['id']}/content")
        assert served.headers["content-type"] == "image/svg+xml"
        assert served.headers["x-content-type-options"] == "nosniff"
        assert served.headers["content-security-policy"] == "default-src 'none'; sandbox"
        assert served.headers["content-disposition"].startswith("attachment")
        # Every picture is served with nosniff, and the others carry no sandbox policy.
        png = await gm.get(f"/tenants/{t}/payloads/{png_payload}/content")
        assert png.status_code == 200 and png.headers["x-content-type-options"] == "nosniff"
        assert "content-security-policy" not in png.headers
        for name, bad in BAD_SVGS.items():
            refused = await gm.post(url, files={"file": ("bad.svg", bad, "image/svg+xml")})
            assert refused.status_code == 422, name
        # A picture of another type is not an SVG however it is named, and a profile picture
        # keeps its old list.
        wrong = await gm.post(url, files={"file": ("sea.svg", _SVG, "text/xml")})
        assert wrong.status_code == 422
        thing = await entry(gm, t, "Thing")
        main = await gm.put(
            f"/tenants/{t}/entities/{thing}/picture",
            files={"file": ("sea.svg", _SVG, "image/svg+xml")},
        )
        assert main.status_code == 201, main.text
    finally:
        await w.clean_up()


def svg(body: str, root: str = '<svg xmlns="http://www.w3.org/2000/svg"') -> bytes:
    return f"{root}>{body}</svg>".encode()


BAD_SVGS = {
    "script": svg("<script>alert(1)</script>"),
    "handler": svg('<rect width="1" height="1" onclick="alert(1)"/>'),
    "handler upper": svg('<rect width="1" height="1" ONLOAD="x"/>'),
    "foreignObject": svg("<foreignObject><p>hi</p></foreignObject>"),
    "link": svg('<a href="https://example.com"><rect width="1" height="1"/></a>'),
    "external image": svg('<image href="https://example.com/x.png"/>'),
    "external use": svg('<use href="https://example.com/x.svg#a"/>'),
    "javascript use": svg(
        '<use xlink:href="javascript:alert(1)" xmlns:xlink="http://www.w3.org/1999/xlink"/>'
    ),
    "javascript spaced": svg('<rect fill="java\tscript:alert(1)"/>'),
    "css import": svg("<style>@import url(https://example.com/a.css);</style>"),
    "css url": svg('<rect style="fill:url(https://example.com/a.png)"/>'),
    "animation": svg('<animate attributeName="href" to="javascript:alert(1)"/>'),
    "set": svg('<set attributeName="x" to="1"/>'),
    "doctype": b'<!DOCTYPE svg [<!ENTITY a "b">]><svg xmlns="http://www.w3.org/2000/svg"/>',
    "processing instruction": (
        b'<?xml-stylesheet href="a.css"?><svg xmlns="http://www.w3.org/2000/svg"/>'
    ),
    "not svg": b'<html xmlns="http://www.w3.org/1999/xhtml"/>',
    "no namespace": b"<svg><rect/></svg>",
    "not xml": b"<svg xmlns='http://www.w3.org/2000/svg'><rect></svg>",
    "empty": b"",
    "editor element": svg(
        '<sodipodi:namedview xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"/>'
    ),
    "editor attribute": svg(
        '<rect inkscape:label="x" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"/>'
    ),
}


def test_the_lint_accepts_drawing_and_refuses_with_one_sentence():
    check_svg(_SVG)
    gradient = '<linearGradient id="g"><stop offset="0"/></linearGradient>'
    check_svg(svg(f'<defs>{gradient}</defs><rect fill="url(#g)"/>'))
    check_svg(svg('<image href="data:image/png;base64,AAAA"/><use href="#a"/>'))
    for name, bad in BAD_SVGS.items():
        with pytest.raises(SvgRefused) as refused:
            check_svg(bad)
        assert refused.value.reason and "alert" not in refused.value.reason, name


def test_the_lint_refuses_a_deep_and_a_large_document():
    deep = svg("<g>" * 70 + "</g>" * 70)
    with pytest.raises(SvgRefused):
        check_svg(deep)
    many = svg("<g/>" * 50_001)
    with pytest.raises(SvgRefused):
        check_svg(many)


async def test_every_picture_has_a_stored_fingerprint(raw_client, fake_jwks_server):
    from _admin_db import admin_session_factory
    from sqlalchemy import select

    from lorenzo_api.models import PayloadPicture

    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        chart = (await make_map(gm, t, "Coast", is_public=True))["id"]
        _, payload = await picture_info(gm, t, chart)
        async with admin_session_factory() as session:
            row = await session.scalar(
                select(PayloadPicture).where(PayloadPicture.payload_id == uuid.UUID(payload))
            )
            assert row is not None
            assert bytes(row.sha256) == hashlib.sha256(_PNG).digest()
    finally:
        await w.clean_up()
