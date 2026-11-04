-- =============================================================================
-- 01_create_reporting_views.sql   (run on EACH AutoCount account-book database)
--
-- Reporting views that the extractor reads. Querying through views (a) gives
-- the read-only login a narrow surface, (b) isolates us from AutoCount schema
-- changes between versions (1.8/1.9 vs 2.0/2.1), (c) lets the AutoCount
-- consultant validate the logic once against the app's own reports.
--
-- VERIFICATION STATUS (from AutoCount's public wiki, Nov 2026 search):
--   CONFIRMED table names : dbo.GLDtl (GL detail lines, has AccNo),
--                           dbo.Debtor (has IsGroupCompany), dbo.ARInvoice
--                           (has DebtorCode), dbo.APInvoice, dbo.OBDtl
--                           (opening balance details).
--   NOT CONFIRMED         : GL header table name, account master table name
--                           (assumed dbo.GLMast), column names other than the
--                           ones above (Description, AccType, DocDate, DR/CR,
--                           Outstanding, DueDate, CompanyName), creditor
--                           master name (assumed dbo.Creditor), how AutoCount
--                           stores DR/CR on GLDtl (two columns vs signed).
--   Debtor/creditor aging is NOT a stored table in AutoCount; the app
--   computes it. We compute buckets ourselves from open items (due date).
--
-- Every TODO-VERIFY below must be checked in SSMS against the real DB:
--   select name from sys.tables order by name;
--   select c.name, t.name from sys.columns c join sys.types t on t.user_type_id=c.user_type_id
--    where c.object_id = object_id('dbo.GLDtl');
-- Then reconcile each view against the matching AutoCount report (Trial
-- Balance, Debtor Aging, Creditor Aging, Bank Book) for one month-end.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Chart of accounts
-- ---------------------------------------------------------------------------
create or alter view dbo.vw_bk_dash_chart_of_accounts
as
select
  a.AccNo                        as AccNo,            -- TODO-VERIFY table dbo.GLMast and column names
  a.Description                  as Description,
  a.AccType                      as AccType,          -- AutoCount account type text, e.g. 'Sales', 'Bank', 'Debtor Control'
  a.ParentAccNo                  as ParentAccNo,
  case when a.IsActive = 'T' then 1 else 0 end as IsActive   -- AutoCount stores booleans as 'T'/'F' (IsGroupCompany='T' is confirmed on Debtor)
from dbo.GLMast a;                                    -- TODO-VERIFY: account master table name
go

-- ---------------------------------------------------------------------------
-- Monthly GL movements per account + all-history running balance.
-- Opening balances (dbo.OBDtl) are folded in as a pseudo-period dated the
-- day before the first fiscal year in the book.
-- ---------------------------------------------------------------------------
create or alter view dbo.vw_bk_dash_gl_monthly
as
with lines as (
  select
    d.AccNo,
    cast(d.DocDate as date)                         as DocDate,          -- TODO-VERIFY column (DocDate vs PostDate)
    cast(coalesce(d.DR, 0) as decimal(18,2))        as DR,               -- TODO-VERIFY: DR/CR columns vs a single signed LocalAmount
    cast(coalesce(d.CR, 0) as decimal(18,2))        as CR
  from dbo.GLDtl d                                                      -- CONFIRMED table name
  union all
  select
    o.AccNo,
    cast(o.DocDate as date),                                            -- TODO-VERIFY: OBDtl date column
    cast(coalesce(o.DR, 0) as decimal(18,2)),
    cast(coalesce(o.CR, 0) as decimal(18,2))
  from dbo.OBDtl o                                                      -- CONFIRMED table name, columns TODO-VERIFY
),
monthly as (
  select
    AccNo,
    datefromparts(year(DocDate), month(DocDate), 1)               as PeriodStart,
    eomonth(DocDate)                                               as PeriodEnd,
    sum(DR)                                                        as Debit,
    sum(CR)                                                        as Credit
  from lines
  group by AccNo, datefromparts(year(DocDate), month(DocDate), 1), eomonth(DocDate)
)
select
  m.AccNo,
  m.PeriodStart,
  m.PeriodEnd,
  m.Debit,
  m.Credit,
  sum(m.Debit - m.Credit) over (partition by m.AccNo order by m.PeriodStart
                                rows between unbounded preceding and current row) as RunningBalance  -- debit positive, all history
from monthly m;
go

-- ---------------------------------------------------------------------------
-- Open AR items (for aging). One row per outstanding invoice/debit note.
-- The extractor buckets by days overdue (as_of - DueDate).
-- ---------------------------------------------------------------------------
create or alter view dbo.vw_bk_dash_ar_open_items
as
select
  i.DebtorCode                                   as CounterpartyCode,   -- CONFIRMED column on ARInvoice
  d.CompanyName                                  as CounterpartyName,   -- TODO-VERIFY column on dbo.Debtor
  i.DocNo                                        as DocNo,              -- TODO-VERIFY
  cast(i.DocDate as date)                        as DocDate,            -- TODO-VERIFY
  cast(coalesce(i.DueDate, i.DocDate) as date)   as DueDate,            -- TODO-VERIFY (may need DATEADD(day, CreditTerm, DocDate))
  cast(i.Outstanding as decimal(18,2))           as Outstanding,        -- TODO-VERIFY: wiki refers to an "Outstanding" value on invoices
  i.Currency                                     as CurrencyCode        -- TODO-VERIFY (may be CurrencyCode)
from dbo.ARInvoice i                                                    -- CONFIRMED table name
join dbo.Debtor d on d.AccNo = i.DebtorCode                              -- CONFIRMED table; join key TODO-VERIFY (AccNo vs DebtorCode)
where i.Outstanding <> 0
  and i.Cancelled = 'F';                                                 -- TODO-VERIFY column
-- NOTE: AR debit notes / unapplied credit notes & payments (ARDN, ARCN, ARPayment)
-- also affect aging. Add UNION ALL branches once the table names are confirmed.
go

-- ---------------------------------------------------------------------------
-- Open AP items (for aging)
-- ---------------------------------------------------------------------------
create or alter view dbo.vw_bk_dash_ap_open_items
as
select
  i.CreditorCode                                 as CounterpartyCode,   -- TODO-VERIFY
  c.CompanyName                                  as CounterpartyName,   -- TODO-VERIFY
  i.DocNo                                        as DocNo,
  cast(i.DocDate as date)                        as DocDate,
  cast(coalesce(i.DueDate, i.DocDate) as date)   as DueDate,
  cast(i.Outstanding as decimal(18,2))           as Outstanding,
  i.Currency                                     as CurrencyCode
from dbo.APInvoice i                                                    -- CONFIRMED table name
join dbo.Creditor c on c.AccNo = i.CreditorCode                          -- TODO-VERIFY table/join key
where i.Outstanding <> 0
  and i.Cancelled = 'F';
go

-- ---------------------------------------------------------------------------
-- Daily closing balance of bank accounts, from the GL (AccType = 'Bank').
-- Days without movement are filled by the extractor (forward fill).
-- ---------------------------------------------------------------------------
create or alter view dbo.vw_bk_dash_bank_daily
as
with bank_accts as (
  select AccNo, Description
  from dbo.GLMast                                                        -- TODO-VERIFY
  where AccType in ('Bank', 'Cash')                                       -- TODO-VERIFY type labels
),
lines as (
  select d.AccNo, cast(d.DocDate as date) as DocDate,
         cast(coalesce(d.DR,0) as decimal(18,2)) - cast(coalesce(d.CR,0) as decimal(18,2)) as Net
  from dbo.GLDtl d
  union all
  select o.AccNo, cast(o.DocDate as date), cast(coalesce(o.DR,0) as decimal(18,2)) - cast(coalesce(o.CR,0) as decimal(18,2))
  from dbo.OBDtl o
),
daily as (
  select l.AccNo, l.DocDate, sum(l.Net) as Net
  from lines l
  join bank_accts b on b.AccNo = l.AccNo
  group by l.AccNo, l.DocDate
)
select
  d.AccNo                                   as BankAccountCode,
  b.Description                             as BankAccountName,
  d.DocDate                                 as BalanceDate,
  sum(d.Net) over (partition by d.AccNo order by d.DocDate
                   rows between unbounded preceding and current row) as ClosingBalance
from daily d
join bank_accts b on b.AccNo = d.AccNo;
go
