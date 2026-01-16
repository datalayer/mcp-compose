# Copyright (c) 2023-2024 Datalayer, Inc.
#
# BSD 3-Clause License

SHELL=/bin/bash

.DEFAULT_GOAL := default

.PHONY: clean build

# Extract version from pyproject.toml
VERSION := $(shell python -c "from mcp_compose.__version__ import __version__; print(__version__)")

default: all ## default target is all

help: ## display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

all: clean build ## clean and build

install:
	pip install .

dev:
	pip install ".[test,lint,typing]"

test: ## run the integration tests
	hatch test

build: build-ui ## build Python package (UI is built first)
	pip install build
	python -m build .

build-ui: ## build the UI artifacts
	@echo "Building UI..."
	cd ui && npm install && npm run build
	@echo "✓ UI built successfully in ui/dist/"

build-all: build-ui build ## build UI and Python package

clean: ## clean
	git clean -fdx

clean-ui: ## clean UI build artifacts
	rm -rf ui/dist ui/node_modules

build-docker: ## build the docker image
	docker buildx build --platform linux/amd64,linux/arm64 --push -t datalayer/mcp-compose:${VERSION} .
	docker buildx build --platform linux/amd64,linux/arm64 --push -t datalayer/mcp-compose:latest .
#	docker image tag datalayer/mcp-compose:${VERSION} datalayer/mcp-compose:latest
	@exec echo open https://hub.docker.com/r/datalayer/mcp-compose/tags

start-docker: ## start the jupyter mcp server in docker
	docker run -i --rm \
	  -e DOCUMENT_URL=http://localhost:8888 \
	  -e DOCUMENT_ID=notebook.ipynb \
	  -e DOCUMENT_TOKEN=MY_TOKEN \
	  -e RUNTIME_URL=http://localhost:8888 \
	  -e START_NEW_RUNTIME=true \
	  -e RUNTIME_TOKEN=MY_TOKEN \
	  --network=host \
	  datalayer/mcp-compose:latest

pull-docker: ## pull the latest docker image
	docker image pull datalayer/mcp-compose:latest

push-docker: ## push the docker image to the registry
	docker push datalayer/mcp-compose:${VERSION}
	docker push datalayer/mcp-compose:latest
	@exec echo open https://hub.docker.com/r/datalayer/mcp-compose/tags

claude-linux: ## run the claude desktop linux app using nix
	NIXPKGS_ALLOW_UNFREE=1 nix run github:k3d3/claude-desktop-linux-flake?rev=6d9eb2a653be8a6c06bc29a419839570e0ffc858 \
		--impure \
		--extra-experimental-features flakes \
		--extra-experimental-features nix-command

start: ## start the jupyter mcp server with streamable-http transport
	@exec echo
	@exec echo curl http://localhost:4040/api/healthz
	@exec echo
	@exec echo 👉 Define in your favorite mcp client the server http://localhost:4040/mcp
	@exec echo
	mcp-compose start \
	  --transport streamable-http \
	  --document-url http://localhost:8888 \
	  --document-id notebook.ipynb \
	  --document-token MY_TOKEN \
	  --runtime-url http://localhost:8888 \
	  --start-new-runtime true \
	  --runtime-token MY_TOKEN \
	  --port 4040

start-no-runtime: ## start the jupyter mcp server with streamable-http transport and no runtime
	@exec echo
	@exec echo curl http://localhost:4040/api/healthz
	@exec echo
	@exec echo 👉 Define in your favorite mcp client the server http://localhost:4040/mcp
	@exec echo
	mcp-compose start \
	  --transport streamable-http \
	  --document-url http://localhost:8888 \
	  --document-id notebook.ipynb \
	  --document-token MY_TOKEN \
	  --runtime-url http://localhost:8888 \
	  --start-new-runtime false \
	  --runtime-token MY_TOKEN \
	  --port 4040

jupyterlab: ## start jupyterlab for the mcp server
	pip uninstall -y pycrdt datalayer_pycrdt
	pip install datalayer_pycrdt
	jupyter lab \
		--port 8888 \
		--ip 0.0.0.0 \
		--ServerApp.root_dir ./dev/content \
		--IdentityProvider.token MY_TOKEN

publish-pypi: build-ui # publish the pypi package
	git clean -fdx -e ui/dist -e ui/node_modules && \
		python -m build
	@exec echo
	@exec echo twine upload ./dist/*-py3-none-any.whl
	@exec echo
	@exec echo https://pypi.org/project/mcp-compose/#history

build-conda: build-ui ## build the conda package (requires: conda install conda-build)
	@command -v conda-build >/dev/null 2>&1 || { echo "❌ conda-build is not installed. Run: conda install conda-build"; exit 1; }
	git clean -fdx -e ui/dist -e ui/node_modules && \
		VERSION=${VERSION} conda-build --output-folder ./dist/conda . -c conda-forge -c datalayer
	@exec echo "✓ Conda package built in ./dist/conda/"

publish-conda: build-conda ## build and publish the conda package to anaconda.org datalayer
	anaconda upload --user datalayer ./dist/conda/noarch/mcp-compose-${VERSION}-*.conda
	@exec echo
	@exec echo "✓ Package published to anaconda.org/datalayer/mcp-compose"
	@exec echo open https://anaconda.org/datalayer/mcp-compose
	@exec echo
	@exec echo "✓ Package published to anaconda.org/datalayer/mcp-compose"
	@exec echo open https://anaconda.org/datalayer/mcp-compose
