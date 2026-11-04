# Metabase (Finance Dept view)

Self-hosted Metabase that reads the finance warehouse (dedicated Supabase
project) through a **read-only Postgres role that can only see the reporting
views**. Metabase's own application database is a local Postgres container in
`docker-compose.yml`; nothing of Metabase's lives in Supabase.

Data never leaves the tenant: Metabase runs on your own host/VPS in Malaysia,
queries Supabase (ap-southeast-1) over TLS, and has tracking/update checks,
public sharing and embedding switched off in the compose file.

## 1. Start Metabase

```bash
cd dashboard/bi
cp ../.env.example ../.env          # fill METABASE_APPDB_PASSWORD, MB_SITE_URL, METABASE_RO_PASSWORD
docker compose --env-file ../.env up -d
docker compose logs -f metabase     # first boot takes ~1-2 min
```

Open `http://localhost:3000`, create the admin user (use a strong password and
enable 2FA via your SSO/proxy if available). Skip "add your data" in the wizard;
do it properly in step 3.

## 2. Create the read-only warehouse role (run once in Supabase SQL editor)

Run as `postgres` on the **warehouse** project, after migrations 001-003.
The role gets `dash_finance` (so `app.current_role()` resolves to `finance`),
`SELECT` on the `v_*` views only, and nothing on base tables or `app.*`.

```sql
-- 1. login role; password from .env METABASE_RO_PASSWORD
create role metabase_ro login password '<METABASE_RO_PASSWORD>' noinherit;
alter role metabase_ro set statement_timeout = '60s';
alter role metabase_ro set search_path = public;

-- 2. audience: finance = all entities, granular views, no 13-week cash flow.
--    Swap for dash_owner if the owner's own Metabase login should see v_cashflow_13w,
--    or dash_board for a board-only Metabase group (separate role per audience).
grant dash_finance to metabase_ro;
alter role metabase_ro inherit;          -- membership privileges must be inherited for pg_has_role(..., 'usage')

-- 3. connectivity + views only
grant connect on database postgres to metabase_ro;
grant usage on schema public to metabase_ro;
revoke all on all tables in schema public from metabase_ro;   -- belt and braces
grant select on
  public.v_pl_monthly, public.v_pl_variance, public.v_balance_sheet_summary,
  public.v_cash_position, public.v_ar_ap_aging_summary, public.v_board_kpis
  -- public.v_cashflow_13w   -- only if the role is dash_owner
to metabase_ro;
-- app schema: usage + execute on helpers were granted to dash_* roles in 002, inherited here.

-- 4. verify
set role metabase_ro;
select app.current_role();              -- finance
select count(*) from public.v_board_kpis; -- rows
select count(*) from public.gl_balances;  -- ERROR: permission denied  (expected)
reset role;
```

Why this works: the `v_*` views are `security_invoker = false` and owned by
`postgres`, so they can read the RLS-protected tables, and each view filters
itself with `app.can_view(entity_id, audiences)`, which maps a DB login to an
audience through `dash_owner / dash_finance / dash_board` membership
(`session_user`). See `supabase/migrations/002_rls_policies.sql`.

One Metabase connection = one audience. If the board gets Metabase access,
create `board_ro` with `dash_board` and a second Metabase database entry, and
restrict Metabase groups per database (Admin > Permissions).

## 3. Connect Metabase to the warehouse

Admin > Databases > Add database:

| Field | Value |
|---|---|
| Database type | PostgreSQL |
| Display name | B&K Finance Warehouse (finance) |
| Host | `WAREHOUSE_DB_HOST` (Supabase pooler host, session mode) |
| Port | 5432 |
| Database name | postgres |
| Username | `metabase_ro.<project-ref>` when using the pooler (`metabase_ro` on direct connection) |
| Password | `METABASE_RO_PASSWORD` |
| Schemas | Only these: `public` |
| Use a secure connection (SSL) | on, `require` |
| Rerun queries for simple explorations | off (nightly data) |
| Choose when syncs and scans happen | manually / daily 03:00 MYT after ingestion |

Under "Advanced", set the **Reporting timezone** (Admin > Settings >
Localization) to `Asia/Kuala_Lumpur`.

After the first sync, go to Admin > Table Metadata and hide anything that is
not a `v_*` view (there should be nothing else visible), set `*_pct` columns
to Percentage (values are already 0-100, so pick "Percent" display without
multiplying) and currency columns to MYR.

## 4. Suggested dashboards

All numbers MYR. Entity filter on every dashboard (field filter on
`entity_code`). Fiscal years differ per entity: label by `period_label` (calendar
month) and use `fiscal_year`/`period_no` only for YTD cards.

### Owner (full picture)
1. **Group cockpit** - `v_board_kpis`: revenue, net margin %, cash, runway per
   entity (table) + `v_cash_position` GROUP total card + staleness warning
   (`staleness_days > 1`).
2. **13-week cash flow** - `v_cashflow_13w` filtered `category = 'TOTAL'`:
   line `closing_cash_projected` by `week_start` per entity; stacked bar of
   categories (`category <> 'TOTAL'`) forecast vs actual; table of weeks with
   `is_empty_week = true` (forecast not keyed).
3. **Working capital** - `v_ar_ap_aging_summary` AR vs AP stacked buckets;
   `v_board_kpis.ar_days`, `ap_days` trend (pin a question per month).
4. **Ingestion health** - a native query on `ingestion_runs` needs the owner
   audience; if Metabase runs as `dash_finance`, build this instead as a
   Supabase SQL snippet or widen the role to `dash_owner`.

### Board (summary only, quarterly pack)
1. **KPI tiles** - `v_board_kpis`: group revenue (sum), group cash, weighted net
   margin, lowest current ratio, any entity with `runway_months < 6`.
2. **Cash** - `v_cash_position` per entity + GROUP.
3. **Receivables risk** - `v_ar_ap_aging_summary` AR `overdue_pct`,
   `over_60_days_pct` per entity.
Only these three views are visible to a `dash_board` connection or a `board`
JWT user, so a board Metabase group cannot stumble into detail.

### Finance (granular + variance)
1. **Monthly P&L** - `v_pl_monthly` table per entity x period; gross margin and
   EBITDA trend lines.
2. **Budget vs actual** - `v_pl_variance` filtered by `metric`; bar of
   `variance_vs_budget` with conditional formatting (negative = red);
   `variance_vs_prior_pct` sparkline.
3. **Balance sheet** - `v_balance_sheet_summary`: assets/liabilities/equity
   stacked, `current_ratio`, and an alert card on `balance_check <> 0`
   (trial balance extract incomplete).
4. **Aging detail** - `v_ar_ap_aging_summary` by entity and ledger; the
   per-debtor detail lives in `ar_aging` (base table, owner/finance JWT via a
   future custom page or a `dash_owner` connection).

Alerts worth setting (Metabase "Alerts" on a saved question, email to finance):
`balance_check <> 0`, `staleness_days > 2`, AR `over_60_days_pct > 15`,
any `runway_months < 6`.

## 5. Operations
- Back up the `metabase-db-data` volume (it holds dashboards and users).
- Upgrade by changing `METABASE_VERSION` and `docker compose up -d`; Metabase
  migrates its app DB automatically. Snapshot the volume first.
- Rotate `METABASE_RO_PASSWORD` with `alter role metabase_ro password '...'`
  and update the connection in Admin > Databases.
