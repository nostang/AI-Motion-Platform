# Explainable Pose V1 — Keyframe Retention Policy

## Decision

Use the existing private bucket with prefix-scoped lifecycle rules:

- Temporary source videos: `uploads/**`
- Assessment keyframes: `motion-assessments/{assessment_id}/keyframes/**`

The one-day delete rule must match only `uploads/`. Objects under
`motion-assessments/` have no age-based lifecycle rule and remain available
while their assessment exists.

`KEYFRAME_ASSET_BUCKET` explicitly configures keyframe storage. For the
current same-bucket strategy it has the same value as `VIDEO_UPLOAD_BUCKET`,
while the two object prefixes keep their retention behavior separate.

## Production audit — 2026-08-18

- Project: `your-gcp-project-id`
- Cloud Run service: `ai-motion` in `asia-east1`
- Runtime service account:
  `service-account@project-id.iam.gserviceaccount.com`
- Video bucket: `your-private-video-bucket`
- Bucket location/storage class: `ASIA-EAST1` / `STANDARD`
- Uniform bucket-level access: enabled
- Public principals: none in the bucket IAM policy
- Runtime bucket role: `roles/storage.objectUser`
- Current lifecycle before the planned change: unconditional `Delete` at age
  1 day
- Current Cloud Run config: `VIDEO_UPLOAD_BUCKET` is set;
  `KEYFRAME_ASSET_BUCKET` is not set
- Other available bucket: the Cloud Build artifact bucket is unrelated,
  multi-region `US`, and does not use uniform bucket-level access. It is not a
  safe application-asset reuse target.

## Repository policy

The reviewed lifecycle file is:

`infra/gcs/video-temp-lifecycle.json`

It contains exactly one delete rule: age 1 day and case-sensitive prefix
`uploads/`. It intentionally contains no rule matching `motion-assessments/`.

## Production change plan — do not run without approval

Run from the repository root:

```bash
gcloud storage buckets update gs://your-private-video-bucket \
  --lifecycle-file=infra/gcs/video-temp-lifecycle.json

gcloud run services update ai-motion \
  --project=your-gcp-project-id \
  --region=asia-east1 \
  --update-env-vars=KEYFRAME_ASSET_BUCKET=your-private-video-bucket
```

Verify the resulting configuration:

```bash
gcloud storage buckets describe \
  gs://your-private-video-bucket \
  --format='json(lifecycle_config,uniform_bucket_level_access,public_access_prevention)'

gcloud run services describe ai-motion \
  --project=your-gcp-project-id \
  --region=asia-east1 \
  --format='json(spec.template.spec.serviceAccountName,spec.template.spec.containers[0].env)'

gcloud storage ls --recursive \
  gs://your-private-video-bucket/motion-assessments
```

Cloud Storage lifecycle changes can take up to 24 hours to take effect, and
the previous rule can still act during that interval. Apply the lifecycle
change before relying on retention for a newly created assessment.

## Existing data

No migration required for current PoC data. Keyframes that still exist under
`motion-assessments/` when the new lifecycle configuration takes effect will
remain outside the one-day delete rule. Keyframes already deleted by the old
rule are not reconstructed by this change.

## Security and access

The bucket remains private. The frontend receives only assessment-scoped API
URLs; bucket names and raw object names are not included in public responses.
The controlled image endpoint continues to download the private object on the
server side.

## Failure isolation

Keyframe extraction and persistence remain presentation-only and fail-soft.
A durable-storage failure does not fail the Clear assessment, and the V0 Pose
fallback remains available.

## Known issue

`OBS-EP-02`: Keyframes durable retention currently lacks an
assessment-delete cleanup hook; potential orphan assets remain until a future
cleanup/lifecycle policy is implemented.
