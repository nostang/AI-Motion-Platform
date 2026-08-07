-- AI Motion Platform
-- Video files are temporary and deleted after analysis.
-- Historical assessment records therefore must not require a video URL.

ALTER TABLE video_analyses
ALTER COLUMN video_url DROP NOT NULL;
