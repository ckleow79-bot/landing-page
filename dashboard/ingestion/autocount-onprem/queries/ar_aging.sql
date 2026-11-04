-- Extractor query: open AR items for aging as of a date
-- params: ? = as_of date (items dated on/before it)
select CounterpartyCode, CounterpartyName, DocNo, DocDate, DueDate, Outstanding, CurrencyCode
from dbo.vw_bk_dash_ar_open_items
where DocDate <= ?
order by CounterpartyCode, DueDate;
