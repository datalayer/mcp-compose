#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Client with GitHub OAuth2 Authentication

This client demonstrates how to:
1. Discover OAuth metadata from an MCP server
2. Load configuration (OAuth app credentials, server URL)
3. Authenticate using OAuth2 with PKCE
4. Connect to MCP server via HTTP Streaming transport with authentication
5. List available tools

Learning Objectives:
1. Understand OAuth2 discovery process
2. Implement PKCE (Proof Key for Code Exchange)
3. Handle browser-based authentication flow
4. Use MCP SDK client with authenticated transport
"""

from typing import Dict, Optional, Any, AsyncIterator
import asyncio
import json

# Import shared OAuth client
from .oauth_client import OAuthClient

# MCP client imports
try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    import httpx
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("⚠️  MCP SDK not installed. Install with: pip install mcp httpx")


class MCPClient:
    """MCP Client with OAuth2 authentication"""
    
    def __init__(self, config_file: str = "config.json"):
        # Use shared OAuth client
        self.oauth = OAuthClient(config_file, verbose=True)
        self.access_token: Optional[str] = None
    
    def discover_metadata(self) -> bool:
        """
        Step 1: Discover OAuth metadata from MCP server
        
        Delegates to shared OAuthClient
        """
        print("\n" + "=" * 70)
        print("🔍 STEP 1: Discovering OAuth Metadata")
        print("=" * 70)
        
        return self.oauth.discover_metadata()
    
    def authenticate(self) -> bool:
        """
        Step 2: Perform OAuth2 authentication flow
        
        Delegates to shared OAuthClient
        """
        print("\n" + "=" * 70)
        print("🔐 STEP 2: OAuth2 Authentication Flow")
        print("=" * 70)
        
        if self.oauth.authenticate():
            self.access_token = self.oauth.get_token()
            return True
        return False
    
    def list_tools(self) -> Optional[Dict[str, Any]]:
        """
        Step 3: Make authenticated request to list tools
        """
        print("\n" + "=" * 70)
        print("🔧  STEP 3: Listing Available Tools")
        print("=" * 70)
        
        if not self.access_token:
            print("❌ Error: No access token. Run authenticate() first.")
            return None
        
        try:
            # Use MCP protocol to list tools with HTTP streaming
            async def _list_tools():
                # Disable SSL verification for localhost (development with mkcert)
                server_url = self.oauth.get_server_url()
                verify_ssl = not server_url.startswith("https://localhost")
                
                # Create HTTP client with auth headers
                async with httpx.AsyncClient(
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    timeout=30.0,
                    verify=verify_ssl
                ) as http_client:
                    # Connect using MCP SDK's streamable HTTP client
                    async with streamablehttp_client(
                        f"{self.oauth.get_server_url()}/mcp",
                        http_client=http_client
                    ) as (read_stream, write_stream):
                        async with ClientSession(read_stream, write_stream) as session:
                            await session.initialize()
                            tools_list = await session.list_tools()
                            return tools_list
            
            # Run async function
            tools_list = asyncio.run(_list_tools())
            
            if tools_list:
                print("✅ Tools retrieved successfully:")
                for tool in tools_list.tools:
                    print(f"\n   📦 {tool.name}")
                    print(f"      {tool.description}")
                return {"tools": [{"name": t.name, "description": t.description} for t in tools_list.tools]}
            else:
                print("❌ Error: No tools returned")
                return None
        
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def invoke_tool_mcp(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Any]:
        """
        Invoke an MCP tool using the MCP SDK client with HTTP streaming
        
        Args:
            tool_name: Name of the tool to invoke
            arguments: Tool arguments
        
        Returns:
            Tool result or None on error
        """
        if not HAS_MCP:
            print("❌ Error: MCP SDK not installed")
            return None
        
        if not self.access_token:
            print("❌ Error: No access token")
            return None
        
        print(f"\n🔧 Invoking tool via MCP protocol: {tool_name}")
        print(f"   Arguments: {arguments}")
        
        try:
            # Disable SSL verification for localhost (development with mkcert)
            server_url = self.oauth.get_server_url()
            verify_ssl = not server_url.startswith("https://localhost")
            
            # Create HTTP client with auth headers
            async with httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=30.0,
                verify=verify_ssl
            ) as http_client:
                # Connect to MCP server via HTTP streaming
                async with streamablehttp_client(
                    f"{self.oauth.get_server_url()}/mcp",
                    http_client=http_client
                ) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        # Initialize the session
                        await session.initialize()
                        
                        # Call the tool
                        result = await session.call_tool(tool_name, arguments)
                        
                        # Extract content from result
                        if hasattr(result, 'content'):
                            content = result.content
                            if isinstance(content, list) and len(content) > 0:
                                # Get the text content from the first item
                                first_content = content[0]
                                if hasattr(first_content, 'text'):
                                    result_text = first_content.text
                                else:
                                    result_text = str(first_content)
                            else:
                                result_text = str(content)
                        else:
                            result_text = str(result)
                        
                        print(f"✅ Tool invoked successfully")
                        print(f"   Result: {result_text}")
                        
                        return result
        
        except Exception as e:
            print(f"❌ Error invoking tool: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def demo(self):
        """Run a complete demonstration"""
        print("\n" + "=" * 70)
        print("🚀 MCP Client with GitHub OAuth2 - Complete Demo")
        print("=" * 70)
        print("\nThis demo will:")
        print("1. Discover OAuth metadata from the MCP server")
        print("2. Authenticate you via GitHub OAuth2")
        print("3. List available tools on the MCP server")
        print("4. Invoke example tools using MCP protocol")
        print("\nPress Enter to start...")
        input()
        
        # Step 1: Discover metadata
        if not self.discover_metadata():
            print("\n❌ Demo failed at metadata discovery")
            return
        
        print("\n✅ Metadata discovery complete!")
        print("\nPress Enter to continue with authentication...")
        input()
        
        # Step 2: Authenticate
        if not self.authenticate():
            print("\n❌ Demo failed at authentication")
            return
        
        print("\n✅ Authentication complete!")
        print("\nPress Enter to list tools...")
        input()
        
        # Step 3: List tools
        tools = self.list_tools()
        if not tools:
            print("\n❌ Demo failed at listing tools")
            return
        
        print("\n✅ Tools listed!")
        print("\nPress Enter to invoke example tools...")
        input()
        
        # Step 4: Invoke tools using MCP protocol
        if not HAS_MCP:
            print("\n⚠️  MCP SDK not available, skipping tool invocation")
            print("   Install with: pip install mcp")
        else:
            print("\n" + "=" * 70)
            print("🎯 STEP 4: Invoking Example Tools via MCP Protocol")
            print("=" * 70)
            
            # Run async tool invocations
            asyncio.run(self._demo_invoke_tools())
        
        print("\n" + "=" * 70)
        print("🎉 Demo Complete!")
        print("=" * 70)
        print("\nYou have successfully:")
        print("✅ Discovered OAuth metadata")
        print("✅ Authenticated with GitHub")
        print("✅ Listed available tools")
        if HAS_MCP:
            print("✅ Invoked MCP tools with authentication")
        print("\n🎓 You now understand how MCP authorization works!")
        print("=" * 70)
    
    async def _demo_invoke_tools(self):
        """Internal method to invoke tools for demo"""
        # Calculator examples
        await self.invoke_tool_mcp("calculator_add", {"a": 15, "b": 27})
        await asyncio.sleep(1)
        
        await self.invoke_tool_mcp("calculator_multiply", {"a": 8, "b": 9})
        await asyncio.sleep(1)
        
        # Greeter examples
        await self.invoke_tool_mcp("greeter_hello", {"name": "Alice"})
        await asyncio.sleep(1)
        
        await self.invoke_tool_mcp("greeter_goodbye", {"name": "Bob"})
        await asyncio.sleep(1)
        
        # Server info
        await self.invoke_tool_mcp("get_server_info", {})


def main():
    """Main entry point"""
    import sys
    import io
    
    # Ensure stdout uses UTF-8 encoding for emoji support
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    try:
        client = MCPClient()
        client.demo()
    except KeyboardInterrupt:
        print("\n\n🛑 Demo cancelled by user")
    except FileNotFoundError:
        print("\n❌ Error: config.json not found")
        print("Please create config.json with your GitHub OAuth credentials")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
