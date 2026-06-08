import logging
from os import getenv

from dotenv import load_dotenv
from fastapi import Depends
from kiota_abstractions.authentication.anonymous_authentication_provider import (
    AnonymousAuthenticationProvider,
)
from kiota_http.httpx_request_adapter import HttpxRequestAdapter

from ap_management.internal.llm import LLM
from ap_management.services.composer import AgenticComposition, Composer
from ap_management.services.composer.strategies.simple import SimpleComposition

from .generated.moma_management.moma_management_client import MomaManagementClient
from .logger import configure_logging

load_dotenv()
configure_logging()


logger = logging.getLogger(__name__)


def get_llm() -> LLM:
    api_base = getenv("LLM_API_BASE")
    api_key = getenv("LLM_API_KEY", None)
    model = getenv("LLM_API_MODEL")
    ssl_verify = getenv("LLM_SSL_VERIFY", "true").lower() == "true"

    if not all([api_base, model]):
        raise ValueError(
            "Missing required environment variables for LLM explanation: LLM_API_BASE, LLM_API_MODEL"
        )

    return LLM(api_base, model, api_key, ssl_verify=ssl_verify)


def get_moma_svc() -> MomaManagementClient:
    # TODO: Handle auth
    base_url = getenv("MOMA_MANAGEMENT_BASE_URL",
                      "http://moma-management:5000")
    adapter = HttpxRequestAdapter(AnonymousAuthenticationProvider())
    adapter.base_url = base_url

    return MomaManagementClient(adapter)


def get_composer(moma_svc: MomaManagementClient = Depends(get_moma_svc)) -> Composer:
    """
    Retrieve the composer with all the strategies configured.
    """

    return Composer(
        strategies=[
            SimpleComposition(),
            AgenticComposition(get_llm())
        ],
        moma_svc=moma_svc
    )
