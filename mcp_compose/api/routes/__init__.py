"""API route modules."""

from .config import router as config_router
from .health import router as health_router
from .servers import router as servers_router
from .status import router as status_router
from .tools import router as tools_router
from .translators import router as translators_router
from .version import router as version_router

__all__ = [
    "config_router",
    "health_router",
    "servers_router",
    "status_router",
    "tools_router",
    "translators_router",
    "version_router",
]
