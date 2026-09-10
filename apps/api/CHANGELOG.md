# Changelog

## [0.3.0](https://github.com/ramsesoriginal/lorenzo/compare/api-v0.2.0...api-v0.3.0) (2026-09-10)


### Features

* **api:** add a real login helper for local dev Authgear tokens ([0524e0b](https://github.com/ramsesoriginal/lorenzo/commit/0524e0bf4fe26f4d6c6b2fc78ff51bbaff9632bd))
* **api:** add a real login helper for local dev Authgear tokens ([e79b006](https://github.com/ramsesoriginal/lorenzo/commit/e79b0065284caaaa984e2d2737ffe84e5e0d7396))
* **api:** add an OpenAPI breaking-change check to CI ([7350b8f](https://github.com/ramsesoriginal/lorenzo/commit/7350b8fa301cb8eb3fd1b9d577afd4283e337b1f))
* **api:** add knowledge/group membership, fix visibility gaps ([530f354](https://github.com/ramsesoriginal/lorenzo/commit/530f354468df209c778d5e6508d65538b5f60bb0))
* **api:** add read-only convenience relationships on Entity ([7852e3f](https://github.com/ramsesoriginal/lorenzo/commit/7852e3f2be11142b487f4ff6ded557461d599332))
* **api:** add the real entity.tenant_id -&gt; tenant.id FK ([443824e](https://github.com/ramsesoriginal/lorenzo/commit/443824eb425cc66eea09ed4290188f7a0717bb78))
* **api:** auth, tenancy, campaigns, and the full RFC 0001/RFC 0002 domain model ([2cc9367](https://github.com/ramsesoriginal/lorenzo/commit/2cc93676ce39f1bb2d4235bb615f06d9cd588ad5))
* **api:** entities REST endpoints - list and rich detail ([240032f](https://github.com/ramsesoriginal/lorenzo/commit/240032f522782e3fcbb7ae9beda3ef1419f90f36))
* **api:** items, item instances, container/owner filtering, docs ([f997068](https://github.com/ramsesoriginal/lorenzo/commit/f9970681343c0de196312526aa2ee4f3e430938c))
* **api:** knowledge, group membership, and public information (ADR 0028) ([96b0a39](https://github.com/ramsesoriginal/lorenzo/commit/96b0a3949ede9b06eb85394291b6e9762d833e3a))
* **api:** REST API foundation - tenant scoping, schemas, payload content ([a0e687b](https://github.com/ramsesoriginal/lorenzo/commit/a0e687b716bd86b5549f6a1dcb550c421fa82a90))
* **api:** sub-slice 1 — restricted app role, RLS now actually enforced ([85e0224](https://github.com/ramsesoriginal/lorenzo/commit/85e0224d45ecb76f677c7c3dff92db6bac809c63))
* **api:** sub-slice 1 — the entity table ([53a0cc9](https://github.com/ramsesoriginal/lorenzo/commit/53a0cc9602c99edb033c4fdd8893bb898a1edc2d))
* **api:** sub-slice 2 — User, full Tenant, Membership ([007d018](https://github.com/ramsesoriginal/lorenzo/commit/007d0185bcd5b1a11c8a6338b084e76952380b6c))
* **api:** sub-slice 3 — Authgear token verification ([5a99677](https://github.com/ramsesoriginal/lorenzo/commit/5a996771f864700a559d58f945fa4d207fff98c0))
* **api:** sub-slice 3 — stat definitions, groups, and per-entity values ([5a02bb3](https://github.com/ramsesoriginal/lorenzo/commit/5a02bb3ea79be57839a05a4aae65b8c7fb2c1c22))
* **api:** sub-slice 4 — Campaign and Player ([4205fec](https://github.com/ramsesoriginal/lorenzo/commit/4205fec76c7caa45822717b7941ad4e86a0a4404))
* **api:** sub-slice 4 — entity_prototype, the inheritance graph ([15ae468](https://github.com/ramsesoriginal/lorenzo/commit/15ae468e58ebf1f647a307102ae08b4ceb30fc04))
* **api:** sub-slice 5 — Character (being), roster reuse, and ownership ([da1804b](https://github.com/ramsesoriginal/lorenzo/commit/da1804bef6c3c7c0c2a18e816dcb24fe2de82f88))
* **api:** sub-slice 5 — containment, the generic physical relation ([19703c4](https://github.com/ramsesoriginal/lorenzo/commit/19703c4e706e86c35b002f6113112c9682bb3b64))
* **api:** sub-slice 6 — Campaign GM, orga, and the campaign access rule ([39f6030](https://github.com/ramsesoriginal/lorenzo/commit/39f60302d00cdfd4506181b498b017b98f4ab839))
* **api:** sub-slice 6 — information and payloads ([10a2db2](https://github.com/ramsesoriginal/lorenzo/commit/10a2db295cef403582faa33045ca9a3f3d031a65))
* **api:** sub-slice 7 — item, item_instance, and the v_item view ([a87b789](https://github.com/ramsesoriginal/lorenzo/commit/a87b7893cf5fc8eef05f8cd6ec79967576d8fad5))
* **api:** tenant table bootstrap ([2137567](https://github.com/ramsesoriginal/lorenzo/commit/21375677169452e766691aa01203a7cd893c223b))


### Bug Fixes

* **api:** add player.campaign_id's missing index ([fedf8b5](https://github.com/ramsesoriginal/lorenzo/commit/fedf8b5bec9ccf2475d08af152f81082467b7763))
* **api:** close out four review findings ([dccc87c](https://github.com/ramsesoriginal/lorenzo/commit/dccc87c0f02276c398a0948120603e1578838f81))
* **api:** close out four review findings ([4c8ae20](https://github.com/ramsesoriginal/lorenzo/commit/4c8ae204b5e1fb00d2c00aa62b1551bdbee910a2))
* **api:** close the same information-disclosure gap in items/item-instances ([f9715ce](https://github.com/ramsesoriginal/lorenzo/commit/f9715ce93a4947d22881de89f605ae590539bc56))
* **api:** make GET /entities/{id} actually respect is_public/knowledge ([0cd215c](https://github.com/ramsesoriginal/lorenzo/commit/0cd215ce47f110eb03d715105a7970dd6e7e8d42))
* **api:** make GET /payloads/{id}/content respect is_public/knowledge too ([aed1f4e](https://github.com/ramsesoriginal/lorenzo/commit/aed1f4e0f7b719f8e12ef9934bae6e75c029a5c9))
* **api:** split v_item into v_item and v_item_instance ([23f5f92](https://github.com/ramsesoriginal/lorenzo/commit/23f5f922974ff881699612bee3cdcdd26fa8ffcd))
* **api:** sync uv.lock after the 0.2.0 bump, close the CI gap that mi… ([a6a2d9f](https://github.com/ramsesoriginal/lorenzo/commit/a6a2d9f3ce29a70a5ad8b9d5b5834cb1357f0182))
* **api:** sync uv.lock after the 0.2.0 bump, close the CI gap that missed it ([7f2c4ff](https://github.com/ramsesoriginal/lorenzo/commit/7f2c4ff8a61ea3a483e1c626a88dee95afa6611b))


### Documentation

* **api:** stop claiming RLS is unenforced now that the role fix shipped ([b616488](https://github.com/ramsesoriginal/lorenzo/commit/b61648823da93e3349572282b7f4748842d4abf0))
* clean up stale non-ADR/RFC documentation ([89dc443](https://github.com/ramsesoriginal/lorenzo/commit/89dc443b5441e1fbe1ebd9d0d5ec4b4465c823d7))
* confirm production deploy is verified end to end, fix stale merge refs ([e527f87](https://github.com/ramsesoriginal/lorenzo/commit/e527f87204df26c509729568f6b0e814b867dd82))
* confirm production deploy is verified end to end, fix stale merge refs ([b6289ad](https://github.com/ramsesoriginal/lorenzo/commit/b6289ad8429a0807de28de83e0dcdedb5df9bff5))
* merge the six per-slice ER diagrams into one domain model diagram ([0749530](https://github.com/ramsesoriginal/lorenzo/commit/0749530d75c0a70fa66041f16602e6afc6a50b15))
* pass 1 — audit and correct stale documentation ([a099830](https://github.com/ramsesoriginal/lorenzo/commit/a099830d778de159d669a08ab41e13dc7c924f56))
* pass 2 — document deployment architecture and observability ([1f836c8](https://github.com/ramsesoriginal/lorenzo/commit/1f836c84cc03355ad2face8aa11db94deb8bd87f))

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
