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
    "bank_name":         [r"^bank( name)?$", r"\bbank\s*name\b", r"\bbank\b.*\bname\b"],
    "opening":           [r"\bopening\b", r"\bb/f\b", r"\bbrought forward\b", r"\bbeginning\b"],
    "account_type":      [r"\bspecial\s*(account|acc)?\s*type\b", r"\b(account|acc|a/c)\s*type\b", r"^type$", r"\bnature\b", r"\bcategory\b", r"\bclass(ification)?\b"],
    "parent":            [r"\bparent\b", r"\bgroup\s*(account|acc)\b"],
    "currency":          [r"^curr(ency)?(\s*code)?$"],
    "account_code":      [r"\b(account|acc|a/c|gl)\.?\s*(no|number|code|num)\b", r"^(acc|account|a/c|gl)\.?\s*(no\.?)?$", r"^code$", r"\baccno\b"],
    "name":              [r"\bdescription\b", r"\b(account|acc|a/c)\s*name\b", r"^name$", r"\bparticulars\b", r"^desc\.?$", r"\baccount\b.*\bname\b"],
    "debit":             [r"\bdebit\b", r"^dr\.?$", r"\bdr\b"],
    "credit":            [r"\bcredit\b", r"^cr\.?$", r"\bcr\b"],
    "total":             [r"\b(grand\s*)?total\b", r"\boutstanding\b", r"\bamount due\b", r"\bnet\b"],
    "bucket":            [r"^current$", r"\bnot (yet )?due\b", r"\d+\s*-\s*\d+", r"\d+\s*to\s*\d+", r"[>+]\s*\d+|\d+\s*\+|\bover\s*\d+|\babove\s*\d+|\d+\s*(days?)?\s*(and|&)\s*(above|over|more)",
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

    def fragment(j: int) -> bool:
        if j < 0 or j >= len(grid.rows):
            return False
        r = grid.rows[j]
        labels = [clean_str(c) for c in r if clean_str(c)]
        if len(set(labels)) < 2 or _row_has_amounts(r) or _is_title_row(r):
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
    m = re.search(r"(\d+)\s*(?:-|to|–)\s*(\d+)", n)
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
    (r"\b(maybank|cimb|public bank|rhb|hong leong|ambank|ocbc|uob|hsbc|bank islam|affin|alliance bank|bsn|standard chartered|agrobank|bank rakyat|mbsb|touch ?n ?go|current account|savings? account|fixed deposit)\b", "asset", "cash", "cash", True, True),
    (r"\bbank\s*(charges|fee|commission|interest)", "opex", None, "operating", None, True),
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
    (r"\b(term loan|hire purchase|h/p|hp (creditor|liabilit|payable)|bank loan|financing|lease liabilit|borrowing)", "liability", "borrowing", "financing", False, True),
    (r"\boverdraft\b", "liability", "borrowing", "financing", True, True),
    (r"\b(director|partner)s?'?s?\s*(loan|advance|account|current account|a/c)\b|\bamount (due|owing) to\b|\badvance from\b|\bdeposit(s)? (received|from customer)|\bunearned|\bdeferred (income|revenue)|\bcustomer deposit", "liability", "other_payable", "financing", True, True),
    (r"\b(share|paid.?up|partners?'?s?|members?'?s?|ordinary)\s*(capital|contribution)\b|\bcapital (account|contribution)\b|\bcapital\b", "equity", "share_capital", "financing", None, True),
    (r"\b(retained|accumulated|unappropriated)\s*(earnings?|profits?|loss(es)?)\b|\breserves?\b|\bdrawings?\b|\bprofit (and|&) loss (b/f|account|appropriation)|\bcurrent year (profit|earnings)", "equity", "retained_earnings", "financing", None, True),
    (r"\binterest (income|received|receivable)|\bdividend|\brental income|\bgain on|\b(forex|fx|exchange|currency)\s*(gain|loss)|\bloss on (disposal|sale)|\bgain|\bother income|\bsundry income|\bmisc(ellaneous)? income|\bwrite[- ]?back|\bbad debt recover", "other", None, "operating", None, True),
    (r"\b(interest expense|interest paid|interest on|finance (cost|charge)|hp interest|loan interest|late payment interest)", "other", "interest", "financing", None, True),
    (r"\b(income tax|taxation|tax expense|deferred tax|corporate tax|tax provision)\b", "other", "tax", "operating", None, True),
    (r"\b(cost of (sales|goods|services|revenue)|direct cost|trainer(s)?'? ?fee|speaker fee|facilitator|venue (cost|rental|hire)|course material|training material|purchase[sd]?|subcontract|freelance (trainer|fee)|cogs)\b", "cogs", None, "operating", None, True),
    (r"\b(training|course|seminar|workshop|programme|program|consultan(cy|t)|advisory|professional|service|management|tuition|coaching|facilitation|speaking|licen[cs]ing|membership|subscription|sponsorship)\s*(fees?|income|revenue|charges?)\b|\b(sales|revenue|fees? income|fee income|income from)\b|\brevenue\b|\bsales\b", "revenue", None, "operating", None, True),
    (r"\b(salar|wages|bonus|allowance|epf|socso|eis|kwsp|perkeso|staff|payroll|commission|director(s)?'? (fee|remuneration)|medical|training (cost|expense)|hrd corp levy)\b", "opex", None, "operating", None, True),
    (r"\b(rent(al)?|utilit|electric|water|telephone|internet|mobile|postage|courier|printing|stationer|office|insurance|travel|petrol|parking|toll|transport|accommodation|entertain|refreshment|market|advertis|promotion|website|domain|hosting|software subscription|zoom|canva|audit|secretarial|tax agent|legal|professional fee|accounting fee|licen[cs]e|permit|upkeep|repair|maintenance|cleaning|donation|penalt|fine|general|sundry|misc|expense|charges?|fee)\b", "opex", None, "operating", None, False),
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
    # 'Current Asset (CA)' / 'CA - Current Asset'
    for part in re.split(r"[()/,\-]+", key):
        part = part.strip()
        if part in SOURCE_TYPE_MAP:
            return SOURCE_TYPE_MAP[part]
    return None


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
        cols = {norm_text(c): c for c in (rdr.fieldnames or [])}
        if "account_code" not in cols or "account_type" not in cols:
            raise SystemExit(f"{path}: needs columns account_code and account_type")
        for i, r in enumerate(rdr, start=2):
            code = clean_str(r.get(cols["account_code"]))
            t = norm_text(r.get(cols["account_type"]))
            if not code or not t:
                continue  # rows left blank in the suggested template are ignored
            if t not in ACCOUNT_TYPES:
                raise SystemExit(f"{path} line {i}: account_type {t!r} not one of {ACCOUNT_TYPES}")
            st = norm_text(r.get(cols.get("account_subtype", ""), "")) or None
            if st and st not in SUBTYPES:
                raise SystemExit(f"{path} line {i}: account_subtype {st!r} not one of {SUBTYPES}")
            b = norm_text(r.get(cols.get("cashflow_bucket", ""), "")) or None
            if b and b not in CASHFLOW_BUCKETS:
                raise SystemExit(f"{path} line {i}: cashflow_bucket {b!r} not one of {CASHFLOW_BUCKETS}")
            ic_raw = norm_text(r.get(cols.get("is_current", ""), ""))
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
                    v = parse_number(cells[c.idx])
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
            opening = parse_number(cells[g["opening"].idx]) if "opening" in g else None
            dr = parse_number(cells[g["debit"].idx]) if "debit" in g else None
            cr = parse_number(cells[g["credit"].idx]) if "credit" in g else None
            bal = parse_number(cells[g["balance"].idx]) if "balance" in g else None
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
            bal = (parse_number(cells[dr_col.idx]) or ZERO) - (parse_number(cells[cr_col.idx]) or ZERO)  # type: ignore[union-attr]
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
