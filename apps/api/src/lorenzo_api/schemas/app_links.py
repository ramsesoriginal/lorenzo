from pydantic import BaseModel


class AppOut(BaseModel):
    url: str


class AppsOut(BaseModel):
    account_hub: AppOut
    inventory_web: AppOut
    beings: AppOut
    bench: AppOut
    calendars: AppOut
    sessions: AppOut | None = None
    writing: AppOut | None = None
    maps: AppOut | None = None
    social: AppOut | None = None
    # Only where the deployment has set LEGAL_URL (ADR 0439); there is no default.
    legal: AppOut | None = None


class AppLinksOut(BaseModel):
    """Where the apps live, and URL templates (`{tenant}`, `{id}`, `{slug}`) between them."""

    apps: AppsOut
    links: dict[str, str]
    # A support link (SUPPORT_URL, ADR 0439), null when the deployment has none.
    support_url: str | None = None
