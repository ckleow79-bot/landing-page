-- =============================================================================
-- seed_demo.sql  ***  DEMO DATA - NOT REAL FIGURES  ***
--
-- Fictitious MYR numbers for the four B & K group entities so Metabase has
-- something to show on day one. Covers the last 3 complete calendar months
-- relative to the day you run it, 45 days of bank balances, two AR/AP aging
-- snapshots, an approved budget and a 13-week cash flow forecast anchored to
-- the current Monday (Asia/Kuala_Lumpur).
--
-- Run as the service role / postgres AFTER migrations 001-003:
--   psql "$WAREHOUSE_DATABASE_URL" -f dashboard/supabase/seed/seed_demo.sql
--
-- Re-runnable: it deletes and recreates the demo entities (fixed UUIDs
-- 0000...0001-0004) and everything hanging off them via ON DELETE CASCADE.
-- Delete the demo before loading real data:
--   delete from public.entities where id::text like '00000000-0000-4000-8000-00000000000%';
--
-- Simplifications (demo only): P&L closing_balance is cumulative within the
-- 3-month window, not true fiscal-YTD; the balance sheet is made to balance
-- by plugging cash.
-- =============================================================================

begin;

-- ---------------------------------------------------------------------------
-- Entities (real names, fictitious numbers). Different year ends on purpose.
-- ---------------------------------------------------------------------------
delete from public.ingestion_runs where metadata->>'demo' = 'true';
delete from public.entities where id in (
  '00000000-0000-4000-8000-000000000001',
  '00000000-0000-4000-8000-000000000002',
  '00000000-0000-4000-8000-000000000003',
  '00000000-0000-4000-8000-000000000004');

insert into public.entities (id, code, name, registration_no, source_system, source_company_ref, fiscal_year_end_month) values
  ('00000000-0000-4000-8000-000000000001', 'BKA',  'B & K Advisory PLT',                 'DEMO-LLP0000001-LGN', 'autocount_cloud',  'DEMO-CLOUD-BKA', 12),
  ('00000000-0000-4000-8000-000000000002', 'BKAC', 'B & K Academy PLT',                  'DEMO-LLP0000002-LGN', 'autocount_cloud',  'DEMO-CLOUD-BKAC', 6),
  ('00000000-0000-4000-8000-000000000003', 'BKTS', 'B & K Training Services PLT',        'DEMO-LLP0000003-LGN', 'autocount_onprem', 'AED_BKTS_DEMO',   3),
  ('00000000-0000-4000-8000-000000000004', 'HITS', 'High Impact Training Services PLT',  'DEMO-LLP0000004-LGN', 'autocount_onprem', 'AED_HITS_DEMO',  12);

-- One audit row so ingestion_runs is not empty (and so fact rows can point at it).
insert into public.ingestion_runs (id, source, entity_id, dataset, triggered_by, started_at, finished_at, rows_extracted, rows_upserted, status, metadata)
values ('00000000-0000-4000-8000-0000000000aa', 'autocount_cloud', null, 'all', 'manual', now() - interval '5 minutes', now(), 0, 0, 'success',
        '{"demo": true, "note": "seed_demo.sql"}'::jsonb);

-- ---------------------------------------------------------------------------
-- Everything else is generated so the balance sheet balances each month.
-- ---------------------------------------------------------------------------
do $$
declare
  v_run      uuid := '00000000-0000-4000-8000-0000000000aa';
  v_m0       date := date_trunc('month', current_date)::date;    -- first day of current month
  v_monday   date := date_trunc('week', (now() at time zone 'Asia/Kuala_Lumpur'))::date;
  e          record;
  m          int;
  pstart     date;
  pend       date;
  fy         int;
  pno        int;
  pid        uuid;
  -- monthly model
  rev        numeric;  cogs numeric;  sal numeric;  rent numeric;  dep numeric;  mkt numeric;  oth numeric;
  intr       numeric;  tax  numeric;  profit numeric;
  cum_profit numeric;
  ar_c       numeric;  ap_c numeric;  accr_c numeric;  taxp_c numeric;  fa_c numeric;  cash_c numeric;
  prev       jsonb;    -- previous closing balances by account code
  cur        jsonb;
  k          text;
  mv         numeric;
  acct       record;
  w          int;
  wk         date;
  cat        text;
  famt       numeric;
begin
  for e in
    select *
    from (values
      -- id, code, rev_base, growth, cogs_pct, salaries, rent, dep, marketing, other, interest, borrowings, share_cap, ret_earn, fixed_assets, ar_days, ap_days
      ('00000000-0000-4000-8000-000000000001'::uuid, 'BKA',  180000, 0.03, 0.30, 62000, 9500, 3200, 4500, 6800,  0,     0,      100000, 410000, 118000, 48, 30),
      ('00000000-0000-4000-8000-000000000002'::uuid, 'BKAC',  95000, 0.05, 0.42, 28000, 7800, 2100, 9500, 4200,  0,     0,       50000,  86000,  64000, 35, 38),
      ('00000000-0000-4000-8000-000000000003'::uuid, 'BKTS', 120000, 0.02, 0.38, 41000, 8200, 2600, 6000, 5100,  0,     0,       80000, 152000,  91000, 55, 32),
      ('00000000-0000-4000-8000-000000000004'::uuid, 'HITS',  60000, -0.04, 0.45, 32000, 6500, 1800, 3000, 3900, 1450, 250000,  30000,  12000,  55000, 62, 45)
    ) as t(id, code, rev_base, growth, cogs_pct, salaries, rent, dep, marketing, other, interest, borrowings, share_cap, ret_earn, fixed_assets, ar_days, ap_days)
  loop
    -- ---------------- chart of accounts (AutoCount-style codes) ----------------
    insert into public.chart_of_accounts (entity_id, account_code, name, account_type, account_subtype, cashflow_bucket, is_current, source_account_type, source_loaded_at) values
      (e.id, '300-0000', 'Maybank Current Account',          'asset',     'cash',             'cash',      true,  'Bank',               now()),
      (e.id, '300-1000', 'CIMB Current Account',             'asset',     'cash',             'cash',      true,  'Bank',               now()),
      (e.id, '310-0000', 'Trade Debtors',                    'asset',     'trade_receivable', 'operating', true,  'Debtor Control',     now()),
      (e.id, '320-0000', 'Deposits & Prepayments',           'asset',     'other_receivable', 'operating', true,  'Current Asset',      now()),
      (e.id, '200-0000', 'Office Equipment (NBV)',           'asset',     'fixed_asset',      'investing', false, 'Fixed Asset',        now()),
      (e.id, '400-0000', 'Trade Creditors',                  'liability', 'trade_payable',    'operating', true,  'Creditor Control',   now()),
      (e.id, '410-0000', 'Accruals',                         'liability', 'accrual',          'operating', true,  'Current Liability',  now()),
      (e.id, '420-0000', 'Tax Payable (CP204)',              'liability', 'tax_payable',      'operating', true,  'Current Liability',  now()),
      (e.id, '450-0000', 'Term Loan',                        'liability', 'borrowing',        'financing', false, 'Long Term Liability',now()),
      (e.id, '100-0000', 'Partners'' Capital',               'equity',    'share_capital',    'financing', null,  'Equity',             now()),
      (e.id, '150-0000', 'Retained Earnings',                'equity',    'retained_earnings','financing', null,  'Equity',             now()),
      (e.id, '500-0000', 'Professional / Training Fees',     'revenue',   null,               'operating', null,  'Sales',              now()),
      (e.id, '600-0000', 'Direct Trainer & Delivery Costs',  'cogs',      null,               'operating', null,  'Cost of Goods Sold', now()),
      (e.id, '900-0000', 'Salaries, EPF & SOCSO',            'opex',      null,               'operating', null,  'Expenses',           now()),
      (e.id, '901-0000', 'Rent & Utilities',                 'opex',      null,               'operating', null,  'Expenses',           now()),
      (e.id, '902-0000', 'Depreciation',                     'opex',      'depreciation',     'non_cash',  null,  'Expenses',           now()),
      (e.id, '903-0000', 'Marketing',                        'opex',      null,               'operating', null,  'Expenses',           now()),
      (e.id, '904-0000', 'Other Administrative Expenses',    'opex',      null,               'operating', null,  'Expenses',           now()),
      (e.id, '950-0000', 'Interest Expense',                 'other',     'interest',         'financing', null,  'Expenses',           now()),
      (e.id, '960-0000', 'Taxation',                         'other',     'tax',              'operating', null,  'Taxation',           now());

    -- opening balances (month before the window)
    ar_c   := round(e.rev_base * e.ar_days / 30.0, 2);
    ap_c   := round((e.rev_base * e.cogs_pct + e.marketing + e.other) * e.ap_days / 30.0, 2);
    accr_c := round(e.salaries * 0.35, 2);
    taxp_c := 0;
    fa_c   := e.fixed_assets;
    cash_c := round(e.share_cap + e.ret_earn + e.borrowings + ap_c + accr_c - ar_c - 15000 - fa_c, 2);  -- 15000 = deposits
    prev := jsonb_build_object(
      '300-0000', round(cash_c * 0.7, 2), '300-1000', round(cash_c * 0.3, 2),
      '310-0000', ar_c, '320-0000', 15000, '200-0000', fa_c,
      '400-0000', -ap_c, '410-0000', -accr_c, '420-0000', 0, '450-0000', -e.borrowings,
      '100-0000', -e.share_cap, '150-0000', -e.ret_earn);
    cum_profit := 0;

    -- ---------------- three months of trial balance ----------------
    for m in reverse 3..1 loop
      pstart := (v_m0 - (m || ' months')::interval)::date;
      pend   := (pstart + interval '1 month' - interval '1 day')::date;
      -- fiscal year / period number from the entity's own year end
      fy  := case when e.code in ('BKA', 'HITS') then extract(year from pstart)::int
                  else case when extract(month from pstart) > (select fiscal_year_end_month from public.entities where id = e.id)
                            then extract(year from pstart)::int + 1 else extract(year from pstart)::int end end;
      pno := ((extract(month from pstart)::int - (select fiscal_year_end_month from public.entities where id = e.id) - 1 + 12) % 12) + 1;

      insert into public.fiscal_periods (entity_id, fiscal_year, period_no, period_start, period_end, label, is_closed)
      values (e.id, fy, pno, pstart, pend, to_char(pstart, 'Mon YYYY'), true)
      returning id into pid;

      -- P&L for the month (3 = oldest)
      rev    := round((e.rev_base * power(1 + e.growth, 3 - m) * (1 + 0.04 * sin(m)))::numeric, 2);
      cogs   := round(rev * e.cogs_pct, 2);
      sal    := e.salaries;
      rent   := e.rent;
      dep    := e.dep;
      mkt    := round((e.marketing * (1 + 0.1 * cos(m)))::numeric, 2);
      oth    := round((e.other * (1 + 0.08 * sin(m * 2)))::numeric, 2);
      intr   := e.interest;
      profit := rev - cogs - sal - rent - dep - mkt - oth - intr;
      tax    := case when profit > 0 then round(profit * 0.17, 2) else 0 end;   -- demo effective rate
      profit := profit - tax;
      cum_profit := cum_profit + profit;

      -- balance sheet closings
      ar_c   := round(rev * e.ar_days / 30.0, 2);
      ap_c   := round((cogs + mkt + oth) * e.ap_days / 30.0, 2);
      accr_c := round(sal * 0.35, 2);
      taxp_c := taxp_c + tax;
      fa_c   := fa_c - dep;
      cash_c := round(e.share_cap + e.ret_earn + cum_profit + e.borrowings + ap_c + accr_c + taxp_c - ar_c - 15000 - fa_c, 2);

      cur := jsonb_build_object(
        '300-0000', round(cash_c * 0.7, 2), '300-1000', cash_c - round(cash_c * 0.7, 2),
        '310-0000', ar_c, '320-0000', 15000, '200-0000', fa_c,
        '400-0000', -ap_c, '410-0000', -accr_c, '420-0000', -taxp_c, '450-0000', -e.borrowings,
        '100-0000', -e.share_cap, '150-0000', -e.ret_earn);

      -- balance sheet rows: movement = closing - previous closing
      for k in select jsonb_object_keys(cur) loop
        mv := (cur->>k)::numeric - (prev->>k)::numeric;
        insert into public.gl_balances (entity_id, period_id, account_id, debit, credit, closing_balance, source_loaded_at, ingestion_run_id)
        select e.id, pid, c.id, greatest(mv, 0), greatest(-mv, 0), (cur->>k)::numeric, now(), v_run
        from public.chart_of_accounts c where c.entity_id = e.id and c.account_code = k;
      end loop;

      -- P&L rows: closing = cumulative within the window (debit positive)
      for acct in
        select * from (values
          ('500-0000', 0::numeric, rev), ('600-0000', cogs, 0::numeric), ('900-0000', sal, 0), ('901-0000', rent, 0),
          ('902-0000', dep, 0), ('903-0000', mkt, 0), ('904-0000', oth, 0), ('950-0000', intr, 0), ('960-0000', tax, 0)
        ) as t(code, dr, cr)
      loop
        insert into public.gl_balances (entity_id, period_id, account_id, debit, credit, closing_balance, source_loaded_at, ingestion_run_id)
        select e.id, pid, c.id, acct.dr, acct.cr,
               coalesce((select g.closing_balance from public.gl_balances g
                          join public.fiscal_periods fp on fp.id = g.period_id
                         where g.account_id = c.id and fp.period_end < pstart
                         order by fp.period_end desc limit 1), 0) + acct.dr - acct.cr,
               now(), v_run
        from public.chart_of_accounts c where c.entity_id = e.id and c.account_code = acct.code;
      end loop;

      -- budget (approved): revenue +5% stretch, costs a touch below actual
      insert into public.budgets (entity_id, period_id, account_id, version, amount)
      select e.id, pid, c.id, 'approved',
             case c.account_code
               when '500-0000' then round((e.rev_base * 1.05 * power(1.02, 3 - m))::numeric, 2)
               when '600-0000' then round((e.rev_base * 1.05 * power(1.02, 3 - m) * e.cogs_pct)::numeric, 2)
               when '900-0000' then sal
               when '901-0000' then rent
               when '902-0000' then dep
               when '903-0000' then round(e.marketing * 0.95, 2)
               when '904-0000' then round(e.other * 0.95, 2)
               when '950-0000' then intr
               when '960-0000' then 0
             end
      from public.chart_of_accounts c
      where c.entity_id = e.id and c.account_type in ('revenue', 'cogs', 'opex', 'other');

      -- month-end AR / AP aging snapshot (5 debtors / 4 creditors, buckets by due date)
      insert into public.ar_aging (entity_id, as_of_date, counterparty_code, counterparty_name, bucket_current, bucket_30, bucket_60, bucket_90, bucket_120_plus, source_loaded_at, ingestion_run_id)
      select e.id, pend, d.code, d.name,
             round(ar_c * d.share * 0.55, 2), round(ar_c * d.share * 0.25, 2), round(ar_c * d.share * 0.10, 2),
             round(ar_c * d.share * 0.06, 2), round(ar_c * d.share * 0.04, 2), now(), v_run
      from (values ('D001', 'Demo Client Alpha Sdn Bhd', 0.34), ('D002', 'Demo Client Beta Bhd', 0.26), ('D003', 'Demo Client Gamma Sdn Bhd', 0.18),
                   ('D004', 'Demo Client Delta PLT', 0.14), ('D005', 'Demo Client Epsilon Enterprise', 0.08)) as d(code, name, share);

      insert into public.ap_aging (entity_id, as_of_date, counterparty_code, counterparty_name, bucket_current, bucket_30, bucket_60, bucket_90, bucket_120_plus, source_loaded_at, ingestion_run_id)
      select e.id, pend, s.code, s.name,
             round(ap_c * s.share * 0.62, 2), round(ap_c * s.share * 0.28, 2), round(ap_c * s.share * 0.07, 2),
             round(ap_c * s.share * 0.03, 2), 0, now(), v_run
      from (values ('C001', 'Demo Trainer Services Sdn Bhd', 0.45), ('C002', 'Demo Venue & Catering Sdn Bhd', 0.30),
                   ('C003', 'Demo IT & Software Sdn Bhd', 0.15), ('C004', 'Demo Printing Enterprise', 0.10)) as s(code, name, share);

      prev := cur;
    end loop;

    -- ---------------- bank balances: last 45 days, daily, two accounts ----------------
    insert into public.bank_balances (entity_id, bank_account_code, bank_name, account_no_masked, gl_account_id, balance_date, closing_balance, source, source_loaded_at, ingestion_run_id)
    select e.id, 'MBB-CA', 'Maybank', '****4471', (select id from public.chart_of_accounts where entity_id = e.id and account_code = '300-0000'),
           d::date, round((cash_c * 0.7 * (1 + 0.06 * sin(extract(doy from d) / 5.0)) + 2500 * ((extract(day from d)::int % 7) - 3))::numeric, 2),
           'autocount', now(), v_run
    from generate_series(current_date - 45, current_date - 1, interval '1 day') d
    union all
    select e.id, 'CIMB-CA', 'CIMB', '****9018', (select id from public.chart_of_accounts where entity_id = e.id and account_code = '300-1000'),
           d::date, round((cash_c * 0.3 * (1 + 0.04 * cos(extract(doy from d) / 4.0)))::numeric, 2),
           'autocount', now(), v_run
    from generate_series(current_date - 45, current_date - 1, interval '1 day') d;

    -- a fresher aging snapshot as of yesterday (slightly better collections)
    insert into public.ar_aging (entity_id, as_of_date, counterparty_code, counterparty_name, bucket_current, bucket_30, bucket_60, bucket_90, bucket_120_plus, source_loaded_at, ingestion_run_id)
    select entity_id, current_date - 1, counterparty_code, counterparty_name,
           round(bucket_current * 1.08, 2), round(bucket_30 * 0.9, 2), round(bucket_60 * 0.85, 2), round(bucket_90 * 0.9, 2), round(bucket_120_plus * 0.95, 2), now(), v_run
    from public.ar_aging where entity_id = e.id and as_of_date = pend;

    insert into public.ap_aging (entity_id, as_of_date, counterparty_code, counterparty_name, bucket_current, bucket_30, bucket_60, bucket_90, bucket_120_plus, source_loaded_at, ingestion_run_id)
    select entity_id, current_date - 1, counterparty_code, counterparty_name,
           round(bucket_current * 1.05, 2), round(bucket_30 * 0.8, 2), round(bucket_60 * 0.7, 2), round(bucket_90 * 0.5, 2), 0, now(), v_run
    from public.ap_aging where entity_id = e.id and as_of_date = pend;

    -- ---------------- 13-week cash flow forecast from this Monday ----------------
    for w in 0..12 loop
      wk := v_monday + (w * 7);
      for cat, famt in
        select * from (values
          ('receipts_customers',  round((rev / 4.33 * (1 + 0.15 * sin(w)))::numeric, 2)),
          ('receipts_other',      case when w % 6 = 2 then 4000 else 0 end),
          ('payments_suppliers', -round((cogs + mkt + oth) / 4.33, 2)),
          ('payroll',             case when w % 4 = 3 then -round(sal * 0.78, 2) else 0 end),      -- net pay around 25th
          ('statutory',           case when w % 4 = 1 then -round(sal * 0.22, 2) else 0 end),      -- EPF/SOCSO/EIS/PCB by 15th
          ('rent_utilities',      case when w % 4 = 0 then -rent else 0 end),
          ('tax_instalments',     case when w % 4 = 2 then -round(greatest(tax, 0), 2) else 0 end), -- CP204 monthly instalment
          ('capex',               case when w = 7 then -12000 else 0 end),
          ('financing',           case when e.borrowings > 0 and w % 4 = 0 then -5200 else 0 end),
          ('intercompany',        0),
          ('other',               -800)
        ) as t(cat, amt)
      loop
        continue when famt = 0 and cat <> 'receipts_customers';
        insert into public.cashflow_forecast (entity_id, week_start, category, forecast_amount, actual_amount, notes, updated_by)
        values (e.id, wk, cat, famt,
                case when w = 0 then round(famt * 0.97, 2) end,     -- current week partly actualised
                case when w = 0 then 'demo actual' end, 'seed_demo');
      end loop;
    end loop;
  end loop;
end
$$;

commit;

-- ---------------------------------------------------------------------------
-- Dashboard users: grant roles once the people exist in auth.users.
-- (Cannot be seeded blind; auth.users rows are created by Supabase Auth.)
--
-- insert into public.user_roles (user_id, role, entity_id, granted_by)
-- select id, 'owner', null, 'seed' from auth.users where email = 'owner@example.com';
--
-- insert into public.user_roles (user_id, role, entity_id, granted_by)
-- select u.id, 'finance', e.id, 'seed'
-- from auth.users u, public.entities e
-- where u.email = 'accounts@example.com' and e.code = 'BKA';
--
-- insert into public.user_roles (user_id, role, entity_id, granted_by)
-- select id, 'board', null, 'seed' from auth.users where email = 'director@example.com';
-- ---------------------------------------------------------------------------
