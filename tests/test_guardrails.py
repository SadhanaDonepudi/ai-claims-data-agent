import pytest

from claims_agent.guardrails import GuardrailViolation, validate_and_limit


@pytest.mark.parametrize("sql", [
    "DELETE FROM claims WHERE claim_status = 'Denied'",
    "UPDATE claims SET claim_status = 'Closed'",
    "INSERT INTO claims VALUES ('CLM-99999')",
    "DROP TABLE claims",
    "ALTER TABLE claims ADD COLUMN x INTEGER",
    "TRUNCATE TABLE claims",
    "CREATE TABLE evil (x INTEGER)",
    "SELECT 1; DELETE FROM claims",
    "WITH t AS (SELECT 1 AS x) DELETE FROM claims",
])
def test_mutations_and_multi_statement_blocked(sql):
    with pytest.raises(GuardrailViolation):
        validate_and_limit(sql)


@pytest.mark.parametrize("col", ["claimant_name", "claimant_ssn", "claimant_email", "claimant_phone"])
def test_pii_columns_blocked(col):
    with pytest.raises(GuardrailViolation):
        validate_and_limit(f"SELECT {col} FROM claims")


def test_pii_blocked_in_subquery():
    with pytest.raises(GuardrailViolation):
        validate_and_limit("SELECT claim_id FROM (SELECT claim_id, claimant_ssn FROM claims) t")


def test_select_star_blocked_but_count_star_allowed():
    with pytest.raises(GuardrailViolation):
        validate_and_limit("SELECT * FROM claims")
    assert "COUNT(*)" in validate_and_limit("SELECT COUNT(*) FROM claims")


def test_row_limit_injected_and_capped():
    assert "LIMIT 1000" in validate_and_limit("SELECT claim_id FROM claims")
    assert "LIMIT 1000" in validate_and_limit("SELECT claim_id FROM claims LIMIT 999999")
    assert "LIMIT 5" in validate_and_limit("SELECT claim_id FROM claims LIMIT 5")


def test_cte_select_allowed():
    out = validate_and_limit("WITH t AS (SELECT claim_type FROM claims) SELECT * FROM t")         if False else validate_and_limit("WITH t AS (SELECT claim_type FROM claims) SELECT claim_type FROM t")
    assert out.upper().startswith("WITH")
