# AI Motion PoC — current deployment handoff

Verified: 2026-09-30 (Asia/Taipei)

## Product and repository

- Repository: `https://github.com/nostang/AI-Motion-Platform.git`
- Deployment branch: `codex/standalone-cloud-deploy-20260930`
- Deployed product commit: `70ade83`
- Product release tag: `ai-motion-poc-release-20260930-1`
- The documentation commit containing this handoff is newer than the deployed
  product commit. It does not change the deployed application image.

## Independent Google Cloud boundary

- Account: `blue26929@gmail.com`
- Project: `ai-motion-lab-ivesmi`
- Service: `ai-motion-poc` in `asia-east1`
- Public URL: `https://ai-motion-poc-987230868182.asia-east1.run.app/`
- Current revision: `ai-motion-poc-00005-buz`, `100%`, tag `current`
- Rollback revision: `ai-motion-poc-00001-jal`, `0%`, tag `rollback`
- Current image:
  `asia-east1-docker.pkg.dev/ai-motion-lab-ivesmi/ai-motion-poc/app@sha256:3d980f2cf3b06fc3c8c4bee85193f2f4e600098e3827710e0ef9509f77cc0b02`
- Database: Cloud SQL `ai-motion-poc-db`, database `ai_motion_poc`
- Queue: `ai-motion-poc-analysis`
- Media bucket: `ai-motion-lab-ivesmi-ai-motion-poc-media`
- Runtime identity:
  `ai-motion-poc-runtime@ai-motion-lab-ivesmi.iam.gserviceaccount.com`

Badminton Plus One (`badminton-plus-one-ivesmi`) and CASHelpMe
(`cashhelpme-lab-ivesmi`) were not changed by this release. Their Cloud Run,
database, Storage, queue, secret and IAM resources are not referenced by this
deployment.

## Access and runtime decisions

- Cloud Run invocation is public by explicit owner approval.
- Standalone PoC mode avoids Badminton Plus One authentication and repeated
  login prompts.
- Internal analysis workers remain protected with OIDC plus a dedicated
  internal API key.
- Min instances `0`, max instances `1`, request concurrency `1`.
- The queue dispatches at most one job at a time.
- This is a shared demo-user environment. Do not upload personal, confidential
  or production customer data.

## Verification evidence

- Automated tests: `258 passed, 2 skipped`.
- Production upload: `137` files, approximately `6.5 MiB`.
- Real end-to-end assessment `2` completed through signed upload, private
  Storage, Cloud Tasks, Cloud Run and Cloud SQL.
- Result: `693/693` detected frames, `8/8` events, score `85.039`.
- Anonymous checks: health, home, summary, assessment, report, visualization
  and upload-ticket endpoints all returned HTTP `200`.
- No repeated worker `401` remained after commit `70ade83`.

## Cost and retention

- Cloud Run can scale to zero; Cloud SQL remains the main fixed recurring cost.
- Cloud SQL: PostgreSQL 16, `db-f1-micro`, 10 GB HDD, zonal, backups disabled,
  deletion protection enabled, no authorized public network.
- Temporary `uploads/` objects expire after one day.
- Experiments, datasets, model weights, local videos, tests, docs, caches,
  virtual environments and `.env` files are excluded from Cloud Build.

## Known limitations and rollback

- No independent end-user authentication exists yet; the public demo user and
  reports are intentionally shared.
- The retained rollback revision has the older worker-secret comparison bug.
  It can restore the web/database surface, but queued analysis may return
  `401`.
- Rollback command:
  `gcloud run services update-traffic ai-motion-poc --project=ai-motion-lab-ivesmi --region=asia-east1 --to-revisions=ai-motion-poc-00001-jal=100`
- After an emergency rollback, redeploy product commit `70ade83` before
  accepting new analysis jobs.
