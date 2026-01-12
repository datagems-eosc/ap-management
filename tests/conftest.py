from json import loads
from pathlib import Path
from typing import AsyncGenerator, Dict, Generator

import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase
from testcontainers.neo4j import Neo4jContainer

from ap_management.repository.analytical_pattern import Neo4jApRepository
from ap_management.services.analytical_pattern import AnalyticalPatternService

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "assets"


@pytest.fixture
def ap_svc(ap_repository: Neo4jApRepository) -> AnalyticalPatternService:
    """
    Offline ProvenanceService for testing purposes.
    This one does not connect to a real database.
    """
    return AnalyticalPatternService(ap_repository)


@pytest_asyncio.fixture
async def ap_repository(neo4j_container: Neo4jContainer) -> AsyncGenerator[Neo4jApRepository]:
    """Provide an AsyncRepository using AsyncSession."""
    uri = neo4j_container.get_connection_url()
    auth = (neo4j_container.username, neo4j_container.password)
    driver = AsyncGraphDatabase.driver(uri, auth=auth)

    async with driver.session() as session:
        yield Neo4jApRepository(session)

    await driver.close()


@pytest.fixture(scope="session")
def neo4j_container() -> Generator[Neo4jContainer]:
    """Neo4j disposable container for just this testing session"""
    # NOTE : I'm not freezing the neo4j version in testing to check for regression/breaking changes in CI
    container = Neo4jContainer(image="neo4j:latest")
    container.start()
    yield container
    container.stop()


def load_asset(alias: str, as_json: bool = True) -> str:
    """
    Load a file by it's name with or without extension
    Optionally parse it as Json
    """
    p = FIXTURES_DIR / alias
    # Direct search, then search with any extension
    if not p.exists():
        matches = list(FIXTURES_DIR.glob(f"{alias}.*"))
        if matches:
            p = matches[0]
        else:
            p = FIXTURES_DIR / f"{alias}.json"

    if not p.exists():
        raise FileNotFoundError(
            f"No fixture found for alias {alias!r} in {FIXTURES_DIR}")

    text = p.read_text(encoding="utf-8")
    return text
