"""Rule/template-based natural-language -> SQL generator (NO LLM).

Pattern matching over question intents with slot filling. This is the
local substitute for Claude tool use: deterministic, fully testable,
and honest about its coverage — questions outside the templates raise
``UnsupportedQuestion`` instead of hallucinating SQL.
"""
from __future__ import annotations

import re

CLAIM_TYPES = ["Collision", "Theft", "Fire", "Water Damage", "Wind/Hail", "Liability", "Medical"]
STATUSES = ["Open", "Closed", "Denied", "In Review"]
PRODUCT_LINES = ["Auto", "Home", "Commercial", "Life"]
REGIONS = ["Midwest", "Northeast", "South", "West"]
PAYMENT_METHODS = ["Check", "ACH", "Card"]
STATES = ["IL","CA","TX","NY","FL","OH","WA","CO","GA","NC","MI","PA","AZ","TN","IN"]

class UnsupportedQuestion(Exception):
    pass

def _norm(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower().rstrip("?.!"))

def _find(q: str, values: list[str]) -> str | None:
    for v in values:
        if v.lower() in q:
            return v
    return None

def _year(q: str) -> int | None:
    m = re.search(r"\b(20\d{2})\b", q)
    return int(m.group(1)) if m else None

def _threshold(q: str) -> float | None:
    m = re.search(r"(?:over|above|greater than|more than|exceeding)\s+\$?([\d,]+(?:\.\d+)?)", q)
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(r"\$([\d,]+(?:\.\d+)?)\s+or more", q)
    return float(m.group(1).replace(",", "")) if m else None

def _top_n(q: str) -> int | None:
    m = re.search(r"top\s+(\d+)", q)
    return int(m.group(1)) if m else None

def _state(q: str) -> str | None:
    # "in IL", "for TX", "state of CA" or a bare two-letter code
    m = re.search(r"(?:state of|in|for)\s+([A-Z]{2})\b", q)  # applied to original-case later
    return None  # placeholder, actual logic in generate()

def generate_sql(question: str) -> str:
    raw = question
    q = _norm(question)
    # --- explicit status / type / product / method slots (case-sensitive state handled separately)
    status = _find(q, STATUSES)
    ctype = _find(q, CLAIM_TYPES)
    product = _find(q, PRODUCT_LINES)
    method = _find(q, PAYMENT_METHODS)
    year = _year(q)
    thresh = _threshold(q)
    topn = _top_n(q)
    state_m = re.search(r"\b([A-Z]{2})\b", raw)
    # avoid matching words like "IN" at sentence start: require the code to be a known state
    state = None
    for cand in re.findall(r"\b([A-Z]{2})\b", raw):
        if cand in STATES:
            state = cand; break

    def where_claims(extra: list[str] | None = None) -> str:
        clauses = []
        if status: clauses.append(f"claim_status = '{status}'")
        if ctype: clauses.append(f"claim_type = '{ctype}'")
        if state: clauses.append(f"state = '{state}'")
        if year: clauses.append(f"EXTRACT(YEAR FROM claim_date) = {year}")
        if thresh is not None: clauses.append(f"claim_amount > {thresh:g}")
        if extra: clauses.extend(extra)
        return (" WHERE " + " AND ".join(clauses)) if clauses else ""

    # fraud
    if "fraud" in q:
        flag = "false" if ("non-fraud" in q or "not fraud" in q or "without fraud" in q) else "true"
        if "how many" in q or "count" in q or "number of" in q:
            return f"SELECT COUNT(*) AS claim_count FROM claims WHERE fraud_flag = {flag}"
        if "total" in q and ("amount" in q or "paid" in q):
            col = "paid_amount" if "paid" in q else "claim_amount"
            return f"SELECT SUM({col}) AS total FROM claims WHERE fraud_flag = {flag}"

    # payments
    if "payment" in q:
        wpm = f" WHERE payment_method = '{method}'" if method and ("check" in q or "ach" in q or "card" in q) else ""
        if "by payment method" in q or "by method" in q:
            agg = "SUM(payment_amount) AS total" if ("total" in q or "sum" in q) else "COUNT(*) AS payment_count"
            return f"SELECT payment_method, {agg} FROM claim_payments GROUP BY payment_method ORDER BY 2 DESC"
        if "average" in q or "avg" in q:
            return f"SELECT AVG(payment_amount) AS avg_payment FROM claim_payments{wpm}"
        if "total" in q or "sum" in q or "how much" in q:
            return f"SELECT SUM(payment_amount) AS total_paid FROM claim_payments{wpm}"
        if "how many" in q or "count" in q or "number of" in q:
            return f"SELECT COUNT(*) AS payment_count FROM claim_payments{wpm}"
        if "largest" in q or "maximum" in q or "max" in q:
            return "SELECT MAX(payment_amount) AS max_payment FROM claim_payments"

    # adjusters
    if "adjuster" in q and ("how many" in q or "count" in q) and "claim" not in q:
        wr = f" WHERE region = '{_find(q, REGIONS)}'" if _find(q, REGIONS) else ""
        return f"SELECT COUNT(*) AS adjuster_count FROM adjusters{wr}"
    if "adjuster" in q and "by region" in q:
        return "SELECT region, COUNT(*) AS adjuster_count FROM adjusters GROUP BY region ORDER BY adjuster_count DESC"
    if "claims per adjuster" in q or "claims by adjuster" in q:
        return "SELECT adjuster_id, COUNT(*) AS claim_count FROM claims GROUP BY adjuster_id ORDER BY claim_count DESC"
    if "adjuster" in q and ("busiest" in q or "most claims" in q):
        return "SELECT adjuster_id, COUNT(*) AS claim_count FROM claims GROUP BY adjuster_id ORDER BY claim_count DESC LIMIT 1"

    # policies
    if "polic" in q and "claim" not in q:
        wp = []
        if product: wp.append(f"product_line = '{product}'")
        if state: wp.append(f"state = '{state}'")
        wsql = (" WHERE " + " AND ".join(wp)) if wp else ""
        if "by product" in q or "by product line" in q:
            if "premium" in q:
                return "SELECT product_line, SUM(premium_amount) AS total_premium FROM policies GROUP BY product_line ORDER BY total_premium DESC"
            return "SELECT product_line, COUNT(*) AS policy_count FROM policies GROUP BY product_line ORDER BY policy_count DESC"
        if "by state" in q:
            return "SELECT state, COUNT(*) AS policy_count FROM policies GROUP BY state ORDER BY policy_count DESC"
        if "by underwriting" in q or "by tier" in q:
            return "SELECT underwriting_tier, COUNT(*) AS policy_count FROM policies GROUP BY underwriting_tier ORDER BY policy_count DESC"
        if "average premium" in q or "avg premium" in q:
            return f"SELECT AVG(premium_amount) AS avg_premium FROM policies{wsql}"
        if "total premium" in q or "premium revenue" in q or "sum" in q and "premium" in q:
            return f"SELECT SUM(premium_amount) AS total_premium FROM policies{wsql}"
        if "highest premium" in q or "maximum premium" in q or "max premium" in q:
            return f"SELECT MAX(premium_amount) AS max_premium FROM policies{wsql}"
        if "how many" in q or "count" in q or "number of" in q:
            return f"SELECT COUNT(*) AS policy_count FROM policies{wsql}"

    # claims by policy product line (join)
    if "product line" in q and "claim" in q:
        join = "claims c JOIN policies p ON c.policy_id = p.policy_id"
        if "average" in q or "avg" in q:
            return f"SELECT p.product_line, AVG(c.claim_amount) AS avg_claim FROM {join} GROUP BY p.product_line ORDER BY avg_claim DESC"
        if "total" in q or "sum" in q:
            col = "c.paid_amount" if "paid" in q else "c.claim_amount"
            return f"SELECT p.product_line, SUM({col}) AS total FROM {join} GROUP BY p.product_line ORDER BY total DESC"
        return f"SELECT p.product_line, COUNT(*) AS claim_count FROM {join} GROUP BY p.product_line ORDER BY claim_count DESC"

    # monthly trend
    if "month" in q and "claim" in q:
        y = year or 2024
        return (f"SELECT CAST(EXTRACT(MONTH FROM claim_date) AS INTEGER) AS month, COUNT(*) AS claim_count "
                f"FROM claims WHERE EXTRACT(YEAR FROM claim_date) = {y} GROUP BY month ORDER BY month")
    if "by year" in q and "claim" in q:
        if "total" in q:
            return "SELECT CAST(EXTRACT(YEAR FROM claim_date) AS INTEGER) AS year, SUM(claim_amount) AS total FROM claims GROUP BY year ORDER BY year"
        return "SELECT CAST(EXTRACT(YEAR FROM claim_date) AS INTEGER) AS year, COUNT(*) AS claim_count FROM claims GROUP BY year ORDER BY year"

    # grouped claims
    group_map = [
        ("by claim type", "claim_type"), ("by type", "claim_type"),
        ("by status", "claim_status"), ("by claim status", "claim_status"),
        ("by state", "state"),
    ]
    is_top = ("top" in q) or ("highest" in q and "claim" in q and "amount" not in q) or ("most claims" in q)
    for phrase, col in group_map:
        if phrase in q:
            if "average" in q or "avg" in q:
                return f"SELECT {col}, AVG(claim_amount) AS avg_claim FROM claims{where_claims() if col not in ('claim_status','claim_type','state') else ''} GROUP BY {col} ORDER BY avg_claim DESC"
            if "total paid" in q:
                return f"SELECT {col}, SUM(paid_amount) AS total_paid FROM claims GROUP BY {col} ORDER BY total_paid DESC"
            if "total" in q or "sum" in q:
                return f"SELECT {col}, SUM(claim_amount) AS total FROM claims GROUP BY {col} ORDER BY total DESC"
            limit = f" LIMIT {topn}" if topn else ""
            return f"SELECT {col}, COUNT(*) AS claim_count FROM claims GROUP BY {col} ORDER BY claim_count DESC{limit}"

    if is_top or "which state" in q or "which claim type" in q:
        if "claim type" in q:
            agg = "SUM(paid_amount) AS total_paid" if "paid" in q else ("SUM(claim_amount) AS total" if "total" in q else "COUNT(*) AS claim_count")
            order = agg.split(" AS ")[1]
            return f"SELECT claim_type, {agg} FROM claims GROUP BY claim_type ORDER BY {order} DESC LIMIT {topn or 1}"
        if "state" in q:
            agg = "SUM(claim_amount) AS total" if "total" in q else "COUNT(*) AS claim_count"
            order = agg.split(" AS ")[1]
            return f"SELECT state, {agg} FROM claims GROUP BY state ORDER BY {order} DESC LIMIT {topn or 1}"

    # claim aggregates / counts
    if "claim" in q or "claims" in q:
        if "how many" in q or "number of" in q or (("count" in q) and "total" not in q and "amount" not in q):
            return f"SELECT COUNT(*) AS claim_count FROM claims{where_claims()}"
        if "average deductible" in q or "avg deductible" in q:
            return f"SELECT AVG(deductible_amount) AS avg_deductible FROM claims{where_claims()}"
        if "total deductible" in q:
            return f"SELECT SUM(deductible_amount) AS total_deductible FROM claims{where_claims()}"
        if "largest" in q or "maximum claim" in q or "max claim" in q or "biggest claim" in q:
            return f"SELECT MAX(claim_amount) AS max_claim FROM claims{where_claims()}"
        if "smallest" in q or "minimum claim" in q or "min claim" in q:
            return f"SELECT MIN(claim_amount) AS min_claim FROM claims{where_claims()}"
        if "average" in q or "avg" in q:
            col = "paid_amount" if "paid" in q else "claim_amount"
            return f"SELECT AVG({col}) AS avg_amount FROM claims{where_claims()}"
        if "total paid" in q or ("paid" in q and ("total" in q or "sum" in q or "how much" in q)):
            return f"SELECT SUM(paid_amount) AS total_paid FROM claims{where_claims()}"
        if "total" in q or "sum" in q:
            return f"SELECT SUM(claim_amount) AS total_claim_amount FROM claims{where_claims()}"

    # Noun-less fallbacks: the metric name alone implies the table.
    if "deductible" in q:
        if "average" in q or "avg" in q:
            return "SELECT AVG(deductible_amount) AS avg_deductible FROM claims"
        return "SELECT SUM(deductible_amount) AS total_deductible FROM claims"
    if "premium" in q:
        if "by product" in q:
            return "SELECT product_line, SUM(premium_amount) AS total_premium FROM policies GROUP BY product_line ORDER BY total_premium DESC"
        if "average" in q or "avg" in q:
            return "SELECT AVG(premium_amount) AS avg_premium FROM policies"
        if "total" in q or "sum" in q or "revenue" in q:
            return "SELECT SUM(premium_amount) AS total_premium FROM policies"
    if "paid amount" in q:
        if "average" in q or "avg" in q:
            return "SELECT AVG(paid_amount) AS avg_amount FROM claims"
        if "total" in q or "sum" in q:
            return "SELECT SUM(paid_amount) AS total_paid FROM claims"

    raise UnsupportedQuestion(f"no template matches question: {question!r}")
