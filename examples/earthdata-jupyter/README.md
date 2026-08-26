<!--
  ~ Copyright (c) 2023-2026 Datalayer, Inc.
  ~
  ~ BSD 3-Clause License
-->

[![Datalayer](https://assets.datalayer.tech/datalayer-25.svg)](https://datalayer.ai)

# Earthdata + Jupyter

One composition, two servers with different jobs. The
[Earthdata MCP Server](https://github.com/datalayer/earthdata-mcp-server)
finds NASA Earthdata datasets and granules and turns a selection into a
manifest or a download script. The
[Jupyter MCP Server](https://github.com/datalayer/jupyter-mcp-server) runs
that script inside the assigned Code Sandbox. Bytes move from NASA to the
sandbox's filesystem; they never travel through an MCP JSON response.

```
┌────────────────────────────────────────────────────────────────┐
│  Agent                                                          │
│    1. earthdata_search_earth_datasets      (discover)           │
│    2. earthdata_download_earth_data_granules mode=manifest      │
│    3. earthdata_download_earth_data_granules mode=script        │
│    4. jupyter_execute_code  ← the script   (execute in sandbox) │
└───────────────┬────────────────────────────────┬────────────────┘
                │ Streamable HTTP :8888/mcp      │
┌───────────────▼────────────────────────────────▼────────────────┐
│  MCP Compose  "earthdata-jupyter"                                │
│   ┌──────────────────────┐    ┌──────────────────────────────┐   │
│   │ earthdata (stdio)    │    │ jupyter (stdio)              │   │
│   │ search / manifest /  │    │ execute_code, use_notebook,  │   │
│   │ script — no bytes    │    │ insert_execute_code_cell …   │   │
│   └──────────────────────┘    └──────────────┬───────────────┘   │
└──────────────────────────────────────────────┼───────────────────┘
                                               │ kernel
                                    ┌──────────▼──────────┐
                                    │ Code Sandbox        │
                                    │ /data/earthdata/…   │ ← bytes land here
                                    └─────────────────────┘
```

## Why not download through MCP?

A tool result is a JSON document read by a model. A granule is hundreds of
megabytes. Putting one in the other is slow, costly and blind: nobody can say
afterwards which files arrived and whether they are whole. So the Earthdata
server has three modes and only the first two are meant for an agent:

| mode       | returns                                    | bytes moved |
| ---------- | ------------------------------------------ | ----------- |
| `manifest` | the granules a selection resolves to       | none        |
| `script`   | a Python script that downloads them        | none        |
| `download` | files written on the *server's* filesystem | on the server, not in the sandbox |

The script is what crosses over to Jupyter. Executed in the sandbox, it
downloads with `earthaccess` straight to the sandbox path, and the notebook
that ran it keeps the record.

## Run it

```bash
make install          # mcp-compose, earthdata-mcp-server, jupyter-mcp-server
export EARTHDATA_USERNAME=… EARTHDATA_PASSWORD=…
export DOCUMENT_URL=http://localhost:8888 DOCUMENT_TOKEN=… DOCUMENT_ID=notebook.ipynb
export RUNTIME_URL=$DOCUMENT_URL RUNTIME_TOKEN=$DOCUMENT_TOKEN
make start            # composition at http://localhost:8888/mcp
make agent            # in another terminal
```

## Manifest → script → execute

What the agent does, step by step, with the tool names the composition
exposes (`prefix` conflict resolution: `<server>_<tool>`).

**1. Discover.**

```json
{ "tool": "earthdata_search_earth_datasets",
  "arguments": { "search_keywords": "sea surface temperature daily", "count": 5,
                 "temporal": null, "bounding_box": null } }
```

**2. Review the manifest before anything moves.**

```json
{ "tool": "earthdata_download_earth_data_granules",
  "arguments": { "folder_name": "north-sea-sst", "short_name": "MUR-JPL-L4-GLOB-v4.1",
                 "count": 10, "temporal": ["2025-08-01", "2025-08-31"],
                 "bounding_box": [-4.0, 51.0, 9.0, 61.0], "mode": "manifest" } }
```

The answer lists the granules, their sizes and whether the list was
truncated. This is the moment to narrow the selection.

**3. Ask for the script.**

Same call with `"mode": "script"`. The result carries `script`: a
self-contained Python program that logs in with `earthaccess` from the
environment and downloads the same selection into `folder_name`.

**4. Execute it in the sandbox.**

```json
{ "tool": "jupyter_execute_code",
  "arguments": { "code": "<the script>", "timeout_seconds": 600 } }
```

or, to keep the run in the notebook:

```json
{ "tool": "jupyter_insert_execute_code_cell",
  "arguments": { "cell_index": -1, "cell_source": "<the script>" } }
```

The files are now under `/data/earthdata/north-sea-sst` in the sandbox.
`jupyter_list_files` shows them; a Datalayer Dataset can capture them as a
revision, with the notebook cell as provenance.

## As a Contents MCP source

Registered with Datalayer Contents, the composition becomes an MCP source
whose allowlist names the discovery tools and the execution tools — and
nothing else:

```bash
datalayer contents mcp connect earthdata-jupyter \
  --transport streamable-http --endpoint http://composer:8888/mcp \
  --tools earthdata_search_earth_datasets,earthdata_search_earth_datagranules,earthdata_download_earth_data_granules,jupyter_execute_code,jupyter_insert_execute_code_cell \
  --domains earthdata.nasa.gov
datalayer contents mcp tools earthdata-jupyter
datalayer contents mcp call earthdata-jupyter earthdata_download_earth_data_granules \
  --arguments-file manifest.json
```

Every call goes through a Contents session; under the default `explicit`
policy the execution step waits on an approval, which is where a reviewer
sees the script before it runs.

## Files

| File               | Description                                        |
| ------------------ | -------------------------------------------------- |
| `mcp_compose.toml` | The composition: both servers, Streamable HTTP out |
| `agent.py`         | A Pydantic AI agent that walks the four steps      |
| `manifest.json`    | The arguments of the manifest call above           |
| `Makefile`         | `install`, `start`, `agent`                        |
