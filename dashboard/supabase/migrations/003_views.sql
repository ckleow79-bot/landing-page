-- =============================================================================
-- 003_views.sql
-- Reporting views. One data model, three audiences.
--
-- Pattern (see 002 for the full explanation):
--   * app.* views   = unfiltered building blocks. Owned by the migration role,
--                     NOT granted to anyone. Not exposed via PostgREST.
--   * public.v_*    = audience-facing views, `security_invoker = false`
--                     (owner's rights -> bypass table RLS) and self-filtered
--                     with app.can_view(entity_id, '{audiences}').
--   Board users get rows only from views whose audience list includes 'board'.
--
-- Audience legend in each comment:  [owner] [finance] [board]
-- =============================================================================

-- ---------------------------------------------------------------------------
-- app.pl_monthly: P&L by entity x period from trial-balance movements.
-- Sign: revenue/other income positive when credit > debit; costs positive
-- when debit > credit. Includes trailing-3-period helpers for KPI views.
-- ---------------------------------------------------------------------------
create or replace view app.pl_monthly as
with pl as (
  select
    g.entity_id,
    g.period_id,
    sum(case when c.account_type = 'revenue' then g.credit - g.debit else 0 end)                       as revenue,
    sum(case when c.account_type = 'cogs'    then g.debit - g.credit else 0 end)                       as cogs,
    sum(case when c.account_type = 'opex'    then g.debit - g.credit else 0 end)                       as opex,
    sum(case when c.account_type = 'opex' and c.account_subtype in ('depreciation', 'amortisation')
             then g.debit - g.credit else 0 end)                                                       as depreciation_amortisation,
    sum(case when c.account_type = 'other' and c.account_subtype = 'interest'
             then g.debit - g.credit else 0 end)                                                       as interest_expense_net,
    sum(case when c.account_type = 'other' and c.account_subtype = 'tax'
             then g.debit - g.credit else 0 end)                                                       as tax_expense,
    sum(case when c.account_type = 'other' and coalesce(c.account_subtype, 'other') not in ('interest', 'tax')
             then g.credit - g.debit else 0 end)                                                       as other_income_net,
    max(g.source_loaded_at)                                                                            as data_as_of
  from public.gl_balances g
  join public.chart_of_accounts c on c.id = g.account_id
  group by g.entity_id, g.period_id
),
base as (
  select
    e.id                 as entity_id,
    e.code               as entity_code,
    e.name               as entity_name,
    p.id                 as period_id,
    p.fiscal_year,
    p.period_no,
    p.period_start,
    p.period_end,
    p.label              as period_label,
    (p.period_end - p.period_start + 1)                                   as days_in_period,
    pl.revenue,
    pl.cogs,
    pl.revenue - pl.cogs                                                   as gross_profit,
    pl.opex,
    pl.depreciation_amortisation,
    pl.other_income_net,
    pl.interest_expense_net,
    pl.tax_expense,
    -- EBITDA-ish: gross profit - opex (adding back D&A) + other operating income, before interest and tax
    pl.revenue - pl.cogs - pl.opex + pl.depreciation_amortisation + pl.other_income_net  as ebitda,
    pl.revenue - pl.cogs - pl.opex + pl.other_income_net
      - pl.interest_expense_net - pl.tax_expense                           as net_profit,
    pl.data_as_of
  from pl
  join public.entities e        on e.id = pl.entity_id
  join public.fiscal_periods p  on p.id = pl.period_id
)
select
  b.*,
  case when b.revenue <> 0 then round(b.gross_profit / b.revenue * 100, 1) end as gross_margin_pct,
  case when b.revenue <> 0 then round(b.net_profit   / b.revenue * 100, 1) end as net_margin_pct,
  -- trailing 3 periods (or fewer at the start of history), used for AR/AP days and runway
  sum(b.revenue)                 over w3 as revenue_t3p,
  sum(b.cogs + b.opex - b.depreciation_amortisation) over w3 as cash_costs_t3p,
  sum(b.ebitda)                  over w3 as ebitda_t3p,
  sum(b.days_in_period)          over w3 as days_t3p,
  count(*)                       over w3 as periods_t3p
from base b
window w3 as (partition by b.entity_id order by b.period_start rows between 2 preceding and current row);

comment on view app.pl_monthly is 'Internal, unfiltered. Monthly P&L per entity from gl_balances movements. Do not grant.';

-- ---------------------------------------------------------------------------
-- app.bs_summary: balance sheet from closing balances (debit positive).
-- closing_balance of P&L accounts is fiscal-YTD, so equity_total adds YTD profit.
-- ---------------------------------------------------------------------------
create or replace view app.bs_summary as
with bs as (
  select
    g.entity_id,
    g.period_id,
    sum(case when c.account_type = 'asset' then g.closing_balance else 0 end)                                  as total_assets,
    sum(case when c.account_type = 'asset' and c.is_current then g.closing_balance else 0 end)                 as current_assets,
    sum(case when c.account_type = 'asset' and c.account_subtype = 'cash' then g.closing_balance else 0 end)   as cash_and_bank,
    sum(case when c.account_type = 'asset' and c.account_subtype = 'trade_receivable' then g.closing_balance else 0 end) as trade_receivables,
    sum(case when c.account_type = 'liability' then -g.closing_balance else 0 end)                             as total_liabilities,
    sum(case when c.account_type = 'liability' and c.is_current then -g.closing_balance else 0 end)            as current_liabilities,
    sum(case when c.account_type = 'liability' and c.account_subtype = 'trade_payable' then -g.closing_balance else 0 end) as trade_payables,
    sum(case when c.account_type = 'liability' and c.account_subtype = 'borrowing' then -g.closing_balance else 0 end)     as borrowings,
    sum(case when c.account_type = 'equity' then -g.closing_balance else 0 end)                                as equity_opening,
    sum(case when c.account_type in ('revenue', 'cogs', 'opex', 'other') then -g.closing_balance else 0 end)   as ytd_profit,
    max(g.source_loaded_at)                                                                                    as data_as_of
  from public.gl_balances g
  join public.chart_of_accounts c on c.id = g.account_id
  group by g.entity_id, g.period_id
)
select
  e.id            as entity_id,
  e.code          as entity_code,
  e.name          as entity_name,
  p.id            as period_id,
  p.fiscal_year,
  p.period_no,
  p.period_start,
  p.period_end,
  p.label         as period_label,
  bs.total_assets,
  bs.current_assets,
  bs.total_assets - bs.current_assets                       as non_current_assets,
  bs.cash_and_bank,
  bs.trade_receivables,
  bs.total_liabilities,
  bs.current_liabilities,
  bs.total_liabilities - bs.current_liabilities             as non_current_liabilities,
  bs.trade_payables,
  bs.borrowings,
  bs.equity_opening,
  bs.ytd_profit,
  bs.equity_opening + bs.ytd_profit                         as equity_total,
  bs.total_assets - bs.total_liabilities                    as net_assets,
  bs.current_assets - bs.current_liabilities                as working_capital,
  case when bs.current_liabilities <> 0 then round(bs.current_assets / bs.current_liabilities, 2) end as current_ratio,
  -- should be 0.00; anything else means the TB extract is incomplete
  bs.total_assets - bs.total_liabilities - (bs.equity_opening + bs.ytd_profit) as balance_check,
  bs.data_as_of
from bs
join public.entities e       on e.id = bs.entity_id
join public.fiscal_periods p on p.id = bs.period_id;

comment on view app.bs_summary is 'Internal, unfiltered. Balance sheet summary per entity x period from closing balances. Do not grant.';

-- ---------------------------------------------------------------------------
-- app.cash_position: latest balance per bank account, rolled up per entity.
-- ---------------------------------------------------------------------------
create or replace view app.cash_position as
with latest as (
  select distinct on (b.entity_id, b.bank_account_code)
    b.entity_id, b.bank_account_code, b.bank_name, b.currency, b.balance_date, b.closing_balance
  from public.bank_balances b
  order by b.entity_id, b.bank_account_code, b.balance_date desc
)
select
  e.id                       as entity_id,
  e.code                     as entity_code,
  e.name                     as entity_name,
  count(l.bank_account_code) as bank_accounts,
  coalesce(sum(l.closing_balance), 0) as cash_balance,
  max(l.balance_date)        as as_of_date,
  min(l.balance_date)        as oldest_account_as_of,   -- if this lags, one account's feed is stale
  (current_date - min(l.balance_date)) as staleness_days
from public.entities e
left join latest l on l.entity_id = e.id
where e.is_active
group by e.id, e.code, e.name;

comment on view app.cash_position is 'Internal, unfiltered. Latest cash per entity from bank_balances. Do not grant.';

-- ===========================================================================
-- Public, audience-facing views
-- ===========================================================================

-- [owner] [finance]  Monthly P&L per entity.
create or replace view public.v_pl_monthly
with (security_invoker = false) as
select
  entity_id, entity_code, entity_name,
  period_id, fiscal_year, period_no, period_start, period_end, period_label,
  revenue, cogs, gross_profit, gross_margin_pct,
  opex, depreciation_amortisation, ebitda,
  other_income_net, interest_expense_net, tax_expense,
  net_profit, net_margin_pct,
  data_as_of
from app.pl_monthly
where app.can_view(entity_id, array['owner', 'finance']);

comment on view public.v_pl_monthly is '[owner][finance] Monthly P&L per entity: revenue, COGS, gross profit, opex, EBITDA (GP - opex + D&A + other income), net profit. MYR.';

-- [owner] [finance]  Variance: actual vs budget vs prior period, long format
-- (one row per entity x period x metric) so Metabase can filter by metric.
create or replace view public.v_pl_variance
with (security_invoker = false) as
with bud as (
  select
    b.entity_id,
    b.period_id,
    sum(case when c.account_type = 'revenue' then b.amount else 0 end)                      as revenue,
    sum(case when c.account_type = 'cogs'    then b.amount else 0 end)                      as cogs,
    sum(case when c.account_type = 'opex'    then b.amount else 0 end)                      as opex,
    sum(case when c.account_type = 'revenue' then b.amount
             when c.account_type in ('cogs', 'opex') then -b.amount
             when c.account_type = 'other' then b.amount else 0 end)                        as net_profit
  from public.budgets b
  join public.chart_of_accounts c on c.id = b.account_id
  where b.version = 'approved'
  group by b.entity_id, b.period_id
),
act as (
  select
    p.*,
    lag(p.revenue)      over w as prior_revenue,
    lag(p.gross_profit) over w as prior_gross_profit,
    lag(p.opex)         over w as prior_opex,
    lag(p.net_profit)   over w as prior_net_profit
  from app.pl_monthly p
  window w as (partition by p.entity_id order by p.period_start)
),
long as (
  select
    a.entity_id, a.entity_code, a.entity_name,
    a.period_id, a.fiscal_year, a.period_no, a.period_start, a.period_end, a.period_label,
    m.metric, m.actual, m.budget, m.prior_period,
    m.cost_like
  from act a
  left join bud b on b.entity_id = a.entity_id and b.period_id = a.period_id
  cross join lateral (
    values
      ('revenue',      a.revenue,      b.revenue,                    a.prior_revenue,      false),
      ('gross_profit', a.gross_profit, b.revenue - b.cogs,           a.prior_gross_profit, false),
      ('opex',         a.opex,         b.opex,                       a.prior_opex,         true),
      ('net_profit',   a.net_profit,   b.net_profit,                 a.prior_net_profit,   false)
  ) as m(metric, actual, budget, prior_period, cost_like)
)
select
  entity_id, entity_code, entity_name,
  period_id, fiscal_year, period_no, period_start, period_end, period_label,
  metric, actual, budget, prior_period,
  -- favourable = positive. For cost lines, under-spend is favourable.
  case when cost_like then budget - actual        else actual - budget       end as variance_vs_budget,
  case when budget is null or budget = 0 then null
       else round((case when cost_like then budget - actual else actual - budget end) / abs(budget) * 100, 1)
  end                                                                            as variance_vs_budget_pct,
  case when cost_like then prior_period - actual  else actual - prior_period end as variance_vs_prior,
  case when prior_period is null or prior_period = 0 then null
       else round((case when cost_like then prior_period - actual else actual - prior_period end) / abs(prior_period) * 100, 1)
  end                                                                            as variance_vs_prior_pct
from long
where app.can_view(entity_id, array['owner', 'finance']);

comment on view public.v_pl_variance is '[owner][finance] Actual vs approved budget vs prior period, one row per entity/period/metric (revenue, gross_profit, opex, net_profit). Positive variance = favourable.';

-- [owner] [finance]  Balance sheet summary.
create or replace view public.v_balance_sheet_summary
with (security_invoker = false) as
select *
from app.bs_summary
where app.can_view(entity_id, array['owner', 'finance']);

comment on view public.v_balance_sheet_summary is '[owner][finance] Balance sheet summary per entity x period incl. current ratio, working capital and a balance_check that must be 0.';

-- [owner] [board] [finance]  Cash position: latest bank balances per entity
-- plus a GROUP row = total of the entities visible to the caller.
create or replace view public.v_cash_position
with (security_invoker = false) as
with visible as (
  select * from app.cash_position
  where app.can_view(entity_id, array['owner', 'board', 'finance'])
)
select entity_id, entity_code, entity_name, bank_accounts, cash_balance, as_of_date, staleness_days, false as is_group_total
from visible
union all
select null::uuid, 'GROUP', 'Group total (visible entities)', sum(bank_accounts)::bigint, sum(cash_balance),
       max(as_of_date), max(staleness_days), true
from visible
having count(*) > 0;

comment on view public.v_cash_position is '[owner][board][finance] Latest cash per entity from bank_balances plus a GROUP total row (is_group_total = true). staleness_days > 1 means a feed is behind.';

-- [owner] [board] [finance]  AR/AP aging summary at the latest snapshot per entity.
create or replace view public.v_ar_ap_aging_summary
with (security_invoker = false) as
with ar_latest as (
  select entity_id, max(as_of_date) as as_of_date from public.ar_aging group by entity_id
),
ap_latest as (
  select entity_id, max(as_of_date) as as_of_date from public.ap_aging group by entity_id
),
u as (
  select 'AR'::text as ledger, a.entity_id, a.as_of_date,
         count(*) as counterparties,
         sum(a.bucket_current) as bucket_current, sum(a.bucket_30) as bucket_30, sum(a.bucket_60) as bucket_60,
         sum(a.bucket_90) as bucket_90, sum(a.bucket_120_plus) as bucket_120_plus, sum(a.total_outstanding) as total_outstanding
  from public.ar_aging a
  join ar_latest l on l.entity_id = a.entity_id and l.as_of_date = a.as_of_date
  group by a.entity_id, a.as_of_date
  union all
  select 'AP', a.entity_id, a.as_of_date,
         count(*),
         sum(a.bucket_current), sum(a.bucket_30), sum(a.bucket_60), sum(a.bucket_90), sum(a.bucket_120_plus), sum(a.total_outstanding)
  from public.ap_aging a
  join ap_latest l on l.entity_id = a.entity_id and l.as_of_date = a.as_of_date
  group by a.entity_id, a.as_of_date
)
select
  u.ledger,
  e.id as entity_id, e.code as entity_code, e.name as entity_name,
  u.as_of_date, u.counterparties,
  u.bucket_current, u.bucket_30, u.bucket_60, u.bucket_90, u.bucket_120_plus, u.total_outstanding,
  u.total_outstanding - u.bucket_current                                    as overdue_total,
  case when u.total_outstanding <> 0
       then round((u.total_outstanding - u.bucket_current) / u.total_outstanding * 100, 1) end as overdue_pct,
  case when u.total_outstanding <> 0
       then round((u.bucket_90 + u.bucket_120_plus) / u.total_outstanding * 100, 1) end        as over_60_days_pct
from u
join public.entities e on e.id = u.entity_id
where app.can_view(u.entity_id, array['owner', 'board', 'finance']);

comment on view public.v_ar_ap_aging_summary is '[owner][board][finance] Latest debtor (AR) and creditor (AP) aging per entity with overdue %.';

-- [owner]  13-week rolling cash flow.
-- Grain: entity x week x category, plus a 'TOTAL' row per entity x week that
-- carries the week net and the cumulative projected closing cash.
-- Projected closing cash = latest known bank cash + running sum of
-- coalesce(actual, forecast) per week. Weeks are anchored to the current
-- Monday in Asia/Kuala_Lumpur so the window rolls automatically.
-- To let finance see this too, add 'finance' to the audience array below.
create or replace view public.v_cashflow_13w
with (security_invoker = false) as
with anchor as (
  select (date_trunc('week', (now() at time zone 'Asia/Kuala_Lumpur')))::date as this_monday
),
weeks as (
  select a.this_monday + (n * 7) as week_start, n + 1 as week_no
  from anchor a, generate_series(0, 12) as n
),
opening as (
  select entity_id, cash_balance as opening_cash, as_of_date as opening_as_of
  from app.cash_position
),
ents as (
  select e.id as entity_id, e.code as entity_code, e.name as entity_name
  from public.entities e where e.is_active
),
detail as (
  select
    en.entity_id, en.entity_code, en.entity_name,
    w.week_start, w.week_no,
    f.category,
    f.forecast_amount,
    f.actual_amount,
    f.notes
  from ents en
  cross join weeks w
  join public.cashflow_forecast f on f.entity_id = en.entity_id and f.week_start = w.week_start
),
week_totals as (
  select
    en.entity_id, en.entity_code, en.entity_name,
    w.week_start, w.week_no,
    coalesce(sum(f.forecast_amount), 0)                                   as net_forecast,
    case when count(f.actual_amount) > 0 then sum(f.actual_amount) end    as net_actual,  -- null until any actual is keyed
    count(f.id)                                                           as lines
  from ents en
  cross join weeks w
  left join public.cashflow_forecast f on f.entity_id = en.entity_id and f.week_start = w.week_start
  group by en.entity_id, en.entity_code, en.entity_name, w.week_start, w.week_no
),
cum as (
  select
    t.*,
    o.opening_cash,
    o.opening_as_of,
    o.opening_cash + sum(t.net_forecast) over wk                          as closing_cash_forecast,
    o.opening_cash + sum(coalesce(t.net_actual, t.net_forecast)) over wk  as closing_cash_projected
  from week_totals t
  left join opening o on o.entity_id = t.entity_id
  window wk as (partition by t.entity_id order by t.week_start rows between unbounded preceding and current row)
)
select
  c.entity_id, c.entity_code, c.entity_name,
  c.week_start, c.week_no,
  'TOTAL'::text            as category,
  c.net_forecast           as forecast_amount,
  c.net_actual             as actual_amount,
  c.net_actual - c.net_forecast as variance,
  null::text               as notes,
  c.opening_cash, c.opening_as_of,
  c.closing_cash_forecast, c.closing_cash_projected,
  (c.lines = 0)            as is_empty_week
from cum c
where app.can_view(c.entity_id, array['owner'])
union all
select
  d.entity_id, d.entity_code, d.entity_name,
  d.week_start, d.week_no,
  d.category,
  d.forecast_amount,
  d.actual_amount,
  d.actual_amount - d.forecast_amount,
  d.notes,
  c.opening_cash, c.opening_as_of,
  c.closing_cash_forecast, c.closing_cash_projected,
  false
from detail d
join cum c on c.entity_id = d.entity_id and c.week_start = d.week_start
where app.can_view(d.entity_id, array['owner']);

comment on view public.v_cashflow_13w is '[owner] 13-week rolling cash flow from the current KL Monday: forecast vs actual per entity/week/category. Filter category = ''TOTAL'' for the weekly net and cumulative closing cash line.';

-- [owner] [board] [finance]  Board KPIs: one row per entity at its latest period.
create or replace view public.v_board_kpis
with (security_invoker = false) as
with latest_period as (
  select distinct on (entity_id) *
  from app.pl_monthly
  order by entity_id, period_end desc
)
select
  p.entity_id, p.entity_code, p.entity_name,
  p.period_id, p.fiscal_year, p.period_no, p.period_start, p.period_end, p.period_label,
  p.revenue,
  p.gross_profit,
  p.gross_margin_pct,
  p.ebitda,
  p.net_profit,
  p.net_margin_pct,
  coalesce(cp.cash_balance, bs.cash_and_bank)                 as cash,
  cp.as_of_date                                               as cash_as_of,
  bs.trade_receivables,
  bs.trade_payables,
  -- AR / AP days on trailing-3-period activity (annualisation-free, uses actual days)
  case when p.revenue_t3p > 0
       then round(bs.trade_receivables / (p.revenue_t3p / p.days_t3p), 0) end       as ar_days,
  case when p.cash_costs_t3p > 0
       then round(bs.trade_payables / (p.cash_costs_t3p / p.days_t3p), 0) end       as ap_days,
  bs.current_ratio,
  -- Runway: cash / average monthly EBITDA burn over the last 3 periods.
  -- null when EBITDA-positive (no burn); capped at 99 to keep charts sane.
  case when p.ebitda_t3p < 0
       then least(99, round(coalesce(cp.cash_balance, bs.cash_and_bank) / (-p.ebitda_t3p / p.periods_t3p), 1)) end as runway_months,
  greatest(p.data_as_of, bs.data_as_of)                       as data_as_of
from latest_period p
left join app.bs_summary   bs on bs.entity_id = p.entity_id and bs.period_id = p.period_id
left join app.cash_position cp on cp.entity_id = p.entity_id
where app.can_view(p.entity_id, array['owner', 'board', 'finance']);

comment on view public.v_board_kpis is '[owner][board][finance] One row per entity at its latest loaded period: revenue, margins, cash, AR/AP days (trailing 3 periods), current ratio, runway months (null = EBITDA positive).';

-- ---------------------------------------------------------------------------
-- Grants. Views are self-filtering, so SELECT can be granted broadly to the
-- authenticated audience and to the dash_* group roles (Metabase).
-- anon gets nothing. app.* building blocks are granted to nobody.
-- ---------------------------------------------------------------------------
grant select on
  public.v_pl_monthly, public.v_pl_variance, public.v_balance_sheet_summary,
  public.v_cash_position, public.v_ar_ap_aging_summary, public.v_cashflow_13w, public.v_board_kpis
to authenticated, service_role, dash_owner, dash_finance, dash_board;

revoke all on public.v_pl_monthly, public.v_pl_variance, public.v_balance_sheet_summary,
  public.v_cash_position, public.v_ar_ap_aging_summary, public.v_cashflow_13w, public.v_board_kpis
from anon;
