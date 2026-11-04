#!/usr/bin/env python3
"""
AutoCount Accounting (on-premise, SQL Server) -> finance warehouse (Supabase Postgres).

Read-only extraction per entity:
  1. start an ingestion_runs row in the warehouse (service-role DB connection)
  2. query the AutoCount reporting views (queries/*.sql) over pyodbc, read-only intent
  3. stage every dataset as CSV in EXTRACT_OUTPUT_DIR/<entity>/<run-date>/
  4. upsert into the warehouse via jsonb_to_recordset ... on conflict (idempotent)
  5. close the ingestion_runs row (success / failed + error)

Usage
  python extract.py --entity BKTS                 # last EXTRACT_LOOKBACK_MONTHS months + current
  python extract.py --entity all --months 3
  python extract.py --entity HITS --dry-run       # extract + CSV only, no warehouse writes
  python extract.py --entity BKTS --replay out/BKTS/2026-11-04   # re-load from staged CSVs (no SQL Server)

Config: environment variables (see dashboard/.env.example). A dashboard/.env
file is loaded automatically if present. No secrets on the command line.

Schedule with cron on a host inside the office network, after AutoCount's
own nightly jobs, e.g.  15 2 * * *  (Asia/Kuala_Lumpur):
  15 2 * * * cd /opt/bk-dash && /opt/bk-dash/.venv/bin/python extract.py --entity all >> /var/log/bk-extract.log 2>&1
"""
from __future__ import annotations

import argparse
import calendar
import csv
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv is optional
    load_dotenv = None

HERE = Path(__file__).resolve().parent
QUERIES = HERE / "queries"
log = logging.getLogger("bk.extract")

# ---------------------------------------------------------------------------
# AutoCount account type -> dashboard classification
# TODO-VERIFY: the AccType labels below are AutoCount Accounting's standard
# special account types as commonly seen in the UI; confirm the exact strings
# in dbo.vw_bk_dash_chart_of_accounts (select distinct AccType).
# Keep in sync with the ACCTYPE_MAP in ../autocount-cloud/n8n-workflow.json.
# (account_type, account_subtype, cashflow_bucket, is_current)
# ---------------------------------------------------------------------------
ACCTYPE_MAP: dict[str, tuple[str, str | None, str, bool | None]] = {
    "bank":                        ("asset", "cash", "cash", True),
    "cash":                        ("asset", "cash", "cash", True),
    "debtor control":              ("asset", "trade_receivable", "operating", True),
    "current asset":               ("asset", None, "operating", True),
    "stock":                       ("asset", "inventory", "operating", True),
    "deposit":                     ("asset", "other_receivable", "operating", True),
    "fixed asset":                 ("asset", "fixed_asset", "investing", False),
    "accumulated depreciation":    ("asset", "fixed_asset", "investing", False),
    "investment":                  ("asset", None, "investing", False),
    "other asset":                 ("asset", None, "investing", False),
    "creditor control":            ("liability", "trade_payable", "operating", True),
    "current liability":           ("liability", None, "operating", True),
    "long term liability":         ("liability", "borrowing", "financing", False),
    "capital":                     ("equity", "share_capital", "financing", None),
    "reserves":                    ("equity", "retained_earnings", "financing", None),
    "retained earning":            ("equity", "retained_earnings", "financing", None),
    "sales":                       ("revenue", None, "operating", None),
    "sales adjustment":            ("revenue", None, "operating", None),
    "cost of goods sold":          ("cogs", None, "operating", None),
    "expenses":                    ("opex", None, "operating", None),
    "other income":                ("other", None, "operating", None),
    "taxation":                    ("other", "tax", "operating", None),
    "extraordinary income/expense": ("other", None, "operating", None),
}
PL_TYPES = {"revenue", "cogs", "opex", "other"}


def classify(acc_type_raw: str | None, name: str) -> tuple[str, str | None, str, bool | None]:
    key = (acc_type_raw or "").strip().lower()
    account_type, subtype, bucket, is_current = ACCTYPE_MAP.get(key, ("other", None, "operating", None))
    n = name.lower()
    # name hints refine the subtype (finance can still override in the warehouse)
    if account_type == "opex":
        if "depreciation" in n:
            subtype, bucket = "depreciation", "non_cash"
        elif "amortis" in n or "amortiz" in n:
            subtype, bucket = "amortisation", "non_cash"
    elif account_type == "other":
        if "interest" in n:
            subtype, bucket = "interest", "financing"
        elif "tax" in n and "deferred" not in n:
            subtype = "tax"
    elif account_type == "liability" and subtype is None:
        if "accrual" in n:
            subtype = "accrual"
        elif "tax" in n or "sst" in n or "cp204" in n:
            subtype = "tax_payable"
        elif "loan" in n or "hire purchase" in n or "financing" in n:
            subtype = "borrowing"
    return account_type, subtype, bucket, is_current


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass
class Config:
    sql_server: str
    sql_port: str
    sql_user: str
    sql_password: str
    sql_driver: str
    sql_encrypt: str
    sql_trust_cert: str
    sql_timeout: int
    entities: dict[str, dict[str, Any]]
    lookback_months: int
    output_dir: Path
    warehouse_url: str
    max_retries: int

    @staticmethod
    def from_env() -> "Config":
        def need(k: str) -> str:
            v = os.environ.get(k, "").strip()
            if not v:
                raise SystemExit(f"missing env var {k} (see dashboard/.env.example)")
            return v

        return Config(
            sql_server=os.environ.get("AUTOCOUNT_SQL_SERVER", ""),
            sql_port=os.environ.get("AUTOCOUNT_SQL_PORT", "1433"),
            sql_user=os.environ.get("AUTOCOUNT_SQL_USER", ""),
            sql_password=os.environ.get("AUTOCOUNT_SQL_PASSWORD", ""),
            sql_driver=os.environ.get("AUTOCOUNT_SQL_DRIVER", "ODBC Driver 18 for SQL Server"),
            sql_encrypt=os.environ.get("AUTOCOUNT_SQL_ENCRYPT", "yes"),
            sql_trust_cert=os.environ.get("AUTOCOUNT_SQL_TRUST_SERVER_CERTIFICATE", "no"),
            sql_timeout=int(os.environ.get("AUTOCOUNT_SQL_TIMEOUT_SECONDS", "60")),
            entities=json.loads(need("AUTOCOUNT_ONPREM_ENTITIES")),
            lookback_months=int(os.environ.get("EXTRACT_LOOKBACK_MONTHS", "2")),
            output_dir=Path(os.environ.get("EXTRACT_OUTPUT_DIR", "./out")),
            warehouse_url=need("WAREHOUSE_DATABASE_URL"),
            max_retries=int(os.environ.get("EXTRACT_MAX_RETRIES", "3")),
        )


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------
def retry(fn: Callable[[], Any], what: str, tries: int, base_delay: float = 3.0) -> Any:
    last: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - we re-raise after the last attempt
            last = exc
            if attempt == tries:
                break
            delay = base_delay * (2 ** (attempt - 1))
            log.warning("%s failed (attempt %d/%d): %s; retrying in %.0fs", what, attempt, tries, exc, delay)
            time.sleep(delay)
    raise RuntimeError(f"{what} failed after {tries} attempts: {last}") from last


def month_start(d: date) -> date:
    return d.replace(day=1)


def month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def fiscal_year_start(d: date, fye_month: int) -> date:
    """First day of the fiscal year containing d, for a year end in fye_month."""
    fy_start_month = fye_month % 12 + 1
    y = d.year if d.month >= fy_start_month else d.year - 1
    if fye_month == 12:
        y = d.year
    return date(y, fy_start_month, 1)


def dec(v: Any) -> Decimal:
    if v is None or v == "":
        return Decimal("0")
    return Decimal(str(v)).quantize(Decimal("0.01"))


def jsonable(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        o = {}
        for k, v in r.items():
            if isinstance(v, Decimal):
                o[k] = str(v)
            elif isinstance(v, (date, datetime)):
                o[k] = v.isoformat()
            else:
                o[k] = v
        out.append(o)
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        if not rows:
            fh.write("")
            return
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


# ---------------------------------------------------------------------------
# Source: AutoCount SQL Server (read-only)
# ---------------------------------------------------------------------------
class Source:
    def __init__(self, cfg: Config, database: str):
        import pyodbc  # imported lazily so --replay works without ODBC installed

        server = cfg.sql_server if "\\" in cfg.sql_server else f"{cfg.sql_server},{cfg.sql_port}"
        conn_str = (
            f"DRIVER={{{cfg.sql_driver}}};SERVER={server};DATABASE={database};"
            f"UID={cfg.sql_user};PWD={cfg.sql_password};"
            f"Encrypt={cfg.sql_encrypt};TrustServerCertificate={cfg.sql_trust_cert};"
            f"ApplicationIntent=ReadOnly;APP=bk-finance-dash-extract;"
            f"Connection Timeout={cfg.sql_timeout};"
        )
        self.conn = pyodbc.connect(conn_str, autocommit=True, readonly=True, timeout=cfg.sql_timeout)
        self.conn.timeout = cfg.sql_timeout
        cur = self.conn.cursor()
        # belt and braces: nothing we run should ever block AutoCount users
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")  # TODO: switch to SNAPSHOT if enabled on the DB
        cur.execute("SET LOCK_TIMEOUT 5000")
        cur.close()

    def query(self, name: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        sql = (QUERIES / f"{name}.sql").read_text(encoding="utf-8")
        cur = self.conn.cursor()
        cur.execute(sql, params or [])
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
        log.info("source %-18s %6d rows", name, len(rows))
        return rows

    def close(self) -> None:
        self.conn.close()


# ---------------------------------------------------------------------------
# Warehouse: Supabase Postgres (service role / postgres user over TLS)
# Upserts use jsonb_to_recordset so one statement per dataset, resolved by
# natural keys (entity code, account code, period start) - no UUIDs leave Postgres.
# ---------------------------------------------------------------------------
UPSERT_SQL = {
    # classification columns are set on INSERT only; finance overrides in the warehouse persist
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
              parent_account_code = excluded.parent_account_code,
              source_account_type = excluded.source_account_type,
              is_active = excluded.is_active,
              source_loaded_at = now()
    """,
    # fiscal year / period number derived from the entity's own year end
    "fiscal_periods": """
        insert into public.fiscal_periods (entity_id, fiscal_year, period_no, period_start, period_end, label)
        select e.id,
               case when extract(month from r.period_start) > e.fiscal_year_end_month
                    then extract(year from r.period_start)::int + 1
                    else extract(year from r.period_start)::int end,
               ((extract(month from r.period_start)::int - e.fiscal_year_end_month - 1 + 12) %% 12) + 1,  -- %% = SQL modulo (escaped for psycopg)
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
          (entity_id, bank_account_code, bank_name, gl_account_id, currency, balance_date, closing_balance,
           source, source_loaded_at, ingestion_run_id)
        select e.id, r.bank_account_code, r.bank_name, c.id, 'MYR', r.balance_date, r.closing_balance,
               'autocount', now(), %(run_id)s::uuid
        from jsonb_to_recordset(%(rows)s::jsonb) as r(
               entity_code text, bank_account_code text, bank_name text, balance_date date, closing_balance numeric)
        join public.entities e on e.code = r.entity_code
        left join public.chart_of_accounts c on c.entity_id = e.id and c.account_code = r.bank_account_code
        on conflict (entity_id, bank_account_code, balance_date) do update
          set closing_balance = excluded.closing_balance, bank_name = excluded.bank_name,
              gl_account_id = excluded.gl_account_id, source_loaded_at = now(), ingestion_run_id = excluded.ingestion_run_id
    """,
}
UPSERT_SQL["ap_aging"] = UPSERT_SQL["ar_aging"].replace("public.ar_aging", "public.ap_aging")


class Warehouse:
    def __init__(self, url: str):
        import psycopg
        from psycopg.rows import dict_row

        self.conn = psycopg.connect(url, row_factory=dict_row, application_name="bk-finance-dash-extract",
                                    connect_timeout=20)
        self.Jsonb = __import__("psycopg.types.json", fromlist=["Jsonb"]).Jsonb

    def entity(self, code: str) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute("select id, code, fiscal_year_end_month, source_system::text as source_system "
                        "from public.entities where code = %s and is_active", (code,))
            row = cur.fetchone()
        if not row:
            raise SystemExit(f"entity {code} not found in warehouse entities table (seed it first)")
        if row["source_system"] != "autocount_onprem":
            raise SystemExit(f"entity {code} is {row['source_system']}, not autocount_onprem")
        return row

    def start_run(self, entity_id: str, dataset: str, meta: dict[str, Any]) -> str:
        with self.conn.cursor() as cur:
            cur.execute(
                "insert into public.ingestion_runs (source, entity_id, dataset, triggered_by, metadata) "
                "values ('autocount_onprem', %s, %s, %s, %s) returning id",
                (entity_id, dataset, meta.get("triggered_by", "schedule"), self.Jsonb(meta)))
            run_id = str(cur.fetchone()["id"])
        self.conn.commit()
        return run_id

    def finish_run(self, run_id: str, status: str, extracted: int, upserted: int, error: str | None = None) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "update public.ingestion_runs set finished_at = now(), status = %s, rows_extracted = %s, "
                "rows_upserted = %s, error_message = %s where id = %s",
                (status, extracted, upserted, (error or None) and error[:4000], run_id))
        self.conn.commit()

    def upsert(self, dataset: str, rows: list[dict[str, Any]], run_id: str) -> int:
        if not rows:
            return 0
        with self.conn.cursor() as cur:
            cur.execute(UPSERT_SQL[dataset], {"rows": self.Jsonb(jsonable(rows)), "run_id": run_id})
            n = cur.rowcount
        self.conn.commit()
        if n < len(rows) and dataset != "fiscal_periods":
            log.warning("%s: %d of %d rows loaded (missing account/period mappings?)", dataset, n, len(rows))
        log.info("warehouse %-16s %6d rows upserted", dataset, n)
        return n

    def close(self) -> None:
        self.conn.close()


# ---------------------------------------------------------------------------
# Transformations (source rows -> warehouse rows)
# ---------------------------------------------------------------------------
def tx_chart_of_accounts(entity_code: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        name = str(r.get("Description") or r.get("AccNo"))
        account_type, subtype, bucket, is_current = classify(r.get("AccType"), name)
        out.append({
            "entity_code": entity_code,
            "account_code": str(r["AccNo"]).strip(),
            "name": name,
            "account_type": account_type,
            "account_subtype": subtype,
            "cashflow_bucket": bucket,
            "is_current": is_current,
            "parent_account_code": (str(r["ParentAccNo"]).strip() if r.get("ParentAccNo") else None),
            "source_account_type": r.get("AccType"),
            "is_active": str(r.get("IsActive", "1")) not in ("0", "False", "false", "F"),
        })
    return out


def tx_gl(entity_code: str, rows: list[dict[str, Any]], coa: list[dict[str, Any]],
          periods: list[date], fye_month: int) -> list[dict[str, Any]]:
    """Movements per month + closing balance. Balance-sheet closing = running
    balance (all history). P&L closing = fiscal-year-to-date movements."""
    pl_accounts = {c["account_code"] for c in coa if c["account_type"] in PL_TYPES}
    by_acct: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        ps = r["PeriodStart"] if isinstance(r["PeriodStart"], date) else date.fromisoformat(str(r["PeriodStart"])[:10])
        by_acct.setdefault(str(r["AccNo"]).strip(), []).append({**r, "PeriodStart": ps})
    wanted = set(periods)
    out = []
    for acct, lines in by_acct.items():
        lines.sort(key=lambda x: x["PeriodStart"])
        for ln in lines:
            ps = ln["PeriodStart"]
            if ps not in wanted:
                continue
            debit, credit = dec(ln["Debit"]), dec(ln["Credit"])
            if acct in pl_accounts:
                fy0 = fiscal_year_start(ps, fye_month)
                closing = sum((dec(x["Debit"]) - dec(x["Credit"]) for x in lines if fy0 <= x["PeriodStart"] <= ps), Decimal("0"))
            else:
                closing = dec(ln["RunningBalance"])
            out.append({"entity_code": entity_code, "period_start": ps, "account_code": acct,
                        "debit": debit, "credit": credit, "closing_balance": closing})
    return out


def tx_aging(entity_code: str, rows: list[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    """Bucket open items by days overdue at as_of (by due date)."""
    agg: dict[str, dict[str, Any]] = {}
    for r in rows:
        code = str(r["CounterpartyCode"]).strip()
        due = r["DueDate"] if isinstance(r["DueDate"], date) else date.fromisoformat(str(r["DueDate"])[:10])
        amt = dec(r["Outstanding"])
        days = (as_of - due).days
        bucket = ("bucket_current" if days <= 0 else "bucket_30" if days <= 30 else "bucket_60" if days <= 60
                  else "bucket_90" if days <= 90 else "bucket_120_plus")
        a = agg.setdefault(code, {
            "entity_code": entity_code, "as_of_date": as_of, "counterparty_code": code,
            "counterparty_name": str(r.get("CounterpartyName") or code), "currency": (r.get("CurrencyCode") or "MYR"),
            "bucket_current": Decimal("0"), "bucket_30": Decimal("0"), "bucket_60": Decimal("0"),
            "bucket_90": Decimal("0"), "bucket_120_plus": Decimal("0")})
        a[bucket] += amt
    return list(agg.values())


def tx_bank(entity_code: str, rows: list[dict[str, Any]], d_from: date, d_to: date) -> list[dict[str, Any]]:
    """Forward-fill movement-day balances into one row per account per calendar day."""
    by_acct: dict[str, list[tuple[date, Decimal, str]]] = {}
    for r in rows:
        bd = r["BalanceDate"] if isinstance(r["BalanceDate"], date) else date.fromisoformat(str(r["BalanceDate"])[:10])
        by_acct.setdefault(str(r["BankAccountCode"]).strip(), []).append((bd, dec(r["ClosingBalance"]), str(r.get("BankAccountName") or "")))
    out = []
    for acct, pts in by_acct.items():
        pts.sort()
        name = pts[-1][2]
        i, bal = 0, None
        d = d_from
        while d <= d_to:
            while i < len(pts) and pts[i][0] <= d:
                bal = pts[i][1]
                i += 1
            if bal is not None:
                out.append({"entity_code": entity_code, "bank_account_code": acct, "bank_name": name,
                            "balance_date": d, "closing_balance": bal})
            d += timedelta(days=1)
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
@dataclass
class RunResult:
    extracted: int = 0
    upserted: int = 0
    datasets: dict[str, int] = field(default_factory=dict)


def run_entity(cfg: Config, code: str, months: int, as_of: date, dry_run: bool, replay: Path | None) -> RunResult:
    ent_cfg = cfg.entities.get(code)
    if not ent_cfg:
        raise SystemExit(f"{code}: not in AUTOCOUNT_ONPREM_ENTITIES")
    wh = retry(lambda: Warehouse(cfg.warehouse_url), "warehouse connect", cfg.max_retries)
    ent = wh.entity(code)
    fye = int(ent["fiscal_year_end_month"])

    periods = [add_months(month_start(as_of), -n) for n in range(months, -1, -1)]  # oldest .. current month
    gl_from = min(fiscal_year_start(periods[0], fye), periods[0])                    # need FY start for P&L YTD
    gl_to = month_end(periods[-1])
    bank_from = periods[0] - timedelta(days=120)                                     # history for forward fill

    stage = replay or (cfg.output_dir / code / as_of.isoformat())
    meta = {"database": ent_cfg["database"], "periods": [p.isoformat() for p in periods], "as_of": as_of.isoformat(),
            "gl_from": gl_from.isoformat(), "gl_to": gl_to.isoformat(), "dry_run": dry_run,
            "replay": str(replay) if replay else None, "host": os.uname().nodename,
            "triggered_by": "backfill" if replay else ("manual" if sys.stdin.isatty() else "schedule")}
    run_id = wh.start_run(str(ent["id"]), "all", meta)
    log.info("%s run %s periods %s..%s", code, run_id, periods[0], periods[-1])
    res = RunResult()
    try:
        if replay:
            raw = {n: read_csv(stage / f"{n}.csv") for n in ("chart_of_accounts", "gl_balances", "ar_aging", "ap_aging", "bank_balances")}
        else:
            src = retry(lambda: Source(cfg, ent_cfg["database"]), f"{code} SQL Server connect", cfg.max_retries)
            try:
                raw = {
                    "chart_of_accounts": src.query("chart_of_accounts"),
                    "gl_balances": src.query("gl_balances", [gl_from, gl_to]),
                    "ar_aging": src.query("ar_aging", [as_of]),
                    "ap_aging": src.query("ap_aging", [as_of]),
                    "bank_balances": src.query("bank_balances", [bank_from, as_of]),
                }
            finally:
                src.close()
            for name, rows in raw.items():
                write_csv(stage / f"{name}.csv", rows)
            log.info("staged CSVs in %s", stage)
        res.extracted = sum(len(v) for v in raw.values())

        coa = tx_chart_of_accounts(code, raw["chart_of_accounts"])
        period_rows = [{"entity_code": code, "period_start": p, "period_end": month_end(p)} for p in periods]
        gl = tx_gl(code, raw["gl_balances"], coa, periods, fye)
        ar = tx_aging(code, raw["ar_aging"], as_of)
        ap = tx_aging(code, raw["ap_aging"], as_of)
        bank = tx_bank(code, raw["bank_balances"], periods[0], as_of)

        # trial balance sanity: movements must net to zero per period
        for p in periods:
            net = sum((r["debit"] - r["credit"] for r in gl if r["period_start"] == p), Decimal("0"))
            if net != 0:
                log.warning("%s %s: debits - credits = %s (TB does not balance; check view / unposted docs)", code, p, net)

        if dry_run:
            log.info("dry-run: would upsert coa=%d periods=%d gl=%d ar=%d ap=%d bank=%d",
                     len(coa), len(period_rows), len(gl), len(ar), len(ap), len(bank))
            wh.finish_run(run_id, "success", res.extracted, 0, "dry-run")
            return res

        for name, rows in (("chart_of_accounts", coa), ("fiscal_periods", period_rows), ("gl_balances", gl),
                           ("ar_aging", ar), ("ap_aging", ap), ("bank_balances", bank)):
            n = retry(lambda: wh.upsert(name, rows, run_id), f"upsert {name}", cfg.max_retries)
            res.datasets[name] = n
            res.upserted += n
        status = "success" if res.datasets.get("gl_balances", 0) == len(gl) else "partial"
        wh.finish_run(run_id, status, res.extracted, res.upserted,
                      None if status == "success" else "some gl rows skipped: accounts missing from chart_of_accounts")
        return res
    except Exception as exc:  # noqa: BLE001
        log.exception("%s failed", code)
        try:
            wh.finish_run(run_id, "failed", res.extracted, res.upserted, f"{type(exc).__name__}: {exc}")
        finally:
            wh.close()
        raise
    finally:
        try:
            wh.close()
        except Exception:  # noqa: BLE001
            pass


def main(argv: list[str] | None = None) -> int:
    if load_dotenv:
        load_dotenv(HERE.parents[1] / ".env")   # dashboard/.env
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entity", required=True, help="entity code from AUTOCOUNT_ONPREM_ENTITIES, or 'all'")
    ap.add_argument("--months", type=int, default=None, help="months back to (re)load, default EXTRACT_LOOKBACK_MONTHS")
    ap.add_argument("--as-of", type=lambda s: date.fromisoformat(s), default=None, help="aging/bank as-of date (default: yesterday, KL)")
    ap.add_argument("--dry-run", action="store_true", help="extract and stage CSVs, no warehouse writes")
    ap.add_argument("--replay", type=Path, default=None, help="load from a staged CSV folder instead of SQL Server")
    args = ap.parse_args(argv)

    logging.basicConfig(level=os.environ.get("EXTRACT_LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = Config.from_env()
    kl_now = datetime.now(timezone(timedelta(hours=8)))
    as_of = args.as_of or (kl_now.date() - timedelta(days=1))
    months = cfg.lookback_months if args.months is None else args.months
    codes = list(cfg.entities) if args.entity == "all" else [args.entity]

    failures = 0
    for code in codes:
        try:
            r = run_entity(cfg, code, months, as_of, args.dry_run, args.replay)
            log.info("%s done: extracted=%d upserted=%d %s", code, r.extracted, r.upserted, r.datasets)
        except Exception:  # noqa: BLE001
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
