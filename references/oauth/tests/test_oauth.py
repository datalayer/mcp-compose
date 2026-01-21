# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Test script to verify the authentication flow works correctly
"""

import requests


def test_unauthenticated_access():
    """Test that unauthenticated requests return 401"""
    print("Testing unauthenticated access...")
    
    response = requests.get("http://localhost:8080/tools")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    assert "WWW-Authenticate" in response.headers, "Missing WWW-Authenticate header"
    
    print("✅ Unauthenticated access correctly returns 401")


def test_metadata_endpoints():
    """Test that metadata endpoints are accessible"""
    print("\nTesting metadata endpoints...")
    
    # Test protected resource metadata
    response = requests.get("http://localhost:8080/.well-known/oauth-protected-resource")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    metadata = response.json()
    assert "authorization_servers" in metadata, "Missing authorization_servers"
    print("✅ Protected resource metadata works")
    
    # Test authorization server metadata
    response = requests.get("http://localhost:8080/.well-known/oauth-authorization-server")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    metadata = response.json()
    assert "authorization_endpoint" in metadata, "Missing authorization_endpoint"
    assert "token_endpoint" in metadata, "Missing token_endpoint"
    print("✅ Authorization server metadata works")


def test_authenticated_access():
    """Test authenticated access (requires valid token)"""
    print("\nNote: Full authentication test requires a valid GitHub token")
    print("Run the client.py to perform complete OAuth flow and MCP tool invocation")


def test_mcp_endpoints():
    """Test that MCP endpoints exist"""
    print("\nTesting MCP endpoints...")
    
    # Test MCP endpoint (should return 401 without auth)
    response = requests.get("http://localhost:8080/mcp")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    print("✅ MCP endpoint requires authentication")
    
    # Test root endpoint
    response = requests.get("http://localhost:8080/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "mcp" in data.get("endpoints", {}), "Missing MCP endpoints"
    print("✅ Root endpoint shows MCP configuration")


if __name__ == "__main__":
    print("=" * 70)
    print("Testing MCP Server with OAuth Authentication")
    print("=" * 70)
    print("\nMake sure the server is running: python server.py")
    print()
    
    try:
        test_unauthenticated_access()
        test_metadata_endpoints()
        test_mcp_endpoints()
        test_authenticated_access()
        
        print("\n" + "=" * 70)
        print("✅ All basic tests passed!")
        print("=" * 70)
    
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to server. Is it running on http://localhost:8080?")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
