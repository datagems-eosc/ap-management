from logging import getLogger

from fastapi import Depends, HTTPException, Request, status
from neo4j import AsyncSession
from neo4j.exceptions import Neo4jError

from ap_management.di import get_db_conn

logger = getLogger(__name__)


async def health_check(rq: Request, db: AsyncSession = Depends(get_db_conn)):
    try:
        await db.run("RETURN 1 AS n")
        return {"status": "healthy"}

    except Neo4jError as e:
        logger.error("Database connection failed", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        ) from e
