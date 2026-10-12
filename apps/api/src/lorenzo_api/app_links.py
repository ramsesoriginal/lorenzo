"""The registry of app links (ADR 0273): where the Lorenzo apps live and what the default
links between them are. Pure: it builds the document `GET /app-links` serves from Settings,
so it is tested without a database. Nothing is stored; the source is the environment.

A link is a URL template with named placeholders in braces (`{tenant}`, `{id}`, `{slug}`)
that the client fills in, percent-encoding each value. The shapes are exactly the ones the
apps already build by hand, so a link that works today keeps working.
"""

from typing import Any

from lorenzo_api.config import Settings

# Per link: which app it lives in and the path (with query) relative to that app's address.
_DEFAULTS: dict[str, tuple[str, str]] = {
    # The hub's notifications page, and where a notification leads when it names no target.
    "notifications": ("account_hub", "/notifications/"),
    "notification": ("account_hub", "/notifications/"),
    # The hub's page of repositories, and the authoring studio entry point.
    "repository": ("account_hub", "/repositories/"),
    "studio": ("account_hub", "/studio/"),
    # Where a user approves a command line or script (the device-code flow).
    "device": ("account_hub", "/device/"),
    # inventory-web: an item or an inventory item, by id or by slug; a character's board.
    "item": ("inventory_web", "/item/?tenant={tenant}&id={id}"),
    "item_by_slug": ("inventory_web", "/item/?tenant={tenant}&slug={slug}"),
    "inventory": ("inventory_web", "/board/?tenant={tenant}&character={id}"),
    "board": ("inventory_web", "/board/?tenant={tenant}&character={id}"),
    # Lorenzo Beings: a being's page, by id or by slug.
    "being": ("beings", "/being/?tenant={tenant}&id={id}"),
    "being_by_slug": ("beings", "/being/?tenant={tenant}&slug={slug}"),
}


def _clean(url: str) -> str:
    return url.strip().rstrip("/")


def apps(settings: Settings) -> dict[str, str]:
    """Each app's address, without a trailing slash."""
    return {
        "account_hub": _clean(settings.account_hub_url),
        "inventory_web": _clean(settings.inventory_web_url),
        "beings": _clean(settings.beings_url),
        "bench": _clean(settings.bench_url),
    }


def account_hub_url(settings: Settings) -> str:
    """The account hub's address (no trailing slash), for code that needs it server-side."""
    return apps(settings)["account_hub"]


def device_url(settings: Settings) -> str:
    """The hub's device-approval page, e.g. the verification URI of the device-code flow."""
    return links(settings)["device"]


def links(settings: Settings) -> dict[str, str]:
    """Every link template, defaults first, then APP_LINK_TEMPLATES overrides on top."""
    where = apps(settings)
    built = {name: where[app] + path for name, (app, path) in _DEFAULTS.items()}
    built.update(settings.app_link_templates)
    return built


def document(settings: Settings) -> dict[str, Any]:
    """The `GET /app-links` body."""
    return {
        "apps": {name: {"url": url} for name, url in apps(settings).items()},
        "links": links(settings),
    }
