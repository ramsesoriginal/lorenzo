"""The official Lorenzo, which the CLI talks to when nothing else is named (ADR 0164).

Three public values, none of them a secret. They are one set: `config.load_settings` fills them
in together or not at all. If the API address, the Authgear project or the client moves, this is
the file to change (docs/operations/deployment-setup.md).
"""

OFFICIAL_API_URL = "https://lorenzo-api-100817212329.europe-west1.run.app"
OFFICIAL_ISSUER = "https://lorenzo.authgear.cloud"
OFFICIAL_CLIENT_ID = "745e5fa9ac3cd9a1"
