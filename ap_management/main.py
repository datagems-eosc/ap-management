import logging
from importlib.metadata import version
from os import getenv
from pathlib import Path
from tomllib import loads as loads_toml

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from ap_management.api.v1.routes import router
from ap_management.di import container_lifespan

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
# Retrieve current project version from toml
pyproject = loads_toml(Path("pyproject.toml").read_text())
project_version = pyproject["project"]["version"]

ROOT_PATH = getenv("ROOT_PATH", "")

app = FastAPI(
    title="Analytical Pattern Management API",
    description="API to manage AP",
    lifespan=container_lifespan,
    version=project_version,
    root_path=ROOT_PATH,
)


@app.get("/")
def index():
    return {
        "service": "Provenance Demo",
        "version": app.version
    }


app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
