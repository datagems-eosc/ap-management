from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase
from testcontainers.neo4j import Neo4jContainer

from ap_management.repository import Neo4jApRepository, Neo4jTaskRepository
from ap_management.services.analytical_pattern import AnalyticalPatternService
from ap_management.services.embeddings.embedder import Embedder
from ap_management.services.embeddings.local_embedder import LocalEmbedder
from ap_management.services.task import TaskService


@pytest.fixture
def task_svc(task_repository: Neo4jTaskRepository, ap_repository: Neo4jApRepository) -> TaskService:
    """TaskService for testing purposes."""
    return TaskService(task_repository, ap_repository)


@pytest_asyncio.fixture
async def task_repository(neo4j_container: Neo4jContainer) -> AsyncGenerator[Neo4jTaskRepository]:
    """Provide a TaskRepository using AsyncSession."""
    uri = neo4j_container.get_connection_url()
    auth = (neo4j_container.username, neo4j_container.password)
    driver = AsyncGraphDatabase.driver(uri, auth=auth)

    async with driver.session() as session:
        yield Neo4jTaskRepository(session)

    await driver.close()


@pytest.fixture(scope="session")
def embedder() -> Embedder:
    """Embedder for testing purposes."""
    return LocalEmbedder()


@pytest.fixture
def ap_svc(ap_repository: Neo4jApRepository, embedder: Embedder) -> AnalyticalPatternService:
    """
    AnalyticalPatternService for testing purposes using local schema files.
    """
    schema_path = Path(__file__).parent.parent / "assets"
    return AnalyticalPatternService(ap_repository, f"file://{schema_path}", embedder=embedder)


@pytest_asyncio.fixture
async def ap_repository(neo4j_container: Neo4jContainer, embedder: Embedder) -> AsyncGenerator[Neo4jApRepository]:
    """Provide an AsyncRepository using AsyncSession."""
    uri = neo4j_container.get_connection_url()
    auth = (neo4j_container.username, neo4j_container.password)
    driver = AsyncGraphDatabase.driver(uri, auth=auth)

    async with driver.session() as session:
        repo = Neo4jApRepository(session)
        await repo.enable_embeddings(embedder.dimensions)
        yield repo

    await driver.close()


@pytest.fixture(scope="session")
def neo4j_container() -> Generator[Neo4jContainer]:
    """Neo4j disposable container for just this testing session"""
    # NOTE : I'm not freezing the neo4j version in testing to check for regression/breaking changes in CI
    container = Neo4jContainer(image="neo4j:latest")
    container.start()
    yield container
    container.stop()
