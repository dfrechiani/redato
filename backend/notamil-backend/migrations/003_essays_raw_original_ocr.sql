-- Migration: add original_ocr_content column to essays_raw
-- Run once:
--   bq query --use_legacy_sql=false --project_id=notamil-prd \
--     < migrations/003_essays_raw_original_ocr.sql
--
-- When an essay is submitted from an OCR flow, the backend now snapshots the
-- raw OCR output (with <uncertain> tags intact) into this column so auditors
-- can diff "what the OCR returned" vs the final essays_raw.content the
-- student submitted.
--
-- NULL for essays typed manually or submitted before this migration.

ALTER TABLE `notamil-prd.redato.essays_raw`
ADD COLUMN IF NOT EXISTS original_ocr_content STRING;
