from contextlib import asynccontextmanager
from os import getenv
from typing import AsyncGenerator

from fastapi import Depends, FastAPI
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession

from ap_management.repository import (
    ApRepository,
    Neo4jApRepository,
    Neo4jTaskRepository,
    TaskRepository,
)
from ap_management.services.analytical_pattern import AnalyticalPatternService
from ap_management.services.task import TaskService

NEO4J_URI = getenv("NEO4J_URI", "")
NEO4J_USER = getenv("NEO4J_USER", "")
NEO4J_PASSWORD = getenv("NEO4J_PASSWORD", "")

driver: AsyncDriver


@asynccontextmanager
async def container_lifespan(_: FastAPI):
    """
    Lifespan context manager to setup and teardown the Neo4j async driver.
    This ties the driver's lifecycle to that of the FastAPI application and prevents connection leaks.
    """
    global driver
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
        max_connection_pool_size=5,
    )

    yield

    await driver.close()


async def get_db_conn() -> AsyncGenerator[AsyncSession, None]:
    """
    Returns an async session from the Neo4j driver.
    """
    async with driver.session() as session:
        yield session


async def get_ap_repo(session: AsyncSession = Depends(get_db_conn)) -> ApRepository:
    """
    Return the physical storage facade to store Aps
    """
    return Neo4jApRepository(session)


def get_ap_service(repo: ApRepository = Depends(get_ap_repo)) -> AnalyticalPatternService:
    return AnalyticalPatternService(repo)


async def get_task_repo(session: AsyncSession = Depends(get_db_conn)) -> TaskRepository:
    """
    Return the physical storage facade to store Tasks
    """
    return Neo4jTaskRepository(session)


def get_task_service(repo: TaskRepository = Depends(get_task_repo)) -> TaskService:
    return TaskService(repo)
