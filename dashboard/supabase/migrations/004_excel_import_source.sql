-- =============================================================================
-- 004_excel_import_source.sql
-- Adds 'excel_import' to public.source_system so manual loads from AutoCount
-- report exports (dashboard/ingestion/autocount-excel/) are logged in
-- ingestion_runs under their own source. entities.source_system keeps
-- describing where the books live (autocount_cloud / autocount_onprem).
--
-- Run outside an explicit transaction block (psql -f does this per statement).
-- The importer works without this migration: it then logs the run under the
-- entity's own source_system with metadata.importer = 'excel_import'.
-- =============================================================================
alter type public.source_system add value if not exists 'excel_import';

comment on type public.source_system is
  'Where a set of books lives (autocount_cloud | autocount_onprem) or, on ingestion_runs only, that a load came from report exports (excel_import).';
