BEGIN;

ALTER TABLE student_platform.study_groups
    ADD COLUMN IF NOT EXISTS invite_code TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_study_groups_invite_code
    ON student_platform.study_groups (invite_code)
    WHERE invite_code IS NOT NULL;

COMMIT;
