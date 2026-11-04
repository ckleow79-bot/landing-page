-- =============================================================================
-- 00_create_readonly_login.sql   (run on the AutoCount SQL Server as sysadmin)
--
-- Creates a dedicated READ-ONLY login for the dashboard extractor and grants
-- it SELECT on the reporting views only (not on raw AutoCount tables).
-- Repeat the USE/CREATE USER/GRANT block for every account-book database.
--
-- AutoCount keeps one database per company (account book). Database names
-- are whatever was chosen when the book was created (commonly AED_<Company>).
-- TODO-VERIFY: confirm the database names in SSMS (sys.databases) on site.
-- =============================================================================

use master;
go

if not exists (select 1 from sys.server_principals where name = 'bk_dash_ro')
begin
  create login bk_dash_ro with password = '<STRONG-PASSWORD-FROM-ENV>',
    check_policy = on, check_expiration = off, default_database = master;
end
go

-- Never give this login anything at server level.
deny view any database to bk_dash_ro;        -- keeps it from browsing other books
go

-- ---- repeat per account-book database --------------------------------------
use [AED_BKTS];                              -- TODO-VERIFY database name
go
if not exists (select 1 from sys.database_principals where name = 'bk_dash_ro')
  create user bk_dash_ro for login bk_dash_ro;
go
-- Only the reporting views (created by 01_create_reporting_views.sql)
grant select on dbo.vw_bk_dash_chart_of_accounts to bk_dash_ro;
grant select on dbo.vw_bk_dash_gl_monthly         to bk_dash_ro;
grant select on dbo.vw_bk_dash_ar_open_items      to bk_dash_ro;
grant select on dbo.vw_bk_dash_ap_open_items      to bk_dash_ro;
grant select on dbo.vw_bk_dash_bank_daily         to bk_dash_ro;
-- explicitly nothing else
deny select on schema::dbo to bk_dash_ro;    -- NOTE: DENY at schema level overrides the GRANTs above on some
                                             -- SQL Server versions. If the extractor gets "SELECT permission denied",
                                             -- remove this line; the user still has no other grants.
go
-- ---- end repeat --------------------------------------------------------------
