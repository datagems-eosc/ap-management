import logging
from functools import lru_cache
from os import getenv
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends
from kiota_abstractions.authentication.anonymous_authentication_provider import (
    AnonymousAuthenticationProvider,
)
from kiota_http.httpx_request_adapter import HttpxRequestAdapter

from ap_management.internal.llm import LLM
from ap_management.services.ap_catalog.catalog import APCatalog
from ap_management.services.ap_catalog.local_catalog import LocalAPCatalog
from ap_management.services.ap_catalog.moma_catalog import MomaCatalog
from ap_management.services.authentication import Authentication
from ap_management.services.composer import AgenticComposition, Composer
from ap_management.services.composer.strategies.simple import SimpleComposition
from ap_management.services.matchmaker import Matchmaker
from ap_management.services.planner import Planner
from ap_management.services.value_suggester import ValueSuggester

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


def get_catalog(moma_svc: MomaManagementClient = Depends(get_moma_svc)) -> APCatalog:
    # return LocalAPCatalog(Path("/workspaces/ap-management/assets"))
    return MomaCatalog(moma_svc)


def get_matchmaker(catalog: APCatalog = Depends(get_catalog)) -> Matchmaker:
    return Matchmaker(llm=get_llm(), catalog=catalog)


def get_value_suggester() -> ValueSuggester:
    return ValueSuggester(llm=get_llm())


def get_planner(
    matchmaker: Matchmaker = Depends(get_matchmaker),
    composer: Composer = Depends(get_composer),
    ap_catalog: APCatalog = Depends(get_catalog),
    value_suggester: ValueSuggester = Depends(get_value_suggester),
) -> Planner:
    return Planner(matchmaker=matchmaker, composer=composer, ap_catalog=ap_catalog, value_suggester=value_suggester)


@lru_cache(maxsize=1)
def get_authentication_service() -> Optional[Authentication]:
    """Return a JwtValidator configured from environment variables."""
    if not getenv("OIDC_ISSUER"):
        logger.warning("OIDC_ISSUER not set, authentication disabled")
        return None

    return Authentication(
        issuer=getenv("OIDC_ISSUER", ""),
        ttl=int(getenv("JWKS_TTL_SECONDS", "300")),
        client_id=getenv("OIDC_CLIENT_ID") or None,
        client_secret=getenv("OIDC_CLIENT_SECRET") or None,
        exchange_scope=getenv("OIDC_EXCHANGE_SCOPE"),
    )
