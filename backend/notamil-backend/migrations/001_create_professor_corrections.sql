-- Migration: create professor_corrections table
-- Run once against the notamil-prd.redato BigQuery dataset.
--
--   bq query --use_legacy_sql=false \
--     --project_id=notamil-prd \
--     < migrations/001_create_professor_corrections.sql
--
-- Stores professor-authored feedback on student essays. One row per essay;
-- subsequent saves UPDATE the existing row via MERGE (see handle_bq.py).

CREATE TABLE IF NOT EXISTS `notamil-prd.redato.professor_corrections` (
  id STRING NOT NULL,
  essay_id STRING NOT NULL,
  professor_id STRING NOT NULL,
  feedback_text STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY essay_id;
