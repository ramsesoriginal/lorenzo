# Rate-limiting the invite-link endpoints

[ADR 0092](../adr/0092-campaign-invite-links.md) adds two routes that anyone on the internet can call: `GET /invites/{token}` (a public preview) and `POST /invites/{token}/redeem`. This project has no rate limiter of its own to lean on ([ADR 0008](../adr/0008-deferred-taskiq-and-fastapi-limiter.md) deferred one because it needs Redis), so the protection is two layers, and **only one of them is real**.

> **The invite-link feature must not be exposed publicly until the edge rule below is in place.** The in-process backstop alone is not enough: every Cloud Run instance keeps its own buckets, so it only limits each instance separately, and a determined caller simply gets spread across instances.

## The two layers

| Layer | What it is | Where it lives | What it protects against |
| --- | --- | --- | --- |
| **Edge rule** (the control) | A rate-limit rule on `/invites/*`, enforced before a request reaches the API | Cloudflare or Cloud Armor, configured by hand | Floods, probing, cost. Works across every instance. |
| **In-process backstop** | A per-instance token bucket keyed by client address, returning `429` + `Retry-After` | `apps/api` (`rate_limit.py`) | One client hammering one instance, and an absent or misconfigured edge rule |

Tokens themselves are 256 random bits, so guessing one is infeasible whatever the limits are; the limits exist for flooding and for spotting probes, not for making guessing hard.

## 1. The edge rule (do this before exposing the feature)

Pick whichever fits how the API is actually reached. **I have not been able to run either of these against a real account**, so treat the exact flags and field names as a starting point to check against the current vendor documentation, and verify the result with the test at the end.

### Cloudflare (a Cloudflare-proxied hostname in front of the API)

*Security → WAF → Rate limiting rules → Create rule*:

- **If incoming requests match:** custom expression `starts_with(http.request.uri.path, "/invites/")`
- **Characteristics:** IP
- **Requests / period:** start around 30 per minute per IP, and check which periods your plan permits (lower plans allow only some)
- **Action:** Block (or Managed Challenge), for a short duration such as a minute

### Cloud Armor (an external HTTP(S) load balancer in front of Cloud Run)

```bash
gcloud compute security-policies rules create 1000 \
  --security-policy=lorenzo-api-policy \
  --expression="request.path.matches('/invites/.*')" \
  --action=rate-based-ban \
  --rate-limit-threshold-count=30 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=300 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP
```

### The caveat that matters: the direct URL

A Cloud Run service is reachable at its own `*.run.app` address as well as at any hostname you front it with. **An edge rule only protects traffic that goes through the edge.** If the direct address stays open, an attacker can skip the rule entirely and only the in-process backstop remains. Either restrict Cloud Run's ingress so it only accepts traffic from the load balancer, or accept that the direct address is protected by the backstop alone and keep the feature's own limits (short expiry, revocation) as your containment.

## 2. The in-process backstop

Configured by environment variables on the API:

| Variable | Default | Meaning |
| --- | --- | --- |
| `INVITE_RATE_LIMIT_PER_MINUTE` | `30` | Requests per client per minute, per instance, across both routes. `0` disables the backstop. |
| `INVITE_RATE_LIMIT_TRUSTED_PROXY_HOPS` | `0` | How many reverse proxies in front of the API can be trusted. |

**`INVITE_RATE_LIMIT_TRUSTED_PROXY_HOPS` is the setting that goes wrong.** Behind Cloud Run every request arrives from Google's front end, so at `0` every caller looks like the same address and **all users share one bucket**: the backstop then throttles the feature for everyone at once. `.github/workflows/deploy-api.yml` sets it to `1`, which keys the limiter on the rightmost `X-Forwarded-For` entry, the address the front end actually saw. Anything to its left is written by the client and is deliberately ignored, or a caller could dodge the limit by rotating a fake header.

If you put a CDN such as Cloudflare in front of Cloud Run, there are then two trusted hops and this must become `2`. Confirm the value against a real request's `X-Forwarded-For` before relying on it; a wrong value fails toward the shared bucket, not toward being open.

## 3. Verify it works

From one machine, well past the limit:

```bash
for i in $(seq 1 60); do
  curl -s -o /dev/null -w "%{http_code}\n" "https://your-api.example/invites/not-a-real-token"
done | sort | uniq -c
```

You should see `404` for the first requests, then `429`. To tell **which layer** answered, look at the response: the edge rule answers before the API, so the API's own logs will not contain the rejected requests, whereas the backstop's `429` carries a `Retry-After` header and a problem-details body (`"type": "too-many-requests"`).

## 4. Watching for probes

The API never logs a token (`tests/test_invite_token_redaction.py` fails if one appears in a span or a log line), but it does log every rejected attempt and every throttled one, against the client address:

- `invite_link_rejected`: an unknown, expired, revoked or exhausted token (the response is identical for all four, on purpose)
- `invite_rate_limited`: the backstop refused a request

A spike of `invite_link_rejected` from one address is a probe. Filter Cloud Logging on the event name and group by `source`, then tighten the edge rule.

## See also

- [ADR 0092](../adr/0092-campaign-invite-links.md): the design, including why uses are unlimited by default and what that costs.
- [Deployment setup](deployment-setup.md) and `.github/workflows/deploy-api.yml`.
