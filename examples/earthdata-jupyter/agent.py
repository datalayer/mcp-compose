# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Discover with Earthdata, execute with Jupyter — through one composition.

The agent is told the shape of the work in its instructions: manifest first,
then the script, then execution in the sandbox. It never asks the Earthdata
server to download, because a download there lands on the wrong machine and
travels as JSON; the sandbox is where the bytes belong.
"""

from __future__ import annotations

import asyncio
import sys

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP

COMPOSITION_URL = "http://localhost:8888/mcp"

INSTRUCTIONS = """
You acquire NASA Earthdata for analysis in a Jupyter notebook.

Work in this order and do not skip a step:
1. Find candidate datasets with earthdata_search_earth_datasets and pick one
   short_name.
2. Call earthdata_download_earth_data_granules with mode="manifest" and show
   the user the granules, their sizes and whether the list was truncated.
   Narrow the selection if it is large.
3. Call the same tool with mode="script" to obtain a download script.
4. Run the script in the sandbox with jupyter_execute_code (or
   jupyter_insert_execute_code_cell to keep it in the notebook).
5. Confirm the files with jupyter_list_files.

Never use mode="download": the files would land on the MCP server rather than
in the sandbox, and their bytes would travel through a tool result.
"""


async def main(model: str) -> None:
    composition = MCPServerStreamableHTTP(url=COMPOSITION_URL, timeout=600.0)
    agent = Agent(model=model, toolsets=[composition], instructions=INSTRUCTIONS)
    prompt = (
        "Find daily sea-surface-temperature datasets covering the North Sea, "
        "list the granules for August 2025 as a manifest, and download the "
        "selected ones into /data/earthdata/north-sea-sst in the sandbox."
    )
    async with agent:
        result = await agent.run(prompt)
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "anthropic:claude-sonnet-4-0"))
