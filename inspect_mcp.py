
import inspect
from mcp.server.lowlevel.server import Server

print("Inspecting mcp.server.lowlevel.server.Server")
print("-" * 50)
print(f"Server.run signature: {inspect.signature(Server.run)}")
if hasattr(Server, '_handle_request'):
    print(f"Server._handle_request signature: {inspect.signature(Server._handle_request)}")
else:
    print("Server._handle_request does not exist")

if hasattr(Server, '_handle_message'):
    print(f"Server._handle_message signature: {inspect.signature(Server._handle_message)}")
else:
    print("Server._handle_message does not exist")
