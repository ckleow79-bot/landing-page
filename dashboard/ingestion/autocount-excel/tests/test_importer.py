"""
Tests for import_autocount_exports.py.

Unit tests use synthetic workbooks from make_fixtures.py (generated into a
temp folder; nothing binary is committed). The end-to-end --write test runs
only when BK_TEST_DATABASE_URL points at a Postgres with migrations 001-004
applied (see README: throwaway cluster recipe).

    pytest -q tests
    BK_TEST_DATABASE_URL='postgresql://postgres@/postgres?host=/tmp/pgx2&port=54330' pytest -q tests
"""
from __future__ import annotations

import csv
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import import_autocount_exports as imp  # noqa: E402
import make_fixtures as fx  # noqa: E402

D = Decimal


@pytest.fixture(scope="session")
def files(tmp_path_factory) -> dict[str, Path]:
    return fx.make_all(tmp_path_factory.mktemp("autocount_fixtures"))


# ---------------------------------------------------------------------------
# number / date parsing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw, expected", [
    ("1,234.56", D("1234.56")), ("(1,234.56)", D("-1234.56")), ("-1,234.56", D("-1234.56")), ("1,234.56-", D("-1234.56")),
    ("1,234.56 CR", D("-1234.56")), ("1,234.56 DR", D("1234.56")), ("RM 1,234.56", D("1234.56")), ("MYR1,234", D("1234.00")),
    ("-", None), ("", None), (None, None), ("abc", None), (1234.5, D("1234.50")), (0, D("0.00")), (" 12.345 ", D("12.35")),
    ("(500.00)", D("-500.00")), ("−1,000", D("-1000.00")), ("31/10/2026", None), ("1,234.56 CR", D("-1234.56")),
])
def test_parse_number(raw, expected):
    assert imp.parse_number(raw) == expected


def test_parse_cell_cr_suffix_in_credit_column():
    # 'CR' in the Credit column restates the column; in a balance column it is a credit balance
    assert imp.parse_cell("20,000.00 CR", "credit") == D("20000.00")
    assert imp.parse_cell("20,000.00 CR", "balance") == D("-20000.00")
    assert imp.parse_cell("20,000.00 DR", "credit") == D("-20000.00")
    assert imp.parse_cell("(1,500.00)", "debit") == D("-1500.00")


@pytest.mark.parametrize("text, expected", [
    ("As At 31/10/2026", date(2026, 10, 31)), ("Period 01/08/2026 to 31/08/2026", date(2026, 8, 31)),
    ("For the month ended 30 September 2026", date(2026, 9, 30)), ("Oct 2026", date(2026, 10, 31)),
    ("Trial Balance 2026-09", date(2026, 9, 30)), ("TB_Aug-26", date(2026, 8, 31)), ("no date here", None),
])
def test_find_dates(text, expected):
    ds = imp.find_dates(text)
    assert (max(ds) if ds else None) == expected


def test_period_parsing_and_file_override(tmp_path):
    assert imp.parse_period("2026-10") == date(2026, 10, 1)
    assert imp.parse_period("Oct 2026") == date(2026, 10, 1)
    p, per = imp._split_file_period("/some/TB Oct.xlsx=2026-10")
    assert p == Path("/some/TB Oct.xlsx") and per == date(2026, 10, 1)
    real = tmp_path / "x=y.xlsx"
    real.write_bytes(b"")
    assert imp._split_file_period(str(real)) == (real, None)  # existing file with '=' in its name is left alone


@pytest.mark.parametrize("label, bucket", [
    ("Current", "bucket_current"), ("Not Due", "bucket_current"), ("1 - 30", "bucket_30"), ("1-30 Days", "bucket_30"),
    ("31-60 Days", "bucket_60"), ("61 - 90", "bucket_90"), ("91-120 Days", "bucket_120_plus"), ("> 90", "bucket_120_plus"),
    ("Over 120 Days", "bucket_120_plus"), ("120+", "bucket_120_plus"), ("1 Month", "bucket_30"), ("4 Months & Above", "bucket_120_plus"),
    ("Total", None), ("Debtor Name", None), ("30", "bucket_30"), ("90 days", "bucket_90"),
])
def test_bucket_for_label(label, bucket):
    assert imp.bucket_for_label(label) == bucket


def test_bucket_for_month_columns():
    as_of = date(2026, 10, 31)
    assert imp.bucket_for_label("Oct 2026", as_of) == "bucket_current"
    assert imp.bucket_for_label("Sep 2026", as_of) == "bucket_30"
    assert imp.bucket_for_label("Jul 2026", as_of) == "bucket_90"
    assert imp.bucket_for_label("Jun 2026 & before", as_of) == "bucket_120_plus"


def test_fiscal_helpers():
    assert imp.fiscal_year_start(date(2026, 8, 1), 12) == date(2026, 1, 1)
    assert imp.fiscal_year_start(date(2026, 8, 1), 6) == date(2026, 7, 1)
    assert imp.fiscal_year_label(date(2026, 8, 1), 6) == 2027 and imp.period_no(date(2026, 8, 1), 6) == 2
    assert imp.fiscal_year_label(date(2026, 8, 1), 12) == 2026 and imp.period_no(date(2026, 8, 1), 12) == 8


# ---------------------------------------------------------------------------
# header detection + trial balance
# ---------------------------------------------------------------------------
def test_tb_header_detection_and_balance(files):
    grid = imp.load_grid(files["tb_2026-08"])
    assert grid.merged_ranges == 3
    h = imp.detect_header(grid)
    assert h is not None and h.row_idx == 4 and h.merged_with is None          # row 5 (1-based), title rows not merged in
    roles = {c.role: c.label for c in h.columns if c.role}
    assert roles == {"account_code": "Account No.", "name": "Description", "debit": "Debit", "credit": "Credit"}
    d = imp.Diag("trial_balance", files["tb_2026-08"].name)
    rows = imp.parse_trial_balance(grid, None, d)
    assert d.notes[0] == "period 2026-08 (from title rows)"
    assert d.counts["accounts"] == 28 and d.counts["total_rows_skipped"] == 11      # 10 subtotals + grand total
    assert d.totals["2026-08"]["balanced"] is True and not any("balance" in w for w in d.warnings)
    by = {r.account_code: r for r in rows}
    assert by["200-0100"].closing == D("-12000.00")       # "(12,000.00)" in the debit column
    assert by["430-0000"].closing == D("-20000.00")       # "20,000.00 CR" in the credit column
    assert by["300-1000"].closing == D("23000.50")        # "23,000.50" text with comma
    assert by["990-0000"].section == "CURRENT ASSETS"      # section header carried to the TB-only account
    assert all(r.debit is None for r in rows)              # closing-balance layout, no movements in file


def test_tb_multi_month_merged_header_matches_single_files(files):
    grid = imp.load_grid(files["tb_multi"])
    h = imp.detect_header(grid)
    assert h is not None and h.row_idx == 4 and h.merged_with == 3                # 'Aug 2026' row merged into 'Debit | Credit'
    assert [c.period for c in h.columns if c.role == "debit"] == [date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)]
    d = imp.Diag("trial_balance", "multi")
    multi = {(r.period_start, r.account_code): r.closing for r in imp.parse_trial_balance(grid, None, d)}
    assert d.counts["periods"] == 3 and all(v["balanced"] for v in d.totals.values())
    single = {}
    for m in fx.MONTHS:
        for r in imp.parse_trial_balance(imp.load_grid(files[f"tb_{m}"]), None, imp.Diag("tb", m)):
            single[(r.period_start, r.account_code)] = r.closing
    assert multi == single
    for (p, code), v in multi.items():
        assert v == fx.expected_closing(code, p.strftime("%Y-%m"))


def test_tb_period_override_and_missing_period(tmp_path, files):
    grid = imp.load_grid(files["tb_2026-08"])
    d = imp.Diag("tb", "x")
    rows = imp.parse_trial_balance(grid, date(2026, 7, 1), d)
    assert rows and rows[0].period_start == date(2026, 7, 1) and "override" in d.notes[0]
    # strip the title rows so no period is detectable
    grid.rows = grid.rows[4:]
    grid.path = tmp_path / "no_date.xlsx"
    d2 = imp.Diag("tb", "x")
    assert imp.parse_trial_balance(grid, None, d2) == [] and any("period not found" in w for w in d2.warnings)


def test_detect_header_rejects_data_rows_as_fragments(files):
    # COA: the first data row sits right under the header and must not be merged into it
    h = imp.detect_header(imp.load_grid(files["coa"]))
    assert h is not None and h.merged_with is None and h.row_idx == 4
    assert [c.role for c in h.columns] == ["account_code", "name", "account_type", "account_type", "parent", None]


# ---------------------------------------------------------------------------
# chart of accounts + classification
# ---------------------------------------------------------------------------
def test_coa_parse_and_classification(files):
    d = imp.Diag("coa", "coa")
    rows = imp.parse_coa(imp.load_grid(files["coa"]), d)
    assert d.counts == {"accounts": 27, "rows_skipped": 0, "type_columns": 2}
    by = {r.account_code: r for r in rows}
    assert by["300-0000"].source_type == "BA / Bank" and by["200-0100"].parent == "200-0000"

    def cls(code, **kw):
        r = by[code]
        return imp.classify_account(code, r.name, r.source_type, None, kw.get("ov", {}), "generic")

    c = cls("300-0000"); assert (c.account_type, c.account_subtype, c.cashflow_bucket, c.is_current, c.confidence) == ("asset", "cash", "cash", True, "high")
    c = cls("310-0000"); assert (c.account_type, c.account_subtype) == ("asset", "trade_receivable")
    c = cls("200-0100"); assert (c.account_type, c.account_subtype, c.is_current) == ("asset", "fixed_asset", False)
    c = cls("420-0000"); assert (c.account_type, c.account_subtype) == ("liability", "tax_payable")          # keyword refines subtype
    c = cls("450-0000"); assert (c.account_type, c.account_subtype, c.cashflow_bucket, c.is_current) == ("liability", "borrowing", "financing", False)
    c = cls("150-0000"); assert (c.account_type, c.account_subtype) == ("equity", "retained_earnings")
    c = cls("902-0000"); assert (c.account_type, c.account_subtype, c.cashflow_bucket) == ("opex", "depreciation", "non_cash")
    c = cls("950-0000"); assert (c.account_type, c.account_subtype, c.confidence) == ("other", "interest", "medium")  # 'Expenses' + interest name
    c = cls("960-0000"); assert (c.account_type, c.account_subtype) == ("other", "tax")
    c = cls("800-0000"); assert c.account_type == "other"
    c = cls("500-0000"); assert c.account_type == "revenue" and c.source == "source_type"
    # unknown source type 'Mystery Type' -> code range (9 -> opex) agrees with keyword -> medium
    c = cls("905-0000"); assert (c.account_type, c.source, c.confidence) == ("opex", "code_range", "medium")
    assert imp._source_type_lookup("Mystery Type") is None
    # override file wins and is high confidence
    ov = imp.load_account_map(files["account_map"])
    assert set(ov) == {"990-0000", "905-0000"}
    c = imp.classify_account("990-0000", "Suspense Account", None, "CURRENT ASSETS", ov, "generic")
    assert (c.account_type, c.account_subtype, c.source, c.confidence, c.is_current) == ("asset", "other_receivable", "override", "high", True)
    # without override: TB section header gives a medium-confidence asset
    c = imp.classify_account("990-0000", "Suspense Account", None, "CURRENT ASSETS", {}, "generic")
    assert (c.account_type, c.source, c.confidence) == ("asset", "section", "medium")


def test_classification_fallbacks_without_source_type():
    # strong keyword beats a contradicting code range, but is flagged low
    c = imp.classify_account("300-0000", "Maybank Current Account", None, None, {}, "generic")   # generic: 3xx = liability
    assert (c.account_type, c.account_subtype, c.confidence, c.source) == ("asset", "cash", "low", "keyword")
    c = imp.classify_account("300-0000", "Maybank Current Account", None, None, {}, "autocount")
    assert (c.account_type, c.account_subtype, c.confidence) == ("asset", "cash", "medium")
    c = imp.classify_account("450-0000", "Term Loan - Maybank", None, None, {}, "autocount")
    assert (c.account_type, c.account_subtype) == ("liability", "borrowing")                       # loan rule before bank-name rule
    c = imp.classify_account("904-0000", "Bank Charges", None, None, {}, "autocount")
    assert c.account_type == "opex"
    c = imp.classify_account("XYZ", "Something odd", None, None, {}, "generic")
    assert (c.account_type, c.source, c.confidence) == ("other", "default", "low")
    log: list[str] = []
    names = [(c, n) for c, n, *_ in fx.COA]
    assert imp.pick_convention(names, "auto", log) == "autocount" and "TODO-VERIFY" in log[0]
    assert imp.pick_convention(names, "generic", log) == "generic"


def test_account_map_validation(tmp_path):
    bad = tmp_path / "account_map.csv"
    bad.write_text("account_code,account_type\n100-0000,capital\n")
    with pytest.raises(SystemExit):
        imp.load_account_map(bad)
    ok = tmp_path / "ok.csv"
    ok.write_text("account_code,account_type,account_subtype,cashflow_bucket,is_current,name\n100,equity,Share Capital,Financing,,x\n200,,,,,blank row ignored\n")
    assert imp.load_account_map(ok) == {"100": {"account_type": "equity", "account_subtype": "share_capital", "cashflow_bucket": "financing", "is_current": None}}


# ---------------------------------------------------------------------------
# aging + bank
# ---------------------------------------------------------------------------
def test_ar_aging_two_row_header_and_aggregation(files):
    d = imp.Diag("ar_aging", "ar")
    rows, as_of = imp.parse_aging(imp.load_grid(files["ar"]), None, d)
    assert as_of == date(2026, 10, 31) and d.header_row == 6 and d.merged_with == 5
    labels = {c.split(" -> ")[-1] for c in d.columns if "bucket" in c}
    assert labels == set(imp.BUCKETS)
    assert d.counts["counterparties"] == 5 and d.counts["rows_merged_into_counterparties"] == 1
    by = {r.counterparty_code: r for r in rows}
    assert by["D001"].buckets["bucket_current"] == D("13500.00")            # 12,500 + 1,000 second line
    assert by["D004"].buckets["bucket_current"] == D("-500.00")             # parentheses credit balance
    assert by["D003"].buckets["bucket_120_plus"] == D("1800.00")            # '> 90'
    for code, tot in fx.AR_TOTAL_BY_CODE.items():
        assert sum(by[code].buckets.values()) == tot
    assert d.totals["grand_total"] == D("52200.00") == d.totals["file_total_row"]["total"]
    assert not d.warnings


def test_ap_aging_csv_six_buckets(files):
    d = imp.Diag("ap_aging", "ap")
    rows, as_of = imp.parse_aging(imp.load_grid(files["ap"]), date(2026, 10, 31), d)
    assert as_of == date(2026, 10, 31) and d.header_row == 5 and not d.warnings
    by = {r.counterparty_code: r for r in rows}
    assert by["C003"].buckets == {"bucket_current": D("0.00"), "bucket_30": D("0.00"), "bucket_60": D("0.00"), "bucket_90": D("600.00"), "bucket_120_plus": D("400.00")}
    assert by["C001"].buckets["bucket_current"] == D("9800.00")           # 'Not Due'
    assert d.totals["grand_total"] == D("19800.00")


def test_aging_as_of_conflict_is_reported(files):
    d = imp.Diag("ar_aging", "ar")
    imp.parse_aging(imp.load_grid(files["ar"]), date(2026, 9, 30), d)
    assert any("title rows say 2026-10-31" in w for w in d.warnings)


def test_bank_summary(files):
    d = imp.Diag("bank", "bank")
    rows, as_of = imp.parse_bank(imp.load_grid(files["bank"]), None, d)
    assert as_of == date(2026, 10, 31) and len(rows) == 2
    by = {r.bank_account_code: r for r in rows}
    assert by["300-0000"].closing_balance == fx.BAL["300-0000"][2]           # book balance, not statement balance
    assert by["300-0000"].account_no_masked == "****6789" and by["300-1000"].account_no_masked == "****4567"
    assert by["300-0000"].bank_name == "Maybank" and by["300-0000"].gl_account_code == "300-0000"
    assert "Book Balance" in d.notes[-1]


# ---------------------------------------------------------------------------
# dry-run CLI end to end (no database)
# ---------------------------------------------------------------------------
def _cli_args(files, out: Path, extra: list[str] | None = None) -> list[str]:
    return ["--entity", "BKAC", "--fye-month", "12",
            "--tb", str(files["tb_2026-08"]), str(files["tb_2026-09"]), str(files["tb_2026-10"]),
            "--coa", str(files["coa"]), "--ar-aging", str(files["ar"]), "--ap-aging", str(files["ap"]), "--bank", str(files["bank"]),
            "--as-of", "2026-10-31", "--account-map", str(files["account_map"]), "--out", str(out), *(extra or [])]


def test_cli_dry_run(files, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("WAREHOUSE_DATABASE_URL", raising=False)
    out = tmp_path / "out"
    assert imp.main(_cli_args(files, out)) == 0
    report = capsys.readouterr().out
    assert "0 warning(s). DRY RUN" in report
    assert "balanced=True" in report and "NOT ZERO" not in report
    # console stays aggregate: no counterparty names, no account numbers
    for name in [r[1] for r in fx.AR] + [r[1] for r in fx.AP]:
        assert name not in report
    assert "6789" not in report and "4567" not in report
    assert (out / "mapping_report.txt").read_text().strip() == report.strip()
    for f in ("chart_of_accounts", "fiscal_periods", "gl_balances", "ar_aging", "ap_aging", "bank_balances", "account_map_suggested"):
        assert (out / f"{f}.csv").exists()
    with (out / "gl_balances.csv").open() as fh:
        gl = {(r["period_start"], r["account_code"]): r for r in csv.DictReader(fh)}
    assert len(gl) == 83                                   # 28 + 27 + 27 TB lines + 990-0000 zeroed in Sep
    assert gl[("2026-08-01", "500-0000")]["basis"] == "ytd_as_movement" and gl[("2026-08-01", "500-0000")]["credit"] == "620000.00"
    assert gl[("2026-09-01", "500-0000")]["basis"] == "delta" and gl[("2026-09-01", "500-0000")]["credit"] == "85000.00"
    assert gl[("2026-10-01", "600-0000")]["debit"] == "35000.00"
    assert gl[("2026-09-01", "990-0000")]["basis"] == "absent_zeroed" and gl[("2026-09-01", "990-0000")]["credit"] == "150.00"
    assert gl[("2026-09-01", "200-0100")]["credit"] == "700.00" and gl[("2026-09-01", "200-0100")]["closing_balance"] == "-12700.00"
    for p in ("2026-08-01", "2026-09-01", "2026-10-01"):
        assert sum(D(r["closing_balance"]) for k, r in gl.items() if k[0] == p) == 0
    with (out / "account_map_suggested.csv").open() as fh:
        sug = {r["account_code"]: r for r in csv.DictReader(fh)}
    assert set(sug) == {"950-0000"}                        # everything else is high confidence (COA types + overrides)
    with (out / "ar_aging.csv").open() as fh:
        ar = list(csv.DictReader(fh))
    assert len(ar) == 5 and sum(D(r["total_outstanding"]) for r in ar) == D("52200.00")
    with (out / "bank_balances.csv").open() as fh:
        bank = list(csv.DictReader(fh))
    assert [r["account_no_masked"] for r in bank] == ["****6789", "****4567"]


def test_cli_refuses_to_write_without_database(files, tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("WAREHOUSE_DATABASE_URL", raising=False)
    with pytest.raises(SystemExit, match="DATABASE_URL"):
        imp.main(_cli_args(files, tmp_path / "o", ["--write"]))


def test_cli_bank_from_tb(files, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    out = tmp_path / "out"
    args = ["--entity", "BKAC", "--fye-month", "12", "--tb", f"{files['tb_multi']}", "--coa", str(files["coa"]), "--bank-from-tb", "--out", str(out),
            "--account-map", str(files["account_map"])]
    assert imp.main(args) == 0
    with (out / "bank_balances.csv").open() as fh:
        bank = {r["bank_account_code"]: r for r in csv.DictReader(fh)}
    assert set(bank) == {"300-0000", "300-1000", "300-2000"} and bank["300-0000"]["balance_date"] == "2026-10-31"


# ---------------------------------------------------------------------------
# end to end against a real Postgres (optional)
# ---------------------------------------------------------------------------
DB_URL = os.environ.get("BK_TEST_DATABASE_URL")


@pytest.mark.skipif(not DB_URL, reason="set BK_TEST_DATABASE_URL to a Postgres with migrations 001-004 applied")
def test_e2e_write(files, tmp_path, capsys, monkeypatch):
    import psycopg
    from psycopg.rows import dict_row

    monkeypatch.setenv("DATABASE_URL", DB_URL)
    out = tmp_path / "out"
    rc = imp.main(_cli_args(files, out, ["--write"]))
    txt = capsys.readouterr().out
    assert rc == 0, txt
    assert "WRITTEN. ingestion_runs.id" in txt
    rc2 = imp.main(_cli_args(files, out, ["--write"]))   # idempotent re-run
    assert rc2 == 0

    with psycopg.connect(DB_URL, row_factory=dict_row) as conn:
        conn.execute("do $$ begin if not pg_has_role('postgres', 'dash_owner', 'member') then execute 'grant dash_owner to postgres'; end if; end $$")
        ent = conn.execute("select id, fiscal_year_end_month from entities where code = 'BKAC'").fetchone()
        assert ent and ent["fiscal_year_end_month"] == 12
        eid = ent["id"]
        n = lambda sql: conn.execute(sql, (eid,)).fetchone()["c"]  # noqa: E731
        assert n("select count(*) c from chart_of_accounts where entity_id = %s") == 28
        assert n("select count(*) c from fiscal_periods where entity_id = %s") == 3
        assert n("select count(*) c from gl_balances where entity_id = %s") == 83
        assert n("select count(*) c from ar_aging where entity_id = %s and as_of_date = '2026-10-31'") == 5
        assert n("select count(*) c from ap_aging where entity_id = %s and as_of_date = '2026-10-31'") == 3
        assert n("select count(*) c from bank_balances where entity_id = %s and balance_date = '2026-10-31'") == 2
        runs = conn.execute("select source::text, status::text, rows_upserted, metadata from ingestion_runs where entity_id = %s order by started_at", (eid,)).fetchall()
        assert len(runs) >= 2 and all(r["status"] == "success" for r in runs[-2:]) and runs[-1]["source"] == "excel_import"
        assert runs[-1]["metadata"]["importer"] == "excel_import" and runs[-1]["rows_upserted"] > 0
        # the override file's mapping is applied in the warehouse; the suspense account exists although it is not in the COA export
        acc = conn.execute("select account_type::text t, account_subtype s from chart_of_accounts where entity_id = %s and account_code = '990-0000'", (eid,)).fetchone()
        assert (acc["t"], acc["s"]) == ("asset", "other_receivable")
        pl = conn.execute("select period_label, revenue, cogs, opex, net_profit from v_pl_monthly where entity_code = 'BKAC' order by period_start").fetchall()
        assert [r["period_label"] for r in pl] == ["Aug 2026", "Sep 2026", "Oct 2026"]
        assert pl[1]["revenue"] == D("97000.00") and pl[2]["revenue"] == D("94000.00")
        assert pl[2]["cogs"] == D("44000.00")                        # 35,000 trainer + 9,000 venue
        kpi = conn.execute("select * from v_board_kpis where entity_code = 'BKAC'").fetchone()
        assert kpi and kpi["period_label"] == "Oct 2026" and kpi["cash"] == D("153000.00")
        assert kpi["trade_receivables"] == D("51200.00") and kpi["trade_payables"] == D("19800.00")
        bs = conn.execute("select period_label, balance_check, cash_and_bank from v_balance_sheet_summary where entity_code = 'BKAC' order by period_start").fetchall()
        assert len(bs) == 3 and all(r["balance_check"] == 0 for r in bs) and bs[-1]["cash_and_bank"] == D("153500.00")
        ag = {r["ledger"]: r for r in conn.execute("select * from v_ar_ap_aging_summary where entity_code = 'BKAC'").fetchall()}
        assert ag["AR"]["total_outstanding"] == D("52200.00") and ag["AP"]["total_outstanding"] == D("19800.00")
        cash = conn.execute("select cash_balance from v_cash_position where entity_code = 'BKAC'").fetchone()
        assert cash["cash_balance"] == D("153000.00")
