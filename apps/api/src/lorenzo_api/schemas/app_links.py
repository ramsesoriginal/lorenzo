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
    maps: AppOut | None = None


class AppLinksOut(BaseModel):
    """Where the apps live, and URL templates (`{tenant}`, `{id}`, `{slug}`) between them."""

    apps: AppsOut
    links: dict[str, str]
