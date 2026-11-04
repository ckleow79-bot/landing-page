#!/usr/bin/env python3
"""
AutoCount Cloud Accounting report exports (Excel / CSV) -> finance warehouse.

Heuristic, forgiving importer for the five reports the dashboard needs:
  Trial Balance (one file per month-end, or one file with month columns),
  Chart of Accounts, Debtor Aging, Creditor Aging, Bank balances.

AutoCount exports carry title rows above the real header, merged header cells,
section and subtotal rows, and amounts as text ("1,234.56", "(1,234.56)",
"1,234.56 CR"). Nothing here assumes a fixed column layout: the header row is
detected by scanning the first ~30 rows, columns are mapped by synonyms, and a
mapping report is produced BEFORE anything is written.

Usage
  # 1) inspect: mapping report on the console + normalised CSVs in ./out
  python import_autocount_exports.py --entity BKAC --fye-month 12 \
      --tb "TB Aug 2026.xlsx" "TB Sep 2026.xlsx" "TB Oct 2026.xlsx=2026-10" \
      --coa coa.xlsx --ar-aging debtor_aging.xlsx --ap-aging creditor_aging.xlsx \
      --bank bank_book.xlsx --as-of 2026-10-31 --dry-run

  # 2) load: same arguments plus --write, DATABASE_URL in the environment
  DATABASE_URL=postgresql://... python import_autocount_exports.py ... --write

Writes (only with --write): entities (ensure row), fiscal_periods,
chart_of_accounts, gl_balances, ar_aging, ap_aging, bank_balances, all by the
natural keys in 001_finance_schema.sql, in one transaction, logged in
ingestion_runs (source 'excel_import' once migration 004 is applied). Rows are
never deleted.

Console output stays at aggregate level: counterparty names never appear in
the report (they do appear in the CSVs under --out and in the database).
"""
from __future__ import annotations

import argparse
import calendar
import csv
import io
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

try:
    from dotenv import load_dotenv
except ImportError:  # optional
    load_dotenv = None

HERE = Path(__file__).resolve().parent
ZERO = Decimal("0.00")
CENT = Decimal("0.01")
HEADER_SCAN_ROWS = 30
BUCKETS = ("bucket_current", "bucket_30", "bucket_60", "bucket_90", "bucket_120_plus")
PL_TYPES = {"revenue", "cogs", "opex", "other"}
ACCOUNT_TYPES = ("asset", "liability", "equity", "revenue", "cogs", "opex", "other")
CASHFLOW_BUCKETS = ("cash", "operating", "investing", "financing", "non_cash")
SUBTYPES = ("cash", "trade_receivable", "other_receivable", "inventory", "fixed_asset",
            "trade_payable", "other_payable", "accrual", "borrowing", "tax_payable",
            "share_capital", "retained_earnings",
            "depreciation", "amortisation", "interest", "tax", "other")

# Public identifiers only (see dashboard/README.md entity register). Used to
# create the entities row when it does not exist yet.
KNOWN_ENTITIES = {
    "BKAC": {"name": "B & K Academy PLT", "registration_no": "202504000011 (LLP0041499-LGN)", "msic": "85499"},
    "BKA":  {"name": "B & K Advisory PLT", "registration_no": "201604001561 (LLP0008273-LGN)", "msic": "70201"},
    "BKTS": {"name": "B & K Training Services PLT", "registration_no": "LLP0046779-LGN", "msic": None},
}


# =============================================================================
# 1. Low-level parsing: numbers, dates, text
# =============================================================================
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_name) if m})
MONTHS.update({"sept": 9})

_NUM_CLEAN = re.compile(r"[,\s ]")
_NUM_RE = re.compile(r"^[-+]?\d+(\.\d+)?$")


def norm_text(v: Any) -> str:
    """Lower-cased, single-spaced text for matching."""
    if v is None:
        return ""
    s = str(v).replace("\n", " ").replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def clean_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return re.sub(r"\s+", " ", str(v)).strip()


def parse_number(v: Any) -> Decimal | None:
    """Parse an amount cell. Returns None for blank / dash / non-numeric text.

    Accepts: 1234.5, "1,234.56", "(1,234.56)", "-1,234.56", "1,234.56-",
    "1,234.56 CR", "1,234.56 DR", "RM 1,234.56", "MYR1,234.56", "-", "–", "".
    CR suffix is treated as negative (credit) and DR as positive.
    """
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float, Decimal)):
        try:
            return Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP)
        except InvalidOperation:
            return None
    if isinstance(v, (date, datetime)):
        return None
    s = str(v).strip()
    if s in ("", "-", "–", "—", "nil", "NIL", "n/a", "N/A"):
        return None
    neg = False
    up = s.upper().replace(" ", " ")
    if up.endswith(" CR") or up.endswith("CR"):
        tail = up[-2:]
        if tail == "CR" and (len(up) == 2 or not up[-3].isalpha()):
            neg, up = True, up[:-2].strip()
    if up.endswith(" DR") or (up.endswith("DR") and (len(up) == 2 or not up[-3].isalpha())):
        up = up[:-2].strip()
    up = re.sub(r"^(RM|MYR|USD|SGD|\$)\s*", "", up)
    if up.startswith("(") and up.endswith(")"):
        neg, up = not neg, up[1:-1].strip()
    if up.endswith("-"):
        neg, up = not neg, up[:-1].strip()
    if up.startswith("−"):  # unicode minus
        neg, up = not neg, up[1:].strip()
    up = _NUM_CLEAN.sub("", up)
    if up.startswith("-"):
        neg, up = not neg, up[1:]
    if up.startswith("+"):
        up = up[1:]
    if not _NUM_RE.match(up):
        return None
    try:
        d = Decimal(up).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    return -d if neg else d


def _suffix(v: Any) -> str | None:
    if isinstance(v, str):
        m = re.search(r"\b(CR|DR)\.?\s*$", v.strip().upper())
        return m[1] if m else None
    return None


def parse_cell(v: Any, role: str | None) -> Decimal | None:
    """parse_number, but a 'CR' suffix inside a Credit column (or 'DR' in a
    Debit column) restates the column rather than flipping the sign."""
    d = parse_number(v)
    if d is None:
        return None
    sfx = _suffix(v)
    if role == "credit" and sfx == "CR":
        return -d
    if role == "debit" and sfx == "DR":
        return d
    if role == "credit" and sfx == "DR":
        return -d
    return d


def is_amount_cell(v: Any) -> bool:
    """True when a cell is an amount (not a small bucket label like 30/60/90)."""
    if isinstance(v, bool) or v is None:
        return False
    d = parse_number(v)
    if d is None:
        return False
    if isinstance(v, str) and not re.search(r"[.,()]", v) and d == d.to_integral_value() and 0 <= d <= 400:
        return False  # "30", "60", "90", "120" header labels
    if not isinstance(v, str) and d == d.to_integral_value() and 0 < d <= 400 and d % 30 == 0:
        return False
    return True


_DATE_PATTERNS = [
    # 31/10/2026, 31-10-2026, 31.10.2026 (day first, Malaysian convention)
    (re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b"), "dmy"),
    # 2026-10-31
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "ymd"),
    # 31 Oct 2026 / 31 October 2026 / 31st Oct, 2026
    (re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b"), "dMy"),
    # October 31, 2026
    (re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b"), "Mdy"),
    # Oct 2026 / October 2026 / Oct-2026 / Oct'26 / Oct-26 / Oct 26
    (re.compile(r"\b([A-Za-z]{3,9})\.?[\s\-'/]*(\d{4}|\d{2})\b"), "My"),
    # 2026-10 / 2026/10
    (re.compile(r"\b(\d{4})[-/](\d{1,2})\b(?![-/]\d)"), "ym"),
    # 10/2026
    (re.compile(r"\b(\d{1,2})[/\-](\d{4})\b"), "my"),
]


def find_dates(text: str) -> list[date]:
    """All dates mentioned in text (month-only mentions become the month end)."""
    out: list[date] = []
    if not text:
        return out
    text = text.replace("_", " ")
    for rx, kind in _DATE_PATTERNS:
        for m in rx.finditer(text):
            try:
                if kind == "dmy":
                    d, mo, y = int(m[1]), int(m[2]), int(m[3])
                    if mo > 12 and d <= 12:
                        d, mo = mo, d
                    out.append(date(y, mo, d))
                elif kind == "ymd":
                    out.append(date(int(m[1]), int(m[2]), int(m[3])))
                elif kind == "dMy":
                    mo = MONTHS.get(m[2].lower())
                    if mo:
                        out.append(date(int(m[3]), mo, int(m[1])))
                elif kind == "Mdy":
                    mo = MONTHS.get(m[1].lower())
                    if mo:
                        out.append(date(int(m[3]), mo, int(m[2])))
                elif kind == "My":
                    mo = MONTHS.get(m[1].lower())
                    if mo:
                        y = int(m[2])
                        y = y + 2000 if y < 100 else y
                        if 1990 <= y <= 2100:
                            out.append(month_end(date(y, mo, 1)))
                elif kind == "ym":
                    y, mo = int(m[1]), int(m[2])
                    if 1 <= mo <= 12 and 1990 <= y <= 2100:
                        out.append(month_end(date(y, mo, 1)))
                elif kind == "my":
                    mo, y = int(m[1]), int(m[2])
                    if 1 <= mo <= 12 and 1990 <= y <= 2100:
                        out.append(month_end(date(y, mo, 1)))
            except ValueError:
                continue
    return out


def cell_date(v: Any) -> date | None:
    """A date held in a cell: real datetime, or text with exactly one date."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        ds = find_dates(v)
        if ds:
            return max(ds)
    return None


def month_start(d: date) -> date:
    return d.replace(day=1)


def month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def parse_period(s: str) -> date:
    """'2026-10' | '2026/10' | 'Oct 2026' | '31/10/2026' -> first day of that month."""
    ds = find_dates(s.strip())
    if not ds:
        raise argparse.ArgumentTypeError(f"cannot read a month from {s!r} (use YYYY-MM)")
    return month_start(max(ds))


def fiscal_year_start(d: date, fye_month: int) -> date:
    fy_start_month = fye_month % 12 + 1
    if fye_month == 12:
        return date(d.year, 1, 1)
    y = d.year if d.month >= fy_start_month else d.year - 1
    return date(y, fy_start_month, 1)


def fiscal_year_label(d: date, fye_month: int) -> int:
    return d.year + 1 if d.month > fye_month else d.year


def period_no(d: date, fye_month: int) -> int:
    return ((d.month - fye_month - 1 + 12) % 12) + 1


def fmt_amt(d: Decimal | None) -> str:
    if d is None:
        return "-"
    return f"{d:,.2f}"


# =============================================================================
# 2. Loading a sheet into a plain grid (list of rows, each a list of cells)
# =============================================================================
@dataclass
class Grid:
    path: Path
    sheet: str
    rows: list[list[Any]]
    merged_ranges: int = 0

    @property
    def ncols(self) -> int:
        return max((len(r) for r in self.rows), default=0)


def load_grid(path: Path, sheet: str | None = None) -> Grid:
    """Read the first (or named) sheet of an .xlsx/.xlsm, or a CSV/TSV/TXT file.

    Merged cells are expanded (every cell of a merged range gets the anchor's
    value) so a merged 'Aging' label above 'Current | 1-30 | ...' reaches each
    column. Formulas are read as their cached values (data_only=True).
    """
    suffix = path.suffix.lower()
    if suffix in (".csv", ".txt", ".tsv"):
        raw = path.read_bytes()
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel_tab if suffix == ".tsv" else csv.excel
        rows = [list(r) for r in csv.reader(io.StringIO(text), dialect)]
        return Grid(path, "csv", rows)
    if suffix == ".xls":
        raise SystemExit(f"{path.name}: legacy .xls is not supported; re-save as .xlsx or export CSV")
    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True, read_only=False)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    if sheet is None and len(wb.worksheets) > 1:
        # pick the first sheet that has something in it
        for cand in wb.worksheets:
            if cand.max_row and cand.max_column and any(c.value is not None for row in cand.iter_rows(max_row=min(cand.max_row, 40)) for c in row):
                ws = cand
                break
    rows: list[list[Any]] = [[c for c in r] for r in ws.iter_rows(values_only=True)]
    merged = list(ws.merged_cells.ranges)
    for rng in merged:
        anchor = rows[rng.min_row - 1][rng.min_col - 1] if rng.min_row - 1 < len(rows) and rng.min_col - 1 < len(rows[rng.min_row - 1]) else None
        if anchor is None:
            continue
        for r in range(rng.min_row - 1, min(rng.max_row, len(rows))):
            row = rows[r]
            for c in range(rng.min_col - 1, rng.max_col):
                if c < len(row) and row[c] is None:
                    row[c] = anchor
    return Grid(path, ws.title, rows, len(merged))


# =============================================================================
# 3. Column roles and header detection
# =============================================================================
# role -> list of regexes matched against the normalised header label.
# Order within the list does not matter; the FIRST ROLE whose pattern matches
# wins, so specific roles come before generic ones in ROLE_ORDER.
ROLE_PATTERNS: dict[str, list[str]] = {
    "counterparty_code": [r"\b(debtor|customer|supplier|creditor|vendor)\s*(code|no\.?|id)\b", r"\bcust(omer)?\s*code\b"],
    "counterparty_name": [r"\b(debtor|customer|supplier|creditor|vendor|company)\s*name\b", r"\bbusiness name\b"],
    "bank_account_no":   [r"\b(bank\s*)?(account|acc|a/c)\s*(no|number|num)\b.*bank|\bbank\s*(account|acc|a/c)\s*(no|number|num)\b"],
    "bank_name":         [r"^bank( name)?$", r"\bbank\s*name\b", r"\bbank\b.*\bname\b", r"^bank\s*(account|acc|a/c)?\s*(name|description)?$"],
    "opening":           [r"\bopening\b", r"\bb/f\b", r"\bbrought forward\b", r"\bbeginning\b"],
    "account_type":      [r"\bspecial\s*(account|acc)?\s*type\b", r"\b(account|acc|a/c)\s*type\b", r"^type$", r"\bnature\b", r"\bcategory\b", r"\bclass(ification)?\b"],
    "parent":            [r"\bparent\b", r"\bgroup\s*(account|acc)\b"],
    "currency":          [r"^curr(ency)?(\s*code)?$"],
    "account_code":      [r"\b(account|acc|a/c|gl)\.?\s*(no|number|code|num)\b", r"^(acc|account|a/c|gl)\.?\s*(no\.?)?$", r"^code$", r"\baccno\b"],
    "name":              [r"\bdescription\b", r"\b(account|acc|a/c)\s*name\b", r"^name$", r"\bparticulars\b", r"^desc\.?$", r"\baccount\b.*\bname\b"],
    "debit":             [r"\bdebit\b", r"^dr\.?$", r"\bdr\b"],
    "credit":            [r"\bcredit\b", r"^cr\.?$", r"\bcr\b"],
    "total":             [r"\b(grand\s*)?total\b", r"\boutstanding\b", r"\bamount due\b", r"\bnet\b"],
    "bucket":            [r"^current$", r"\bnot (yet )?due\b", r"\b\d{1,3}\s*-\s*\d{1,3}\b", r"\b\d{1,3}\s*to\s*\d{1,3}\b", r"[>+]\s*\d+|\d+\s*\+|\bover\s*\d+|\babove\s*\d+|\d+\s*(days?)?\s*(and|&)\s*(above|over|more)",
                          r"^\d{2,3}(\s*days?)?$", r"\b\d\s*months?\b", r"\b(one|two|three|four)\s*months?\b"],
    "balance":           [r"\bbalance\b", r"\bclosing\b", r"\bamount\b", r"\bytd\b", r"\bc/f\b", r"\bcarried forward\b"],
}
ROLE_ORDER = ["counterparty_code", "counterparty_name", "bank_account_no", "bank_name", "opening", "account_type",
              "parent", "currency", "account_code", "name", "debit", "credit", "bucket", "total", "balance"]
_ROLE_RX = {role: [re.compile(p) for p in pats] for role, pats in ROLE_PATTERNS.items()}
# tokens that count towards "this row is a header"
HEADER_TOKENS = ["account_code", "name", "debit", "credit", "balance", "counterparty_code", "counterparty_name",
                 "bank_name", "bucket", "total", "account_type", "opening"]
TITLE_WORDS = re.compile(r"\b(as at|as of|report|trial balance|aging|ageing|chart of account|period|from .* to|page \d|printed|print date|company|sdn|bhd|plt|llp)\b")


def label_role(label: str) -> str | None:
    n = norm_text(label)
    if not n:
        return None
    for role in ROLE_ORDER:
        for rx in _ROLE_RX[role]:
            if rx.search(n):
                return role
    return None


def _row_labels(row: list[Any]) -> list[str]:
    return [clean_str(c) for c in row]


def header_score(row: list[Any]) -> tuple[int, set[str]]:
    roles: set[str] = set()
    for c in row:
        if c is None:
            continue
        if is_amount_cell(c):
            continue
        r = label_role(clean_str(c))
        if r in HEADER_TOKENS:
            roles.add(r)
    return len(roles), roles


def _is_title_row(row: list[Any]) -> bool:
    vals = [clean_str(c) for c in row if clean_str(c)]
    distinct = {v for v in vals}
    if len(distinct) <= 1 and vals:
        return bool(TITLE_WORDS.search(norm_text(vals[0]))) or bool(find_dates(vals[0]))
    return False


def _row_has_amounts(row: list[Any]) -> bool:
    return any(is_amount_cell(c) for c in row)


@dataclass
class Column:
    idx: int
    label: str
    role: str | None
    period: date | None = None      # for TB month columns ("Aug 2026 Debit")
    bucket: str | None = None       # for aging bucket columns

    def describe(self) -> str:
        extra = ""
        if self.period:
            extra += f" period={self.period:%Y-%m}"
        if self.bucket:
            extra += f" -> {self.bucket}"
        return f"col{self.idx + 1} {self.label!r} -> {self.role or '(ignored)'}{extra}"


@dataclass
class Header:
    row_idx: int                 # index of the (lower) header row in grid.rows
    merged_with: int | None      # index of the neighbouring row merged into the labels
    columns: list[Column]
    data_start: int
    score: int
    title_text: str              # everything above the header, for period / as-of detection

    def col(self, role: str) -> Column | None:
        for c in self.columns:
            if c.role == role:
                return c
        return None

    def cols(self, role: str) -> list[Column]:
        return [c for c in self.columns if c.role == role]


def detect_header(grid: Grid, min_score: int = 2) -> Header | None:
    """Find the header row in the first HEADER_SCAN_ROWS rows.

    Picks the row with the most distinct header tokens (ties -> earliest). If
    the row directly above or below also looks like a header fragment (>= 2
    labels, no amounts, not a title), the two are merged label-wise, which
    handles 'Aging' over 'Current | 1-30 | ...' and 'Aug 2026' over
    'Debit | Credit'.
    """
    best: tuple[int, int, set[str]] | None = None
    limit = min(len(grid.rows), HEADER_SCAN_ROWS)
    for i in range(limit):
        row = grid.rows[i]
        if _row_has_amounts(row) and sum(1 for c in row if is_amount_cell(c)) >= 2:
            continue  # data rows are not headers
        score, roles = header_score(row)
        if score >= min_score and (best is None or score > best[0]):
            best = (score, i, roles)
    if best is None:
        return None
    score, hi, roles = best
    header = list(grid.rows[hi])
    merged_with = None

    key_cols = [i for i, c in enumerate(header)
                if label_role(clean_str(c)) in ("account_code", "counterparty_code", "name", "counterparty_name", "bank_name")]

    def fragment(j: int) -> bool:
        if j < 0 or j >= len(grid.rows):
            return False
        r = grid.rows[j]
        labels = [clean_str(c) for c in r if clean_str(c)]
        if len(set(labels)) < 2 or _row_has_amounts(r) or _is_title_row(r):
            return False
        for i in key_cols:  # a value under 'Account No' that is not itself a label = data row
            v = clean_str(r[i]) if i < len(r) else ""
            if v and (label_role(v) in (None, "bucket")):
                return False
        # a neighbour that is itself a plausible header fragment (bucket labels, dates, debit/credit, ...)
        frag_score, frag_roles = header_score(r)
        return frag_score >= 1 or any(find_dates(l) for l in labels)

    lower = hi
    for j in (hi + 1, hi - 1):
        if fragment(j):
            other = grid.rows[j]
            upper_row, lower_row = (header, other) if j > hi else (other, header)
            width = max(len(upper_row), len(lower_row))
            combined: list[Any] = []
            for c in range(width):
                u = clean_str(upper_row[c]) if c < len(upper_row) else ""
                l = clean_str(lower_row[c]) if c < len(lower_row) else ""
                if u and l and norm_text(u) != norm_text(l):
                    combined.append(f"{u} {l}")
                else:
                    combined.append(u or l)
            header = combined
            merged_with = j
            lower = max(hi, j)
            break

    columns: list[Column] = []
    for idx, lab in enumerate(header):
        label = clean_str(lab)
        role = label_role(label) if label else None
        col = Column(idx=idx, label=label, role=role)
        ds = find_dates(label)
        if ds and role in ("debit", "credit", "balance", "bucket", "total", None) and label:
            col.period = month_start(max(ds))
            if role is None:
                col.role = "balance"   # bare month column holds balances
        columns.append(col)
    title_text = " | ".join(clean_str(c) for i in range(min(hi, merged_with if merged_with is not None else hi))
                            for c in grid.rows[i] if clean_str(c))
    return Header(row_idx=hi, merged_with=merged_with, columns=columns, data_start=lower + 1, score=score,
                  title_text=title_text)


# ---- aging bucket labels ----------------------------------------------------
_WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def bucket_for_label(label: str, as_of: date | None = None) -> str | None:
    """Map an aging column label to a schema bucket.

    'Current'/'Not due' -> bucket_current; ranges by upper bound (1-30 -> 30,
    31-60 -> 60, 61-90 -> 90, anything above 90 -> 120_plus); '>90', '90+',
    'over 120' -> 120_plus; '1 month' -> 30 ... '4 months & above' -> 120_plus.
    Month-name columns (AutoCount can age by invoice month) are mapped by
    distance from as_of: same month -> current, 1 month back -> 30, ...
    """
    n = norm_text(label)
    if not n:
        return None
    if re.search(r"\bcurrent\b|\bnot (yet )?due\b", n):
        return "bucket_current"
    if re.search(r"\b(grand\s*)?total\b|\boutstanding\b", n):
        return None
    m = re.search(r"\b(\d{1,3})\s*(?:-|to|–)\s*(\d{1,3})\b", n)
    if m:
        hi = int(m[2])
        return "bucket_30" if hi <= 30 else "bucket_60" if hi <= 60 else "bucket_90" if hi <= 90 else "bucket_120_plus"
    m = re.search(r"(?:>|over|above|more than)\s*(\d+)|(\d+)\s*\+|(\d+)\s*(?:days?)?\s*(?:and|&)\s*(?:above|over|more)", n)
    if m:
        lo = int(next(g for g in m.groups() if g))
        return "bucket_120_plus" if lo >= 90 else "bucket_90" if lo >= 60 else "bucket_60" if lo >= 30 else "bucket_30"
    m = re.search(r"\b(\d+|one|two|three|four|five|six)\s*months?\b", n)
    if m:
        k = _WORD_NUM.get(m[1], None) or int(m[1])
        return {1: "bucket_30", 2: "bucket_60", 3: "bucket_90"}.get(k, "bucket_120_plus") if k > 0 else "bucket_current"
    m = re.fullmatch(r"(\d{2,3})(\s*days?)?", n)
    if m:
        d = int(m[1])
        return "bucket_30" if d <= 30 else "bucket_60" if d <= 60 else "bucket_90" if d <= 90 else "bucket_120_plus"
    ds = find_dates(label)
    if ds and as_of:
        d = ds[0]
        months_back = (as_of.year - d.year) * 12 + (as_of.month - d.month)
        if months_back <= 0:
            return "bucket_current"
        return {1: "bucket_30", 2: "bucket_60", 3: "bucket_90"}.get(months_back, "bucket_120_plus")
    return None


# =============================================================================
# 4. Account classification
#    priority: account_map.csv override > export's own account type column
#              > section header in the TB > code-range heuristic > keywords
#    Keywords always refine the subtype / cash-flow bucket.
# =============================================================================
# (account_type, account_subtype, cashflow_bucket, is_current)
Cls = tuple[str, str | None, str, bool | None]

# AutoCount "Special Account Type" / "Account Type" values.
# TODO-VERIFY: AutoCount Cloud's exact labels and abbreviations were not
# confirmed from vendor documentation. Long labels follow what the AutoCount
# UI commonly shows; the two-/three-letter codes are the usual abbreviations
# and are the least certain. Anything matched through this table is written
# to out/account_map_suggested.csv with confidence 'medium' (abbreviation) or
# 'high' (label) so the owner can confirm. Unknown values are reported.
SOURCE_TYPE_MAP: dict[str, tuple[Cls, str]] = {
    # key (normalised)              classification                                             certainty
    "bank":                        (("asset", "cash", "cash", True), "high"),
    "ba":                          (("asset", "cash", "cash", True), "medium"),       # TODO-VERIFY
    "cash":                        (("asset", "cash", "cash", True), "high"),
    "cash in hand":                (("asset", "cash", "cash", True), "high"),
    "debtor control":              (("asset", "trade_receivable", "operating", True), "high"),
    "debtors control":             (("asset", "trade_receivable", "operating", True), "high"),
    "account receivable":          (("asset", "trade_receivable", "operating", True), "high"),
    "accounts receivable":         (("asset", "trade_receivable", "operating", True), "high"),
    "dc":                          (("asset", "trade_receivable", "operating", True), "medium"),  # TODO-VERIFY
    "ar":                          (("asset", "trade_receivable", "operating", True), "medium"),  # TODO-VERIFY
    "current asset":               (("asset", None, "operating", True), "high"),
    "current assets":              (("asset", None, "operating", True), "high"),
    "ca":                          (("asset", None, "operating", True), "medium"),   # TODO-VERIFY (Current Asset)
    "stock":                       (("asset", "inventory", "operating", True), "high"),
    "inventory":                   (("asset", "inventory", "operating", True), "high"),
    "st":                          (("asset", "inventory", "operating", True), "medium"),  # TODO-VERIFY
    "deposit":                     (("asset", "other_receivable", "operating", True), "high"),
    "fixed asset":                 (("asset", "fixed_asset", "investing", False), "high"),
    "fixed assets":                (("asset", "fixed_asset", "investing", False), "high"),
    "fa":                          (("asset", "fixed_asset", "investing", False), "medium"),   # TODO-VERIFY
    "accumulated depreciation":    (("asset", "fixed_asset", "investing", False), "high"),
    "ad":                          (("asset", "fixed_asset", "investing", False), "medium"),   # TODO-VERIFY
    "investment":                  (("asset", None, "investing", False), "high"),
    "inv":                         (("asset", None, "investing", False), "medium"),           # TODO-VERIFY
    "other asset":                 (("asset", None, "investing", False), "high"),
    "other assets":                (("asset", None, "investing", False), "high"),
    "oa":                          (("asset", None, "investing", False), "medium"),           # TODO-VERIFY
    "creditor control":            (("liability", "trade_payable", "operating", True), "high"),
    "creditors control":           (("liability", "trade_payable", "operating", True), "high"),
    "account payable":             (("liability", "trade_payable", "operating", True), "high"),
    "accounts payable":            (("liability", "trade_payable", "operating", True), "high"),
    "cc":                          (("liability", "trade_payable", "operating", True), "medium"),  # TODO-VERIFY
    "ap":                          (("liability", "trade_payable", "operating", True), "medium"),  # TODO-VERIFY
    "current liability":           (("liability", None, "operating", True), "high"),
    "current liabilities":         (("liability", None, "operating", True), "high"),
    "cl":                          (("liability", None, "operating", True), "medium"),       # TODO-VERIFY
    "long term liability":         (("liability", "borrowing", "financing", False), "high"),
    "long term liabilities":       (("liability", "borrowing", "financing", False), "high"),
    "long-term liability":         (("liability", "borrowing", "financing", False), "high"),
    "ltl":                         (("liability", "borrowing", "financing", False), "medium"),   # TODO-VERIFY
    "capital":                     (("equity", "share_capital", "financing", None), "high"),
    "cap":                         (("equity", "share_capital", "financing", None), "medium"),    # TODO-VERIFY
    "equity":                      (("equity", "share_capital", "financing", None), "high"),
    "reserve":                     (("equity", "retained_earnings", "financing", None), "high"),
    "reserves":                    (("equity", "retained_earnings", "financing", None), "high"),
    "retained earning":            (("equity", "retained_earnings", "financing", None), "high"),
    "retained earnings":           (("equity", "retained_earnings", "financing", None), "high"),
    "re":                          (("equity", "retained_earnings", "financing", None), "medium"),  # TODO-VERIFY
    "appropriation":               (("equity", "retained_earnings", "financing", None), "high"),
    "sales":                       (("revenue", None, "operating", None), "high"),
    "revenue":                     (("revenue", None, "operating", None), "high"),
    "income":                      (("revenue", None, "operating", None), "high"),
    "sa":                          (("revenue", None, "operating", None), "medium"),    # TODO-VERIFY (Sales, or Sales Adjustment)
    "sales adjustment":            (("revenue", None, "operating", None), "high"),
    "cost of goods sold":          (("cogs", None, "operating", None), "high"),
    "cost of sales":               (("cogs", None, "operating", None), "high"),
    "cost of sale":                (("cogs", None, "operating", None), "high"),
    "purchase":                    (("cogs", None, "operating", None), "high"),
    "purchases":                   (("cogs", None, "operating", None), "high"),
    "purchase adjustment":         (("cogs", None, "operating", None), "high"),
    "cs":                          (("cogs", None, "operating", None), "medium"),       # TODO-VERIFY
    "cogs":                        (("cogs", None, "operating", None), "high"),
    "expenses":                    (("opex", None, "operating", None), "high"),
    "expense":                     (("opex", None, "operating", None), "high"),
    "exp":                         (("opex", None, "operating", None), "medium"),       # TODO-VERIFY
    "other income":                (("other", None, "operating", None), "high"),
    "oi":                          (("other", None, "operating", None), "medium"),      # TODO-VERIFY
    "other expenses":              (("other", None, "operating", None), "high"),
    "other expense":               (("other", None, "operating", None), "high"),
    "oe":                          (("other", None, "operating", None), "medium"),      # TODO-VERIFY
    "taxation":                    (("other", "tax", "operating", None), "high"),
    "tax":                         (("other", "tax", "operating", None), "high"),
    "extraordinary income/expense": (("other", None, "operating", None), "high"),
    "extraordinary":               (("other", None, "operating", None), "high"),
    # generic words sometimes used by exports / section headers
    "asset":                       (("asset", None, "operating", None), "medium"),
    "assets":                      (("asset", None, "operating", None), "medium"),
    "liability":                   (("liability", None, "operating", None), "medium"),
    "liabilities":                 (("liability", None, "operating", None), "medium"),
    "profit and loss":             (("opex", None, "operating", None), "low"),
}

# Code-range fallback. TODO-VERIFY against the entity's actual chart.
#   generic   : the convention described in the brief (1xx/2xx assets, 3xx
#               liabilities, 4xx equity, 5xx revenue, 6xx COGS, 7xx-9xx opex)
#   autocount : the layout of AutoCount's default Malaysian chart as used in
#               seed_demo.sql (1xx equity, 2xx fixed assets, 3xx current
#               assets, 4xx liabilities, 5xx sales, 6xx COGS, 7xx-9xx expenses)
CODE_CONVENTIONS: dict[str, dict[str, str]] = {
    "generic":   {"1": "asset", "2": "asset", "3": "liability", "4": "equity", "5": "revenue", "6": "cogs", "7": "opex", "8": "opex", "9": "opex"},
    "autocount": {"1": "equity", "2": "asset", "3": "asset", "4": "liability", "5": "revenue", "6": "cogs", "7": "opex", "8": "opex", "9": "opex"},
}

# Keyword rules on the account name: (regex, account_type, subtype, bucket, is_current, strong)
# strong = the keyword alone is enough to set the account_type when no source
# type is available (it then beats the code-range fallback).
KEYWORD_RULES: list[tuple[str, str, str | None, str, bool | None, bool]] = [
    (r"\b(accumulated|accum\.?)\s*dep", "asset", "fixed_asset", "investing", False, True),
    (r"\bdepreciation\b", "opex", "depreciation", "non_cash", None, True),
    (r"\bamorti[sz]ation\b", "opex", "amortisation", "non_cash", None, True),
    (r"\b(petty cash|cash in hand|cash on hand|cash at bank|cash & bank|cash and bank)\b", "asset", "cash", "cash", True, True),
    (r"\b(term loan|hire purchase|h/p|hp (creditor|liabilit|payable)|bank loan|financing|lease liabilit|borrowing|overdraft|od\b)", "liability", "borrowing", "financing", False, True),
    (r"\bbank\s*(charges|fee|commission)", "opex", None, "operating", None, True),
    (r"\b(interest expense|interest paid|interest on|bank interest|finance (cost|charge)|hp interest|loan interest|late payment interest)", "other", "interest", "financing", None, True),
    (r"\b(maybank|cimb|public bank|rhb|hong leong|ambank|ocbc|uob|hsbc|bank islam|affin|alliance bank|bsn|standard chartered|agrobank|bank rakyat|mbsb|touch ?n ?go|current account|savings? account|fixed deposit)\b", "asset", "cash", "cash", True, True),
    (r"\bbank\b", "asset", "cash", "cash", True, False),
    (r"\b(trade|sundry|other)?\s*debtors?\b|\baccounts? receivable\b|\btrade receivable", "asset", "trade_receivable", "operating", True, True),
    (r"\b(other|sundry) receivable|\bprepayment|\bprepaid|\bdeposits?\b(?!.*(received|from customer))|\badvance to\b|\bamount (due|owing) from\b|\bstaff (loan|advance)|\b(gst|sst) (input|claimable|recoverable)\b", "asset", "other_receivable", "operating", True, True),
    (r"\b(stock|inventor(y|ies)|work in progress)\b", "asset", "inventory", "operating", True, True),
    (r"\b(furniture|fittings?|equipment|computer|laptop|motor vehicle|renovation|plant|machinery|software|signboard|air.?cond|property|premises|building)\b", "asset", "fixed_asset", "investing", False, True),
    (r"\b(trade|sundry)?\s*creditors?\b|\baccounts? payable\b|\btrade payable", "liability", "trade_payable", "operating", True, True),
    (r"\baccru(al|ed)", "liability", "accrual", "operating", True, True),
    (r"\b(sst|gst|service tax|sales tax)\b.*\b(payable|output|control)\b|\b(output|payable)\b.*\b(sst|gst)\b|\bsst\b", "liability", "tax_payable", "operating", True, True),
    (r"\b(epf|kwsp|socso|perkeso|eis|pcb|mtd|hrdf?|hrd corp|levy|zakat)\b.*\bpayable|\bpayable\b.*\b(epf|socso|eis|pcb|hrdf?)\b|\b(epf|socso|eis|pcb)\s*(payable|contribution payable)\b", "liability", "tax_payable", "operating", True, True),
    (r"\b(income )?tax payable|\bprovision for tax|\bcp\s?204|\bcp\s?500|\btaxation payable|\btax liabilit", "liability", "tax_payable", "operating", True, True),
    (r"\b(director|partner)s?'?s?\s*(loan|advance|account|current account|a/c)\b|\bamount (due|owing) to\b|\badvance from\b|\bdeposit(s)? (received|from customer)|\bunearned|\bdeferred (income|revenue)|\bcustomer deposit", "liability", "other_payable", "financing", True, True),
    (r"\b(share|paid.?up|partners?'?s?|members?'?s?|ordinary)\s*(capital|contribution)\b|\bcapital (account|contribution)\b|\bcapital\b", "equity", "share_capital", "financing", None, True),
    (r"\b(retained|accumulated|unappropriated)\s*(earnings?|profits?|loss(es)?)\b|\breserves?\b|\bdrawings?\b|\bprofit (and|&) loss (b/f|account|appropriation)|\bcurrent year (profit|earnings)", "equity", "retained_earnings", "financing", None, True),
    (r"\binterest (income|received|receivable)|\bdividend|\brental income|\bgain on|\b(forex|fx|exchange|currency)\s*(gain|loss)|\bloss on (disposal|sale)|\bgain|\bother income|\bsundry income|\bmisc(ellaneous)? income|\bwrite[- ]?back|\bbad debt recover", "other", None, "operating", None, True),
    (r"\b(income tax|taxation|tax expense|deferred tax|corporate tax|tax provision)\b", "other", "tax", "operating", None, True),
    (r"\b(cost of (sales|goods|services|revenue)|direct cost|trainer(s)?'? ?fees?|speaker fees?|facilitator|venue|catering|course material|training material|purchase[sd]?|subcontract|freelance (trainer|fee)|cogs)\b", "cogs", None, "operating", None, True),
    (r"\b(training|course|seminar|workshop|programme|program|consultan(cy|t)|advisory|professional|service|management|tuition|coaching|facilitation|speaking|licen[cs]ing|membership|subscription|sponsorship)\s*(fees?|income|revenue|charges?)\b|\b(sales|revenue|fees? income|fee income|income from)\b|\brevenue\b|\bsales\b", "revenue", None, "operating", None, True),
    (r"\b(salar|wages|bonus|allowance|epf|socso|eis|kwsp|perkeso|staff|payroll|commission|director(s)?'? (fee|remuneration)|medical|training (cost|expense)|hrd corp levy)\b", "opex", None, "operating", None, True),
    (r"\b(rent(al)?|utilit|electric|water|telephone|internet|mobile|postage|courier|printing|stationer|office|insurance|travel|petrol|parking|toll|transport|accommodation|entertain(ment)?|refreshment|marketing|advertis(ing|ement)?|promotion|website|domain|hosting|software subscription|zoom|canva|audit|secretarial|tax agent|legal|professional fee|accounting fee|licen[cs]e|permit|upkeep|repair|maintenance|cleaning|donation|penalt|fine|general|sundry|misc|expense|charges?|fee)\b", "opex", None, "operating", None, False),
    (r"\b(suspense|clearing|contra)\b", "asset", "other_receivable", "operating", True, False),
]
_KEYWORD_RX = [(re.compile(p, re.I), t, s, b, c, strong) for p, t, s, b, c, strong in KEYWORD_RULES]


def _default_is_current(account_type: str, subtype: str | None, given: bool | None) -> bool | None:
    if account_type in PL_TYPES:
        return None
    if given is not None:
        return given
    if account_type == "asset":
        return subtype != "fixed_asset"
    if account_type == "liability":
        return subtype != "borrowing"
    return None


@dataclass
class Classification:
    account_type: str
    account_subtype: str | None
    cashflow_bucket: str
    is_current: bool | None
    source: str          # override | source_type | section | code_range | keyword | default
    confidence: str      # high | medium | low
    note: str = ""


def _source_type_lookup(raw: str | None) -> tuple[Cls, str] | None:
    if not raw:
        return None
    key = norm_text(raw).replace("-", " ").replace("_", " ")
    key = re.sub(r"[^a-z0-9/& ]", "", key).strip()
    if key in SOURCE_TYPE_MAP:
        return SOURCE_TYPE_MAP[key]
    # 'Current Asset (CA)' / 'CA - Current Asset' / 'BA / Bank' (special type / account type)
    hits = [SOURCE_TYPE_MAP[part.strip()] for part in re.split(r"[()/,\-]+", key) if part.strip() in SOURCE_TYPE_MAP]
    if not hits:
        return None
    first = hits[0]
    if all(h[0][0] == first[0][0] for h in hits):
        rank = {"high": 2, "medium": 1, "low": 0}
        return first[0], max((h[1] for h in hits), key=lambda c: rank[c])
    return first[0], "medium"


def classify_account(code: str, name: str, source_type: str | None, section: str | None,
                     overrides: dict[str, dict[str, Any]], convention: str) -> Classification:
    name = name or ""
    # 1) owner override file
    ov = overrides.get(code.strip())
    if ov:
        t = ov["account_type"]
        st = ov.get("account_subtype") or None
        cls = Classification(t, st, ov.get("cashflow_bucket") or ("cash" if st == "cash" else "operating"),
                             _default_is_current(t, st, ov.get("is_current")), "override", "high", "account_map.csv")
        return cls

    # keyword candidate (always computed: refines subtype, decides when nothing else is known)
    kw: tuple[str, str | None, str, bool | None, bool, str] | None = None
    for rx, t, s, b, c, strong in _KEYWORD_RX:
        if rx.search(name):
            kw = (t, s, b, c, strong, rx.pattern[:40])
            break

    # 2) export's own account type
    hit = _source_type_lookup(source_type)
    src = "source_type"
    conf = None
    if hit is None and section:
        hit = _source_type_lookup(section)
        src = "section"
        if hit:
            hit = (hit[0], "medium" if hit[1] == "high" else "low")
    if hit:
        (t, s, b, c), conf = hit
        note = f"source type {source_type!r}" if src == "source_type" else f"TB section {section!r}"
        # keyword refinement of subtype / bucket within the same account_type
        if kw and kw[0] == t and (s is None or kw[1] in ("depreciation", "amortisation", "interest", "tax", "cash")):
            s, b, c = kw[1] or s, kw[2] if kw[1] else b, kw[3] if kw[3] is not None else c
        elif kw and t == "opex" and kw[0] == "other" and kw[1] in ("interest", "tax"):
            # 'Interest Expense' / 'Taxation' typed as plain Expenses: move below EBITDA, flag for confirmation
            t, s, b = "other", kw[1], kw[2]
            conf = "medium"
            note += f"; name says {kw[1]} -> account_type other (below EBITDA)"
        elif kw and kw[4] and kw[0] != t and src == "section":
            conf = "low"
            note += f"; keyword suggests {kw[0]}"
        return Classification(t, s, b, _default_is_current(t, s, c), src, conf, note)

    # 3) code range
    digits = re.match(r"\D*(\d)", code or "")
    range_type = CODE_CONVENTIONS.get(convention, CODE_CONVENTIONS["generic"]).get(digits[1]) if digits else None
    if range_type:
        t = range_type
        if kw and kw[0] == t:
            return Classification(t, kw[1], kw[2], _default_is_current(t, kw[1], kw[3]), "code_range", "medium",
                                  f"code range {convention} + keyword agree")
        if kw and kw[4]:
            # strong keyword contradicts the code range: trust the name, flag it
            return Classification(kw[0], kw[1], kw[2], _default_is_current(kw[0], kw[1], kw[3]), "keyword", "low",
                                  f"code range {convention} says {t}, name says {kw[0]} (keyword won) - confirm")
        return Classification(t, None, "operating", _default_is_current(t, None, None), "code_range", "low",
                              f"code range {convention} only; no source type, no keyword")
    # 4) keyword only
    if kw:
        return Classification(kw[0], kw[1], kw[2], _default_is_current(kw[0], kw[1], kw[3]), "keyword",
                              "medium" if kw[4] else "low", "keyword only")
    return Classification("other", None, "operating", None, "default", "low", "no source type, code range or keyword matched")


def load_account_map(path: Path | None) -> dict[str, dict[str, Any]]:
    """account_map.csv: account_code, account_type, [account_subtype], [cashflow_bucket], [is_current]."""
    if not path or not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rdr = csv.DictReader(fh)
        cols = {re.sub(r"\s+", "_", c.strip().lower().lstrip("\ufeff")): c for c in (rdr.fieldnames or [])}
        if "account_code" not in cols or "account_type" not in cols:
            raise SystemExit(f"{path}: needs columns account_code and account_type")
        for i, r in enumerate(rdr, start=2):
            code = clean_str(r.get(cols["account_code"]))
            def tok(col: str) -> str:
                return re.sub(r"[\s-]+", "_", str(r.get(cols.get(col, ""), "") or "").strip().lower())

            t = tok("account_type")
            if not code or not t:
                continue  # rows left blank in the suggested template are ignored
            if t not in ACCOUNT_TYPES:
                raise SystemExit(f"{path} line {i}: account_type {t!r} not one of {ACCOUNT_TYPES}")
            st = tok("account_subtype") or None
            if st and st not in SUBTYPES:
                raise SystemExit(f"{path} line {i}: account_subtype {st!r} not one of {SUBTYPES}")
            b = tok("cashflow_bucket") or None
            if b and b not in CASHFLOW_BUCKETS:
                raise SystemExit(f"{path} line {i}: cashflow_bucket {b!r} not one of {CASHFLOW_BUCKETS}")
            ic_raw = tok("is_current")
            ic = True if ic_raw in ("true", "1", "yes", "y") else False if ic_raw in ("false", "0", "no", "n") else None
            out[code] = {"account_type": t, "account_subtype": st, "cashflow_bucket": b, "is_current": ic}
    return out


# =============================================================================
# 5. Report parsers (grid -> normalised rows + diagnostics)
# =============================================================================
TOTAL_RX = re.compile(r"^\s*(sub[- ]?total|grand\s*total|total|net (profit|loss|surplus)|balance (c/f|b/f)|closing balance|profit/\(loss\)|profit (and|&) loss|surplus|deficit)\b|\btotal\s*:?\s*$", re.I)
CODE_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-./_]{0,30}$")


@dataclass
class Diag:
    """What the mapping report prints for one file (aggregates only, no names)."""
    kind: str
    file: str
    sheet: str = ""
    header_row: int | None = None
    merged_with: int | None = None
    columns: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, Any] = field(default_factory=dict)
    totals: dict[str, Any] = field(default_factory=dict)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)


def _looks_like_code(s: str) -> bool:
    s = s.strip()
    if not s or TOTAL_RX.search(s):
        return False
    if not CODE_RX.match(s):
        return False
    return any(ch.isdigit() for ch in s) or (len(s) <= 12 and s.isalnum())


def _is_total_row(cells: list[Any], roles: dict[int, str]) -> bool:
    for i, c in enumerate(cells):
        if isinstance(c, str) and TOTAL_RX.search(c.strip()) and roles.get(i) in ("account_code", "name", "counterparty_code", "counterparty_name", "bank_name", None):
            return True
    return False


def _text_cells(cells: list[Any]) -> list[str]:
    return [clean_str(c) for c in cells if isinstance(c, str) and clean_str(c) and not is_amount_cell(c)]


# ---- Trial Balance ---------------------------------------------------------
@dataclass
class TBRow:
    period_start: date
    account_code: str
    name: str
    debit: Decimal | None      # movement if the file has opening+closing columns, else None
    credit: Decimal | None
    closing: Decimal           # debit positive
    section: str | None
    source_type: str | None


def parse_trial_balance(grid: Grid, period_override: date | None, diag: Diag) -> list[TBRow]:
    h = detect_header(grid)
    if not h:
        diag.warn("no header row found (need a row with at least two of: account no/code, description, debit, credit, balance)")
        return []
    diag.header_row, diag.merged_with, diag.sheet = h.row_idx + 1, (h.merged_with + 1 if h.merged_with is not None else None), grid.sheet
    code_col, name_col, type_col = h.col("account_code"), h.col("name"), h.col("account_type")
    if code_col is None and name_col is None:
        diag.warn("header found but no account code / description column")
        return []
    if code_col is None:
        diag.warn("no account code column; using the description as the code (fix with --coa or account_map.csv)")

    # Column model: either (a) debit/credit[/opening/closing] once, or (b) per-period groups.
    period_cols = [c for c in h.columns if c.period and c.role in ("debit", "credit", "balance", "total")]
    plain_dc = [c for c in h.columns if not c.period and c.role in ("debit", "credit")]
    plain_bal = [c for c in h.columns if not c.period and c.role in ("balance", "total")]
    plain_open = [c for c in h.columns if not c.period and c.role == "opening"]
    diag.columns = [c.describe() for c in h.columns if c.role or c.period]

    periods: dict[date, dict[str, Column]] = {}
    if period_cols:
        for c in period_cols:
            periods.setdefault(c.period, {})[c.role] = c  # type: ignore[index]
        diag.note(f"multi-period layout: {len(periods)} month column group(s): " + ", ".join(f"{p:%Y-%m}" for p in sorted(periods)))
        if period_override:
            diag.warn(f"--period {period_override:%Y-%m} ignored: file has its own month columns")
    else:
        p = period_override
        src = "override"
        if p is None:
            ds = find_dates(h.title_text) or find_dates(grid.path.stem)
            if ds:
                p = month_start(max(ds))
                src = "title rows" if find_dates(h.title_text) else "file name"
        if p is None:
            diag.warn("period not found in title rows or file name; pass --period YYYY-MM or FILE=YYYY-MM")
            return []
        diag.note(f"period {p:%Y-%m} (from {src})")
        if plain_dc:
            periods[p] = {c.role: c for c in plain_dc}  # type: ignore[misc]
            if plain_bal:
                periods[p]["balance"] = plain_bal[-1]
            if plain_open:
                periods[p]["opening"] = plain_open[0]
        elif plain_bal:
            periods[p] = {"balance": plain_bal[-1]}
        else:
            diag.warn("no debit/credit or balance column found")
            return []

    movement_mode = any("opening" in g and ("balance" in g) for g in periods.values())
    if movement_mode:
        diag.note("opening + debit + credit + closing columns found: debit/credit are read as period MOVEMENTS")
    else:
        diag.note("debit/credit (or balance) read as CLOSING balances; movements are derived month-on-month")

    rows: list[TBRow] = []
    roles = {c.idx: c.role for c in h.columns}
    section: str | None = None
    n_total = n_section = n_blank = 0
    file_totals: dict[str, Decimal] = {}
    for r in grid.rows[h.data_start:]:
        cells = list(r) + [None] * (len(h.columns) - len(r))
        if all(clean_str(c) == "" for c in cells):
            n_blank += 1
            continue
        code = clean_str(cells[code_col.idx]) if code_col else ""
        name = clean_str(cells[name_col.idx]) if name_col else ""
        if _is_total_row(cells, roles) or (not code and name and TOTAL_RX.search(name)):
            n_total += 1
            # remember the last total row's figures for the balancing check
            for role in ("debit", "credit", "balance"):
                c = next((x for x in h.columns if x.role == role and not x.period), None)
                if c is not None and c.idx < len(cells):
                    v = parse_cell(cells[c.idx], role)
                    if v is not None:
                        file_totals[role] = v
            continue
        if not _row_has_amounts(cells):
            # section header such as 'CURRENT ASSETS' or a parent account line without figures
            txt = _text_cells(cells)
            if txt:
                section = txt[-1] if not code or not _looks_like_code(code) else section
            n_section += 1
            continue
        if code_col is None:
            code = name
        if not _looks_like_code(code):
            if name and not code:
                n_section += 1
                section = name
                continue
            diag.warn(f"row skipped: account code {code!r} does not look like a code")
            continue
        source_type = clean_str(cells[type_col.idx]) if type_col else None
        for p, g in periods.items():
            opening = parse_cell(cells[g["opening"].idx], "balance") if "opening" in g else None
            dr = parse_cell(cells[g["debit"].idx], "debit") if "debit" in g else None
            cr = parse_cell(cells[g["credit"].idx], "credit") if "credit" in g else None
            bal = parse_cell(cells[g["balance"].idx], "balance") if "balance" in g else None
            if movement_mode:
                closing = bal if bal is not None else (opening or ZERO) + (dr or ZERO) - (cr or ZERO)
                rows.append(TBRow(p, code, name, dr or ZERO, cr or ZERO, closing, section, source_type))
            else:
                if dr is None and cr is None and bal is None:
                    continue  # account has no figure in this month column
                if dr is not None or cr is not None:
                    closing = (dr or ZERO) - (cr or ZERO)
                else:
                    closing = bal or ZERO
                rows.append(TBRow(p, code, name, None, None, closing, section, source_type))
    diag.counts.update({"accounts": len({r.account_code for r in rows}), "tb_rows": len(rows),
                        "total_rows_skipped": n_total, "section_or_blank_rows": n_section + n_blank, "periods": len(periods)})
    # balance check per period
    for p in sorted(periods):
        pr = [r for r in rows if r.period_start == p]
        dr_sum = sum((r.closing for r in pr if r.closing > 0), ZERO)
        cr_sum = -sum((r.closing for r in pr if r.closing < 0), ZERO)
        diff = dr_sum - cr_sum
        diag.totals[f"{p:%Y-%m}"] = {"debit": dr_sum, "credit": cr_sum, "difference": diff, "balanced": diff == 0}
        if diff != 0:
            diag.warn(f"{p:%Y-%m}: TB does not balance by {fmt_amt(diff)} (subtotal rows left in? P&L appropriation missing? closing-vs-movement mix?)")
    if file_totals and not period_cols:
        diag.totals["file_total_row"] = file_totals
        if "debit" in file_totals and "credit" in file_totals and file_totals["debit"] != file_totals["credit"]:
            diag.warn(f"the file's own total row is unbalanced: {fmt_amt(file_totals['debit'])} vs {fmt_amt(file_totals['credit'])}")
        diag.note("file total row is shown for reference; it can differ from the parsed totals when negatives are netted within a column")
    dupes = {}
    for p in periods:
        seen: dict[str, int] = {}
        for r in rows:
            if r.period_start == p:
                seen[r.account_code] = seen.get(r.account_code, 0) + 1
        dupes.update({k: v for k, v in seen.items() if v > 1})
    if dupes:
        diag.warn(f"duplicate account codes within one period: {sorted(dupes)[:20]}{' ...' if len(dupes) > 20 else ''} (amounts will be summed)")
    return rows


# ---- Chart of Accounts ---------------------------------------------------------
@dataclass
class COARow:
    account_code: str
    name: str
    source_type: str | None
    parent: str | None
    is_active: bool = True


def parse_coa(grid: Grid, diag: Diag) -> list[COARow]:
    h = detect_header(grid)
    if not h:
        diag.warn("no header row found (need account code + description/name)")
        return []
    diag.header_row, diag.merged_with, diag.sheet = h.row_idx + 1, (h.merged_with + 1 if h.merged_with is not None else None), grid.sheet
    diag.columns = [c.describe() for c in h.columns if c.role]
    code_col, name_col = h.col("account_code"), h.col("name")
    if code_col is None or name_col is None:
        diag.warn("need both an account code column and a name/description column")
        return []
    type_cols = h.cols("account_type")
    parent_col = h.col("parent")
    active_col = next((c for c in h.columns if re.search(r"\b(active|status)\b", norm_text(c.label))), None)
    rows: list[COARow] = []
    n_skip = 0
    roles = {c.idx: c.role for c in h.columns}
    for r in grid.rows[h.data_start:]:
        cells = list(r) + [None] * (len(h.columns) - len(r))
        code, name = clean_str(cells[code_col.idx]), clean_str(cells[name_col.idx])
        if not code or _is_total_row(cells, roles) or not _looks_like_code(code):
            n_skip += 1
            continue
        types = [clean_str(cells[c.idx]) for c in type_cols if clean_str(cells[c.idx])]
        # prefer the 'special account type' column when both exist; keep both for reconciliation
        special = [clean_str(cells[c.idx]) for c in type_cols if "special" in norm_text(c.label) and clean_str(cells[c.idx])]
        source_type = (special[0] if special else types[0]) if types else None
        if len(types) > 1:
            source_type = " / ".join(dict.fromkeys([source_type] + types))
        parent = clean_str(cells[parent_col.idx]) if parent_col else None
        active = True
        if active_col is not None:
            av = norm_text(cells[active_col.idx])
            active = av not in ("no", "n", "false", "0", "inactive", "f")
        rows.append(COARow(code, name or code, source_type, parent or None, active))
    diag.counts.update({"accounts": len(rows), "rows_skipped": n_skip, "type_columns": len(type_cols)})
    if not type_cols:
        diag.warn("no account type column found; classification will rely on code ranges and keywords")
    return rows


# ---- Debtor / Creditor aging -----------------------------------------------------
@dataclass
class AgingRow:
    counterparty_code: str
    counterparty_name: str
    currency: str
    buckets: dict[str, Decimal]
    file_total: Decimal | None


def parse_aging(grid: Grid, as_of: date | None, diag: Diag) -> tuple[list[AgingRow], date | None]:
    h = detect_header(grid)
    if not h:
        diag.warn("no header row found (need debtor/customer or supplier/creditor columns plus aging buckets)")
        return [], as_of
    diag.header_row, diag.merged_with, diag.sheet = h.row_idx + 1, (h.merged_with + 1 if h.merged_with is not None else None), grid.sheet
    detected = max(find_dates(h.title_text), default=None)
    if as_of is None:
        as_of = detected
        if as_of:
            diag.note(f"as-of {as_of} taken from the title rows")
    elif detected and detected != as_of:
        diag.warn(f"title rows say {detected} but --as-of {as_of} is used")
    if as_of is None:
        diag.warn("no as-of date: pass --as-of YYYY-MM-DD")
        return [], None
    code_col = h.col("counterparty_code") or h.col("account_code")
    name_col = h.col("counterparty_name") or h.col("name")
    total_col = h.col("total")
    cur_col = h.col("currency")
    bucket_cols: list[Column] = []
    for c in h.columns:
        if c.role in ("bucket",) or (c.role in ("balance", "debit", "credit") and c.period):
            b = bucket_for_label(c.label, as_of)
            if b:
                c.bucket, c.role = b, "bucket"
                bucket_cols.append(c)
        elif c.role is None and c.label:
            b = bucket_for_label(c.label, as_of)
            if b:
                c.bucket, c.role = b, "bucket"
                bucket_cols.append(c)
    if any(c.period for c in bucket_cols):
        diag.warn("bucket columns are month names: interpreted as months before the as-of date (TODO-VERIFY against AutoCount's aging basis)")
    diag.columns = [c.describe() for c in h.columns if c.role]
    if not bucket_cols:
        diag.warn("no aging bucket columns recognised (Current, 1-30, 31-60, 61-90, >90 ...)")
        return [], as_of
    if code_col is None and name_col is None:
        diag.warn("no debtor/creditor code or name column")
        return [], as_of
    if code_col is None:
        diag.warn("no counterparty code column; a code is derived from the name (NAME:<slug>)")
    rows: dict[str, AgingRow] = {}
    n_total = n_skip = n_detail = 0
    roles = {c.idx: c.role for c in h.columns}
    file_grand: dict[str, Decimal] | None = None
    for r in grid.rows[h.data_start:]:
        cells = list(r) + [None] * (len(h.columns) - len(r))
        if all(clean_str(c) == "" for c in cells):
            continue
        if _is_total_row(cells, roles):
            n_total += 1
            g = {c.bucket: parse_number(cells[c.idx]) or ZERO for c in bucket_cols if c.bucket}
            tot = parse_number(cells[total_col.idx]) if total_col else None
            if any(v != 0 for v in g.values()) or tot:
                file_grand = {**{b: ZERO for b in BUCKETS}, **_sum_buckets(bucket_cols, cells), "total": tot}
            continue
        if not _row_has_amounts(cells):
            n_skip += 1
            continue
        code = clean_str(cells[code_col.idx]) if code_col else ""
        name = clean_str(cells[name_col.idx]) if name_col else ""
        if not code and not name:
            n_detail += 1  # invoice detail line under a debtor; nothing to key on
            continue
        if not code:
            code = "NAME:" + re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")[:40]
        buckets = _sum_buckets(bucket_cols, cells)
        tot = parse_number(cells[total_col.idx]) if total_col else None
        cur = clean_str(cells[cur_col.idx]) if cur_col else ""
        if code in rows:
            n_detail += 1
            for b, v in buckets.items():
                rows[code].buckets[b] += v
            if tot is not None:
                rows[code].file_total = (rows[code].file_total or ZERO) + tot
        else:
            rows[code] = AgingRow(code, name or code, (cur or "MYR")[:3].upper(), buckets, tot)
    out = list(rows.values())
    sums = {b: sum((r.buckets[b] for r in out), ZERO) for b in BUCKETS}
    grand = sum(sums.values(), ZERO)
    diag.counts.update({"counterparties": len(out), "rows_merged_into_counterparties": n_detail,
                        "total_rows_skipped": n_total, "text_only_rows_skipped": n_skip})
    diag.totals.update({**sums, "grand_total": grand})
    mism = [r for r in out if r.file_total is not None and r.file_total != sum(r.buckets.values(), ZERO)]
    if mism:
        diag.warn(f"{len(mism)} counterparties where the file's Total column differs from the sum of buckets (bucket columns missing or double-counted?)")
    if file_grand:
        diag.totals["file_total_row"] = file_grand
        if file_grand.get("total") is not None and file_grand["total"] != grand:
            diag.warn(f"file grand total {fmt_amt(file_grand['total'])} != sum of parsed buckets {fmt_amt(grand)}")
    return out, as_of


def _sum_buckets(bucket_cols: list[Column], cells: list[Any]) -> dict[str, Decimal]:
    out = {b: ZERO for b in BUCKETS}
    for c in bucket_cols:
        if c.bucket and c.idx < len(cells):
            out[c.bucket] += parse_number(cells[c.idx]) or ZERO
    return out


# ---- Bank balances -------------------------------------------------------------
BANK_WORDS = re.compile(r"\b(maybank|malayan banking|cimb|public bank|rhb|hong leong|ambank|ocbc|uob|hsbc|bank islam|affin|alliance|bsn|standard chartered|agrobank|bank rakyat|mbsb|citibank|bank muamalat|kuwait finance|al rajhi|gx bank|boost bank|aeon bank)\b", re.I)


@dataclass
class BankRow:
    bank_account_code: str
    bank_name: str
    account_no_masked: str | None
    gl_account_code: str | None
    currency: str
    closing_balance: Decimal


def parse_bank(grid: Grid, as_of: date | None, diag: Diag) -> tuple[list[BankRow], date | None]:
    h = detect_header(grid, min_score=2)
    if not h:
        diag.warn("no header row found (need a bank/account column and a balance column)")
        return [], as_of
    diag.header_row, diag.merged_with, diag.sheet = h.row_idx + 1, (h.merged_with + 1 if h.merged_with is not None else None), grid.sheet
    detected = max(find_dates(h.title_text), default=None)
    if as_of is None and detected:
        as_of = detected
        diag.note(f"balance date {as_of} taken from the title rows")
    elif detected and as_of and detected != as_of:
        diag.warn(f"title rows say {detected} but --as-of {as_of} is used")
    if as_of is None:
        diag.warn("no balance date: pass --as-of YYYY-MM-DD")
        return [], None
    code_col = h.col("account_code")
    name_col = h.col("bank_name") or h.col("name")
    no_col = h.col("bank_account_no")
    cur_col = h.col("currency")
    # balance column: prefer book/closing balance over statement balance
    cands = [c for c in h.columns if c.role in ("balance", "total")]
    book = [c for c in cands if re.search(r"book|closing|ledger|gl\b|cash book", norm_text(c.label))]
    stmt = [c for c in cands if re.search(r"statement", norm_text(c.label))]
    bal_col = (book or [c for c in cands if c not in stmt] or cands or [None])[-1] if cands else None
    dr_col, cr_col = h.col("debit"), h.col("credit")
    diag.columns = [c.describe() for c in h.columns if c.role]
    if bal_col is None and not (dr_col and cr_col):
        diag.warn("no balance column recognised")
        return [], as_of
    if bal_col is not None:
        diag.note(f"balance taken from {bal_col.label!r}" + (" (statement balance column ignored)" if stmt and bal_col not in stmt else ""))
    rows: list[BankRow] = []
    roles = {c.idx: c.role for c in h.columns}
    n_skip = 0
    for r in grid.rows[h.data_start:]:
        cells = list(r) + [None] * (len(h.columns) - len(r))
        if all(clean_str(c) == "" for c in cells) or _is_total_row(cells, roles) or not _row_has_amounts(cells):
            n_skip += 1
            continue
        code = clean_str(cells[code_col.idx]) if code_col else ""
        name = clean_str(cells[name_col.idx]) if name_col else ""
        if not code and not name:
            n_skip += 1
            continue
        if bal_col is not None:
            bal = parse_number(cells[bal_col.idx])
        else:
            bal = (parse_cell(cells[dr_col.idx], "debit") or ZERO) - (parse_cell(cells[cr_col.idx], "credit") or ZERO)  # type: ignore[union-attr]
        if bal is None:
            n_skip += 1
            continue
        acc_no = clean_str(cells[no_col.idx]) if no_col else ""
        digits = re.sub(r"\D", "", acc_no)
        masked = f"****{digits[-4:]}" if len(digits) >= 4 else None
        m = BANK_WORDS.search(name or "")
        bank_name = m[0].title() if m else (name or code)
        bank_code = code or re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")[:40]
        cur = clean_str(cells[cur_col.idx]) if cur_col else ""
        rows.append(BankRow(bank_code, bank_name, masked, code or None, (cur or "MYR")[:3].upper(), bal))
    diag.counts.update({"bank_accounts": len(rows), "rows_skipped": n_skip, "with_masked_account_no": sum(1 for r in rows if r.account_no_masked)})
    diag.totals["cash_total"] = sum((r.closing_balance for r in rows), ZERO)
    return rows, as_of


# =============================================================================
# 6. Assembly: classified chart, derived movements, snapshot rows
# =============================================================================
@dataclass
class Account:
    account_code: str
    name: str
    source_type: str | None
    parent: str | None
    is_active: bool
    cls: Classification
    origin: str          # coa | tb | bank


@dataclass
class Bundle:
    entity: str
    fye_month: int
    accounts: dict[str, Account] = field(default_factory=dict)
    tb: list[TBRow] = field(default_factory=list)
    gl: list[dict[str, Any]] = field(default_factory=list)         # normalised gl_balances rows
    periods: list[date] = field(default_factory=list)
    ar: list[AgingRow] = field(default_factory=list)
    ap: list[AgingRow] = field(default_factory=list)
    ar_as_of: date | None = None
    ap_as_of: date | None = None
    bank: list[BankRow] = field(default_factory=list)
    bank_as_of: date | None = None
    diags: list[Diag] = field(default_factory=list)
    unknown_source_types: dict[str, int] = field(default_factory=dict)
    movement_notes: list[str] = field(default_factory=list)


def pick_convention(names: list[tuple[str, str]], requested: str, log: list[str]) -> str:
    """'auto': the code-range convention that agrees most often with strong name keywords."""
    if requested != "auto":
        return requested
    scores: dict[str, int] = {}
    for conv, table in CODE_CONVENTIONS.items():
        agree = 0
        for code, name in names:
            m = re.match(r"\D*(\d)", code or "")
            if not m or m[1] not in table:
                continue
            for rx, t, _s, _b, _c, strong in _KEYWORD_RX:
                if rx.search(name or ""):
                    if strong and t == table[m[1]]:
                        agree += 1
                    break
        scores[conv] = agree
    best = max(scores, key=lambda k: (scores[k], k == "generic"))
    log.append("note: code-range convention 'auto' -> " + ", ".join(f"{k}={v} agreements" for k, v in scores.items()) + f"; using {best!r} (TODO-VERIFY)")
    return best


def build_accounts(b: Bundle, coa_rows: list[COARow], overrides: dict[str, dict[str, Any]], convention: str) -> None:
    for r in coa_rows:
        cls = classify_account(r.account_code, r.name, r.source_type, None, overrides, convention)
        b.accounts[r.account_code] = Account(r.account_code, r.name, r.source_type, r.parent, r.is_active, cls, "coa")
        if r.source_type and _source_type_lookup(r.source_type) is None:
            b.unknown_source_types[r.source_type] = b.unknown_source_types.get(r.source_type, 0) + 1
    # accounts that appear in the TB but not in the chart: create them from the TB line
    for t in b.tb:
        if t.account_code not in b.accounts:
            cls = classify_account(t.account_code, t.name, t.source_type, t.section, overrides, convention)
            b.accounts[t.account_code] = Account(t.account_code, t.name or t.account_code, t.source_type, None, True, cls, "tb")
            if t.source_type and _source_type_lookup(t.source_type) is None:
                b.unknown_source_types[t.source_type] = b.unknown_source_types.get(t.source_type, 0) + 1
        elif b.accounts[t.account_code].origin == "coa" and not b.accounts[t.account_code].name and t.name:
            b.accounts[t.account_code].name = t.name
    # bank accounts with a GL code the TB/COA did not mention
    for bk in b.bank:
        if bk.gl_account_code and bk.gl_account_code not in b.accounts:
            cls = classify_account(bk.gl_account_code, bk.bank_name, "Bank", None, overrides, convention)
            b.accounts[bk.gl_account_code] = Account(bk.gl_account_code, bk.bank_name, "Bank", None, True, cls, "bank")


def derive_gl(b: Bundle, prior_closings: dict[str, Decimal] | None, prior_period: date | None) -> None:
    """gl_balances rows: closing from the TB, movements from month-on-month deltas.

    P&L closings in a trial balance are fiscal-year-to-date, so a month that
    starts a fiscal year has movement = closing. For the earliest loaded month
    the prior closing comes from the warehouse (prior_closings) when available;
    otherwise balance-sheet movements are 0 and P&L movements = YTD closing,
    which is flagged.
    """
    by_key: dict[tuple[date, str], TBRow] = {}
    for t in b.tb:
        k = (t.period_start, t.account_code)
        if k in by_key:  # duplicates summed
            prev = by_key[k]
            by_key[k] = TBRow(t.period_start, t.account_code, prev.name, (prev.debit or ZERO) + (t.debit or ZERO) if prev.debit is not None else None,
                              (prev.credit or ZERO) + (t.credit or ZERO) if prev.credit is not None else None, prev.closing + t.closing, prev.section, prev.source_type)
        else:
            by_key[k] = t
    b.periods = sorted({p for p, _ in by_key})
    if not b.periods:
        return
    gl: list[dict[str, Any]] = []
    first = b.periods[0]
    prev_closing: dict[str, Decimal] = {}
    if prior_closings and prior_period == add_months(first, -1):
        prev_closing = dict(prior_closings)
        b.movement_notes.append(f"{first:%Y-%m}: movements derived against warehouse closings of {prior_period:%Y-%m}")
    elif first != fiscal_year_start(first, b.fye_month):
        b.movement_notes.append(
            f"{first:%Y-%m} is the first month loaded and not the start of the fiscal year (FYE month {b.fye_month}): "
            f"its P&L movements are fiscal-YTD figures and balance-sheet movements are 0. Load the preceding month to fix.")
    else:
        b.movement_notes.append(f"{first:%Y-%m} is the first fiscal month: movements = closing balances")
    codes = sorted({c for _, c in by_key})
    for i, p in enumerate(b.periods):
        if i > 0 and b.periods[i - 1] != add_months(p, -1):
            b.movement_notes.append(f"gap between {b.periods[i - 1]:%Y-%m} and {p:%Y-%m}: movements for {p:%Y-%m} span the gap")
        fy0 = fiscal_year_start(p, b.fye_month)
        cur_closing: dict[str, Decimal] = {}
        for code in codes:
            t = by_key.get((p, code))
            acct = b.accounts[code]
            is_pl = acct.cls.account_type in PL_TYPES
            if t is None:
                # account absent from this month's TB: a trial balance lists every non-zero
                # balance, so the account is taken as zero (movement = -previous closing)
                prev = prev_closing.get(code)
                if prev is None or prev == ZERO:
                    continue
                cur_closing[code] = ZERO
                dr, cr = (ZERO, prev) if prev > 0 else (-prev, ZERO)
                gl.append({"entity_code": b.entity, "period_start": p, "period_end": month_end(p), "account_code": code,
                           "debit": dr, "credit": cr, "closing_balance": ZERO, "basis": "absent_zeroed"})
                continue
            closing = t.closing
            cur_closing[code] = closing
            if t.debit is not None and t.credit is not None:
                dr, cr, basis = t.debit, t.credit, "file_movements"
            else:
                if code in prev_closing and not (is_pl and p == fy0):
                    mv = closing - prev_closing[code]
                    basis = "delta"
                elif i == 0 and not prev_closing and not is_pl and p != fy0:
                    mv = ZERO
                    basis = "unknown_prior"
                elif i == 0 and not prev_closing and is_pl and p != fy0:
                    mv = closing
                    basis = "ytd_as_movement"
                else:
                    mv = closing
                    basis = "fy_start" if p == fy0 else "first_seen"
                dr, cr = (mv, ZERO) if mv >= 0 else (ZERO, -mv)
            gl.append({"entity_code": b.entity, "period_start": p, "period_end": month_end(p), "account_code": code,
                       "debit": dr, "credit": cr, "closing_balance": closing, "basis": basis})
        prev_closing = cur_closing
    b.gl = gl


# =============================================================================
# 7. Outputs: normalised CSVs, suggested account map, mapping report
# =============================================================================
def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        if not rows:
            fh.write(",".join(fieldnames or []) + "\n")
            return
        w = csv.DictWriter(fh, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else (v.isoformat() if isinstance(v, (date, datetime)) else v)) for k, v in r.items()})


def account_rows(b: Bundle) -> list[dict[str, Any]]:
    out = []
    for a in sorted(b.accounts.values(), key=lambda x: x.account_code):
        out.append({"entity_code": b.entity, "account_code": a.account_code, "name": a.name,
                    "account_type": a.cls.account_type, "account_subtype": a.cls.account_subtype,
                    "cashflow_bucket": a.cls.cashflow_bucket, "is_current": a.cls.is_current,
                    "parent_account_code": a.parent, "source_account_type": a.source_type, "is_active": a.is_active,
                    "origin": a.origin, "classified_by": a.cls.source, "confidence": a.cls.confidence, "note": a.cls.note})
    return out


def aging_rows(b: Bundle, rows: list[AgingRow], as_of: date | None) -> list[dict[str, Any]]:
    return [{"entity_code": b.entity, "as_of_date": as_of, "counterparty_code": r.counterparty_code,
             "counterparty_name": r.counterparty_name, "currency": r.currency, **{k: r.buckets[k] for k in BUCKETS},
             "total_outstanding": sum(r.buckets.values(), ZERO), "file_total": r.file_total} for r in rows]


def bank_rows(b: Bundle) -> list[dict[str, Any]]:
    return [{"entity_code": b.entity, "bank_account_code": r.bank_account_code, "bank_name": r.bank_name,
             "account_no_masked": r.account_no_masked, "gl_account_code": r.gl_account_code, "currency": r.currency,
             "balance_date": b.bank_as_of, "closing_balance": r.closing_balance, "source": "autocount"} for r in b.bank]


def period_rows(b: Bundle) -> list[dict[str, Any]]:
    return [{"entity_code": b.entity, "fiscal_year": fiscal_year_label(p, b.fye_month), "period_no": period_no(p, b.fye_month),
             "period_start": p, "period_end": month_end(p), "label": p.strftime("%b %Y")} for p in b.periods]


def write_outputs(b: Bundle, out: Path) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    files["chart_of_accounts"] = out / "chart_of_accounts.csv"
    write_csv(files["chart_of_accounts"], account_rows(b))
    files["fiscal_periods"] = out / "fiscal_periods.csv"
    write_csv(files["fiscal_periods"], period_rows(b), ["entity_code", "fiscal_year", "period_no", "period_start", "period_end", "label"])
    files["gl_balances"] = out / "gl_balances.csv"
    write_csv(files["gl_balances"], [{**g, "name": b.accounts[g["account_code"]].name, "account_type": b.accounts[g["account_code"]].cls.account_type} for g in b.gl],
              ["entity_code", "period_start", "period_end", "account_code", "name", "account_type", "debit", "credit", "closing_balance", "basis"])
    files["ar_aging"] = out / "ar_aging.csv"
    write_csv(files["ar_aging"], aging_rows(b, b.ar, b.ar_as_of), ["entity_code", "as_of_date", "counterparty_code", "counterparty_name", "currency", *BUCKETS, "total_outstanding", "file_total"])
    files["ap_aging"] = out / "ap_aging.csv"
    write_csv(files["ap_aging"], aging_rows(b, b.ap, b.ap_as_of), ["entity_code", "as_of_date", "counterparty_code", "counterparty_name", "currency", *BUCKETS, "total_outstanding", "file_total"])
    files["bank_balances"] = out / "bank_balances.csv"
    write_csv(files["bank_balances"], bank_rows(b), ["entity_code", "bank_account_code", "bank_name", "account_no_masked", "gl_account_code", "currency", "balance_date", "closing_balance", "source"])
    # template for the owner: every account that is not high-confidence (blank rows are ignored on load)
    sug = [{"account_code": a["account_code"], "account_type": a["account_type"], "account_subtype": a["account_subtype"] or "",
            "cashflow_bucket": a["cashflow_bucket"], "is_current": "" if a["is_current"] is None else str(a["is_current"]).lower(),
            "name": a["name"], "source_account_type": a["source_account_type"] or "", "classified_by": a["classified_by"],
            "confidence": a["confidence"], "note": a["note"]}
           for a in account_rows(b) if a["confidence"] != "high"]
    files["account_map_suggested"] = out / "account_map_suggested.csv"
    write_csv(files["account_map_suggested"], sug, ["account_code", "account_type", "account_subtype", "cashflow_bucket", "is_current",
                                                    "name", "source_account_type", "classified_by", "confidence", "note"])
    return files


def mapping_report(b: Bundle, existing: dict[str, dict[str, Any]] | None, files: dict[str, Path], mode: str) -> str:
    L: list[str] = []
    add = L.append
    add("=" * 78)
    add(f"AutoCount export import - mapping report   entity {b.entity}   FYE month {b.fye_month}   mode {mode}")
    add("=" * 78)
    for d in b.diags:
        add(f"\n[{d.kind}] {d.file}" + (f"  (sheet {d.sheet!r})" if d.sheet else ""))
        if d.header_row:
            add(f"  header row {d.header_row}" + (f" merged with row {d.merged_with}" if d.merged_with else ""))
        for c in d.columns:
            add(f"    {c}")
        for n in d.notes:
            add(f"  note: {n}")
        if d.counts:
            add("  counts: " + ", ".join(f"{k}={v}" for k, v in d.counts.items()))
        for k, v in d.totals.items():
            if isinstance(v, dict):
                add(f"  {k}: " + ", ".join(f"{kk}={fmt_amt(vv) if isinstance(vv, Decimal) else vv}" for kk, vv in v.items()))
            else:
                add(f"  {k}: {fmt_amt(v) if isinstance(v, Decimal) else v}")
        for w in d.warnings:
            add(f"  WARNING: {w}")
    if b.accounts:
        add("\n[accounts]")
        by_type: dict[str, int] = {}
        by_conf: dict[str, int] = {}
        by_src: dict[str, int] = {}
        for a in b.accounts.values():
            by_type[a.cls.account_type] = by_type.get(a.cls.account_type, 0) + 1
            by_conf[a.cls.confidence] = by_conf.get(a.cls.confidence, 0) + 1
            by_src[a.cls.source] = by_src.get(a.cls.source, 0) + 1
        add(f"  total {len(b.accounts)}: from COA file {sum(1 for a in b.accounts.values() if a.origin == 'coa')}, "
            f"created from TB lines {sum(1 for a in b.accounts.values() if a.origin == 'tb')}, from bank file {sum(1 for a in b.accounts.values() if a.origin == 'bank')}")
        add("  by account_type: " + ", ".join(f"{k}={by_type[k]}" for k in ACCOUNT_TYPES if k in by_type))
        add("  classified by:   " + ", ".join(f"{k}={v}" for k, v in sorted(by_src.items())))
        add("  confidence:      " + ", ".join(f"{k}={by_conf.get(k, 0)}" for k in ("high", "medium", "low")))
        if b.unknown_source_types:
            add("  UNMAPPED source account types (add to SOURCE_TYPE_MAP or account_map.csv): "
                + ", ".join(f"{k!r} x{v}" for k, v in sorted(b.unknown_source_types.items())))
        low = [a for a in b.accounts.values() if a.cls.confidence == "low"]
        if low:
            add(f"  low-confidence accounts ({len(low)}): " + ", ".join(f"{a.account_code} {a.name[:28]!r} -> {a.cls.account_type}" for a in low[:15]) + (" ..." if len(low) > 15 else ""))
        tb_only = sorted(a.account_code for a in b.accounts.values() if a.origin == "tb")
        if tb_only:
            add(f"  TB accounts not in the COA file: {tb_only[:30]}{' ...' if len(tb_only) > 30 else ''}")
        if existing is not None:
            new = sorted(c for c in b.accounts if c not in existing)
            changed = sorted(c for c, a in b.accounts.items() if c in existing and existing[c]["account_type"] != a.cls.account_type)
            add(f"  warehouse chart_of_accounts for {b.entity}: {len(existing)} existing, {len(new)} new from these files, "
                f"{len(changed)} where the warehouse account_type differs from this run's heuristic (warehouse value kept unless overridden)")
            if changed:
                add("    differing: " + ", ".join(f"{c}: db={existing[c]['account_type']} file={b.accounts[c].cls.account_type}" for c in changed[:15]))
    if b.periods:
        add("\n[gl_balances]")
        add("  periods: " + ", ".join(f"{p:%b %Y} (FY{fiscal_year_label(p, b.fye_month)} P{period_no(p, b.fye_month)})" for p in b.periods))
        add(f"  rows: {len(b.gl)}")
        for n in b.movement_notes:
            add(f"  note: {n}")
        for p in b.periods:
            rows = [g for g in b.gl if g["period_start"] == p]
            rev = sum((g["credit"] - g["debit"] for g in rows if b.accounts[g["account_code"]].cls.account_type == "revenue"), ZERO)
            cost = sum((g["debit"] - g["credit"] for g in rows if b.accounts[g["account_code"]].cls.account_type in ("cogs", "opex")), ZERO)
            cash = sum((g["closing_balance"] for g in rows if b.accounts[g["account_code"]].cls.account_subtype == "cash"), ZERO)
            net = sum((g["closing_balance"] for g in rows), ZERO)
            add(f"  {p:%b %Y}: revenue mv {fmt_amt(rev)}, cogs+opex mv {fmt_amt(cost)}, cash closing {fmt_amt(cash)}, sum of closings {fmt_amt(net)} {'OK' if net == 0 else 'NOT ZERO'}")
    for label, rows, as_of in (("ar_aging", b.ar, b.ar_as_of), ("ap_aging", b.ap, b.ap_as_of)):
        if rows:
            add(f"\n[{label}] as of {as_of}: {len(rows)} counterparties, total {fmt_amt(sum((sum(r.buckets.values(), ZERO) for r in rows), ZERO))} "
                f"(names only in {files.get(label)})")
    if b.bank:
        add(f"\n[bank_balances] as of {b.bank_as_of}: {len(b.bank)} accounts, total {fmt_amt(sum((r.closing_balance for r in b.bank), ZERO))}, "
            f"{sum(1 for r in b.bank if r.gl_account_code in b.accounts)} matched to a GL account")
    add("\n[files]")
    for k, p in files.items():
        add(f"  {k:<22} {p}")
    warns = sum(len(d.warnings) for d in b.diags)
    add(f"\n{warns} warning(s). " + ("DRY RUN: nothing was written. Review the CSVs, fill out/account_map_suggested.csv -> account_map.csv, then re-run with --write."
                                     if mode == "dry-run" else "Written to the warehouse."))
    return "\n".join(L)


# =============================================================================
# 8. Warehouse (psycopg). Same jsonb_to_recordset upsert pattern as
#    ../autocount-onprem/extract.py; natural keys; never deletes.
# =============================================================================
UPSERT_SQL = {
    # classification set on INSERT only (finance overrides in the warehouse persist) ...
    "chart_of_accounts": """
        insert into public.chart_of_accounts
          (entity_id, account_code, name, account_type, account_subtype, cashflow_bucket, is_current,
           parent_account_code, source_account_type, is_active, source_loaded_at)
        select e.id, r.account_code, r.name, r.account_type::public.account_type, r.account_subtype,
               r.cashflow_bucket::public.cashflow_bucket, r.is_current, r.parent_account_code,
               r.source_account_type, coalesce(r.is_active, true), now()
        from jsonb_to_recordset(%(rows)s::jsonb) as r(
               entity_code text, account_code text, name text, account_type text, account_subtype text,
               cashflow_bucket text, is_current boolean, parent_account_code text,
               source_account_type text, is_active boolean)
        join public.entities e on e.code = r.entity_code
        on conflict (entity_id, account_code) do update
          set name = excluded.name,
              parent_account_code = coalesce(excluded.parent_account_code, public.chart_of_accounts.parent_account_code),
              source_account_type = coalesce(excluded.source_account_type, public.chart_of_accounts.source_account_type),
              is_active = excluded.is_active,
              source_loaded_at = now()
    """,
    # ... except for rows from account_map.csv, where the owner's mapping always wins
    "chart_of_accounts_override": """
        insert into public.chart_of_accounts
          (entity_id, account_code, name, account_type, account_subtype, cashflow_bucket, is_current,
           parent_account_code, source_account_type, is_active, source_loaded_at)
        select e.id, r.account_code, r.name, r.account_type::public.account_type, r.account_subtype,
               r.cashflow_bucket::public.cashflow_bucket, r.is_current, r.parent_account_code,
               r.source_account_type, coalesce(r.is_active, true), now()
        from jsonb_to_recordset(%(rows)s::jsonb) as r(
               entity_code text, account_code text, name text, account_type text, account_subtype text,
               cashflow_bucket text, is_current boolean, parent_account_code text,
               source_account_type text, is_active boolean)
        join public.entities e on e.code = r.entity_code
        on conflict (entity_id, account_code) do update
          set name = excluded.name,
              account_type = excluded.account_type, account_subtype = excluded.account_subtype,
              cashflow_bucket = excluded.cashflow_bucket, is_current = excluded.is_current,
              parent_account_code = coalesce(excluded.parent_account_code, public.chart_of_accounts.parent_account_code),
              source_account_type = coalesce(excluded.source_account_type, public.chart_of_accounts.source_account_type),
              is_active = excluded.is_active,
              source_loaded_at = now()
    """,
    "fiscal_periods": """
        insert into public.fiscal_periods (entity_id, fiscal_year, period_no, period_start, period_end, label)
        select e.id,
               case when extract(month from r.period_start) > e.fiscal_year_end_month
                    then extract(year from r.period_start)::int + 1
                    else extract(year from r.period_start)::int end,
               ((extract(month from r.period_start)::int - e.fiscal_year_end_month - 1 + 12) %% 12) + 1,
               r.period_start, r.period_end, to_char(r.period_start, 'Mon YYYY')
        from jsonb_to_recordset(%(rows)s::jsonb) as r(entity_code text, period_start date, period_end date)
        join public.entities e on e.code = r.entity_code
        on conflict (entity_id, period_start) do nothing
    """,
    "gl_balances": """
        insert into public.gl_balances
          (entity_id, period_id, account_id, debit, credit, closing_balance, source_loaded_at, ingestion_run_id)
        select e.id, p.id, c.id, r.debit, r.credit, r.closing_balance, now(), %(run_id)s::uuid
        from jsonb_to_recordset(%(rows)s::jsonb) as r(
               entity_code text, period_start date, account_code text,
               debit numeric, credit numeric, closing_balance numeric)
        join public.entities e on e.code = r.entity_code
        join public.fiscal_periods p on p.entity_id = e.id and p.period_start = r.period_start
        join public.chart_of_accounts c on c.entity_id = e.id and c.account_code = r.account_code
        on conflict (entity_id, period_id, account_id) do update
          set debit = excluded.debit, credit = excluded.credit, closing_balance = excluded.closing_balance,
              source_loaded_at = now(), ingestion_run_id = excluded.ingestion_run_id
    """,
    "ar_aging": """
        insert into public.ar_aging
          (entity_id, as_of_date, counterparty_code, counterparty_name, currency,
           bucket_current, bucket_30, bucket_60, bucket_90, bucket_120_plus, source_loaded_at, ingestion_run_id)
        select e.id, r.as_of_date, r.counterparty_code, r.counterparty_name, coalesce(r.currency, 'MYR'),
               r.bucket_current, r.bucket_30, r.bucket_60, r.bucket_90, r.bucket_120_plus, now(), %(run_id)s::uuid
        from jsonb_to_recordset(%(rows)s::jsonb) as r(
               entity_code text, as_of_date date, counterparty_code text, counterparty_name text, currency text,
               bucket_current numeric, bucket_30 numeric, bucket_60 numeric, bucket_90 numeric, bucket_120_plus numeric)
        join public.entities e on e.code = r.entity_code
        on conflict (entity_id, as_of_date, counterparty_code) do update
          set counterparty_name = excluded.counterparty_name, currency = excluded.currency,
              bucket_current = excluded.bucket_current, bucket_30 = excluded.bucket_30, bucket_60 = excluded.bucket_60,
              bucket_90 = excluded.bucket_90, bucket_120_plus = excluded.bucket_120_plus,
              source_loaded_at = now(), ingestion_run_id = excluded.ingestion_run_id
    """,
    "bank_balances": """
        insert into public.bank_balances
          (entity_id, bank_account_code, bank_name, account_no_masked, gl_account_id, currency, balance_date, closing_balance,
           source, source_loaded_at, ingestion_run_id)
        select e.id, r.bank_account_code, r.bank_name, r.account_no_masked, c.id, coalesce(r.currency, 'MYR'), r.balance_date, r.closing_balance,
               coalesce(r.source, 'autocount'), now(), %(run_id)s::uuid
        from jsonb_to_recordset(%(rows)s::jsonb) as r(
               entity_code text, bank_account_code text, bank_name text, account_no_masked text, gl_account_code text,
               currency text, balance_date date, closing_balance numeric, source text)
        join public.entities e on e.code = r.entity_code
        left join public.chart_of_accounts c on c.entity_id = e.id and c.account_code = r.gl_account_code
        on conflict (entity_id, bank_account_code, balance_date) do update
          set closing_balance = excluded.closing_balance, bank_name = excluded.bank_name,
              account_no_masked = coalesce(excluded.account_no_masked, public.bank_balances.account_no_masked),
              gl_account_id = coalesce(excluded.gl_account_id, public.bank_balances.gl_account_id),
              source_loaded_at = now(), ingestion_run_id = excluded.ingestion_run_id
    """,
}
UPSERT_SQL["ap_aging"] = UPSERT_SQL["ar_aging"].replace("public.ar_aging", "public.ap_aging")


def jsonable(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        out.append({k: (str(v) if isinstance(v, Decimal) else v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in r.items()})
    return out


class Warehouse:
    def __init__(self, url: str):
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb

        self.conn = psycopg.connect(url, row_factory=dict_row, application_name="bk-autocount-excel-import", connect_timeout=20)
        self.conn.autocommit = False
        self.Jsonb = Jsonb

    def close(self) -> None:
        self.conn.close()

    def q(self, sql: str, params: Any = None) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else []

    def entity(self, code: str) -> dict[str, Any] | None:
        rows = self.q("select id, code, name, fiscal_year_end_month, source_system::text as source_system from public.entities where code = %s", (code,))
        return rows[0] if rows else None

    def ensure_entity(self, code: str, name: str, registration_no: str | None, source_system: str, fye_month: int) -> dict[str, Any]:
        self.q("""insert into public.entities (code, name, registration_no, source_system, fiscal_year_end_month)
                  values (%s, %s, %s, %s::public.source_system, %s) on conflict (code) do nothing""",
               (code, name, registration_no, source_system, fye_month))
        return self.entity(code)  # type: ignore[return-value]

    def existing_accounts(self, entity_id: str) -> dict[str, dict[str, Any]]:
        rows = self.q("select account_code, name, account_type::text as account_type, account_subtype, cashflow_bucket::text as cashflow_bucket "
                      "from public.chart_of_accounts where entity_id = %s", (entity_id,))
        return {r["account_code"]: r for r in rows}

    def prior_closings(self, entity_id: str, before: date) -> tuple[dict[str, Decimal], date | None]:
        rows = self.q("""select p.period_start, c.account_code, g.closing_balance
                         from public.gl_balances g
                         join public.fiscal_periods p on p.id = g.period_id
                         join public.chart_of_accounts c on c.id = g.account_id
                         where g.entity_id = %s and p.period_start = (
                           select max(period_start) from public.fiscal_periods where entity_id = %s and period_start < %s)""",
                      (entity_id, entity_id, before))
        if not rows:
            return {}, None
        return {r["account_code"]: Decimal(r["closing_balance"]) for r in rows}, rows[0]["period_start"]

    def run_source(self, fallback: str) -> str:
        vals = self.q("select unnest(enum_range(null::public.source_system))::text as v")
        return "excel_import" if any(r["v"] == "excel_import" for r in vals) else fallback

    def start_run(self, source: str, entity_id: str, meta: dict[str, Any]) -> str:
        run_id = str(self.q("insert into public.ingestion_runs (source, entity_id, dataset, triggered_by, metadata) "
                            "values (%s::public.source_system, %s, 'all', 'manual', %s) returning id",
                            (source, entity_id, self.Jsonb(meta)))[0]["id"])
        self.conn.commit()  # the running row survives a failed load
        return run_id

    def finish_run(self, run_id: str, status: str, extracted: int, upserted: int, error: str | None = None) -> None:
        self.q("update public.ingestion_runs set finished_at = now(), status = %s::public.ingestion_status, rows_extracted = %s, "
               "rows_upserted = %s, error_message = %s where id = %s", (status, extracted, upserted, (error or None) and error[:4000], run_id))

    def upsert(self, dataset: str, rows: list[dict[str, Any]], run_id: str) -> int:
        if not rows:
            return 0
        with self.conn.cursor() as cur:
            cur.execute(UPSERT_SQL[dataset], {"rows": self.Jsonb(jsonable(rows)), "run_id": run_id})
            return cur.rowcount


def write_warehouse(b: Bundle, wh: Warehouse, ent: dict[str, Any], meta: dict[str, Any], out_log: list[str]) -> tuple[str, dict[str, int]]:
    source = wh.run_source(ent["source_system"])
    if source != "excel_import":
        out_log.append("note: enum public.source_system has no 'excel_import' value yet (apply migrations/004_excel_import_source.sql); "
                       f"logging the run under source {source!r} with metadata.importer = 'excel_import'")
    meta = {**meta, "importer": "excel_import"}
    run_id = wh.start_run(source, str(ent["id"]), meta)
    counts: dict[str, int] = {}
    acc = account_rows(b)
    plain = [{k: v for k, v in a.items() if k not in ("origin", "classified_by", "confidence", "note")} for a in acc if a["classified_by"] != "override"]
    over = [{k: v for k, v in a.items() if k not in ("origin", "classified_by", "confidence", "note")} for a in acc if a["classified_by"] == "override"]
    gl = [{k: g[k] for k in ("entity_code", "period_start", "account_code", "debit", "credit", "closing_balance")} for g in b.gl]
    datasets = [
        ("chart_of_accounts", plain), ("chart_of_accounts_override", over), ("fiscal_periods", period_rows(b)), ("gl_balances", gl),
        ("ar_aging", [{k: v for k, v in r.items() if k not in ("total_outstanding", "file_total")} for r in aging_rows(b, b.ar, b.ar_as_of)]),
        ("ap_aging", [{k: v for k, v in r.items() if k not in ("total_outstanding", "file_total")} for r in aging_rows(b, b.ap, b.ap_as_of)]),
        ("bank_balances", bank_rows(b)),
    ]
    extracted = sum(len(r) for _, r in datasets)
    try:
        for name, rows in datasets:
            n = wh.upsert(name, rows, run_id)
            counts[name] = n
            if name == "gl_balances" and n < len(rows):
                raise RuntimeError(f"gl_balances: only {n} of {len(rows)} rows matched an account/period")
            if name in ("ar_aging", "ap_aging", "bank_balances") and n < len(rows):
                raise RuntimeError(f"{name}: only {n} of {len(rows)} rows loaded")
        wh.finish_run(run_id, "success", extracted, sum(counts.values()))
        wh.conn.commit()
    except Exception as exc:  # noqa: BLE001
        wh.conn.rollback()
        try:
            wh.finish_run(run_id, "failed", extracted, 0, f"{type(exc).__name__}: {exc}")
            wh.conn.commit()
        finally:
            pass
        raise
    return run_id, counts


# =============================================================================
# 9. CLI
# =============================================================================
def _split_file_period(spec: str) -> tuple[Path, date | None]:
    """'FILE' or 'FILE=YYYY-MM'."""
    if "=" in spec and not Path(spec).exists():
        f, p = spec.rsplit("=", 1)
        return Path(f), parse_period(p)
    return Path(spec), None


def main(argv: list[str] | None = None) -> int:
    if load_dotenv:
        load_dotenv(HERE.parents[1] / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entity", required=True, help="entity code, e.g. BKAC")
    ap.add_argument("--entity-name", default=None, help="name used when the entities row has to be created")
    ap.add_argument("--fye-month", type=int, default=None, choices=range(1, 13), metavar="1-12", help="financial year end month (default: entities table; 12 if no DB)")
    ap.add_argument("--source-system", default="autocount_cloud", choices=["autocount_cloud", "autocount_onprem"], help="entities.source_system when creating the entity")
    ap.add_argument("--tb", nargs="+", default=[], metavar="FILE[=YYYY-MM]", help="trial balance file(s)")
    ap.add_argument("--coa", default=None, metavar="FILE", help="chart of accounts export")
    ap.add_argument("--ar-aging", default=None, metavar="FILE", help="debtor aging export")
    ap.add_argument("--ap-aging", default=None, metavar="FILE", help="creditor aging export")
    ap.add_argument("--bank", default=None, metavar="FILE", help="bank book / bank reconciliation summary")
    ap.add_argument("--bank-from-tb", action="store_true", help="also create bank_balances rows at each TB month end from accounts with subtype 'cash'")
    ap.add_argument("--as-of", type=date.fromisoformat, default=None, help="snapshot date for aging / bank (YYYY-MM-DD)")
    ap.add_argument("--period", type=parse_period, default=None, help="month for TB files that carry no detectable period (YYYY-MM)")
    ap.add_argument("--sheet", default=None, help="worksheet name to read (default: first non-empty sheet)")
    ap.add_argument("--account-map", type=Path, default=Path("account_map.csv"), help="owner overrides: account_code, account_type, account_subtype, cashflow_bucket[, is_current]")
    ap.add_argument("--code-convention", default="auto", choices=["auto", *sorted(CODE_CONVENTIONS)], help="code-range fallback convention; auto = whichever agrees most with the account names (TODO-VERIFY)")
    ap.add_argument("--out", type=Path, default=Path("out"), help="folder for normalised CSVs and the report")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True, help="report + CSVs only (default)")
    g.add_argument("--write", action="store_true", help="upsert into the warehouse (DATABASE_URL)")
    ap.add_argument("--database-url", default=None, help="overrides DATABASE_URL / WAREHOUSE_DATABASE_URL")
    args = ap.parse_args(argv)
    mode = "write" if args.write else "dry-run"
    if not (args.tb or args.coa or args.ar_aging or args.ap_aging or args.bank):
        ap.error("nothing to import: give at least one of --tb/--coa/--ar-aging/--ap-aging/--bank")

    url = args.database_url or os.environ.get("DATABASE_URL") or os.environ.get("WAREHOUSE_DATABASE_URL")
    if args.write and not url:
        raise SystemExit("--write needs DATABASE_URL (or WAREHOUSE_DATABASE_URL) in the environment")
    wh: Warehouse | None = None
    ent: dict[str, Any] | None = None
    log: list[str] = []
    if url:
        try:
            wh = Warehouse(url)
            ent = wh.entity(args.entity)
        except Exception as exc:  # noqa: BLE001
            if args.write:
                raise SystemExit(f"cannot connect to the warehouse: {exc}") from exc
            log.append(f"note: warehouse not reachable ({type(exc).__name__}); dry-run continues without DB comparison")
            wh = None
    known = KNOWN_ENTITIES.get(args.entity, {})
    fye = args.fye_month
    if fye is None and ent:
        fye = int(ent["fiscal_year_end_month"])
        log.append(f"note: FYE month {fye} taken from the entities table")
    elif fye is not None and ent and int(ent["fiscal_year_end_month"]) != fye:
        log.append(f"WARNING: --fye-month {fye} differs from entities.fiscal_year_end_month {ent['fiscal_year_end_month']}; the CLI value is used for this run")
    if fye is None:
        fye = 12
        log.append("WARNING: no --fye-month and no entities row: assuming financial year end = December (12). Pass --fye-month to be sure.")

    b = Bundle(entity=args.entity, fye_month=fye)
    overrides = load_account_map(args.account_map)
    if overrides:
        log.append(f"note: {len(overrides)} account overrides loaded from {args.account_map}")
    elif args.account_map and args.account_map != Path("account_map.csv"):
        log.append(f"WARNING: --account-map {args.account_map} not found")

    # --- parse every file -------------------------------------------------
    coa_rows: list[COARow] = []
    if args.coa:
        d = Diag("chart_of_accounts", Path(args.coa).name)
        b.diags.append(d)
        coa_rows = parse_coa(load_grid(Path(args.coa), args.sheet), d)
    for spec in args.tb:
        path, per = _split_file_period(spec)
        d = Diag("trial_balance", path.name)
        b.diags.append(d)
        b.tb.extend(parse_trial_balance(load_grid(path, args.sheet), per or args.period, d))
    if args.ar_aging:
        d = Diag("ar_aging", Path(args.ar_aging).name)
        b.diags.append(d)
        b.ar, b.ar_as_of = parse_aging(load_grid(Path(args.ar_aging), args.sheet), args.as_of, d)
    if args.ap_aging:
        d = Diag("ap_aging", Path(args.ap_aging).name)
        b.diags.append(d)
        b.ap, b.ap_as_of = parse_aging(load_grid(Path(args.ap_aging), args.sheet), args.as_of, d)
    if args.bank:
        d = Diag("bank_balances", Path(args.bank).name)
        b.diags.append(d)
        b.bank, b.bank_as_of = parse_bank(load_grid(Path(args.bank), args.sheet), args.as_of, d)

    convention = pick_convention([(r.account_code, r.name) for r in coa_rows] + [(t.account_code, t.name) for t in b.tb], args.code_convention, log)
    build_accounts(b, coa_rows, overrides, convention)
    prior, prior_p = ({}, None)
    if wh and ent and b.tb:
        prior, prior_p = wh.prior_closings(str(ent["id"]), min(t.period_start for t in b.tb))
    derive_gl(b, prior, prior_p)
    if args.bank_from_tb and b.gl:
        last = b.periods[-1]
        extra = [BankRow(g["account_code"], (BANK_WORDS.search(b.accounts[g["account_code"]].name) or [b.accounts[g["account_code"]].name])[0],
                         None, g["account_code"], "MYR", g["closing_balance"])
                 for g in b.gl if g["period_start"] == last and b.accounts[g["account_code"]].cls.account_subtype == "cash"]
        if extra and not b.bank:
            b.bank, b.bank_as_of = extra, month_end(last)
            log.append(f"note: --bank-from-tb: {len(extra)} bank_balances rows at {b.bank_as_of} from TB cash accounts")
        elif extra:
            log.append("note: --bank-from-tb ignored because --bank was given")
    existing = wh.existing_accounts(str(ent["id"])) if (wh and ent) else None

    files = write_outputs(b, args.out)
    report = mapping_report(b, existing, files, mode)
    if log:
        report = "\n".join(log) + "\n" + report
    print(report)
    (args.out / "mapping_report.txt").write_text(report + "\n", encoding="utf-8")

    hard = [w for d in b.diags for w in d.warnings if "does not balance" in w or "no header" in w or "not found" in w and "period" in w]
    if not args.write:
        if wh:
            wh.close()
        return 1 if hard else 0
    if hard:
        print("\nREFUSING to write: fix the warnings above first (unbalanced TB / missing header / missing period).")
        wh.close()  # type: ignore[union-attr]
        return 2
    assert wh is not None
    if ent is None:
        ent = wh.ensure_entity(args.entity, args.entity_name or known.get("name") or args.entity, known.get("registration_no"), args.source_system, fye)
        print(f"created entities row {args.entity} ({ent['name']}, FYE month {fye}, {args.source_system})")
    meta = {"files": [Path(_split_file_period(s)[0]).name for s in args.tb] + [Path(f).name for f in (args.coa, args.ar_aging, args.ap_aging, args.bank) if f],
            "periods": [p.isoformat() for p in b.periods], "as_of": args.as_of.isoformat() if args.as_of else None,
            "fye_month": fye, "code_convention": convention, "overrides": len(overrides), "host": os.uname().nodename,
            "warnings": sum(len(d.warnings) for d in b.diags)}
    try:
        run_id, counts = write_warehouse(b, wh, ent, meta, log)
    finally:
        wh.close()
    print(f"\nWRITTEN. ingestion_runs.id = {run_id}; rows upserted: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    for line in log[-1:]:
        if line.startswith("note: enum"):
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
