"""
此模块实现了一个基于 MCP 的通用数据库服务，用于管理数据库数据。
使用 SQLite3 作为数据库，支持通过 MCP 协议进行交互。
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
import uvicorn
from .db_handler import get_session, list_tables, describe_table, read_data, write_data, create_table, TOOLS

async def main(db_path: str, server_type: str = 'sse'):
    """
    启动数据库服务的主函数

    :param db_path: SQLite 数据库文件的路径
    :param server_type: 服务器启动类型，支持 'sse' 和 'stdio'，默认为 'sse'
    """
    logging.info(f"Starting DB Service (DB Path: {db_path}, Server Type: {server_type})" )
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # 数据库配置
    db_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_engine(db_url)
    SessionLocal = get_session(db_url)

    mcp = FastMCP("db-service")
    app = mcp._mcp_server

    @app.list_tools()
    async def list_tools() -> List[Dict[str, Any]]:
        """
        动态返回启用的工具列表
        """
        logging.info('列出可用工具')
        return TOOLS

    @app.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        统一调用工具处理函数
        """
        logging.info(f'调用工具: {name}, 参数: {arguments}')
        try:
            if name == 'list_tables':
                tables = list_tables(engine)
                return [{{"type": "text", "text": json.dumps({
                    'result': 'success',
                    'tables': tables
                })}}]
            elif name == 'describe_table':
                table_info = describe_table(engine, arguments['table_name'])
                return [{{"type": "text", "text": json.dumps({
                    'result': 'success',
                    'table_info': table_info
                })}}]
            elif name == 'read_data':
                data = read_data(
                    SessionLocal,
                    arguments['table_name'],
                    arguments.get('limit', 10)
                )
                return [{{"type": "text", "text": json.dumps({
                    'result': 'success',
                    'data': data
                })}}]
            elif name == 'write_data':
                write_data(SessionLocal, arguments['table_name'], arguments['data'])
                return [{{"type": "text", "text": json.dumps({
                    'result': 'success',
                    'message': '数据写入成功'
                })}}]
            elif name == 'create_table':
                result = create_table(engine, arguments['table_name'], arguments['columns'])
                return [{{"type": "text", "text": json.dumps({
                    'result': result['status'],
                    'message': result['message']
                })}}]
            return [{{"type": "text", "text": json.dumps({
                'result': 'failed',
                'error': f'未知工具: {name}'
            })}}]
        except Exception as e:
            return [{{"type": "text", "text": json.dumps({
                'result': 'failed',
                'error': str(e)
            })}}]

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
        parser = argparse.ArgumentParser(description='MCP DB server')
        parser.add_argument('--host', type=str, default='0.0.0.0', help='hosts')
        parser.add_argument('--port', type=int, default=config.db_service_port, help='port')
        args = parser.parse_args()

        # 绑定 SSE 请求处理到 MCP 服务器
        mcp_server = mcp._mcp_server
        starlette_app = create_starlette_app(mcp_server, debug=True)

        @starlette_app.on_event("startup")
        async def startup_event(): pass

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
                    server_name="sqlite",
                    server_version="0.1.2",
                    capabilities=app.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    else:
        logging.error(f"不支持的服务器类型: {server_type}")
        raise ValueError(f"不支持的服务器类型: {server_type}")

if __name__ == "__main__":
    """
    命令行：
        python ./mcps/db-service/main.py --db-path ./data/test.sqlite --server-type sse
        python ./mcps/db-service/main.py --db-path ./data/test.sqlite --server-type stdio
    mcp cli:
        # 导入必要的模块
        from pathlib import Path
        from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, StdioConnectionParams

        # 定义工具路径和数据库路径
        tool_path = Path('d:/ipanel/study/toutiao_video/mcps/db-service')
        db_path = Path('./data/test.sqlite')
        # 方式 1：使用 uv 命令启动服务, 定义 Stdio 服务器参数
        db_server_parameters = StdioServerParameters(
            command='uv',
            args=[
                "--directory",
                str(tool_path),
                "run",
                "main.py",
                "--db-path",
                str(db_path),
                "--server-type",
                "stdio"
            ],
            tool_filter=[],
        )
        # 选择一种服务器参数来创建 MCPToolset 实例，这里以 db_server_parameters 为例
        try:
            db_tool = MCPToolset(
                connection_params=StdioConnectionParams(
                    server_params=db_server_parameters,
                    timeout=300.0
                ),
            )
            # 获取并打印工具信息
            for t in await db_tool.get_tools():
                logger.info(f'tool name:{t.name}, description:{t.description}')
            return db_tool
        except Exception as e:
            logger.error(f"加载 DB 服务工具失败: {e}")
            raise
    """
    parser = argparse.ArgumentParser(description='DB Service')
    parser.add_argument('--db-path', default='./data/db.sqlite', help='Path to SQLite database file')
    parser.add_argument('--server-type', choices=['sse', 'stdio'], default='sse', help='Server type: sse or stdio')
    args = parser.parse_args()
    asyncio.run(main(args.db_path, args.server_type))