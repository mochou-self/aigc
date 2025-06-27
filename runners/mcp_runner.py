from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

"""
Sample code

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # Executable
    args=["example_server.py"],  # Optional command line arguments
    env=None,  # Optional environment variables
)


# Optional: create a sampling callback
async def handle_sampling_message(
    message: types.CreateMessageRequestParams,
) -> types.CreateMessageResult:
    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(
            type="text",
            text="Hello, world! from model",
        ),
        model="gpt-3.5-turbo",
        stopReason="endTurn",
    )

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
            read, write, sampling_callback=handle_sampling_message
        ) as session:
            # Initialize the connection
            await session.initialize()

            # List available prompts
            prompts = await session.list_prompts()

            # Get a prompt
            prompt = await session.get_prompt(
                "example-prompt", arguments={"arg1": "value"}
            )

            # List available resources
            resources = await session.list_resources()

            # List available tools
            tools = await session.list_tools()

            # Read a resource
            content, mime_type = await session.read_resource("file://some/path")

            # Call a tool
            result = await session.call_tool("tool-name", arguments={"arg1": "value"})

if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
"""

class MCPClientRunner:
    def __init__(self, args):
        self.args = args
    
    async def run(self):
        client = stdio_client if type(self.args.server_params) == StdioServerParameters else sse_client
        async with client(self.args.server_params) as (read, write):
            async with ClientSession(
                read, write
            ) as session:
                # Initialize the connection
                await session.initialize()

                # Call a tool
                results = []
                for tool_call in self.args.get("tool_calls", []):
                    print(tool_call)
                    result = await session.call_tool(tool_call.name, arguments=tool_call.args)
                    print(result)
                    results.append(result)
                if not results:
                    # List available tools
                    tools = await session.list_tools()
                    print(tools)
                return results