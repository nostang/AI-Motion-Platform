BEGIN;

-- The public assessment_id is now video_analyses.analysis_id (BIGINT).
DROP INDEX IF EXISTS public.idx_video_analyses_external_id;
ALTER TABLE public.video_analyses
    DROP CONSTRAINT IF EXISTS video_analyses_external_analysis_id_key,
    DROP COLUMN IF EXISTS external_analysis_id;

COMMIT;
