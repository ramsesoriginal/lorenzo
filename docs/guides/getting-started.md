# Getting started

## Prerequisites

- [mise](https://mise.jdx.dev) — manages every other toolchain
- Git

## Right now

```bash
git clone git@github.com:ramsesoriginal/lorenzo.git
cd lorenzo
mise install
```

That's it — there's no app scaffolded yet, so there's nothing to run. See [docs/guides/adding-an-app.md](adding-an-app.md) for what happens next, and [docs/architecture/overview.md](../architecture/overview.md) for the intended shape of the whole system.

## Troubleshooting

- **`mise: command not found`** — install mise itself first; it's the one thing this repo can't install for you.
