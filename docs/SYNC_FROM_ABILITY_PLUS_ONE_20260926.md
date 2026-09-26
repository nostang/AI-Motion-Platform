# Ability +1 motion sync — 2026-09-26

## Scope

This standalone repository was updated from the Motion module at:

`/Users/ivesmi/Documents/badminton-plus-one/modules/03_AI_Motion`

The source repository checkpoint was `2cadbc2`, tagged
`authenticated-motion-media-deployed-20260925-2`. This sync copied current
Motion engine, API, frontend, contracts, tests, migrations, and offline
experiment harnesses into a dedicated PoC branch. It did not modify, build, or
deploy Badminton Plus One.

## Preserved PoC content

- repository history, remote, README, license, and portfolio assets;
- local `.env`, datasets, generated output, virtual environment, and videos;
- PoC-only documents and the pre-existing untracked
  `scripts/offline_demo_server.py`;
- local development database configuration.

No delete-style synchronization was used, so PoC-only files remain available.

## Isolation contract

`AI_Motion_PoC` is not a deployment source for `badminton-motion-api`. The
application validates its resource configuration at startup and refuses known
Badminton Plus One production database, bucket, and task-queue identifiers.
Local experiments default to `APP_ENV=development` and a local PostgreSQL
database.

Any future standalone deployment requires a dedicated database, Storage
bucket, Cloud Tasks queue, service account, secrets, release tag, preview
verification, and explicit traffic approval. Reusing the retired `ai-motion`
service configuration without replacing its production resource references is
not permitted.

## Retired URL diagnosis

`https://ai-motion-1051941896828.asia-east1.run.app/` currently returns HTTP
403 before the request reaches FastAPI. Cloud Run has no invoker binding for
the public, and the only revision is tagged `retired`. Logs show successful
container startup followed by unauthenticated-request rejection, so the
observed failure is IAM access control rather than a crashed application.

## Verification

- Before sync: 216 tests and 18 subtests passed.
- After source sync, PoC isolation protection, and dependency refresh: 234
  tests passed and 2 skipped. The skipped cases are wallet integration tests
  that intentionally require a separate `TEST_MOTION_DATABASE_URL`.
- Local smoke: `/health` returned 200 and `/` returned 200.
- Isolation guard tests cover local acceptance, production database rejection,
  production bucket rejection, production queue rejection, and attempts to
  disable the guard.
