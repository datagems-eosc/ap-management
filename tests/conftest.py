from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest
from dotenv import load_dotenv
from kiota_abstractions.authentication.anonymous_authentication_provider import (
    AnonymousAuthenticationProvider,
)
from kiota_http.httpx_request_adapter import HttpxRequestAdapter
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from ap_management.generated.moma_management.moma_management_client import (
    MomaManagementClient,
)
from ap_management.services.composer import Composer, SimpleComposition
from tests.ap_test_cases import AP_TEST_CASES, ApTestCase

PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_PATH = PROJECT_ROOT / "assets"

load_dotenv(PROJECT_ROOT / ".env")


@pytest.fixture(scope="session")
def assets_path() -> Path:
    return ASSETS_PATH


@pytest.fixture
def generated_path() -> Path:
    dir = PROJECT_ROOT / "generated"
    dir.mkdir(exist_ok=True)
    return dir


@pytest.fixture(
    scope="session",
    params=AP_TEST_CASES,
    ids=lambda c: c.name
)
def case(request) -> ApTestCase:
    return request.param


@pytest.fixture
def no_ai_composer(moma_client: MomaManagementClient) -> Composer:
    return Composer(strategies=[SimpleComposition()], moma_svc=moma_client)


# MOMA_IMAGE = f"ghcr.io/datagems-eosc/datagems-eosc/moma-management:{os.environ['MOMA_VERSION']}"
# MOMA_PORT = 5000


# @pytest.fixture(scope="session")
# def moma_client() -> Generator[MomaManagementClient, None, None]:
#     with DockerContainer(MOMA_IMAGE).with_exposed_ports(MOMA_PORT) as container:
#         host = container.get_container_host_ip()
#         port = container.get_exposed_port(MOMA_PORT)
#         adapter = HttpxRequestAdapter(AnonymousAuthenticationProvider())
#         adapter.base_url = f"http://{host}:{port}"
#         yield MomaManagementClient(adapter)
