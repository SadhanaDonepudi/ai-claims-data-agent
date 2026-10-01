import pytest

from claims_agent.generator import UnsupportedQuestion, generate_sql
from claims_agent.schema_retrieval import retrieve_schema


@pytest.mark.parametrize("question,fragment", [
    ("How many claims are open?", "claim_status = 'Open'"),
    ("How many Collision claims are there?", "claim_type = 'Collision'"),
    ("What is the total paid amount by claim type?", "SUM(paid_amount)"),
    ("How many claims were filed in 2024?", "EXTRACT(YEAR FROM claim_date) = 2024"),
    ("What are the top 5 states by number of claims?", "GROUP BY state"),
    ("How many claims are there by product line?", "JOIN policies"),
    ("What is the total payment amount by payment method?", "GROUP BY payment_method"),
    ("How many claims are flagged for fraud?", "fraud_flag = true"),
    ("How many claims are over $10,000?", "claim_amount > 10000"),
])
def test_generator_templates(question, fragment):
    assert fragment in generate_sql(question)


def test_generator_unsupported_raises():
    with pytest.raises(UnsupportedQuestion):
        generate_sql("What is the weather in Chicago today?")


def test_schema_retrieval_product_line_pulls_policies():
    schema = retrieve_schema("How many claims are there by product line?")
    assert "policies" in schema["tables"]
    assert "claims" in schema["tables"]


def test_schema_retrieval_describes_columns():
    schema = retrieve_schema("How many claims are open?")
    assert "claims" in schema["columns"]
    assert "claim_status" in schema["columns"]["claims"]
