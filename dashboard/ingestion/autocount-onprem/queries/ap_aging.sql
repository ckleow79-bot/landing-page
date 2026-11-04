-- Extractor query: open AP items for aging as of a date
-- params: ? = as_of date
select CounterpartyCode, CounterpartyName, DocNo, DocDate, DueDate, Outstanding, CurrencyCode
from dbo.vw_bk_dash_ap_open_items
where DocDate <= ?
order by CounterpartyCode, DueDate;
