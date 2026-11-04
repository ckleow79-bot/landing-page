# B & K Group - Live Finance Dashboard (data layer)

Group-level finance warehouse and dashboards for B & K Advisory PLT,
B & K Academy PLT, B & K Training Services PLT and High Impact Training
Services PLT. Books live in **AutoCount Cloud Accounting** (SaaS) for some
entities and **AutoCount Accounting on-premise** (desktop, SQL Server) for
others. Everything here keeps ledger data in-tenant (your Supabase project in
ap-southeast-1, your n8n, your Metabase, your office network); no third-party
AI or analytics service ever touches the ledgers.

This folder is self-contained and independent of the website in the rest of
the repo (different Supabase project, different keys).

```
dashboard/
├── README.md                      <- you are here
├── .env.example                   <- every variable used by n8n, extract.py and Metabase
├── supabase/
│   ├── migrations/
│   │   ├── 001_finance_schema.sql <- tables, enums, indexes
│   │   ├── 002_rls_policies.sql   <- RLS, app.current_role(), grants, dash_* roles
│   │   └── 003_views.sql          <- v_pl_monthly ... v_board_kpis (audience-filtered)
│   └── seed/seed_demo.sql         <- fictitious MYR demo data (3 months, 4 entities)
├── ingestion/
│   ├── autocount-cloud/           <- n8n workflow (daily 02:00 MYT) + README
│   └── autocount-onprem/          <- extract.py (pyodbc -> psycopg), SQL Server views, README
└── bi/                            <- Metabase docker-compose + read-only role + dashboard list
```

## Architecture

```
 +----------------------------+        +------------------------------------+
 | AutoCount Cloud Accounting |        | AutoCount Accounting (on-prem)      |
 | (SaaS)  BKA, BKAC          |        | SQL Server, 1 DB per book BKTS,HITS |
 +-------------+--------------+        +----------------+-------------------+
               | HTTPS API (TODO-VERIFY)                | ODBC, read-only login,
               v                                        | reporting views only
 +-------------+--------------+        +----------------v-------------------+
 | n8n (self-hosted)          |        | extract.py (cron 02:15 MYT)        |
 | daily 02:00 MYT            |        | CSV staging -> upsert              |
 | service-role DB credential |        | service-role DB URL                |
 +-------------+--------------+        +----------------+-------------------+
               |   INSERT ... ON CONFLICT (natural keys) |
               +-----------------+-----------------------+
                                 v
            +--------------------+-----------------------------+
            | Supabase (dedicated finance project, Postgres)    |
            |  tables: entities, fiscal_periods, chart_of_      |
            |  accounts, gl_balances, ar_aging, ap_aging,       |
            |  bank_balances, budgets, cashflow_forecast,       |
            |  ingestion_runs, user_roles        [RLS on all]   |
            |  views : v_pl_monthly, v_pl_variance, v_balance_  |
            |  sheet_summary, v_cash_position, v_ar_ap_aging_   |
            |  summary, v_cashflow_13w, v_board_kpis            |
            |  helper: app.current_role(), app.can_view()       |
            +-----+------------------------+--------------------+
                  | metabase_ro (dash_finance)   | Supabase Auth JWT (owner/board/finance)
                  v                              v
     +------------+-------------+   +------------+--------------------+
     | Metabase (self-hosted)   |   | Custom board page (later)       |
     | Finance Dept view        |   | anon key + RLS, summary views   |
     +--------------------------+   +---------------------------------+
```

Transforms are plain SQL views (no dbt yet). Facts are stored at trial-balance
grain (entity x month x account) plus snapshots (aging, bank balances); views
derive P&L, balance sheet, KPIs and the 13-week cash flow on read. Fiscal
years differ per entity (`entities.fiscal_year_end_month`) and are derived at
load time; nothing assumes a December year end. All amounts are
`numeric(18,2)`; MYR unless a `currency` column says otherwise; timestamps are
`timestamptz`, business dates are `date` in Asia/Kuala_Lumpur.

## Role model

One data model, three audiences, enforced in the database (not in the BI tool):

| Audience | Who | Sees | How it is granted |
|---|---|---|---|
| `owner` | you | everything: all tables, all views, all entities, 13-week cash flow | `user_roles(role='owner', entity_id=null)` or DB role in `dash_owner` |
| `finance` | accounts team | granular tables and `v_pl_monthly`, `v_pl_variance`, `v_balance_sheet_summary`, `v_cash_position`, `v_ar_ap_aging_summary`, `v_board_kpis`; scoped to `entity_id` (null = all entities); **not** `cashflow_forecast` | `user_roles(role='finance', entity_id=<entity or null>)` or DB role in `dash_finance` |
| `board` | directors / partners | only `v_board_kpis`, `v_cash_position`, `v_ar_ap_aging_summary`; zero rows from any base table | `user_roles(role='board')` or DB role in `dash_board` |

Mechanics (details in `002_rls_policies.sql`):
1. RLS is enabled on every table. SELECT policies exist only for owner and
   finance; nobody has INSERT/UPDATE/DELETE policies. Writes happen only via
   the service role / table owner (n8n, extract.py), which bypass RLS.
2. Views are `security_invoker = false` and owned by `postgres`, so they can
   read the RLS-protected tables; each view filters itself with
   `app.can_view(entity_id, '{audiences}')`.
3. `app.current_role()` resolves the audience from `user_roles` for a Supabase
   JWT (`auth.uid()`), or from membership of the `dash_owner / dash_finance /
   dash_board` Postgres roles for direct DB logins (Metabase). Helpers are
   `SECURITY DEFINER` with an empty `search_path`.
4. Supabase SQL editor sessions (`postgres`) are in no dash role and have no
   JWT, so the views return nothing there; query the base tables instead, or
   `grant dash_owner to postgres` if you want the views to work in the editor.

## Setup, in order

1. **Create the warehouse project** in Supabase (region Singapore
   `ap-southeast-1`; separate from the website project). Note the project ref,
   database password, service-role key.
2. **Apply migrations** as `postgres`:
   ```bash
   cp dashboard/.env.example dashboard/.env   # fill WAREHOUSE_* first
   psql "$WAREHOUSE_DATABASE_URL" -v ON_ERROR_STOP=1 \
     -f dashboard/supabase/migrations/001_finance_schema.sql \
     -f dashboard/supabase/migrations/002_rls_policies.sql \
     -f dashboard/supabase/migrations/003_views.sql
   ```
   (or paste each file into the SQL editor in that order, or drop them into a
   Supabase CLI `supabase/migrations` folder). Keep `app` out of PostgREST's
   exposed schemas (default).
3. **Load the demo data** so Metabase has something to show:
   `psql "$WAREHOUSE_DATABASE_URL" -f dashboard/supabase/seed/seed_demo.sql`.
   Delete it before real loads (instructions at the top of the file). Then
   insert the real `entities` rows (codes, `source_system`,
   `fiscal_year_end_month`, `source_company_ref`).
4. **Users**: invite people through Supabase Auth, then grant roles:
   ```sql
   insert into public.user_roles (user_id, role, entity_id)
   select id, 'owner', null from auth.users where email = 'you@bk.my';
   ```
   (finance with `entity_id = <uuid>` for entity-scoped staff; board with
   `role = 'board'`).
5. **Metabase**: `dashboard/bi/README.md` (compose up, create `metabase_ro`
   with `dash_finance`, connect, build the suggested dashboards).
6. **AutoCount Cloud ingestion**: `dashboard/ingestion/autocount-cloud/README.md`
   (import the n8n workflow, set credentials, fill the `TODO-VERIFY`
   placeholders once AutoCount confirms the API).
7. **AutoCount on-prem ingestion**:
   `dashboard/ingestion/autocount-onprem/README.md` (create reporting views and
   the read-only SQL login on the AutoCount server, install ODBC driver, run
   `extract.py --dry-run`, schedule).
8. **Budgets and 13-week forecast** are keyed by finance directly into
   `budgets` and `cashflow_forecast` (a small Supabase table editor session or
   a CSV import with the service role) - no ingestion needed. Forecast weeks
   must start on a Monday; amounts are signed (inflow +, outflow -).
9. **Checks after the first real load**:
   `select * from v_balance_sheet_summary where balance_check <> 0;` (must be
   empty), `select * from ingestion_runs order by started_at desc;`,
   `select * from v_cash_position;` (staleness_days <= 1).

## Security notes

- **Service-role key / DB password only in n8n and extract.py.** Never in a
  browser, in Metabase, or in this repo. Rotate it if it is ever pasted into a
  chat or ticket.
- **RLS for everything**: all 11 tables have RLS enabled with select-only
  policies; `anon` has no privileges at all; `authenticated` has SELECT only
  (rows still filtered by RLS). Views are self-filtering. Do not set
  `FORCE ROW LEVEL SECURITY` (it would break the view pattern) and do not add
  insert policies for `authenticated`; keep writes on the service path.
- **Metabase** uses a Postgres login that can select the views only
  (`metabase_ro` in `dash_finance`); one Metabase connection = one audience.
  Metabase's own app DB is a local container, telemetry/public sharing/embedding
  are off.
- **PDPA 2010 / data minimisation**: the warehouse holds account balances,
  budget figures and counterparty *business* names and codes. No contact
  persons, IC/passport numbers, addresses, full bank account numbers
  (`account_no_masked` keeps the last 4 digits), payroll detail or employee
  data. Ledger data flows AutoCount -> your n8n / extractor host -> Supabase over
  TLS; nothing is sent to third-party AI services. If you later add an
  LLM-based commentary feature, run it inside the tenant (self-hosted) or pass
  only aggregated view outputs, never ledger rows.
- **Audit**: every load writes `ingestion_runs` (source, entity, dataset,
  timing, row counts, status, error text; no payloads, no secrets).
- **Network**: SQL Server is reachable only from the extractor host; n8n and
  Metabase sit behind SSO/VPN on the office network or a Malaysian VPS.
- **Backups**: Supabase PITR/daily backups for the warehouse; the Metabase app
  DB volume; the `N8N_ENCRYPTION_KEY`.

## TO VERIFY (AutoCount specifics that could not be confirmed from public sources)

AutoCount Cloud Accounting does have an official integration API: the
"Getting Started with Cloud Accounting Integration API" guide at
https://accounting-api.autocountcloud.com/documentation/ . Search snippets
indicate keys are created in the web app under Settings > API Keys (Key ID +
API Key sent as request headers) and that permissions are set per API method.
The host was not reachable from this build environment, so endpoint paths and
response shapes are still unconfirmed. Separately, the AOTG REST API
(https://aotgapi.autocountcloud.com/swagger) serves the desktop product and
needs a client service on the AutoCount machine.
Before switching the ingestion from demo to live, confirm:

1. **AutoCount Cloud Accounting API**: whether your subscription tier includes
   "API for Integration" in Malaysia, the base URL, the auth model (API key
   header vs. token exchange like the AOTG API's
   `POST /api/public/v1/TokenAuth/Authenticate` vs. OAuth2), rate limits, and
   the endpoints + response fields for trial balance / GL balances by period,
   chart of accounts (with account types), debtor aging, creditor aging and
   bank balances. Every path and field in the n8n workflow is a labelled
   placeholder.
2. **Whether the AOTG API** (documented, desktop product, requires the AOTG
   Client on the AutoCount server, includes "AR Debtor Aging" in 2.1) is an
   option for the on-prem entities as an alternative to SQL extraction.
3. **On-prem schema**: confirmed from the wiki only `GLDtl` (`AccNo`),
   `Debtor` (`IsGroupCompany`), `ARInvoice` (`DebtorCode`), `APInvoice`,
   `OBDtl`. Not confirmed: account master table (assumed `GLMast`), GL header
   table, `Creditor`, column names (`Description`, `AccType`, `DocDate`,
   `DR`/`CR`, `Outstanding`, `DueDate`, `CompanyName`, `Cancelled`), how
   opening balances are stored, and the SQL instance name (often `A2006`).
4. **Account type labels** used by both mapping tables (`Bank`, `Debtor
   Control`, `Sales`, `Cost of Goods Sold`, `Expenses`, `Other Income`,
   `Taxation`, ...), and that the TB closing balance for P&L accounts is
   fiscal-year-to-date in the API output.
5. **Aging logic**: AutoCount computes aging in the application (by invoice or
   by due date, with knock-off details). Our on-prem path buckets open items by
   due date; reconcile one month-end against AutoCount's Debtor Aging report
   and adjust `vw_bk_dash_ar_open_items` (credit notes, unapplied payments).
6. **Metabase image tag** pinned in `.env.example` (`v0.52.8`) - check it is a
   current, supported tag on Docker Hub before deploying.

## Known gaps / next steps
- No dbt or tests yet; the only data test is `balance_check` in
  `v_balance_sheet_summary` and the TB-nets-to-zero check in both loaders.
- Multi-currency is stored but views sum MYR with any other currency as-is;
  add FX translation when a non-MYR book appears.
- Consolidation is a simple sum of entities (no intercompany eliminations);
  the `intercompany` forecast category is a placeholder for that.
- The custom board page (anon key + Supabase Auth + `v_board_kpis`) is not in
  this folder yet; the role model already supports it.
- Local verification of the SQL was done on Postgres 16 with a Supabase-like
  shim (`auth.users`, `auth.uid()`, `anon/authenticated/service_role`).

## Verification log

2026-11-04: migrations 001 -> 002 -> 003 and `seed/seed_demo.sql` applied cleanly on PostgreSQL 16 with a Supabase shim (`anon`/`authenticated`/`service_role` roles, `auth.uid()`). Role tests against the seeded data:

| Session | Base tables | `v_pl_monthly` / `v_pl_variance` | `v_board_kpis` / `v_cash_position` | `v_cashflow_13w` | Writes |
|---|---|---|---|---|---|
| anon | permission denied | denied | denied | denied | denied |
| board | 0 rows | 0 rows | all entities | 0 rows | denied |
| finance (scoped to one entity) | that entity only | that entity only | that entity only | 0 rows | denied |
| owner | all | all | all | all | denied (service role writes) |

AutoCount Cloud endpoints and on-premise table names remain `TODO-VERIFY` placeholders until confirmed against the live systems.
