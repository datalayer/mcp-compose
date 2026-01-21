#!/usr/bin/env python3
# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Test Dynamic Client Registration (DCR)

This script tests the /register endpoint and verifies that:
1. Client registration works
2. Authorization flow validates registered redirect URIs
3. Invalid redirect URIs are rejected
"""

import requests
import json
import sys

SERVER_URL = "http://localhost:8080"


def test_register_client():
    """Test client registration"""
    print("\n" + "=" * 70)
    print("Testing Dynamic Client Registration")
    print("=" * 70)
    
    # Test 1: Valid registration
    print("\n1️⃣  Testing valid client registration...")
    response = requests.post(
        f"{SERVER_URL}/register",
        json={
            "redirect_uris": ["http://localhost:9999/callback", "http://localhost:9999/other"],
            "client_name": "Test Client",
            "client_uri": "https://example.com",
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none"
        }
    )
    
    if response.status_code != 201:
        print(f"❌ Registration failed: {response.status_code}")
        print(response.text)
        return None
    
    registration = response.json()
    client_id = registration.get("client_id")
    
    print(f"✅ Client registered successfully!")
    print(f"   Client ID: {client_id}")
    print(f"   Redirect URIs: {registration.get('redirect_uris')}")
    print(f"   Issued at: {registration.get('client_id_issued_at')}")
    
    # Test 2: Missing redirect_uris
    print("\n2️⃣  Testing registration without redirect_uris (should fail)...")
    response = requests.post(
        f"{SERVER_URL}/register",
        json={
            "client_name": "Invalid Client"
        }
    )
    
    if response.status_code == 400:
        error = response.json()
        print(f"✅ Correctly rejected: {error.get('error_description')}")
    else:
        print(f"❌ Should have returned 400, got {response.status_code}")
    
    # Test 3: Empty redirect_uris
    print("\n3️⃣  Testing registration with empty redirect_uris (should fail)...")
    response = requests.post(
        f"{SERVER_URL}/register",
        json={
            "redirect_uris": [],
            "client_name": "Invalid Client 2"
        }
    )
    
    if response.status_code == 400:
        error = response.json()
        print(f"✅ Correctly rejected: {error.get('error_description')}")
    else:
        print(f"❌ Should have returned 400, got {response.status_code}")
    
    return client_id


def test_authorization_with_registered_client(client_id):
    """Test authorization flow with registered client"""
    print("\n" + "=" * 70)
    print("Testing Authorization with Registered Client")
    print("=" * 70)
    
    # Test 4: Valid redirect_uri (should work)
    print("\n4️⃣  Testing authorization with valid redirect_uri...")
    response = requests.get(
        f"{SERVER_URL}/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": "http://localhost:9999/callback",
            "response_type": "code",
            "state": "test123",
            "code_challenge": "CHALLENGE",
            "code_challenge_method": "S256"
        },
        allow_redirects=False
    )
    
    if response.status_code in (302, 307):
        print(f"✅ Authorization started (redirecting to GitHub)")
        print(f"   Redirect to: {response.headers.get('Location', '')[:100]}...")
    else:
        print(f"❌ Expected redirect, got {response.status_code}")
        print(response.text)
    
    # Test 5: Invalid redirect_uri (should fail)
    print("\n5️⃣  Testing authorization with invalid redirect_uri (should fail)...")
    response = requests.get(
        f"{SERVER_URL}/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": "http://evil.com/callback",
            "response_type": "code",
            "state": "test123",
            "code_challenge": "CHALLENGE",
            "code_challenge_method": "S256"
        },
        allow_redirects=False
    )
    
    if response.status_code == 400:
        error = response.json()
        print(f"✅ Correctly rejected: {error.get('error_description')}")
    else:
        print(f"❌ Should have returned 400, got {response.status_code}")
        print(response.text)


def test_metadata_discovery():
    """Test that DCR is advertised in metadata"""
    print("\n" + "=" * 70)
    print("Testing Metadata Discovery")
    print("=" * 70)
    
    print("\n6️⃣  Testing authorization server metadata...")
    response = requests.get(f"{SERVER_URL}/.well-known/oauth-authorization-server")
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch metadata: {response.status_code}")
        return
    
    metadata = response.json()
    registration_endpoint = metadata.get("registration_endpoint")
    
    if registration_endpoint:
        print(f"✅ DCR advertised in metadata")
        print(f"   Registration endpoint: {registration_endpoint}")
    else:
        print(f"❌ registration_endpoint not found in metadata")
    
    print(f"\n📋 Authorization Server Metadata:")
    print(json.dumps(metadata, indent=2))


def main():
    print("\n🧪 Dynamic Client Registration Test Suite")
    print("=" * 70)
    print(f"Testing server: {SERVER_URL}")
    print("Make sure the server is running: make start")
    print("=" * 70)
    
    # Check if server is running
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=2)
        if response.status_code != 200:
            print(f"\n❌ Server returned {response.status_code}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to {SERVER_URL}")
        print("   Make sure the server is running: make start")
        sys.exit(1)
    
    # Run tests
    client_id = test_register_client()
    
    if client_id:
        test_authorization_with_registered_client(client_id)
    
    test_metadata_discovery()
    
    print("\n" + "=" * 70)
    print("✅ All DCR tests completed!")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
