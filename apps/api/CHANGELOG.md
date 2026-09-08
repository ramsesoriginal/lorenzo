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

* **api:** copy README.md into the Docker build context ([4e6e7d7](https://github.com/ramsesoriginal/lorenzo/commit/4e6e7d7b51e5cfe68825a99fb8b7c3333055fb3f))
* **api:** copy README.md into the Docker build context ([d88fdac](https://github.com/ramsesoriginal/lorenzo/commit/d88fdac826bfa7d2def8001171578583dd47cc92))
* **api:** drop Neon's channel_binding param for asyncpg too ([3751955](https://github.com/ramsesoriginal/lorenzo/commit/3751955740c339077fbf05cb45c61a8a70689020))
* **api:** drop Neon's channel_binding param for asyncpg too ([1caec90](https://github.com/ramsesoriginal/lorenzo/commit/1caec904dd85e2c044e5b5215e473f4e76ee65a7))
* **api:** let uv own the Python version, not mise, and target 3.14 ([896e4ea](https://github.com/ramsesoriginal/lorenzo/commit/896e4ea14c3421072c1af51ee258c5c6c68de1c4))
* **api:** listen on Cloud Run's $PORT instead of a hardcoded 8000 ([52773f8](https://github.com/ramsesoriginal/lorenzo/commit/52773f8d463c8deabee7c1831867c8e2fef64791))
* **api:** listen on Cloud Run's $PORT instead of a hardcoded 8000 ([d06c395](https://github.com/ramsesoriginal/lorenzo/commit/d06c3951ebe9bf458a56b481f8bdd2d93db5a484))
* **api:** rewrite Neon's sslmode query param for asyncpg ([6e78f2e](https://github.com/ramsesoriginal/lorenzo/commit/6e78f2edc248fdc0f9930c546a2914eb43df7c53))
* **api:** rewrite Neon's sslmode query param for asyncpg ([8cf6349](https://github.com/ramsesoriginal/lorenzo/commit/8cf6349dab30192bf2dc424dfcd5f5aae77620db))
* **ci:** three real failures from the first actual CI run on this PR ([927b71d](https://github.com/ramsesoriginal/lorenzo/commit/927b71d4cc064c900685048a17df6c8869aab86f))
