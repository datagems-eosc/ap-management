from contextlib import asynccontextmanager
from os import getenv
from typing import AsyncGenerator, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession

from ap_management.repository import (
    ApRepository,
    Neo4jApRepository,
    Neo4jTaskRepository,
    TaskRepository,
)
from ap_management.services.analytical_pattern import AnalyticalPatternService
from ap_management.services.analytical_pattern_generator import (
    AnalyticalPatternGenerator,
)
from ap_management.services.embeddings import Embedder
from ap_management.services.embeddings.local_embedder import LocalEmbedder
from ap_management.services.task import TaskService

# NOTE: Dotenv can be loaded multiple times without issue
load_dotenv()

NEO4J_URI = getenv("NEO4J_URI", "")
NEO4J_USER = getenv("NEO4J_USER", "")
NEO4J_PASSWORD = getenv("NEO4J_PASSWORD", "")
SCHEMA_REGISTRY_BASE_URL = getenv("SCHEMA_REGISTRY_BASE_URL", "")

driver: AsyncDriver
embedder: LocalEmbedder


@asynccontextmanager
async def container_lifespan(_: FastAPI):
    """
    Lifespan context manager to setup and teardown the Neo4j async driver.
    This ties the driver's lifecycle to that of the FastAPI application and prevents connection leaks.
    """
    global driver, embedder
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
        max_connection_pool_size=5,
    )
    embedder = LocalEmbedder()

    yield

    await driver.close()


async def get_db_conn() -> AsyncGenerator[AsyncSession, None]:
    """
    Returns an async session from the Neo4j driver.
    """
    async with driver.session() as session:
        yield session


def get_embedder() -> Embedder:
    # TODO: Support remote embedder
    return embedder


async def get_ap_repo(session: AsyncSession = Depends(get_db_conn), embedder: Embedder = Depends(get_embedder)) -> ApRepository:
    """
    Return the physical storage facade to store Aps
    """
    repo = Neo4jApRepository(session)
    await repo.enable_embeddings(embedder.dimensions)
    return repo


def get_ap_service(repo: ApRepository = Depends(get_ap_repo), embedder: Embedder = Depends(get_embedder)) -> AnalyticalPatternService:
    generator = AnalyticalPatternGenerator()
    return AnalyticalPatternService(repo, SCHEMA_REGISTRY_BASE_URL, generator, embedder=embedder)


async def get_task_repo(session: AsyncSession = Depends(get_db_conn)) -> TaskRepository:
    """
    Return the physical storage facade to store Tasks
    """
    return Neo4jTaskRepository(session)


def get_task_service(
    task_repo: TaskRepository = Depends(get_task_repo),
    ap_repo: ApRepository = Depends(get_ap_repo)
) -> TaskService:
    return TaskService(task_repo, ap_repo)
