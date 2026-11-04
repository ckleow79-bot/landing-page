-- Extractor query: chart of accounts (no parameters)
select AccNo, Description, AccType, ParentAccNo, IsActive
from dbo.vw_bk_dash_chart_of_accounts
order by AccNo;
