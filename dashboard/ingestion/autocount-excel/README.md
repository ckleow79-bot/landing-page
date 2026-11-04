# AutoCount Cloud report exports (Excel / CSV) -> warehouse

A manual, heuristic importer for the period before the AutoCount Cloud API
feed (`../autocount-cloud/`) is confirmed. You export five standard reports
from AutoCount Cloud Accounting as Excel (or CSV), run this tool in
**dry-run** to get a mapping report and normalised CSVs, confirm the account
mapping, and only then run it with `--write` to upsert into the finance
warehouse (same tables and natural keys as the other two loaders; rows are
never deleted).

```
AutoCount Cloud  --(export .xlsx/.csv)-->  import_autocount_exports.py --dry-run  -->  mapping report + out/*.csv
                                            import_autocount_exports.py --write    -->  entities, fiscal_periods,
                                                                                        chart_of_accounts, gl_balances,
                                                                                        ar_aging, ap_aging, bank_balances
                                                                                        (+ ingestion_runs, source excel_import)
```

First target: **B & K Academy PLT** (entity code `BKAC`, SSM 202504000011 /
LLP0041499-LGN, MSIC 85499), trial balances for Aug, Sep and Oct 2026 plus
aging and bank balances as at 31 Oct 2026. Nothing is specific to BKAC
except the built-in entity register used to create the `entities` row.

## Files

| File | Purpose |
|---|---|
| `import_autocount_exports.py` | the importer (Python 3.11+, openpyxl + psycopg; pandas is optional for looking at the CSVs) |
| `requirements.txt` | dependencies |
| `tests/make_fixtures.py` | generates synthetic AutoCount-style workbooks (title rows, merged headers, subtotals, text amounts) |
| `tests/test_importer.py` | pytest: parsing, header detection, TB balancing, classification, dry-run CLI, optional end-to-end `--write` |
| `../../supabase/migrations/004_excel_import_source.sql` | adds `excel_import` to the `source_system` enum so runs are logged under their own source |

## 1. Export the reports from AutoCount Cloud

Export each report from AutoCount Cloud Accounting's reporting area as
Excel (`.xlsx`) where offered, otherwise CSV. The importer does not depend on
exact menu names or column layouts; it looks for these reports by content:

| Needed | Report to look for in AutoCount Cloud | Settings when exporting |
|---|---|---|
| Trial balance per month end | **Trial Balance** (G/L reports) | one export per month end (31 Aug, 30 Sep, 31 Oct 2026), *or* one export with a column per month if the report offers a comparative/monthly layout. Include all accounts (do not hide zero balances if there is a choice; it does no harm). |
| Chart of accounts | **Chart of Account(s)** / account listing (G/L maintenance or reports) | include the **Account Type** and, if available, the **Special Account Type** columns; parent account column if offered |
| Debtor aging as at 31 Oct 2026 | **Debtor Aging** / **A/R Aging** (A/R reports) | as at 31/10/2026, summary by debtor (one line per debtor is enough; detail lines are summed per debtor code) |
| Creditor aging as at 31 Oct 2026 | **Creditor Aging** / **A/P Aging** (A/P reports) | as at 31/10/2026, summary by creditor |
| Bank balances as at 31 Oct 2026 | **Bank Reconciliation** summary or **Bank Book** / cash book balance listing | as at 31/10/2026; a listing with one row per bank account and its book (ledger) balance. If no such report exists, skip it and use `--bank-from-tb` (bank balances are then taken from the TB's cash accounts at month end). |

Tips: leave the title rows in (the importer reads the "As At" / period from
them); do not re-type amounts; keep the files as exported. If a report has
several sheets, the first non-empty one is read (`--sheet NAME` to choose).

## 2. Install

```bash
cd dashboard/ingestion/autocount-excel
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

## 3. Dry run (default) - read the mapping report

```bash
python import_autocount_exports.py --entity BKAC --fye-month 12 \
  --tb "TB Aug 2026.xlsx" "TB Sep 2026.xlsx" "TB Oct 2026.xlsx" \
  --coa "Chart of Accounts.xlsx" \
  --ar-aging "Debtor Aging.xlsx" --ap-aging "Creditor Aging.xlsx" \
  --bank "Bank Reconciliation Summary.xlsx" \
  --as-of 2026-10-31 --out out
```

* `--fye-month` is the entity's financial year end month. With `DATABASE_URL`
  set it is read from the `entities` table; without it the tool assumes
  December and says so. It matters: P&L closing balances in a trial balance
  are fiscal-year-to-date and the monthly movement is derived from them.
* Every file is optional; import whatever you have.
* TB period: detected from the title rows ("As At 31/08/2026", "Period ... to
  ...", "Aug 2026") or the file name. Override per file with
  `"TB Oct.xlsx=2026-10"`, or for all files with `--period 2026-10`.
* `--as-of` is the snapshot date for aging and bank balances; if omitted the
  "As At" date in each file's title rows is used.
* With `DATABASE_URL` (or `WAREHOUSE_DATABASE_URL`) set, a dry run also
  compares the accounts with the warehouse `chart_of_accounts` and uses the
  previous month already in the warehouse to derive the first month's
  movements. Nothing is written in dry-run.

### What the mapping report says

For each file:

* `header row N [merged with row M]`: the row recognised as the column header
  (1-based, as in Excel) and, when the header spans two rows (e.g. "Aging"
  over "Current | 1-30 | ..." or "Aug 2026" over "Debit | Credit"), the row it
  was merged with. The header is the first-30-rows row with the most header
  words (account/code, description/name, debit, credit, balance, debtor,
  supplier, bank, current, 30/60/90/120 ...).
* `colN 'label' -> role`: how each column is used. Aging columns show the
  bucket (`bucket_current`, `bucket_30`, `bucket_60`, `bucket_90`,
  `bucket_120_plus`; several columns such as "91-120" and "Over 120" add
  into `bucket_120_plus`). Month columns in a TB show `period=YYYY-MM`.
* `counts`: rows read, subtotal / total rows stripped, section or blank rows
  skipped, accounts or counterparties found, lines merged into one
  counterparty.
* Trial balance: `debit`, `credit`, `difference`, `balanced=True/False` per
  month computed from the parsed lines, plus the file's own total row for
  reference (it can differ when a column nets negatives, e.g. accumulated
  depreciation shown as "(12,000.00)" in the Debit column). An unbalanced TB
  blocks `--write`.
* Aging: bucket totals, grand total and the file's total row; a warning if
  the file's Total column disagrees with the sum of buckets.
* `[accounts]`: how many accounts came from the COA export, how many were
  created from TB lines that are not in the COA, the split by `account_type`,
  by classification source (`override` = your `account_map.csv`,
  `source_type` = AutoCount's account type column, `section` = the TB
  section header above the line, `code_range`, `keyword`, `default`) and by
  confidence. `UNMAPPED source account types` lists AutoCount type labels the
  tool does not know. Low-confidence accounts are listed with their code
  and name (account names are not sensitive; counterparty names never
  appear on the console).
* `[gl_balances]`: periods with fiscal year / period number, how movements
  were derived, and per month: revenue movement, cost movement, cash closing
  and `sum of closings` (must be 0.00).
* Aging / bank sections print counts and totals only. Names and masked
  account numbers are in the CSVs under `--out`.

### Files written under `--out` (default `./out`)

`chart_of_accounts.csv`, `fiscal_periods.csv`, `gl_balances.csv` (with a
`basis` column: `delta`, `fy_start`, `ytd_as_movement`, `unknown_prior`,
`absent_zeroed`, `file_movements`), `ar_aging.csv`, `ap_aging.csv`,
`bank_balances.csv`, `mapping_report.txt`, and
**`account_map_suggested.csv`**: every account whose classification is not
high-confidence, pre-filled with the tool's guess. Review it, correct
`account_type` / `account_subtype` / `cashflow_bucket` / `is_current`, delete
rows you agree with (or leave them), save it as `account_map.csv` next to
where you run the tool (or pass `--account-map FILE`). Rows in that file win
over every heuristic and are also applied to accounts that already exist in
the warehouse. Allowed values are the schema enums:
`account_type` asset | liability | equity | revenue | cogs | opex | other;
`cashflow_bucket` cash | operating | investing | financing | non_cash;
`account_subtype` as in `chart_of_accounts.account_subtype`.

### How accounts are classified

1. `account_map.csv` (owner override).
2. The export's own account type column (`Special Account Type` first, then
   `Account Type`), via `SOURCE_TYPE_MAP` in the script.
3. For TB-only accounts, the section header above the line in the TB
   ("CURRENT ASSETS", "EXPENSES", ...).
4. Code-range fallback: `--code-convention auto` picks whichever of the two
   built-in conventions (`generic`: 1xx/2xx assets, 3xx liabilities, 4xx
   equity, 5xx revenue, 6xx COGS, 7xx-9xx opex; `autocount`: 1xx equity,
   2xx/3xx assets, 4xx liabilities, 5xx revenue, 6xx COGS, 7xx-9xx opex)
   agrees most with the account names, and says so.
5. Keyword rules on the account name (bank names, debtor/creditor, director,
   retained, SST/EPF/SOCSO, depreciation, interest, taxation, training income,
   trainer fees, ...). Keywords always refine the subtype and cash-flow
   bucket; "Interest Expense" / "Taxation" typed as plain Expenses are moved
   to `other` so they sit below EBITDA.

Anything decided by 3-5, or by an abbreviated source type, lands in
`account_map_suggested.csv`.

## 4. Write

```bash
export DATABASE_URL='postgresql://postgres.<ref>:<password>@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require'
psql "$DATABASE_URL" -f ../../supabase/migrations/004_excel_import_source.sql   # once
python import_autocount_exports.py --entity BKAC --fye-month 12 ... --as-of 2026-10-31 --write
```

* The `entities` row is created if missing (name and registration number
  from the built-in register for BKAC/BKA/BKTS, `--entity-name` otherwise,
  `source_system` = `--source-system`, default `autocount_cloud`).
* Order inside one transaction: chart_of_accounts -> fiscal_periods ->
  gl_balances -> ar_aging -> ap_aging -> bank_balances; any failure rolls
  everything back. An `ingestion_runs` row is opened first (status
  `running`) and closed as `success` or `failed` with the error text, source
  `excel_import` (or the entity's own source with `metadata.importer =
  'excel_import'` if migration 004 is not applied yet).
* Re-running the same files is idempotent (upserts by natural key).
  Classification columns of existing accounts are left alone unless the
  account is in `account_map.csv`; finance's edits in the warehouse survive.
* `--write` is refused while the report has an unbalanced TB, a missing
  header or a TB without a period.
* Afterwards: `select * from v_balance_sheet_summary where balance_check <> 0;`
  must be empty; `select * from v_board_kpis;` shows the entity at its latest
  month.

### Month-on-month movements

A trial balance holds closing balances. `gl_balances` needs movements too,
so the tool derives them: balance-sheet movement = closing - previous
month's closing; P&L movement = the same within a fiscal year and = closing
in the first fiscal month. For the earliest month you load it looks for the
previous month in the warehouse; if there is none and the month is not the
start of the fiscal year, its P&L movements are the fiscal-YTD figures and
balance-sheet movements are 0 (flagged in the report and in `basis`). Load
the earlier months, or accept that the first month's P&L is YTD. An account
that disappears from a later TB is taken as zero (a TB lists every non-zero
balance). If a TB export carries Opening / Debit / Credit / Closing columns,
Debit/Credit are used as the period's movements directly.

## 5. Tests

```bash
pip install pytest
pytest -q tests                                  # unit tests, no database
# end-to-end against a throwaway PostgreSQL 16 with the Supabase shim and migrations 001-004 applied:
BK_TEST_DATABASE_URL='postgresql://postgres@/postgres?host=/tmp/pgx2&port=54330' pytest -q tests
python tests/make_fixtures.py out/fixtures       # look at the synthetic workbooks
```

The e2e test writes BKAC fixture data twice (idempotency), then checks row
counts, `ingestion_runs`, `v_pl_monthly`, `v_board_kpis`,
`v_balance_sheet_summary.balance_check = 0`, `v_ar_ap_aging_summary` and
`v_cash_position`. It grants `dash_owner` to `postgres` on that test cluster
so the audience-filtered views return rows.

## TODO-VERIFY (confirm against the real exports before trusting the numbers)

1. **AutoCount account type labels and abbreviations.** `SOURCE_TYPE_MAP`
   holds the long labels commonly shown in the AutoCount UI (Bank, Cash,
   Debtor Control, Current Asset, Stock, Fixed Asset, Accumulated
   Depreciation, Creditor Control, Current Liability, Long Term Liability,
   Capital, Retained Earning, Sales, Sales Adjustment, Cost of Goods Sold,
   Expenses, Other Income, Other Expenses, Taxation, Extraordinary ...) and
   guessed abbreviations (BA, DC, CA, ST, FA, AD, OA, CC, CL, LTL, CAP, RE,
   SA, CS, EXP, OI, OE, TAX). None of these were confirmed from vendor
   documentation; `SA` in particular may mean Sales or Sales Adjustment.
   Unknown labels are listed under `UNMAPPED source account types`.
2. **Code ranges.** Both conventions are fallbacks. Confirm BKAC's own chart;
   accounts classified by `code_range` or `keyword` are in the suggested map.
3. **Trial balance semantics.** Confirm that P&L accounts in the AutoCount
   Cloud TB are fiscal-YTD at the "As At" date and that the TB includes the
   current-year P&L lines (so it balances without an appropriation line). If
   AutoCount exports a TB with opening/movement/closing columns, the tool
   uses the movements directly; check the first month's `basis`.
4. **Aging basis.** Buckets are mapped by their labels (days overdue by due
   date assumed, the same assumption as the on-prem loader). If the report
   ages by invoice date or by month columns, the mapping is labelled in the
   report; reconcile one month end against AutoCount's own aging totals.
5. **Bank balance source.** The tool prefers a "book" / "closing" / "ledger"
   balance column over a "statement" balance. Confirm which column of the
   exported bank report is the GL balance.
6. **Entity details.** Fiscal year end month for BKAC (not in the entity
   register) must be set with `--fye-month` or in `entities` before the
   first write.
7. **Enum change.** Migration 004 adds `excel_import` to `source_system`;
   run it on the warehouse project before the first `--write`, otherwise the
   run is logged under `autocount_cloud` with `metadata.importer`.

## Known limitations

* Legacy `.xls` is not read; re-save as `.xlsx` or export CSV.
* One entity per run; one currency per file (`currency` column honoured per
  row if present, otherwise MYR).
* Aging detail lines without a counterparty code are skipped; without a
  code column a code is derived from the name (`NAME:<slug>`).
* No deletes: a counterparty that drops out of the aging keeps its last
  snapshot row at the earlier `as_of_date` (that is the intended history).
* Header detection needs at least two recognisable header words in one of
  the first 30 rows; exotic layouts will need `--sheet` or a small manual
  clean-up of the export.
* Console output is aggregate-only by design; counterparty names and masked
  account numbers are in `out/*.csv` and in the database.
