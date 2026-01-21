# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tests for server management endpoints.

Tests all server management routes including listing, details,
lifecycle control, removal, log streaming, and metrics.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from mcp_compose.api import create_app
from mcp_compose.api.dependencies import set_composer


@pytest.fixture
def mock_composer():
    """Create a mock composer with test servers."""
    composer = MagicMock()
    
    # Mock configuration with test servers
    server1_config = MagicMock()
    server1_config.name = "test-server-1"
    server1_config.command = "python"
    server1_config.args = ["-m", "test_server"]
    server1_config.env = {"TEST": "value"}
    server1_config.transport = MagicMock(value="stdio")
    server1_config.auto_start = True
    
    server2_config = MagicMock()
    server2_config.name = "test-server-2"
    server2_config.command = "node"
    server2_config.args = ["server.js"]
    server2_config.env = {}
    server2_config.transport = MagicMock(value="sse")
    server2_config.auto_start = False
    
    composer.config.servers = {
        "server1": server1_config,
        "server2": server2_config,
    }
    
    # Mock discovered servers (server1 is running)
    composer.discovered_servers = {"server1": MagicMock()}
    
    # Mock list methods
    composer.list_servers.return_value = ["server1", "server2"]
    composer.list_tools.return_value = ["server1.tool1", "server1.tool2", "server2.tool1"]
    composer.list_prompts.return_value = ["server1.prompt1"]
    composer.list_resources.return_value = ["server1.resource1", "server2.resource1"]
    
    # Mock discover_servers
    async def mock_discover():
        pass
    composer.discover_servers = mock_discover
    
    return composer


@pytest.fixture
def client(mock_composer):
    """Create a test client with mocked dependencies."""
    app = create_app()
    set_composer(mock_composer)
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Authentication headers for requests."""
    return {"X-API-Key": "test-key-12345678"}


class TestListServers:
    """Test server listing endpoint."""
    
    def test_list_all_servers(self, client, auth_headers):
        """Test listing all servers."""
        response = client.get("/api/v1/servers", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "servers" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data
        
        assert data["total"] == 2
        assert len(data["servers"]) == 2
        
        # Check server info
        server1 = next(s for s in data["servers"] if s["id"] == "server1")
        assert server1["name"] == "test-server-1"
        assert server1["command"] == "python"
        assert server1["status"] == "running"
        
        server2 = next(s for s in data["servers"] if s["id"] == "server2")
        assert server2["name"] == "test-server-2"
        assert server2["status"] == "stopped"
    
    def test_list_servers_with_pagination(self, client, auth_headers):
        """Test server listing with pagination."""
        response = client.get(
            "/api/v1/servers?offset=1&limit=1",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["total"] == 2
        assert len(data["servers"]) == 1
        assert data["offset"] == 1
        assert data["limit"] == 1
    
    def test_list_servers_with_status_filter(self, client, auth_headers):
        """Test server listing with status filter."""
        response = client.get(
            "/api/v1/servers?status_filter=running",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert all(s["status"] == "running" for s in data["servers"])
    
    def test_list_servers_requires_auth(self, client):
        """Test that listing servers requires authentication."""
        response = client.get("/api/v1/servers")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetServerDetail:
    """Test server detail endpoint."""
    
    def test_get_running_server_detail(self, client, auth_headers):
        """Test getting details of a running server."""
        response = client.get("/api/v1/servers/server1", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "server" in data
        assert "tools_count" in data
        assert "prompts_count" in data
        assert "resources_count" in data
        assert "uptime_seconds" in data
        
        # Check server info
        assert data["server"]["id"] == "server1"
        assert data["server"]["name"] == "test-server-1"
        assert data["server"]["status"] == "running"
        
        # Check counts
        assert data["tools_count"] == 2  # server1.tool1, server1.tool2
        assert data["prompts_count"] == 1  # server1.prompt1
        assert data["resources_count"] == 1  # server1.resource1
    
    def test_get_stopped_server_detail(self, client, auth_headers):
        """Test getting details of a stopped server."""
        response = client.get("/api/v1/servers/server2", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["server"]["status"] == "stopped"
        assert data["tools_count"] == 0
        assert data["prompts_count"] == 0
        assert data["resources_count"] == 0
    
    def test_get_nonexistent_server(self, client, auth_headers):
        """Test getting details of nonexistent server."""
        response = client.get("/api/v1/servers/nonexistent", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_server_detail_requires_auth(self, client):
        """Test that getting server details requires authentication."""
        response = client.get("/api/v1/servers/server1")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestStartServer:
    """Test server start endpoint."""
    
    @pytest.mark.asyncio
    async def test_start_stopped_server(self, client, auth_headers, mock_composer):
        """Test starting a stopped server."""
        response = client.post("/api/v1/servers/server2/start", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["success"] is True
        assert "started successfully" in data["message"]
        assert data["server_id"] == "server2"
    
    def test_start_running_server(self, client, auth_headers):
        """Test starting an already running server."""
        response = client.post("/api/v1/servers/server1/start", headers=auth_headers)
        assert response.status_code == status.HTTP_409_CONFLICT
    
    def test_start_nonexistent_server(self, client, auth_headers):
        """Test starting a nonexistent server."""
        response = client.post("/api/v1/servers/nonexistent/start", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_start_server_requires_auth(self, client):
        """Test that starting a server requires authentication."""
        response = client.post("/api/v1/servers/server2/start")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestStopServer:
    """Test server stop endpoint."""
    
    def test_stop_running_server(self, client, auth_headers, mock_composer):
        """Test stopping a running server."""
        response = client.post("/api/v1/servers/server1/stop", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["success"] is True
        assert "stopped successfully" in data["message"]
        assert data["server_id"] == "server1"
        
        # Verify server was removed from discovered servers
        assert "server1" not in mock_composer.discovered_servers
    
    def test_stop_stopped_server(self, client, auth_headers):
        """Test stopping an already stopped server."""
        response = client.post("/api/v1/servers/server2/stop", headers=auth_headers)
        assert response.status_code == status.HTTP_409_CONFLICT
    
    def test_stop_nonexistent_server(self, client, auth_headers):
        """Test stopping a nonexistent server."""
        response = client.post("/api/v1/servers/nonexistent/stop", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_stop_server_requires_auth(self, client):
        """Test that stopping a server requires authentication."""
        response = client.post("/api/v1/servers/server1/stop")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRestartServer:
    """Test server restart endpoint."""
    
    @pytest.mark.asyncio
    async def test_restart_running_server(self, client, auth_headers, mock_composer):
        """Test restarting a running server."""
        response = client.post("/api/v1/servers/server1/restart", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["success"] is True
        assert "restarted successfully" in data["message"]
        assert data["server_id"] == "server1"
    
    @pytest.mark.asyncio
    async def test_restart_stopped_server(self, client, auth_headers):
        """Test restarting a stopped server."""
        response = client.post("/api/v1/servers/server2/restart", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["success"] is True
    
    def test_restart_nonexistent_server(self, client, auth_headers):
        """Test restarting a nonexistent server."""
        response = client.post("/api/v1/servers/nonexistent/restart", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_restart_server_requires_auth(self, client):
        """Test that restarting a server requires authentication."""
        response = client.post("/api/v1/servers/server1/restart")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRemoveServer:
    """Test server removal endpoint."""
    
    def test_remove_stopped_server(self, client, auth_headers, mock_composer):
        """Test removing a stopped server."""
        response = client.delete("/api/v1/servers/server2", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["success"] is True
        assert "removed successfully" in data["message"]
        assert data["server_id"] == "server2"
        
        # Verify server was removed from config
        assert "server2" not in mock_composer.config.servers
    
    def test_remove_running_server(self, client, auth_headers):
        """Test removing a running server (should fail)."""
        response = client.delete("/api/v1/servers/server1", headers=auth_headers)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "still running" in response.json()["detail"].lower()
    
    def test_remove_nonexistent_server(self, client, auth_headers):
        """Test removing a nonexistent server."""
        response = client.delete("/api/v1/servers/nonexistent", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_remove_server_requires_auth(self, client):
        """Test that removing a server requires authentication."""
        response = client.delete("/api/v1/servers/server2")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestStreamServerLogs:
    """Test server log streaming endpoint."""
    
    def test_stream_logs_from_running_server(self, client, auth_headers):
        """Test streaming logs from a running server."""
        response = client.get(
            "/api/v1/servers/server1/logs",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # Check SSE headers
        assert "no-cache" in response.headers.get("cache-control", "").lower()
        
        # Check that we receive SSE data
        content = response.text
        assert "data:" in content
        assert "timestamp" in content
    
    def test_stream_logs_from_stopped_server(self, client, auth_headers):
        """Test streaming logs from a stopped server (should fail)."""
        response = client.get(
            "/api/v1/servers/server2/logs",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_409_CONFLICT
    
    def test_stream_logs_from_nonexistent_server(self, client, auth_headers):
        """Test streaming logs from nonexistent server."""
        response = client.get(
            "/api/v1/servers/nonexistent/logs",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_stream_logs_requires_auth(self, client):
        """Test that streaming logs requires authentication."""
        response = client.get("/api/v1/servers/server1/logs")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetServerMetrics:
    """Test server metrics endpoint."""
    
    def test_get_metrics_for_running_server(self, client, auth_headers):
        """Test getting metrics for a running server."""
        response = client.get("/api/v1/servers/server1/metrics", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["server_id"] == "server1"
        assert data["status"] == "running"
        assert data["uptime_seconds"] > 0
        assert data["requests_total"] > 0
        assert "requests_failed" in data
        assert "requests_per_second" in data
        assert "average_response_time_ms" in data
        assert "memory_usage_mb" in data
        assert "cpu_usage_percent" in data
    
    def test_get_metrics_for_stopped_server(self, client, auth_headers):
        """Test getting metrics for a stopped server."""
        response = client.get("/api/v1/servers/server2/metrics", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["server_id"] == "server2"
        assert data["status"] == "stopped"
        assert data["uptime_seconds"] == 0.0
        assert data["requests_total"] == 0
    
    def test_get_metrics_for_nonexistent_server(self, client, auth_headers):
        """Test getting metrics for nonexistent server."""
        response = client.get("/api/v1/servers/nonexistent/metrics", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_metrics_requires_auth(self, client):
        """Test that getting metrics requires authentication."""
        response = client.get("/api/v1/servers/server1/metrics")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestServerEndpointsIntegration:
    """Integration tests for server endpoints."""
    
    @pytest.mark.asyncio
    async def test_server_lifecycle(self, client, auth_headers, mock_composer):
        """Test complete server lifecycle: list, start, stop, remove."""
        # List servers
        response = client.get("/api/v1/servers", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 2
        
        # Get details of stopped server
        response = client.get("/api/v1/servers/server2", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["server"]["status"] == "stopped"
        
        # Start server
        response = client.post("/api/v1/servers/server2/start", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        # Stop server
        mock_composer.discovered_servers["server2"] = MagicMock()
        response = client.post("/api/v1/servers/server2/stop", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        # Remove server
        response = client.delete("/api/v1/servers/server2", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        
        # Verify server was removed
        assert "server2" not in mock_composer.config.servers
