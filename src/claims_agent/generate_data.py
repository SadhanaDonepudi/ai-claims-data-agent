"""Generate the synthetic claims database (DuckDB) + Glue-style catalog.

All data is SYNTHETIC — invented names/SSNs, no real policyholders.
Deterministic (seed 42) so the evaluation harness is reproducible.
DuckDB stands in for Athena; ``data/catalog.json`` stands in for the
AWS Glue Data Catalog.
"""
from __future__ import annotations

import json
import pathlib
import random
from datetime import date, timedelta

import duckdb

from .catalog import CATALOG

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIRST = ["Ava","Liam","Maya","Noah","Zoe","Eli","Nora","Omar","Ivy","Leo","Ruby","Sam","Tara","Hugo","Lena","Cole"]
LAST = ["Patel","Nguyen","Garcia","Smith","Khan","Brown","Lee","Diaz","Shah","Kim","Ross","Ali","Ford","Reyes","Wong","Hill"]
STATES = ["IL","CA","TX","NY","FL","OH","WA","CO","GA","NC","MI","PA","AZ","TN","IN"]
CLAIM_TYPES = ["Collision","Theft","Fire","Water Damage","Wind/Hail","Liability","Medical"]
STATUSES = ["Open","Closed","Denied","In Review"]
PRODUCTS = ["Auto","Home","Commercial","Life"]
REGIONS = ["Midwest","Northeast","South","West"]


def build_database(db_path: pathlib.Path | str) -> pathlib.Path:
    rng = random.Random(42)
    db_path = pathlib.Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    con.execute("""CREATE TABLE policies (policy_id VARCHAR, product_line VARCHAR, state VARCHAR,
        effective_date DATE, expiry_date DATE, premium_amount DOUBLE, underwriting_tier VARCHAR)""")
    con.execute("""CREATE TABLE claims (claim_id VARCHAR, policy_id VARCHAR, claim_date DATE, incident_date DATE,
        claim_type VARCHAR, claim_status VARCHAR, claim_amount DOUBLE, paid_amount DOUBLE,
        deductible_amount DOUBLE, state VARCHAR, fraud_flag BOOLEAN, adjuster_id VARCHAR,
        claimant_name VARCHAR, claimant_ssn VARCHAR, claimant_email VARCHAR, claimant_phone VARCHAR)""")
    con.execute("""CREATE TABLE claim_payments (payment_id VARCHAR, claim_id VARCHAR, payment_date DATE,
        payment_amount DOUBLE, payment_method VARCHAR)""")
    con.execute("CREATE TABLE adjusters (adjuster_id VARCHAR, adjuster_name VARCHAR, region VARCHAR, team VARCHAR)")

    adjusters = []
    for i in range(1, 31):
        adjusters.append((f"ADJ-{i:03d}", f"{rng.choice(FIRST)} {rng.choice(LAST)}", rng.choice(REGIONS), rng.choice(["Auto","Property","Liability"])))
    policies = []
    for i in range(1, 2001):
        eff = date(2022,1,1) + timedelta(days=rng.randrange(0, 1100))
        policies.append((f"POL-{i:05d}", rng.choice(PRODUCTS), rng.choice(STATES), eff,
                         eff + timedelta(days=365), round(rng.uniform(240, 4800), 2),
                         rng.choice(["Preferred","Standard","Standard","Substandard"])))

    claims, payments = [], []
    pid = 1
    for i in range(1, 3501):
        pol = rng.choice(policies)
        cdate = date(2023,1,1) + timedelta(days=rng.randrange(0, 1095))
        status = rng.choice(STATUSES)
        amount = round(rng.uniform(120, 48000), 2)
        paid = 0.0 if status in ("Denied","Open") else round(amount * rng.uniform(0.45, 0.98), 2)
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        claims.append((f"CLM-{i:05d}", pol[0], cdate, cdate - timedelta(days=rng.randrange(0,60)),
                       rng.choice(CLAIM_TYPES), status, amount, paid,
                       rng.choice([250.0,500.0,500.0,1000.0]), rng.choice(STATES),
                       rng.random() < 0.04, rng.choice(adjusters)[0], name,
                       f"900-01-{i:04d}", f"{name.split()[0].lower()}.{name.split()[1].lower()}@example.invalid",
                       f"555-01{i%100:02d}"))
        if paid > 0:
            payments.append((f"PAY-{pid:05d}", f"CLM-{i:05d}", cdate + timedelta(days=rng.randrange(5,90)),
                             paid, rng.choice(["Check","ACH","ACH","Card"])))
            pid += 1
    # Bulk-load via pandas (row-by-row executemany is very slow in DuckDB here).
    import pandas as pd
    for name, rows_data in (("adjusters", adjusters), ("policies", policies), ("claims", claims), ("claim_payments", payments)):
        df = pd.DataFrame(rows_data)
        con.register("_tmp_df", df)
        con.execute(f"INSERT INTO {name} SELECT * FROM _tmp_df")
        con.unregister("_tmp_df")

    # Glue-Data-Catalog stand-in: schema metadata table inside DuckDB too.
    con.execute("CREATE TABLE schema_catalog (table_name VARCHAR, column_name VARCHAR, data_type VARCHAR, is_pii BOOLEAN, description VARCHAR)")
    rows = [(t, c, m["type"], m["pii"], m["description"]) for t, meta in CATALOG.items() for c, m in meta["columns"].items()]
    con.executemany("INSERT INTO schema_catalog VALUES (?,?,?,?,?)", rows)
    con.close()

    (ROOT / "data" / "catalog.json").write_text(json.dumps(CATALOG, indent=2))
    print(f"policies={len(policies)} claims={len(claims)} payments={len(payments)} adjusters={len(adjusters)} db={db_path}")
    return db_path


if __name__ == "__main__":
    build_database(ROOT / "data" / "claims.duckdb")
