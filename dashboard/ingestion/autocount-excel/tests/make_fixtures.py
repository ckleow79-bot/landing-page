#!/usr/bin/env python3
"""
Synthetic AutoCount-style export workbooks for the importer tests.

Everything here is invented (entity name and registration number are the
public identifiers from dashboard/README.md; every figure and counterparty is
fictitious). The layouts deliberately include what real exports do: title
rows, merged header cells, section and subtotal rows, text amounts with
commas, parentheses negatives, a CR suffix, one file per month plus one file
with month columns, an aging with Current/1-30/31-60/61-90/>90 buckets (xlsx)
and one with Not Due/.../91-120/Over 120 buckets (CSV), and a bank summary.

    python tests/make_fixtures.py out/fixtures      # write them somewhere to look at
"""
from __future__ import annotations

import csv
import sys
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

ENTITY_TITLE = "B & K Academy PLT (202504000011 / LLP0041499-LGN)"
MONTHS = ["2026-08", "2026-09", "2026-10"]
MONTH_LABELS = {"2026-08": ("Aug 2026", "31/08/2026"), "2026-09": ("Sep 2026", "30/09/2026"), "2026-10": ("Oct 2026", "31/10/2026")}

# code, name, account type, special type, parent, section in the TB
COA = [
    ("100-0000", "Partners' Capital",                 "Capital",                  "CAP", None,       "EQUITY"),
    ("150-0000", "Retained Earnings",                 "Retained Earning",         "RE",  None,       "EQUITY"),
    ("200-0000", "Office Equipment",                  "Fixed Asset",              "FA",  None,       "FIXED ASSETS"),
    ("200-0100", "Accum. Depreciation - Office Equipment", "Accumulated Depreciation", "AD", "200-0000", "FIXED ASSETS"),
    ("300-0000", "Maybank Current Account",           "Bank",                     "BA",  None,       "CURRENT ASSETS"),
    ("300-1000", "CIMB Current Account",              "Bank",                     "BA",  None,       "CURRENT ASSETS"),
    ("300-2000", "Petty Cash",                        "Cash",                     None,  None,       "CURRENT ASSETS"),
    ("310-0000", "Trade Debtors",                     "Debtor Control",           "DC",  None,       "CURRENT ASSETS"),
    ("320-0000", "Deposits & Prepayments",            "Current Asset",            None,  None,       "CURRENT ASSETS"),
    ("400-0000", "Trade Creditors",                   "Creditor Control",         "CC",  None,       "CURRENT LIABILITIES"),
    ("410-0000", "Accruals",                          "Current Liability",        None,  None,       "CURRENT LIABILITIES"),
    ("420-0000", "SST Payable",                       "Current Liability",        None,  None,       "CURRENT LIABILITIES"),
    ("430-0000", "Amount Due to Director",            "Current Liability",        None,  None,       "CURRENT LIABILITIES"),
    ("450-0000", "Term Loan - Maybank",               "Long Term Liability",      "LTL", None,       "LONG TERM LIABILITIES"),
    ("500-0000", "Training Income",                   "Sales",                    "SA",  None,       "SALES"),
    ("510-0000", "Consultancy Fees",                  "Sales",                    None,  None,       "SALES"),
    ("600-0000", "Trainer Fees",                      "Cost of Goods Sold",       "CS",  None,       "COST OF SALES"),
    ("610-0000", "Venue & Catering",                  "Cost of Goods Sold",       None,  None,       "COST OF SALES"),
    ("800-0000", "Interest Income",                   "Other Income",             "OI",  None,       "OTHER INCOME"),
    ("900-0000", "Salaries & EPF",                    "Expenses",                 "EXP", None,       "EXPENSES"),
    ("901-0000", "Rent",                              "Expenses",                 None,  None,       "EXPENSES"),
    ("902-0000", "Depreciation",                      "Expenses",                 None,  None,       "EXPENSES"),
    ("903-0000", "Marketing",                         "Expenses",                 None,  None,       "EXPENSES"),
    ("904-0000", "Bank Charges",                      "Expenses",                 None,  None,       "EXPENSES"),
    ("905-0000", "HRD Corp Levy",                     "Mystery Type",             None,  None,       "EXPENSES"),
    ("950-0000", "Interest Expense",                  "Expenses",                 None,  None,       "EXPENSES"),
    ("960-0000", "Taxation",                          "Taxation",                 "TAX", None,       "TAXATION"),
]
# only in the TB (not in the chart export), Aug only, under CURRENT ASSETS
TB_ONLY = ("990-0000", "Suspense Account", "CURRENT ASSETS")

# closing balances, debit positive, per month (Maybank 300-0000 is the plug)
BAL: dict[str, list[Decimal]] = {k: [Decimal(x) for x in v] for k, v in {
    "100-0000": ["-50000", "-50000", "-50000"],
    "150-0000": ["-86000", "-86000", "-86000"],
    "200-0000": ["64000", "64000", "64000"],
    "200-0100": ["-12000", "-12700", "-13400"],
    "300-1000": ["23000.50", "24500.25", "21000.00"],
    "300-2000": ["500", "500", "500"],
    "310-0000": ["42000", "45500", "51200"],
    "320-0000": ["15000", "15000", "15000"],
    "400-0000": ["-18000", "-16500", "-19800"],
    "410-0000": ["-9800", "-9800", "-9800"],
    "420-0000": ["-3600", "-4100", "-4800"],
    "430-0000": ["-20000", "-20000", "-20000"],
    "450-0000": ["-40000", "-39000", "-38000"],
    "500-0000": ["-620000", "-705000", "-790000"],
    "510-0000": ["-80000", "-92000", "-101000"],
    "600-0000": ["260000", "296000", "331000"],
    "610-0000": ["70000", "79000", "88000"],
    "800-0000": ["-1200", "-1350", "-1500"],
    "900-0000": ["224000", "252000", "280000"],
    "901-0000": ["62400", "70200", "78000"],
    "902-0000": ["5600", "6300", "7000"],
    "903-0000": ["38000", "42500", "47000"],
    "904-0000": ["960", "1080", "1200"],
    "905-0000": ["6000", "6750", "7500"],
    "950-0000": ["2400", "2650", "2900"],
    "960-0000": ["8000", "8000", "8000"],
    "990-0000": ["150", "0", "0"],
}.items()}
for i in range(3):
    BAL.setdefault("300-0000", [Decimal(0)] * 3)
    BAL["300-0000"][i] = -sum(v[i] for k, v in BAL.items() if k != "300-0000")

SECTIONS = ["EQUITY", "FIXED ASSETS", "CURRENT ASSETS", "CURRENT LIABILITIES", "LONG TERM LIABILITIES",
            "SALES", "COST OF SALES", "OTHER INCOME", "EXPENSES", "TAXATION"]


def expected_closing(code: str, month: str) -> Decimal:
    return BAL[code][MONTHS.index(month)]


def _amt_text(d: Decimal, style: int) -> object:
    """Alternate between a real number and the text forms seen in exports."""
    if d == 0:
        return None
    if style % 3 == 0:
        return float(d)
    if style % 3 == 1:
        return f"{d:,.2f}"
    return f"{d:,.2f}"


def _tb_lines(month: str):
    """Yield (kind, payload) in AutoCount order: section, account rows, subtotal."""
    i = MONTHS.index(month)
    for sec in SECTIONS:
        rows = [(c, n) for c, n, *_rest, s in COA if s == sec]
        if sec == TB_ONLY[2] and BAL[TB_ONLY[0]][i] != 0:
            rows.append((TB_ONLY[0], TB_ONLY[1]))
        yield "section", sec
        sub = Decimal(0)
        for c, n in rows:
            v = BAL[c][i]
            sub += v
            yield "row", (c, n, v)
        yield "subtotal", (f"Total {sec.title()}", sub)


def write_tb_month(path: Path, month: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Trial Balance"
    label, asat = MONTH_LABELS[month]
    ws.append([ENTITY_TITLE])
    ws.append(["Trial Balance"])
    ws.append([f"As At {asat}"])
    ws.append([])
    ws.merge_cells("A1:D1"); ws.merge_cells("A2:D2"); ws.merge_cells("A3:D3")
    ws.append(["Account No.", "Description", "Debit", "Credit"])  # row 5
    ws["A5"].font = Font(bold=True)
    tot_dr = tot_cr = Decimal(0)
    style = 0
    for kind, payload in _tb_lines(month):
        if kind == "section":
            ws.append([None, payload])
        elif kind == "subtotal":
            name, sub = payload
            ws.append([None, name, float(sub) if sub > 0 else None, float(-sub) if sub < 0 else None])
        else:
            code, name, v = payload
            style += 1
            if code == "200-0100":
                # contra asset shown in the debit column in parentheses
                ws.append([code, name, f"({-v:,.2f})", None])
                tot_dr += v
            elif code == "430-0000":
                ws.append([code, name, None, f"{-v:,.2f} CR"])  # CR suffix in the credit column
                tot_cr += -v
            elif v >= 0:
                ws.append([code, name, _amt_text(v, style), "-"])
                tot_dr += v
            else:
                ws.append([code, name, "-", _amt_text(-v, style)])
                tot_cr += -v
    ws.append([])
    ws.append([None, "TOTAL", f"{tot_dr:,.2f}", f"{tot_cr:,.2f}"])
    wb.save(path)


def write_tb_multi(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "TB"
    ws.append([ENTITY_TITLE])
    ws.append(["Trial Balance - Comparative"])
    ws.append(["For the months Aug 2026 to Oct 2026"])
    ws.merge_cells("A1:H1"); ws.merge_cells("A2:H2"); ws.merge_cells("A3:H3")
    head1 = [None, None]
    for m in MONTHS:
        head1 += [MONTH_LABELS[m][0], None]
    ws.append(head1)                                                     # row 4: month labels (merged pairs)
    ws.append(["Account No", "Account Description", "Debit", "Credit", "Debit", "Credit", "Debit", "Credit"])  # row 5
    ws.merge_cells("C4:D4"); ws.merge_cells("E4:F4"); ws.merge_cells("G4:H4")
    codes = [c for c, *_ in COA] + [TB_ONLY[0]]
    names = {c: n for c, n, *_ in COA}
    names[TB_ONLY[0]] = TB_ONLY[1]
    for code in codes:
        row = [code, names[code]]
        for i in range(3):
            v = BAL[code][i]
            row += [f"{v:,.2f}" if v > 0 else None, f"{-v:,.2f}" if v < 0 else None]
        if all(x is None for x in row[2:]):
            continue
        ws.append(row)
    tot = ["", "Grand Total"]
    for i in range(3):
        tot += [float(sum(v[i] for v in BAL.values() if v[i] > 0)), float(-sum(v[i] for v in BAL.values() if v[i] < 0))]
    ws.append(tot)
    wb.save(path)


def write_coa(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Chart of Account"
    ws.append([ENTITY_TITLE])
    ws.append(["Chart of Accounts"])
    ws.append(["Printed: 03/11/2026"])
    ws.append([])
    ws.append(["Account No", "Account Name", "Account Type", "Special Account Type", "Parent Account", "Active"])
    for code, name, t, st, parent, _sec in COA:
        ws.append([code, name, t, st, parent, "Yes"])
    wb.save(path)


AR = [  # code, name, current, 1-30, 31-60, 61-90, >90  (fictitious)
    ("D001", "Fictitious Client Alpha Sdn Bhd", "12,500.00", "4,200.00", "0.00", "0.00", "0.00"),
    ("D002", "Fictitious Client Beta Bhd",       "8,000.00",  "3,100.00", "1,900.00", "0.00", "0.00"),
    ("D003", "Fictitious Client Gamma PLT",      "5,300.00",  "0.00",     "0.00",     "2,400.00", "1,800.00"),
    ("D004", "Fictitious Client Delta Enterprise", "(500.00)", "0.00",    "0.00",     "0.00", "0.00"),
    ("D005", "Fictitious Client Epsilon Sdn Bhd", "6,000.00", "2,000.00", "0.00",     "0.00", "4,500.00"),
    ("D006", "Fictitious Client Zeta Academy",   "0.00",      "0.00",     "0.00",     "0.00", "0.00"),
]
AR_EXTRA_LINE = ("D001", "Fictitious Client Alpha Sdn Bhd", "1,000.00", "0.00", "0.00", "0.00", "0.00")  # second line, same debtor
AR_TOTAL_BY_CODE = {
    "D001": Decimal("17700.00"), "D002": Decimal("13000.00"), "D003": Decimal("9500.00"),
    "D004": Decimal("-500.00"), "D005": Decimal("12500.00"),
}


def write_ar_aging(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Debtor Aging"
    ws.append([ENTITY_TITLE])
    ws.append(["Debtor Aging Report"])
    ws.append(["As At 31/10/2026"])
    ws.append([])
    ws.merge_cells("A1:H1"); ws.merge_cells("A2:H2"); ws.merge_cells("A3:H3")
    ws.append(["Debtor Code", "Debtor Name", "Total", "Aging", None, None, None, None])     # row 5
    ws.append([None, None, None, "Current", "1 - 30", "31 - 60", "61 - 90", "> 90"])        # row 6
    ws.merge_cells("D5:H5"); ws.merge_cells("A5:A6"); ws.merge_cells("B5:B6"); ws.merge_cells("C5:C6")
    rows = list(AR)
    rows.insert(1, AR_EXTRA_LINE)
    def dec(s): return Decimal(s.replace(",", "").replace("(", "-").replace(")", ""))
    g = [Decimal(0)] * 5
    for code, name, *b in rows:
        if all(dec(x) == 0 for x in b):
            continue  # AutoCount hides zero-balance debtors; D006 never appears
        vals = [dec(x) for x in b]
        g = [a + c for a, c in zip(g, vals)]
        ws.append([code, name, f"{sum(vals):,.2f}", *b])
    ws.append([])
    ws.append([None, "Grand Total", f"{sum(g):,.2f}", *[f"{x:,.2f}" for x in g]])
    wb.save(path)


AP = [  # code, name, not due, 1-30, 31-60, 61-90, 91-120, over 120
    ("C001", "Fictitious Trainer Services Sdn Bhd", "9,800.00", "3,500.00", "0.00", "0.00", "0.00", "0.00"),
    ("C002", "Fictitious Venue & Catering Sdn Bhd", "4,200.00", "0.00", "1,300.00", "0.00", "0.00", "0.00"),
    ("C003", "Fictitious IT Services Enterprise",   "0.00", "0.00", "0.00", "600.00", "250.00", "150.00"),
]


def write_ap_aging_csv(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([ENTITY_TITLE])
        w.writerow(["Creditor Aging Report"])
        w.writerow(["As at 31 Oct 2026", "", "", "", "", "", "", "", "Page 1"])
        w.writerow([])
        w.writerow(["Supplier Code", "Supplier Name", "Outstanding", "Not Due", "1-30 Days", "31-60 Days", "61-90 Days", "91-120 Days", "Over 120 Days"])
        tot = [Decimal(0)] * 6
        for code, name, *b in AP:
            vals = [Decimal(x.replace(",", "")) for x in b]
            tot = [a + c for a, c in zip(tot, vals)]
            w.writerow([code, name, f"{sum(vals):,.2f}", *b])
        w.writerow(["", "Total", f"{sum(tot):,.2f}", *[f"{x:,.2f}" for x in tot]])


def write_bank(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Bank Reconciliation"
    ws.append([ENTITY_TITLE])
    ws.append(["Bank Reconciliation Summary"])
    ws.append(["As At 31/10/2026"])
    ws.append([])
    ws.append(["Account No", "Bank Account", "Bank Account No", "Book Balance", "Statement Balance"])
    ws.append(["300-0000", "Maybank Current Account", "5141 2345 6789", f"{BAL['300-0000'][2]:,.2f}", f"{BAL['300-0000'][2] + 1500:,.2f}"])
    ws.append(["300-1000", "CIMB Current Account", "8001234567", float(BAL["300-1000"][2]), float(BAL["300-1000"][2])])
    ws.append([])
    ws.append([None, "Total", None, f"{BAL['300-0000'][2] + BAL['300-1000'][2]:,.2f}", None])
    wb.save(path)


def write_account_map(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["account_code", "account_type", "account_subtype", "cashflow_bucket", "is_current", "note"])
        w.writerow(["990-0000", "asset", "other_receivable", "operating", "true", "owner confirmed: suspense is a receivable"])
        w.writerow(["905-0000", "opex", "", "operating", "", "HRD Corp levy is an operating expense"])


def make_all(folder: Path) -> dict[str, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}
    for m in MONTHS:
        p = folder / f"TB {MONTH_LABELS[m][0]}.xlsx"
        write_tb_month(p, m)
        files[f"tb_{m}"] = p
    files["tb_multi"] = folder / "TB Aug-Oct 2026 comparative.xlsx"
    write_tb_multi(files["tb_multi"])
    files["coa"] = folder / "Chart of Accounts.xlsx"
    write_coa(files["coa"])
    files["ar"] = folder / "Debtor Aging 31-10-2026.xlsx"
    write_ar_aging(files["ar"])
    files["ap"] = folder / "Creditor Aging.csv"
    write_ap_aging_csv(files["ap"])
    files["bank"] = folder / "Bank Reconciliation Summary.xlsx"
    write_bank(files["bank"])
    files["account_map"] = folder / "account_map.csv"
    write_account_map(files["account_map"])
    return files


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures")
    for k, v in make_all(target).items():
        print(f"{k:<12} {v}")
