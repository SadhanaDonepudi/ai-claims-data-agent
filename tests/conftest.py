import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from claims_agent.agent import ClaimsAgent  # noqa: E402
from claims_agent.generate_data import build_database  # noqa: E402


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("data") / "claims_test.duckdb"
    build_database(path)
    return path


@pytest.fixture(scope="session")
def agent(db_path):
    a = ClaimsAgent(db_path=db_path)
    yield a
    a.close()
