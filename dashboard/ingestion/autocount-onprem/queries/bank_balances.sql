-- Extractor query: daily bank balances on movement days
-- params: ? = from date, ? = to date
select BankAccountCode, BankAccountName, BalanceDate, ClosingBalance
from dbo.vw_bk_dash_bank_daily
where BalanceDate between ? and ?
order by BankAccountCode, BalanceDate;
