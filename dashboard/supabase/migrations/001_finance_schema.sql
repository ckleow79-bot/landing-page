-- =============================================================================
-- 001_finance_schema.sql
-- B & K group finance warehouse: core schema.
--
-- Target: dedicated Supabase project (Postgres 15+). Apply as the project
-- `postgres` role (Supabase SQL editor or `supabase db push`). Everything
-- lives in `public` so PostgREST/Metabase can see it; helpers go in `app`.
--
-- Conventions
--   * Money: numeric(18,2), MYR unless `currency` says otherwise.
--   * Time: timestamptz (UTC on disk). Business dates are `date`
--     (Asia/Kuala_Lumpur calendar dates as the accounting system reports them).
--   * GL sign convention: debit positive. `closing_balance` = cumulative
--     balance at period end (as per trial balance), `debit`/`credit` = period
--     movements. P&L views use movements, balance sheet views use closing.
--   * Fiscal years differ per entity: see entities.fiscal_year_end_month and
--     fiscal_periods; never assume December year-end.
-- =============================================================================

create extension if not exists pgcrypto;   -- gen_random_uuid()

create schema if not exists app;
comment on schema app is 'Internal helper functions (RLS helpers etc.). Not exposed via PostgREST.';

-- ---------------------------------------------------------------------------
-- Enums (created before any table that references them)
-- ---------------------------------------------------------------------------
create type public.source_system as enum ('autocount_cloud', 'autocount_onprem');
comment on type public.source_system is 'Which accounting system an entity''s books live in.';

create type public.account_type as enum
  ('asset', 'liability', 'equity', 'revenue', 'cogs', 'opex', 'other');
comment on type public.account_type is
  'Dashboard-level classification. `other` = non-operating P&L lines (interest, tax, FX, disposal gains).';

create type public.cashflow_bucket as enum
  ('cash', 'operating', 'investing', 'financing', 'non_cash');
comment on type public.cashflow_bucket is
  'Indirect-method cash flow classification of the account. `cash` = cash & bank; `non_cash` = depreciation etc.';

create type public.ingestion_status as enum ('running', 'success', 'partial', 'failed');

-- ---------------------------------------------------------------------------
-- entities: the group companies
-- ---------------------------------------------------------------------------
create table public.entities (
  id                    uuid primary key default gen_random_uuid(),
  code                  text not null unique,                 -- short code used by ingestion config, e.g. BKA
  name                  text not null,
  registration_no       text,                                 -- SSM / LLP registration no. (not PII)
  source_system         public.source_system not null,
  source_company_ref    text,                                 -- AutoCount account book / company id in the source
  fiscal_year_end_month smallint not null check (fiscal_year_end_month between 1 and 12),
  base_currency         char(3) not null default 'MYR',
  timezone              text not null default 'Asia/Kuala_Lumpur',
  is_active             boolean not null default true,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);
comment on table public.entities is 'Group legal entities (one row per set of books). Seeded manually, not by ingestion.';
comment on column public.entities.fiscal_year_end_month is 'Month number of financial year end (e.g. 12 = Dec, 6 = Jun). Differs per entity.';
comment on column public.entities.source_company_ref is 'Identifier of the account book in AutoCount (Cloud company id or on-prem database name).';

-- ---------------------------------------------------------------------------
-- ingestion_runs: audit log of every extraction/load (created early so fact
-- tables can reference it)
-- ---------------------------------------------------------------------------
create table public.ingestion_runs (
  id              uuid primary key default gen_random_uuid(),
  source          public.source_system not null,
  entity_id       uuid references public.entities(id) on delete set null,
  dataset         text not null,                  -- e.g. gl_balances | ar_aging | ap_aging | bank_balances | all
  triggered_by    text not null default 'schedule', -- schedule | manual | backfill
  started_at      timestamptz not null default now(),
  finished_at     timestamptz,
  rows_extracted  integer,
  rows_upserted   integer,
  status          public.ingestion_status not null default 'running',
  error_message   text,
  metadata        jsonb not null default '{}'::jsonb,  -- period range, host, workflow id, etc. No secrets.
  constraint ingestion_runs_finished_after_start check (finished_at is null or finished_at >= started_at)
);
comment on table public.ingestion_runs is 'One row per ingestion attempt. Written by n8n / extract.py with the service role. Never store credentials in metadata.';

create index ingestion_runs_started_idx on public.ingestion_runs (started_at desc);
create index ingestion_runs_entity_status_idx on public.ingestion_runs (entity_id, status, started_at desc);

-- ---------------------------------------------------------------------------
-- fiscal_periods: monthly accounting periods per entity
-- ---------------------------------------------------------------------------
create table public.fiscal_periods (
  id            uuid primary key default gen_random_uuid(),
  entity_id     uuid not null references public.entities(id) on delete cascade,
  fiscal_year   smallint not null,                 -- FY label, e.g. 2026 for FYE 30 Jun 2026
  period_no     smallint not null check (period_no between 1 and 13),  -- 13 allowed for a year-end adjustment period
  period_start  date not null,
  period_end    date not null,
  label         text not null,                     -- e.g. 'Sep 2026' (calendar) - what dashboards display
  is_closed     boolean not null default false,
  created_at    timestamptz not null default now(),
  constraint fiscal_periods_range check (period_end >= period_start),
  constraint fiscal_periods_entity_start_uq unique (entity_id, period_start),
  constraint fiscal_periods_entity_fy_no_uq unique (entity_id, fiscal_year, period_no)
);
comment on table public.fiscal_periods is 'Monthly periods per entity. Generated by ingestion on first sight of a period (insert ... on conflict do nothing).';
comment on column public.fiscal_periods.fiscal_year is 'Financial year the period belongs to, per the entity''s own year end.';

create index fiscal_periods_entity_end_idx on public.fiscal_periods (entity_id, period_end desc);

-- ---------------------------------------------------------------------------
-- chart_of_accounts: per-entity account master with dashboard classification
-- ---------------------------------------------------------------------------
create table public.chart_of_accounts (
  id                  uuid primary key default gen_random_uuid(),
  entity_id           uuid not null references public.entities(id) on delete cascade,
  account_code        text not null,                 -- AutoCount AccNo
  name                text not null,
  account_type        public.account_type not null,
  account_subtype     text check (account_subtype in (
                        'cash', 'trade_receivable', 'other_receivable', 'inventory', 'fixed_asset',
                        'trade_payable', 'other_payable', 'accrual', 'borrowing', 'tax_payable',
                        'share_capital', 'retained_earnings',
                        'depreciation', 'amortisation', 'interest', 'tax', 'other')),
  cashflow_bucket     public.cashflow_bucket not null default 'operating',
  is_current          boolean,                       -- balance sheet accounts only: current vs non-current
  parent_account_code text,
  source_account_type text,                          -- raw AutoCount account type, kept for reconciliation
  is_active           boolean not null default true,
  source_loaded_at    timestamptz,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  constraint chart_of_accounts_entity_code_uq unique (entity_id, account_code)
);
comment on table public.chart_of_accounts is 'Per-entity chart of accounts. account_type/subtype/cashflow_bucket are the dashboard mapping; ingestion sets them from a mapping table and finance can override.';
comment on column public.chart_of_accounts.account_subtype is 'Fine-grained tag used by views: trade_receivable/trade_payable for AR/AP days, depreciation/amortisation for EBITDA, cash for cash position.';
comment on column public.chart_of_accounts.is_current is 'Balance-sheet accounts: true = current, false = non-current, null = P&L account.';

create index chart_of_accounts_entity_type_idx on public.chart_of_accounts (entity_id, account_type);

-- ---------------------------------------------------------------------------
-- gl_balances: trial-balance grain (entity x period x account)
-- ---------------------------------------------------------------------------
create table public.gl_balances (
  id                uuid primary key default gen_random_uuid(),
  entity_id         uuid not null references public.entities(id) on delete cascade,
  period_id         uuid not null references public.fiscal_periods(id) on delete cascade,
  account_id        uuid not null references public.chart_of_accounts(id) on delete cascade,
  debit             numeric(18,2) not null default 0 check (debit >= 0),     -- period movement
  credit            numeric(18,2) not null default 0 check (credit >= 0),    -- period movement
  closing_balance   numeric(18,2) not null default 0,                        -- cumulative, debit positive
  currency          char(3) not null default 'MYR',
  source_loaded_at  timestamptz not null default now(),
  ingestion_run_id  uuid references public.ingestion_runs(id) on delete set null,
  constraint gl_balances_natural_uq unique (entity_id, period_id, account_id)
);
comment on table public.gl_balances is 'Monthly trial balance per account. debit/credit = movements in the period; closing_balance = cumulative balance at period end (debit positive, credit negative).';

create index gl_balances_entity_period_idx on public.gl_balances (entity_id, period_id);
create index gl_balances_account_idx on public.gl_balances (account_id);

-- ---------------------------------------------------------------------------
-- ar_aging / ap_aging: snapshot per counterparty per as-of date
-- ---------------------------------------------------------------------------
create table public.ar_aging (
  id                 uuid primary key default gen_random_uuid(),
  entity_id          uuid not null references public.entities(id) on delete cascade,
  as_of_date         date not null,
  counterparty_code  text not null,                 -- AutoCount DebtorCode
  counterparty_name  text not null,                 -- business name only; no personal contact data
  currency           char(3) not null default 'MYR',
  bucket_current     numeric(18,2) not null default 0,   -- not yet due
  bucket_30          numeric(18,2) not null default 0,   -- 1-30 days overdue
  bucket_60          numeric(18,2) not null default 0,   -- 31-60
  bucket_90          numeric(18,2) not null default 0,   -- 61-90
  bucket_120_plus    numeric(18,2) not null default 0,   -- 91+ (incl. 120+)
  total_outstanding  numeric(18,2) generated always as
                       (bucket_current + bucket_30 + bucket_60 + bucket_90 + bucket_120_plus) stored,
  source_loaded_at   timestamptz not null default now(),
  ingestion_run_id   uuid references public.ingestion_runs(id) on delete set null,
  constraint ar_aging_natural_uq unique (entity_id, as_of_date, counterparty_code)
);
comment on table public.ar_aging is 'Debtor aging snapshot. One row per debtor per as_of_date; buckets are days overdue (by due date). Latest as_of_date per entity is "current".';

create index ar_aging_entity_asof_idx on public.ar_aging (entity_id, as_of_date desc);

create table public.ap_aging (
  id                 uuid primary key default gen_random_uuid(),
  entity_id          uuid not null references public.entities(id) on delete cascade,
  as_of_date         date not null,
  counterparty_code  text not null,                 -- AutoCount CreditorCode
  counterparty_name  text not null,
  currency           char(3) not null default 'MYR',
  bucket_current     numeric(18,2) not null default 0,
  bucket_30          numeric(18,2) not null default 0,
  bucket_60          numeric(18,2) not null default 0,
  bucket_90          numeric(18,2) not null default 0,
  bucket_120_plus    numeric(18,2) not null default 0,
  total_outstanding  numeric(18,2) generated always as
                       (bucket_current + bucket_30 + bucket_60 + bucket_90 + bucket_120_plus) stored,
  source_loaded_at   timestamptz not null default now(),
  ingestion_run_id   uuid references public.ingestion_runs(id) on delete set null,
  constraint ap_aging_natural_uq unique (entity_id, as_of_date, counterparty_code)
);
comment on table public.ap_aging is 'Creditor aging snapshot. Same shape as ar_aging.';

create index ap_aging_entity_asof_idx on public.ap_aging (entity_id, as_of_date desc);

-- ---------------------------------------------------------------------------
-- bank_balances: daily closing balance per bank account
-- ---------------------------------------------------------------------------
create table public.bank_balances (
  id                 uuid primary key default gen_random_uuid(),
  entity_id          uuid not null references public.entities(id) on delete cascade,
  bank_account_code  text not null,                 -- stable code, e.g. MBB-CA-1
  bank_name          text not null,                 -- e.g. Maybank
  account_no_masked  text,                          -- last 4 digits only, e.g. ****1234
  gl_account_id      uuid references public.chart_of_accounts(id) on delete set null,
  currency           char(3) not null default 'MYR',
  balance_date       date not null,
  closing_balance    numeric(18,2) not null,
  source             text not null default 'autocount',  -- autocount | bank_statement | manual
  source_loaded_at   timestamptz not null default now(),
  ingestion_run_id   uuid references public.ingestion_runs(id) on delete set null,
  constraint bank_balances_natural_uq unique (entity_id, bank_account_code, balance_date)
);
comment on table public.bank_balances is 'Daily closing balance per bank account (from the GL bank account or a bank feed). Never store full account numbers.';

create index bank_balances_entity_date_idx on public.bank_balances (entity_id, balance_date desc);

-- ---------------------------------------------------------------------------
-- budgets: approved budget per entity x period x account
-- ---------------------------------------------------------------------------
create table public.budgets (
  id          uuid primary key default gen_random_uuid(),
  entity_id   uuid not null references public.entities(id) on delete cascade,
  period_id   uuid not null references public.fiscal_periods(id) on delete cascade,
  account_id  uuid not null references public.chart_of_accounts(id) on delete cascade,
  version     text not null default 'approved',     -- approved | reforecast_q2 | ...
  amount      numeric(18,2) not null,               -- same sign convention as P&L views: revenue positive, costs positive
  notes       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint budgets_natural_uq unique (entity_id, period_id, account_id, version)
);
comment on table public.budgets is 'Budget by account and period. amount is a natural (positive) figure: revenue budget 100000 means RM100k revenue; opex budget 20000 means RM20k cost.';

create index budgets_entity_period_idx on public.budgets (entity_id, period_id);

-- ---------------------------------------------------------------------------
-- cashflow_forecast: 13-week rolling direct cash flow
-- ---------------------------------------------------------------------------
create table public.cashflow_forecast (
  id               uuid primary key default gen_random_uuid(),
  entity_id        uuid not null references public.entities(id) on delete cascade,
  week_start       date not null check (extract(isodow from week_start) = 1),  -- Mondays
  category         text not null check (category in (
                     'receipts_customers', 'receipts_other',
                     'payments_suppliers', 'payroll', 'statutory',        -- statutory = EPF/SOCSO/EIS/PCB/SST/HRDF
                     'rent_utilities', 'tax_instalments',                 -- CP204 / CP500 instalments
                     'capex', 'financing', 'intercompany', 'other')),
  forecast_amount  numeric(18,2) not null default 0,   -- signed: inflow +, outflow -
  actual_amount    numeric(18,2),                      -- null until the week has happened
  notes            text,
  updated_by       text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint cashflow_forecast_natural_uq unique (entity_id, week_start, category)
);
comment on table public.cashflow_forecast is 'Rolling 13-week direct cash flow. Signed amounts (inflow positive, outflow negative). Opening cash comes from bank_balances, not from this table.';

create index cashflow_forecast_entity_week_idx on public.cashflow_forecast (entity_id, week_start);

-- ---------------------------------------------------------------------------
-- user_roles: dashboard access model
-- ---------------------------------------------------------------------------
create table public.user_roles (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  role        text not null check (role in ('owner', 'board', 'finance')),
  entity_id   uuid references public.entities(id) on delete cascade,  -- null = all entities
  granted_by  text,
  created_at  timestamptz not null default now(),
  constraint user_roles_user_entity_uq unique nulls not distinct (user_id, entity_id)
);
comment on table public.user_roles is
  'Who may see what. owner: everything incl. 13-week cash flow. finance: granular tables + variance, scoped to entity_id (null = all). board: summary views only. One row per user per entity (entity null = group-wide).';

create index user_roles_user_idx on public.user_roles (user_id);

-- ---------------------------------------------------------------------------
-- updated_at maintenance
-- ---------------------------------------------------------------------------
create or replace function app.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger entities_set_updated_at            before update on public.entities            for each row execute function app.set_updated_at();
create trigger chart_of_accounts_set_updated_at   before update on public.chart_of_accounts   for each row execute function app.set_updated_at();
create trigger budgets_set_updated_at             before update on public.budgets             for each row execute function app.set_updated_at();
create trigger cashflow_forecast_set_updated_at   before update on public.cashflow_forecast   for each row execute function app.set_updated_at();
