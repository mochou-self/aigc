"""
此模块实现了一个基于 MCP 的图像生成服务，用于根据文本描述生成图像。
"""
import asyncio
import argparse
import json
from typing import List, Dict, Any
from pathlib import Path
from conf.common_config import config
from mcp.server import Server, InitializationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from mcp.server.lowlevel import NotificationOptions
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
from .image_model import ImageModel

TOOLS = [
    {
        "name": "generate_image",
        "description": "根据输入的文本描述生成图像",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "图像的文本描述"},
                "response_format": {"type": "string", "default": "url", "description": "生成图像的返回格式，可选 'url' 或 'b64_json'"},
                "size": {"type": "string", "default": "1024x1024", "description": "生成图像的宽高像素"},
                "seed": {"type": "integer", "default": -1, "description": "随机数种子"},
                "guidance_scale": {"type": "number", "default": 2.5, "description": "模型输出与提示词的一致程度"},
                "watermark": {"type": "boolean", "default": True, "description": "是否添加水印"}
            },
            "required": ["text"]
        }
    }
]

async def main(model_name: str, api_key: str, server_type: str = 'sse'):
    """
    启动图像生成服务的主函数

    :param model_name: 使用的模型名称
    :param api_key: 火山引擎 API 密钥
    :param server_type: 服务器启动类型，支持 'sse' 和 'stdio'，默认为 'sse'
    """
    Path('.').parent.mkdir(parents=True, exist_ok=True)
    model = ImageModel(model_name, api_key)

    mcp = FastMCP("image-service")
    app = mcp._mcp_server

    @app.list_tools()
    async def list_tools() -> List[Dict[str, Any]]:
        """
        动态返回启用的工具列表
        """
        return TOOLS

    @app.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        统一调用工具处理函数
        """
        try:
            if name == 'generate_image':
                image_path = await model.generate_image(
                    arguments['text'],
                    arguments.get('response_format', 'url'),
                    arguments.get('size', '1024x1024'),
                    arguments.get('seed', -1),
                    arguments.get('guidance_scale', 2.5),
                    arguments.get('watermark', True)
                )
                return [{"type": "text", "text": image_path}]
            return [{"type": "text", "text": json.dumps({
                'result': 'failed',
                'error': f'未知工具: {name}'
            })}]
        except Exception as e:
            return [{"type": "text", "text": json.dumps({
                'result': 'failed',
                'error': str(e)
            })}]

    # 创建 Starlette 应用
    def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
        """
        创建一个 Starlette 应用，用于通过 SSE 协议服务 MCP 服务器
        """
        sse = SseServerTransport("/messages/")

        async def handle_sse(request: Request) -> None:
            async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
            ) as (read_stream, write_stream):
                await mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server.create_initialization_options(),
                )
        return Starlette(
            debug=debug,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )

    if server_type == 'sse':
        parser = argparse.ArgumentParser(description='MCP Image server')
        parser.add_argument('--host', type=str, default='0.0.0.0', help='hosts')
        parser.add_argument('--port', type=int, default=config.image_service_port, help='port')
        args = parser.parse_args()

        # 绑定 SSE 请求处理到 MCP 服务器
        mcp_server = mcp._mcp_server
        starlette_app = create_starlette_app(mcp_server, debug=True)

        @starlette_app.on_event("startup")
        async def startup_event(): 
            pass

        import uvicorn
        uvicorn.run(
            starlette_app,
            host=args.host,
            port=args.port,
        )
    elif server_type == 'stdio':
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="image-service",
                    server_version="0.1.2",
                    capabilities=app.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    else:
        raise ValueError(f"不支持的服务器类型: {server_type}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Image Service')
    parser.add_argument('--model', required=True, help='使用的模型名称')
    parser.add_argument('--api-key', required=True, help='火山引擎 API 密钥')
    parser.add_argument('--server-type', choices=['sse', 'stdio'], default='sse', help='Server type: sse or stdio')
    args = parser.parse_args()
    asyncio.run(main(args.model, args.api_key, args.server_type))