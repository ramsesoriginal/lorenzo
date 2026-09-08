# Changelog

## [0.2.0](https://github.com/ramsesoriginal/lorenzo/compare/api-v0.1.0...api-v0.2.0) (2026-09-08)


### Features

* **api:** add continuous deployment to Cloud Run + Neon ([2cd7938](https://github.com/ramsesoriginal/lorenzo/commit/2cd7938d926e2d5514471d1c571315759fde385f))
* **api:** add mypy type checking ([99b1e80](https://github.com/ramsesoriginal/lorenzo/commit/99b1e80962e1a2d578ffdb52aac4417badaa564d))
* **api:** add OpenTelemetry tracing (FastAPI + SQLAlchemy) ([bde94b6](https://github.com/ramsesoriginal/lorenzo/commit/bde94b6753689e44c5f8f7cbc72671acf6094d98))
* **api:** add RFC 9457 problem+json error responses ([8465f89](https://github.com/ramsesoriginal/lorenzo/commit/8465f89cd6ac0f66b6473734efae4590c07554ce))
* **api:** scaffold apps/api - infra only, no domain models yet ([dc2b916](https://github.com/ramsesoriginal/lorenzo/commit/dc2b916994b310294ba241ddda390abf23965630))
* **api:** wire up fastapi-pagination ([d052b33](https://github.com/ramsesoriginal/lorenzo/commit/d052b33a19b55f517b8941d378ba69302c38cd94))
* **infra:** add local Postgres via Docker Compose ([4daaa42](https://github.com/ramsesoriginal/lorenzo/commit/4daaa42a51c8bef16047aba66adc41e274a63d25))


### Bug Fixes

* **api:** let uv own the Python version, not mise, and target 3.14 ([896e4ea](https://github.com/ramsesoriginal/lorenzo/commit/896e4ea14c3421072c1af51ee258c5c6c68de1c4))
* **ci:** three real failures from the first actual CI run on this PR ([927b71d](https://github.com/ramsesoriginal/lorenzo/commit/927b71d4cc064c900685048a17df6c8869aab86f))
