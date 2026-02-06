# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Protocol translator for MCP Compose.

Provides bidirectional translation between STDIO and SSE transports,
enabling STDIO clients to access SSE servers and vice versa.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from asyncio import Queue
from typing import Any

import httpx
from fastapi import Request
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)


class ProtocolTranslator(ABC):
    """Abstract base class for protocol translators."""

    @abstractmethod
    async def translate(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Translate a message from one protocol to another.

        Args:
            message: Message in source protocol format.

        Returns:
            Message in target protocol format.
        """
        pass

    @abstractmethod
    async def start(self):
        """Start the translator."""
        pass

    @abstractmethod
    async def stop(self):
        """Stop the translator."""
        pass


class StdioToSseTranslator(ProtocolTranslator):
    """
    Translates STDIO (stdin/stdout) to SSE (Server-Sent Events).

    Enables STDIO clients to communicate with SSE servers by:
    1. Reading JSON-RPC messages from stdin
    2. Converting to HTTP POST requests
    3. Streaming SSE responses back to stdout
    """

    def __init__(
        self,
        sse_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize STDIO to SSE translator.

        Args:
            sse_url: URL of the SSE server endpoint.
            headers: Optional HTTP headers (e.g., authentication).
            timeout: Request timeout in seconds.
        """
        self.sse_url = sse_url
        self.headers = headers or {}
        self.timeout = timeout
        self.client: httpx.AsyncClient | None = None
        self.running = False
        self.input_queue: Queue = Queue()
        self.output_queue: Queue = Queue()

    async def start(self):
        """Start the translator."""
        self.running = True
        self.client = httpx.AsyncClient(timeout=self.timeout)

        # Start tasks
        asyncio.create_task(self._read_stdin())
        asyncio.create_task(self._process_messages())
        asyncio.create_task(self._write_stdout())

        logger.info(f"STDIO→SSE translator started for {self.sse_url}")

    async def stop(self):
        """Stop the translator."""
        self.running = False
        if self.client:
            await self.client.aclose()
        logger.info("STDIO→SSE translator stopped")

    async def _read_stdin(self):
        """Read JSON-RPC messages from stdin."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, asyncio.sys.stdin)

        while self.running:
            try:
                # Read line from stdin
                line = await reader.readline()
                if not line:
                    break

                # Parse JSON-RPC message
                message = json.loads(line.decode("utf-8"))
                await self.input_queue.put(message)

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from stdin: {e}")
            except Exception as e:
                logger.error(f"Error reading stdin: {e}")
                break

    async def _process_messages(self):
        """Process messages from input queue and send to SSE server."""
        while self.running:
            try:
                # Get message from queue
                message = await asyncio.wait_for(self.input_queue.get(), timeout=1.0)

                # Translate and send to SSE server
                response = await self._send_to_sse(message)

                # Put response in output queue
                await self.output_queue.put(response)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    async def _send_to_sse(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Send message to SSE server via HTTP POST.

        Args:
            message: JSON-RPC message.

        Returns:
            Response from SSE server.
        """
        try:
            # Send POST request to SSE server
            response = await self.client.post(
                self.sse_url,
                json=message,
                headers=self.headers,
            )
            response.raise_for_status()

            # Parse response
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending to SSE server: {e}")
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32000,
                    "message": f"HTTP error: {str(e)}",
                },
            }
        except Exception as e:
            logger.error(f"Error sending to SSE server: {e}")
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                },
            }

    async def _write_stdout(self):
        """Write responses to stdout."""
        while self.running:
            try:
                # Get response from queue
                response = await asyncio.wait_for(self.output_queue.get(), timeout=1.0)

                # Write to stdout
                output = json.dumps(response) + "\n"
                asyncio.sys.stdout.write(output)
                await asyncio.sys.stdout.drain()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error writing stdout: {e}")

    async def translate(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Translate a single message (for testing/direct use).

        Args:
            message: JSON-RPC message from STDIO.

        Returns:
            Response from SSE server.
        """
        return await self._send_to_sse(message)


class SseToStdioTranslator(ProtocolTranslator):
    """
    Translates SSE (Server-Sent Events) to STDIO (stdin/stdout).

    Enables SSE clients to communicate with STDIO servers by:
    1. Receiving HTTP/SSE requests
    2. Converting to JSON-RPC messages
    3. Sending to STDIO server's stdin
    4. Reading responses from stdout
    5. Streaming back as SSE events
    """

    def __init__(
        self,
        command: str,
        args: list | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ):
        """
        Initialize SSE to STDIO translator.

        Args:
            command: Command to run STDIO server.
            args: Command arguments.
            env: Environment variables.
            cwd: Working directory.
        """
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.cwd = cwd
        self.process: asyncio.subprocess.Process | None = None
        self.running = False
        self.request_queue: Queue = Queue()
        self.response_map: dict[Any, asyncio.Future] = {}
        self._next_id = 1

    async def start(self):
        """Start the translator by launching STDIO server."""
        try:
            # Start STDIO server process
            self.process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env,
                cwd=self.cwd,
            )

            self.running = True

            # Start tasks
            asyncio.create_task(self._read_stdout())
            asyncio.create_task(self._write_stdin())

            logger.info(f"SSE→STDIO translator started: {self.command}")

        except Exception as e:
            logger.error(f"Failed to start STDIO server: {e}")
            raise

    async def stop(self):
        """Stop the translator and STDIO server."""
        self.running = False

        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()

        logger.info("SSE→STDIO translator stopped")

    async def _write_stdin(self):
        """Write requests to STDIO server's stdin."""
        if not self.process or not self.process.stdin:
            return

        while self.running:
            try:
                # Get request from queue
                message = await asyncio.wait_for(self.request_queue.get(), timeout=1.0)

                # Write to stdin
                output = json.dumps(message) + "\n"
                self.process.stdin.write(output.encode("utf-8"))
                await self.process.stdin.drain()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error writing to stdin: {e}")
                break

    async def _read_stdout(self):
        """Read responses from STDIO server's stdout."""
        if not self.process or not self.process.stdout:
            return

        while self.running:
            try:
                # Read line from stdout
                line = await self.process.stdout.readline()
                if not line:
                    break

                # Parse JSON-RPC response
                response = json.loads(line.decode("utf-8"))

                # Match response to request
                request_id = response.get("id")
                if request_id in self.response_map:
                    future = self.response_map.pop(request_id)
                    if not future.done():
                        future.set_result(response)

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from stdout: {e}")
            except Exception as e:
                logger.error(f"Error reading stdout: {e}")
                break

    async def translate(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Translate a message from SSE to STDIO.

        Args:
            message: HTTP request payload.

        Returns:
            Response from STDIO server.
        """
        # Generate request ID if not present
        if "id" not in message:
            message["id"] = self._next_id
            self._next_id += 1

        # Create future for response
        future = asyncio.Future()
        self.response_map[message["id"]] = future

        try:
            # Send to STDIO server
            await self.request_queue.put(message)

            # Wait for response (with timeout)
            response = await asyncio.wait_for(future, timeout=30.0)
            return response

        except asyncio.TimeoutError:
            self.response_map.pop(message["id"], None)
            return {
                "jsonrpc": "2.0",
                "id": message["id"],
                "error": {
                    "code": -32000,
                    "message": "Request timeout",
                },
            }
        except Exception as e:
            self.response_map.pop(message["id"], None)
            logger.error(f"Error translating message: {e}")
            return {
                "jsonrpc": "2.0",
                "id": message["id"],
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                },
            }

    async def handle_sse_request(self, request: Request) -> EventSourceResponse:
        """
        Handle SSE request from client.

        Args:
            request: FastAPI request object.

        Returns:
            EventSourceResponse with streamed events.
        """

        async def event_generator():
            """Generate SSE events from STDIO responses."""
            try:
                # Get request body
                body = await request.json()

                # Translate to STDIO
                response = await self.translate(body)

                # Yield as SSE event
                yield {
                    "event": "message",
                    "data": json.dumps(response),
                }

            except Exception as e:
                logger.error(f"Error in SSE event generator: {e}")
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(e)}),
                }

        return EventSourceResponse(event_generator())


class TranslatorManager:
    """
    Manages multiple protocol translators.

    Provides centralized management for all active translators.
    """

    def __init__(self):
        """Initialize translator manager."""
        self.translators: dict[str, ProtocolTranslator] = {}

    async def add_stdio_to_sse(
        self,
        name: str,
        sse_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> StdioToSseTranslator:
        """
        Add STDIO→SSE translator.

        Args:
            name: Translator identifier.
            sse_url: SSE server URL.
            headers: Optional HTTP headers.
            timeout: Request timeout.

        Returns:
            Created translator.
        """
        translator = StdioToSseTranslator(sse_url, headers, timeout)
        await translator.start()
        self.translators[name] = translator
        return translator

    async def add_sse_to_stdio(
        self,
        name: str,
        command: str,
        args: list | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> SseToStdioTranslator:
        """
        Add SSE→STDIO translator.

        Args:
            name: Translator identifier.
            command: STDIO server command.
            args: Command arguments.
            env: Environment variables.
            cwd: Working directory.

        Returns:
            Created translator.
        """
        translator = SseToStdioTranslator(command, args, env, cwd)
        await translator.start()
        self.translators[name] = translator
        return translator

    async def remove_translator(self, name: str):
        """
        Remove and stop a translator.

        Args:
            name: Translator identifier.
        """
        if name in self.translators:
            translator = self.translators.pop(name)
            await translator.stop()

    async def stop_all(self):
        """Stop all translators."""
        for translator in list(self.translators.values()):
            await translator.stop()
        self.translators.clear()

    def get_translator(self, name: str) -> ProtocolTranslator | None:
        """
        Get translator by name.

        Args:
            name: Translator identifier.

        Returns:
            Translator instance or None.
        """
        return self.translators.get(name)


__all__ = [
    "ProtocolTranslator",
    "StdioToSseTranslator",
    "SseToStdioTranslator",
    "TranslatorManager",
]
