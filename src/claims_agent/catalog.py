"""Local schema catalog — stand-in for the AWS Glue Data Catalog.

In production this metadata would come from the Glue Data Catalog APIs.
Locally it is a static, version-controlled description of the DuckDB
tables that stand in for Athena tables.  Every column carries a
``pii`` flag; PII columns are enforced by the guardrails module.
"""
from __future__ import annotations

CATALOG: dict[str, dict] = {
    "policies": {
        "description": "Insurance policies (synthetic). One row per policy.",
        "columns": {
            "policy_id": {"type": "VARCHAR", "pii": False, "description": "Policy identifier, e.g. POL-00001"},
            "product_line": {"type": "VARCHAR", "pii": False, "description": "Auto, Home, Commercial, or Life"},
            "state": {"type": "VARCHAR", "pii": False, "description": "Two-letter US state code"},
            "effective_date": {"type": "DATE", "pii": False, "description": "Policy start date"},
            "expiry_date": {"type": "DATE", "pii": False, "description": "Policy end date"},
            "premium_amount": {"type": "DOUBLE", "pii": False, "description": "Annual premium in USD"},
            "underwriting_tier": {"type": "VARCHAR", "pii": False, "description": "Preferred, Standard, or Substandard"},
        },
    },
    "claims": {
        "description": "Insurance claims (synthetic). One row per claim.",
        "columns": {
            "claim_id": {"type": "VARCHAR", "pii": False, "description": "Claim identifier, e.g. CLM-00001"},
            "policy_id": {"type": "VARCHAR", "pii": False, "description": "FK to policies.policy_id"},
            "claim_date": {"type": "DATE", "pii": False, "description": "Date the claim was filed"},
            "incident_date": {"type": "DATE", "pii": False, "description": "Date of the incident"},
            "claim_type": {"type": "VARCHAR", "pii": False, "description": "Collision, Theft, Fire, Water Damage, Wind/Hail, Liability, or Medical"},
            "claim_status": {"type": "VARCHAR", "pii": False, "description": "Open, Closed, Denied, or In Review"},
            "claim_amount": {"type": "DOUBLE", "pii": False, "description": "Amount claimed in USD"},
            "paid_amount": {"type": "DOUBLE", "pii": False, "description": "Amount paid in USD (0 for denied/open)"},
            "deductible_amount": {"type": "DOUBLE", "pii": False, "description": "Deductible in USD"},
            "state": {"type": "VARCHAR", "pii": False, "description": "Two-letter US state code where the claim occurred"},
            "fraud_flag": {"type": "BOOLEAN", "pii": False, "description": "True if flagged for suspected fraud"},
            "adjuster_id": {"type": "VARCHAR", "pii": False, "description": "Adjuster identifier, e.g. ADJ-007"},
            "claimant_name": {"type": "VARCHAR", "pii": True, "description": "PII — claimant full name (BLOCKED)"},
            "claimant_ssn": {"type": "VARCHAR", "pii": True, "description": "PII — claimant SSN (BLOCKED)"},
            "claimant_email": {"type": "VARCHAR", "pii": True, "description": "PII — claimant email (BLOCKED)"},
            "claimant_phone": {"type": "VARCHAR", "pii": True, "description": "PII — claimant phone (BLOCKED)"},
        },
    },
    "claim_payments": {
        "description": "Payments made on claims (synthetic). One row per payment.",
        "columns": {
            "payment_id": {"type": "VARCHAR", "pii": False, "description": "Payment identifier"},
            "claim_id": {"type": "VARCHAR", "pii": False, "description": "FK to claims.claim_id"},
            "payment_date": {"type": "DATE", "pii": False, "description": "Payment date"},
            "payment_amount": {"type": "DOUBLE", "pii": False, "description": "Payment amount in USD"},
            "payment_method": {"type": "VARCHAR", "pii": False, "description": "Check, ACH, or Card"},
        },
    },
    "adjusters": {
        "description": "Claims adjusters (synthetic, internal staff only).",
        "columns": {
            "adjuster_id": {"type": "VARCHAR", "pii": False, "description": "Adjuster identifier"},
            "adjuster_name": {"type": "VARCHAR", "pii": False, "description": "Internal staff name"},
            "region": {"type": "VARCHAR", "pii": False, "description": "Midwest, Northeast, South, or West"},
            "team": {"type": "VARCHAR", "pii": False, "description": "Auto, Property, or Liability team"},
        },
    },
}

PII_COLUMNS: frozenset[str] = frozenset(
    col for table in CATALOG.values() for col, meta in table["columns"].items() if meta["pii"]
)

# Table-level keyword hints used by schema retrieval.
TABLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "policies": ("policy", "policies", "premium", "product line", "product_line", "underwriting"),
    "claims": ("claim", "claims", "fraud", "deductible", "incident", "adjuster claim"),
    "claim_payments": ("payment", "payments", "paid out via", "payment method"),
    "adjusters": ("adjuster", "adjusters", "region", "team"),
}


def list_tables() -> list[str]:
    return sorted(CATALOG)


def describe_table(table: str) -> dict:
    if table not in CATALOG:
        raise KeyError(f"unknown table: {table!r}; known tables: {sorted(CATALOG)}")
    return CATALOG[table]


def all_columns() -> dict[str, str]:
    """column name -> table name (first table wins for shared names)."""
    out: dict[str, str] = {}
    for table, meta in CATALOG.items():
        for col in meta["columns"]:
            out.setdefault(col, table)
    return out
