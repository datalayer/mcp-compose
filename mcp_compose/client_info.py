# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

from typing import Any

from mcp.types import Implementation

FALLBACK_CLIENT_INFO = Implementation(name="mcp-compose", version="0.1.0")


def resolve_client_info(ctx: Any = None) -> Implementation:
    """Return upstream clientInfo from a FastMCP Context, or the mcp-compose fallback."""
    try:
        if ctx is not None:
            client_params = ctx.session.client_params
            if client_params is not None:
                return client_params.clientInfo
    except AttributeError:
        pass
    return FALLBACK_CLIENT_INFO
