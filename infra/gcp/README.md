# AI_Motion_PoC standalone Google Cloud deployment

This deployment is independent from Badminton Plus One.

Dedicated resource boundary:

- Google Cloud account: `blue26929@gmail.com`
- Google Cloud project: `ai-motion-lab-ivesmi`
- Cloud Run service: `ai-motion-poc`
- Cloud SQL instance: `ai-motion-poc-db`
- PostgreSQL database: `ai_motion_poc`
- Runtime service account: `ai-motion-poc-runtime`
- Cloud Tasks queue: `ai-motion-poc-analysis`
- Storage bucket: `ai-motion-lab-ivesmi-ai-motion-poc-media`
- Secret names use the `ai-motion-poc-` prefix.

The service is a standalone demo. It uses the repository's local demo user
`user_id=1`; it does not use Badminton Plus One login, wallet, database,
Storage, queue, secrets, service accounts, or Cloud Run services.

The `badminton-plus-one-ivesmi` and `cashhelpme-lab-ivesmi` projects are
explicitly out of scope for this deployment.

Release rules:

1. Build only from a clean committed revision.
2. Use a unique image tag, never `latest`.
3. Deploy a no-traffic preview revision first.
4. Verify health, home, database schema, upload ticket and one real analysis.
5. Route traffic only to the verified exact revision.
6. Keep max instances at one and queue concurrency at one for cost control.
7. Never replace the dedicated resource names above with Badminton Plus One
   production identifiers.

## Current standalone release (2026-09-30)

- Public URL: `https://ai-motion-poc-987230868182.asia-east1.run.app/`
- Cloud Run canonical URL:
  `https://ai-motion-poc-dsqjlyd2ba-de.a.run.app/`
- Current revision: `ai-motion-poc-00008-wip` (`100%`, tag `current`)
- Current image digest:
  `sha256:d7200a18e3010c6031d67d8091aca34e79e2ef1bea65a4293c6c3badf70bdf28`
- Deployed product commit: `98218ca`
- Product release tag: `ai-motion-poc-release-20260930-2`
- Rollback revision: `ai-motion-poc-00005-buz` (`0%`, tag `rollback`)
- Runtime limits: min instances `0`, max instances `1`, concurrency `1`,
  queue dispatch rate `1/s`, queue concurrency `1`.

The service intentionally runs in standalone PoC mode (`APP_ENV=staging`) so
it does not require or reuse Badminton Plus One login credentials. Cloud Run
invocation is public (`allUsers` has `roles/run.invoker`) by explicit owner
approval. The demo user and its assessment/report endpoints are therefore
publicly reachable. Do not store personal or sensitive videos or user data in
this environment.

Standalone analysis billing is locked to `AI_MOTION_BILLING_MODE=free`.
Creating or quoting an assessment does not read or write Goo wallets,
entitlements or analysis charges. The old wallet tables remain only as unused
schema history; they are not part of the standalone user flow.

The worker URL uses the stable service URL rather than a preview tag. Its
Cloud Tasks request still carries a service-account OIDC token and the
dedicated internal API key. The public web/API boundary and the internal
worker authorization are separate controls.

Release verification:

- Python tests: `264 passed, 2 skipped`.
- Cloud Build upload: `138` production files, approximately `6.5 MiB`.
- Upload excludes experiments, tests, documentation, datasets, model weights,
  local videos, virtual environments, caches and `.env` files.
- Anonymous smoke checks returned HTTP `200` for health, home, user summary,
  assessment status, report, visualization and upload-ticket creation.
- Real Cloud Storage + Cloud Tasks analysis completed for assessment `2`:
  `693/693` detected frames, `8/8` footwork events, score `85.039`.
- The worker request returned HTTP `200`; the earlier repeated `401` condition
  was removed by normalizing the Secret Manager value before comparison.
- A second-use assessment for the same demo user returned HTTP `202` with
  `charge_kind=poc_free`, `points=0`, then completed as assessment `4` with
  `8/8` footwork events and score `84.762`.

The rollback revision is the previously verified standalone release and still
contains the inherited Goo billing rule. It is suitable for emergency web and
analysis recovery, but a demo user's later assessment can return `402` after
its first-free allowance. Redeploy product commit `98218ca` to restore free
standalone analysis after any rollback.

Cloud SQL is the primary continuing fixed cost even while Cloud Run scales to
zero. This PoC uses PostgreSQL 16 on `db-f1-micro`, a 10 GB HDD, no automated
backups, no authorized public network and deletion protection enabled. Uploaded
source objects under `uploads/` expire after one day; generated assessment
artifacts are retained for the demo.
