-- Extractor query: monthly GL movements + running balance
-- params: ? = from date (first day of earliest month needed), ? = to date (last day of latest month)
select AccNo, PeriodStart, PeriodEnd, Debit, Credit, RunningBalance
from dbo.vw_bk_dash_gl_monthly
where PeriodStart >= ? and PeriodEnd <= ?
order by AccNo, PeriodStart;
