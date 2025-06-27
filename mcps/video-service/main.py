"""
此模块实现了一个基于 MCP 的视频生成服务，用于根据图像生成视频。
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
from .video_model import VideoModel


# 图生视频工具列表
VIDEO_TOOLS = [
    {
        "name": "image_to_video",
        "description": "根据输入的图像生成视频",
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "输入图像的路径"},
                "output_format": {"type": "string", "default": "mp4", "description": "生成视频的格式"},
                "fps": {"type": "integer", "default": 25, "description": "视频帧率"}
            },
            "required": ["image_path"]
        }
    }
]


async def main(model_name: str, api_key: str, server_type: str = 'sse'):
    """
    启动视频生成服务的主函数

    :param model_name: 使用的模型名称
    :param api_key: 火山引擎 API 密钥
    :param server_type: 服务器启动类型，支持 'sse' 和 'stdio'，默认为 'sse'
    """
    Path('.').parent.mkdir(parents=True, exist_ok=True)
    model = VideoModel(model_name, api_key)

    mcp = FastMCP("video-service")
    app = mcp._mcp_server

    @app.list_tools()
    async def list_video_tools() -> List[Dict[str, Any]]:
        """
        动态返回启用的视频工具列表
        """
        return VIDEO_TOOLS

    @app.call_tool()
    async def call_video_tool(name: str, arguments: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        统一调用视频工具处理函数
        """
        try:
            if name == 'image_to_video':
                video_path = await model.image_to_video(
                    arguments['image_path'],
                    arguments.get('output_format', 'mp4'),
                    arguments.get('fps', 25)
                )
                return [{"type": "text", "text": video_path}]
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
        parser = argparse.ArgumentParser(description='MCP Video server')
        parser.add_argument('--host', type=str, default='0.0.0.0', help='hosts')
        parser.add_argument('--port', type=int, default=config.video_service_port, help='port')
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
                    server_name="video-service",
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
    parser = argparse.ArgumentParser(description='Video Service')
    parser.add_argument('--model', required=True, help='使用的模型名称')
    parser.add_argument('--api-key', required=True, help='火山引擎 API 密钥')
    parser.add_argument('--server-type', choices=['sse', 'stdio'], default='sse', help='Server type: sse or stdio')
    args = parser.parse_args()
    asyncio.run(main(args.model, args.api_key, args.server_type))