import pytest

from ap_management.services.analytical_pattern import AnalyticalPatternService


@pytest.fixture(scope="session")
def unit_prov_svc():
    """
    Offline ProvenanceService for testing purposes.
    This one does not connect to a real database.
    """
    return AnalyticalPatternService(None)  # type: ignore
