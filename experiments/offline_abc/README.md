# Offline A/B/C experiments

This directory is intentionally isolated from Badminton Plus One production.
It contains repeatable, local-only experiments for:

- existing MediaPipe motion analysis;
- local Gemma 4 explanation generated from structured report JSON;
- a minimal YOLOv12 training proof.

The experiments must not deploy a Cloud Run service, write to the Badminton
Plus One Cloud SQL instance, use its Storage bucket, or dispatch to its Cloud
Tasks queue. Generated results, model checkpoints, datasets, and virtual
environments are ignored by Git.

Gemma is an optional explanation layer. It must not replace or alter the
versioned assessment score. YOLOv12 remains an offline detector experiment and
does not participate in production scoring.
