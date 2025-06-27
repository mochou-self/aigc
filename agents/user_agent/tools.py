import logging
from typing import Any, AsyncIterable, Dict, Optional, List
from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger('agent')
book = {
    "张三丰": "1234567890",
    "李四远": "0987654321",
    "王五成": "1122334455",
    "张六侠": "1333094848",
}

def get_user_list(tool_context: ToolContext) -> List[str]:
    """获取用户列表"""
    logger.info('tool_context: %s, %s', tool_context, tool_context.state.to_dict())

    state = tool_context.state
    if 'get_user_list' not in state:
        state['get_user_list'] = 0
    state['get_user_list'] += 1
    
    return {
        "user_list": list(book.keys())
    }

def get_phone_number(user:str, tool_context: ToolContext) -> str:
    """获取用户手机号"""
    logger.info('tool_context: %s, %s', tool_context, tool_context.state.to_dict())

    state = tool_context.state
    if 'get_phone_number' not in state:
        state['get_phone_number'] = 0
    state['get_phone_number'] += 1

    return {
        "user": user,
        "phone_number": book.get(user, "Unknown"),
    }

def call_number(phone_number: str, tool_context: ToolContext) -> str:
    """拨打电话"""
    logger.info('tool_context: %s, %s', tool_context, tool_context.state.to_dict())

    state = tool_context.state
    if 'call_number' not in state:
        state['call_number'] = 0
    state['call_number'] += 1

    return {
        "phone_number": phone_number, 
        "result": f"Calling {phone_number}...",
    }
