# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Version information endpoint.

Provides detailed version and build information.
"""

import platform
import sys
from datetime import datetime
from typing import Optional

from fastapi import APIRouter

from ..models import VersionResponse

router = APIRouter(tags=["version"])


@router.get("/version", response_model=VersionResponse)
async def get_version() -> VersionResponse:
    """
    Get version information.
    
    Returns detailed information about the API version, build,
    and runtime environment.
    
    Returns:
        VersionResponse with version details.
    """
    from ...__version__ import __version__
    
    # Try to get git commit (in production, this would be set during build)
    git_commit: Optional[str] = None
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            git_commit = result.stdout.strip()
    except Exception:
        pass  # Git not available or not a git repo
    
    # Build date (would be set during build in production)
    # For now, use a placeholder
    build_date: Optional[datetime] = None
    
    return VersionResponse(
        version=__version__,
        build_date=build_date,
        git_commit=git_commit,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        platform=platform.platform(),
        timestamp=datetime.utcnow(),
    )


__all__ = ["router"]
