# AutoCount Cloud Accounting -> warehouse (n8n)

Self-hosted n8n workflow that pulls trial balance / GL balances and debtor &
creditor aging from **AutoCount Cloud Accounting** for the entities on the
SaaS edition, and upserts them into the finance warehouse (dedicated Supabase
project). Runs daily at 02:00 Asia/Kuala_Lumpur.

```
Schedule 02:00 MYT
  -> Load entity config  (one item per entity x month; last N months restated)
  -> Start ingestion run (ingestion_runs row, status=running)
  -> HTTP: trial balance for the month          \
  -> [latest month only] HTTP: debtor aging       |-- all with 3 retries, error output -> "Mark run failed"
  -> [latest month only] HTTP: creditor aging    /
  -> Code: map to warehouse schema (classification + validation)
  -> Postgres: upsert chart_of_accounts -> fiscal_periods -> gl_balances -> ar_aging -> ap_aging
  -> Postgres: finish run (success | partial if the TB does not net to zero)
```

## Verification status of the AutoCount Cloud API: NOT VERIFIED

Searched Nov 2026 for public documentation of an AutoCount **Cloud Accounting**
API and found none. What was found:

- AutoCount's Malaysia pricing page lists "API for Integration" as a plan
  feature (regional availability differs; the Philippines page says "To Be
  Announced"). So an API exists or is planned, but its documentation is not
  public.
- The documented AutoCount API is the **AOTG API** (AutoCount On The Go) for
  the **desktop / on-premise** product: REST via an "AOTG Client" service
  installed on the AutoCount server; auth is `POST
  /api/public/v1/TokenAuth/Authenticate` with username, password and an API
  key (from the AOTG subscription portal) returning an `AccessToken` with an
  expiry, then sent on subsequent requests; Swagger reference historically at
  `aotg.cloud:8080/swagger`; the module list includes master data, transactions
  and "AR Debtor Aging (2.1)". This is **not** the Cloud Accounting product,
  but if AutoCount's Cloud API turns out to be the same family, the token
  flow will look like this.
- Apideck lists AutoCount as not integrated (no unified-API shortcut).

Therefore every endpoint, parameter and response field in this workflow is a
**placeholder** marked `TODO-VERIFY`, wired through environment variables so
nothing is hard-coded:

| Placeholder | Where | Fill from |
|---|---|---|
| `AUTOCOUNT_CLOUD_BASE_URL` | `.env` | vendor docs / support |
| `AUTOCOUNT_CLOUD_TB_ENDPOINT`, `_AR_AGING_ENDPOINT`, `_AP_AGING_ENDPOINT` | `.env` | vendor docs |
| query params `companyId`, `dateFrom`, `dateTo`, `asOfDate` | HTTP nodes | vendor docs |
| auth header (credential "AutoCount Cloud API") | n8n credential | vendor docs: API key header, bearer token or OAuth2 |
| response field map `F` | "Map to warehouse schema" Code node | one sample response per endpoint |
| `ACCTYPE_MAP` labels | same Code node | `select distinct accountType` from a COA pull |

**Ask AutoCount (or your reseller) for:** API documentation for Cloud
Accounting, which subscription tier unlocks it, the auth model, rate limits,
and report endpoints for (1) trial balance by date range or period, (2) chart
of accounts with account types, (3) debtor aging and creditor aging as at a
date, (4) bank/GL balances. Confirm whether the TB closing balance for P&L
accounts is fiscal-year-to-date (what the views assume) and whether debit and
credit come as two columns.

**Plan B if no API is available on your tier:** AutoCount Cloud can export
reports to Excel/CSV. Schedule those to a mailbox or shared drive and swap the
three HTTP nodes for an IMAP/Drive trigger + Spreadsheet File node feeding the
same "Map to warehouse schema" node. The rest of the workflow is unchanged.

## Setup

1. **n8n** (self-hosted, e.g. `docker.n8n.io/n8nio/n8n`), with
   `GENERIC_TIMEZONE=Asia/Kuala_Lumpur`, `N8N_ENCRYPTION_KEY` set and backed up,
   and `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` (the Code node reads
   `$env.AUTOCOUNT_CLOUD_*`). Pass the `AUTOCOUNT_CLOUD_*` variables from
   `dashboard/.env` into the n8n container. Keep n8n on the private network /
   behind SSO; it holds the service-role database credential.
2. **Credentials** (n8n > Credentials):
   - *Postgres*: "Supabase Finance Warehouse (service role)": host/port/db/user/
     password from `WAREHOUSE_DB_*`, SSL = require. This login bypasses RLS
     (project `postgres` user or a role with write grants); it must never be
     reused by Metabase or a browser.
   - *HTTP Header Auth*: "AutoCount Cloud API (header auth)": header name and
     value per vendor docs (e.g. `X-API-Key` / `Authorization: Bearer ...`). If
     the vendor uses OAuth2 client credentials, create an OAuth2 credential
     instead and change `genericAuthType` on the three HTTP nodes.
3. **Import** `n8n-workflow.json` (Workflows > Import from file). Open each
   Postgres node and pick the warehouse credential; open each HTTP node and pick
   the AutoCount credential. Workflow Settings > Timezone should show
   Asia/Kuala_Lumpur.
4. **Warehouse**: migrations 001-003 applied; `entities` rows exist with
   `source_system = 'autocount_cloud'` and `code` matching
   `AUTOCOUNT_CLOUD_ENTITIES[].entity_code`. If an entity code is unknown the
   run row is written with `entity_id = null` and the upserts load 0 rows: check
   `ingestion_runs.rows_upserted`.
5. **Fill the placeholders**: run "Fetch trial balance" once manually with
   `AUTOCOUNT_CLOUD_LOOKBACK_MONTHS=0`, look at the output, set `F` in the Code
   node, then run the whole workflow manually and check:
   ```sql
   select * from ingestion_runs order by started_at desc limit 5;
   select * from v_balance_sheet_summary where balance_check <> 0;  -- should be empty
   select entity_code, period_label, revenue, net_profit from v_pl_monthly order by 1,2;
   ```
6. **Activate** the workflow. Add an n8n *Error Workflow* (Settings) that posts
   to email/Slack; "Mark run failed" already records the error on the run row.

## Design notes
- One item per entity x month; the current month and the previous
  `AUTOCOUNT_CLOUD_LOOKBACK_MONTHS` months are re-pulled nightly so late
  postings are restated. Aging is pulled once per entity (latest-month item).
- Upserts are set-based (`jsonb_to_recordset ... on conflict`) keyed on natural
  keys; n8n never handles UUIDs. Each Postgres node returns `upserted` counts
  that roll into `ingestion_runs.rows_upserted`.
- Postgres "Query Parameters" use an expression that resolves to an array
  (`={{ [ JSON.stringify(rows), runId ] }}`) so JSON payloads with commas are
  passed as single parameters (n8n 1.x Postgres node v2.x).
- `chart_of_accounts` classification (`account_type`, `account_subtype`,
  `cashflow_bucket`, `is_current`) is set on first insert only; finance can
  correct it in the warehouse and nightly loads will not overwrite it.
- Trial balance movements that do not net to zero mark the run `partial` with
  a message, so a truncated/paginated response is visible. If the API
  paginates, enable "Pagination" in the HTTP node options (n8n >= 1.20) before
  the Code node sees the data.
- PDPA: only account balances and counterparty business names are pulled; no
  customer contact data. Data path is AutoCount Cloud -> your n8n host ->
  Supabase over TLS, no third-party AI or SaaS in between.
