"""GET /api/v1/health - the first thing to check when a PC cannot reach the master."""

from fastapi import APIRouter

from dap import __version__
from dap.shared.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
