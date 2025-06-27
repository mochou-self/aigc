import json
import random
from typing import Any, AsyncIterable, Dict, Optional, List, Tuple
from contextlib import AsyncExitStack

from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from google.adk.models import LlmRequest
from google.adk.models import LlmResponse
from google.adk.tools import BaseTool
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.adk.events import Event
from google.genai import types
from google.adk.models.lite_llm import LiteLlm


from common.config import config
from common.callbacks import (
    before_agent,
    after_agent,
    before_model,
    after_model,
    before_tool,
    after_tool,
)

from agents import build_sub_agents
from .prompt import DESCRIPTION, INSTRUCTION
from .tools import (
    get_generator_list,
    get_generator_info,
)

async def build_agent(cfg) -> Tuple[LlmAgent, List[AsyncExitStack]]:
    """Builds the LLM agent for the orchestrator agent."""
    arr = await build_sub_agents(cfg)
    sub_agents = []
    exit_stacks = []
    for item in arr:
        if type(item) is tuple:
            agent, exit_stack = item
            sub_agents.append(agent)
            if type(exit_stack) is list:
                exit_stacks.extend(exit_stack)
            else:
                exit_stacks.append(exit_stack)
        else:
            agent = item
            sub_agents.append(agent)
            
    agent = LlmAgent(
        # model="gemini-2.0-flash-001",
        model=LiteLlm(
            model=cfg.llm.model,
            api_base=cfg.llm.base_url,
            api_key=cfg.llm.api_key,
        ),
        name="orchestrator_agent",
        description=cfg.get('description', DESCRIPTION),
        instruction=cfg.get('instruction', INSTRUCTION),
        **cfg.callbacks,
        # tools=[
        #     get_generator_list,
        #     get_generator_info,
        # ],
        sub_agents=sub_agents,
    )
    return agent, exit_stacks