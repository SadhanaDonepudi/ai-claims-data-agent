from claims_agent.correction import propose_correction
from claims_agent.llm import ClaudeBackend


def test_agent_answers_count(agent):
    r = agent.ask("How many claims are there in total?")
    assert r.status == "answered"
    assert r.rows[0][0] == 3500
    assert r.attempts == 1


def test_agent_blocks_pii_question(agent):
    r = agent.ask("Show me claimant names and their SSN")
    assert r.status == "blocked"
    assert r.rows == []


def test_agent_blocks_mutation_question(agent):
    r = agent.ask("Delete all denied claims")
    assert r.status == "blocked"


def test_agent_unsupported_question(agent):
    r = agent.ask("What will claim volume be next quarter?")
    assert r.status == "unsupported"


def test_self_correction_recovers_from_bad_column(agent):
    r = agent.execute_with_correction("SELECT claim_amt FROM claims")
    assert r.status == "answered"
    assert r.attempts >= 2
    assert len(r.rows) == 1000  # guardrail LIMIT was injected


def test_self_correction_gives_up_on_uncorrectable_sql(agent):
    r = agent.execute_with_correction("SELECT zz_nope_column FROM claims")
    assert r.status == "failed"
    assert r.error


def test_propose_correction_maps_misspelling():
    fixed = propose_correction("SELECT claim_amt FROM claims",
                               'Binder Error: Referenced column "claim_amt" not found')
    assert fixed is not None and "claim_amount" in fixed


def test_claude_backend_not_exercised():
    try:
        ClaudeBackend()
        raise AssertionError("ClaudeBackend should refuse to construct locally")
    except NotImplementedError as exc:
        assert "NOT EXERCISED" in str(exc)
