import json
import random
from typing import Any, AsyncIterable, Dict, Optional, List

from google.adk.models.lite_llm import LiteLlm
from google.adk import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_toolset import SseServerParams

from .tools import (
    get_user_list,
    get_phone_number,
    call_number,
)

from .prompt import (
    DESCRIPTION,
    INSTRUCTION,
)

async def build_agent(cfg):
    return Agent(
        model=LiteLlm(
            model=cfg.llm.model,
            api_base=cfg.llm.base_url,
            api_key=cfg.llm.api_key,
        ),
        name="user_agent",
        description=DESCRIPTION,
        instruction=INSTRUCTION,
        **cfg.callbacks,
        tools=[
            get_user_list,
            get_phone_number,
            call_number,
            MCPToolset(
                connection_params=SseServerParams(
                    url='http://localhost:10002/sse',
                    headers={'Accept': 'text/event-stream'},
                ),
            ),
        ],
    )

