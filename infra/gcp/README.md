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
