# AutoCount Accounting (on-premise) -> warehouse extractor

Nightly, read-only pull from the AutoCount Accounting desktop edition's
Microsoft SQL Server databases (one database per account book / company) into
the finance warehouse (Supabase Postgres). Runs on a small Linux or Windows
host **inside the office network** (or on the AutoCount server itself) so SQL
Server is never exposed to the internet. Only outbound TLS to Supabase leaves
the building.

```
AutoCount SQL Server  --(pyodbc, read-only login, reporting views)-->  extract.py
   extract.py  --> CSV staging (out/<entity>/<date>/)  --(psycopg, TLS)-->  Supabase warehouse
   extract.py  --> ingestion_runs row (start / success / failed + error)
```

## What is verified vs. assumed about the AutoCount schema

AutoCount does not publish a schema reference. From the public wiki
(troubleshooting articles and the programmer pages) the following were
**confirmed to exist**: tables `GLDtl` (GL detail lines, column `AccNo`),
`Debtor` (column `IsGroupCompany`), `ARInvoice` (column `DebtorCode`),
`APInvoice`, `OBDtl` (opening balances). Debtor/creditor aging is **not a
stored table**; the application computes it (the API exposes it as a
DataSet), so we compute buckets from open items ourselves.

**Not confirmed**: the account master table name (we assume `GLMast`), the
GL header table, most column names (`Description`, `AccType`, `DocDate`,
`DR`/`CR`, `Outstanding`, `DueDate`, `CompanyName`, `Cancelled`), the creditor
master (`Creditor`), and whether GLDtl stores debit/credit as two columns or
one signed amount. All of these are marked `TODO-VERIFY` in
`queries/01_create_reporting_views.sql`.

Because of that, **do not point the extractor at raw tables**. Have your
AutoCount consultant (or yourself, in SSMS) create the five reporting views in
`queries/01_create_reporting_views.sql` and reconcile each against the matching
AutoCount report for one month-end:

| View | Reconcile against |
|---|---|
| `vw_bk_dash_chart_of_accounts` | G/L > Account Maintenance |
| `vw_bk_dash_gl_monthly` | Trial Balance (per month) and Ledger closing balances |
| `vw_bk_dash_ar_open_items` | A/R Outstanding Invoice / Debtor Aging |
| `vw_bk_dash_ap_open_items` | A/P Outstanding Invoice / Creditor Aging |
| `vw_bk_dash_bank_daily` | Bank Book / bank reconciliation closing balance |

The extractor's queries (`queries/*.sql`) only ever reference those views.

## Setup

1. **SQL Server side (sysadmin, once per account book)**
   - Run `queries/01_create_reporting_views.sql` on each account-book DB
     (fix every `TODO-VERIFY` first; `select name from sys.tables` and
     `sp_help 'dbo.GLDtl'` tell you the real names).
   - Run `queries/00_create_readonly_login.sql`: login `bk_dash_ro`, SELECT on
     the five views only, nothing else, no server roles.
   - Allow TCP 1433 (or the named-instance port) from the extractor host only.
     Turn on `Encrypt=yes`; install a proper certificate when you can and set
     `AUTOCOUNT_SQL_TRUST_SERVER_CERTIFICATE=no`.
   - Optional but recommended: enable `READ_COMMITTED_SNAPSHOT` on the DB so
     reads never block AutoCount users, then change the isolation line in
     `extract.py` from `READ UNCOMMITTED` to `SNAPSHOT`.

2. **Extractor host**
   ```bash
   # Ubuntu/Debian: Microsoft ODBC Driver 18
   curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /usr/share/keyrings/microsoft.gpg
   # add the packages.microsoft.com repo for your release, then:
   sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev

   cd dashboard/ingestion/autocount-onprem
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r requirements.txt
   cp ../../.env.example ../../.env   # fill AUTOCOUNT_SQL_*, AUTOCOUNT_ONPREM_ENTITIES, WAREHOUSE_DATABASE_URL
   chmod 600 ../../.env
   ```
   On Windows, install "ODBC Driver 18 for SQL Server" and run the same with
   `py -3 -m venv`; schedule with Task Scheduler instead of cron.

3. **Warehouse side**: migrations 001-003 applied; the entity rows exist with
   `source_system = 'autocount_onprem'` and the correct
   `fiscal_year_end_month` (P&L year-to-date closing balances depend on it).
   `WAREHOUSE_DATABASE_URL` must be a service-level login (the project
   `postgres` user or a dedicated role with INSERT/UPDATE on the tables; RLS is
   bypassed by the table owner, and `service_role` has BYPASSRLS).

4. **First run**
   ```bash
   python extract.py --entity BKTS --dry-run      # connects, extracts, writes CSVs, no writes
   python extract.py --entity BKTS --months 12    # backfill a year
   python extract.py --entity all                 # nightly form
   ```
   Check `select * from ingestion_runs order by started_at desc limit 5;` and
   `select * from v_balance_sheet_summary where balance_check <> 0;` (should be
   empty; if not, the TB view is missing accounts or unposted documents).

5. **Schedule** (cron, host timezone Asia/Kuala_Lumpur), after AutoCount's
   own backups and 15 minutes after the n8n cloud pull:
   ```
   15 2 * * * cd /opt/bk-dash/dashboard/ingestion/autocount-onprem && .venv/bin/python extract.py --entity all >> /var/log/bk-extract.log 2>&1
   ```

## Behaviour and guarantees
- **Read-only**: `ApplicationIntent=ReadOnly`, `readonly=True`, lock timeout 5 s,
  dirty reads (or snapshot) so AutoCount users are never blocked. The login has
  SELECT on five views only.
- **Idempotent**: every dataset is upserted on its natural key
  (entity, period, account / entity, as-of, counterparty / entity, account,
  date). Re-running a night or backfilling just overwrites.
- **Open months restated**: `EXTRACT_LOOKBACK_MONTHS=2` reloads the current
  and previous two months each night, so late postings and adjustments flow
  through. After year-end audit adjustments, run a one-off `--months 14`.
- **Classification on insert only**: `account_type / account_subtype /
  cashflow_bucket / is_current` are set when an account is first seen (from the
  `ACCTYPE_MAP` in `extract.py`), then left alone so finance can correct them
  in the warehouse.
- **Retries**: connection and upsert steps retry 3x with backoff
  (`EXTRACT_MAX_RETRIES`). Failures are written to `ingestion_runs.error_message`
  and the process exits non-zero (cron mail / monitoring).
- **Replay**: `--replay out/BKTS/2026-11-04` reloads from staged CSVs without
  touching SQL Server. The staging folder contains ledger data: keep it on an
  encrypted disk and purge it (e.g. `find out -mtime +14 -delete`).

## PDPA 2010 notes
- Only business-level data is extracted: account balances, company names of
  debtors/creditors, outstanding amounts. No contact persons, addresses,
  IC numbers, bank account numbers or employee data.
- Data goes AutoCount -> this host -> Supabase (ap-southeast-1) over TLS. No
  third-party processors in between.
- Access to the warehouse is governed by RLS (see `supabase/migrations/002`).
