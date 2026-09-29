from pathlib import Path

import pytest

from steganalysis.db import Store
from steganalysis.engine import create_job, execute_job
from steganalysis.fixtures import make_fixtures
from steganalysis.models import Budget
from steganalysis.storage import ingest


@pytest.fixture(scope="session")
def fixtures(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("benign-fixtures")
    make_fixtures(path)
    return path


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(tmp_path / "data")


@pytest.fixture
def analyze(store):
    def run(data: bytes, name: str, profile="quick", **budget):
        case = store.create_case("Test examination")
        artifact = ingest(store, case["id"], data, name)
        job = create_job(store, case["id"], [artifact["id"]], profile, Budget(**budget))
        execute_job(store, job["id"])
        return store.snapshot(case["id"])

    return run
