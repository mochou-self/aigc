import json
import random
import logging
from typing import Any, AsyncIterable, Dict, Optional, List
from omegaconf import DictConfig
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
from common.callbacks import initialize_callbacks

from agents.orchestrator.agent import build_agent

logger = logging.getLogger('orchestrator')

# Local cache of created request_ids for demo purposes.
request_ids = set()


class Orchestrator:
    """协调员智能体，负责协调多个智能体，是值班机器人对外的总入口。"""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self, cfg:DictConfig, executor):
        logger.info("Initializing Orchestrator: %s", cfg)
        self.cfg = cfg
        self.executor = executor
        self.agent = None
        self.exit_stacks = []
  
    async def open(self) -> None:
        if self.agent is not None:
            return
        await initialize_callbacks()
        self.agent, self.exit_stacks = await build_agent(self.cfg.agent)
        self._runner = Runner(
            app_name=self.cfg.app_name,
            agent=self.agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    async def close(self) -> None:
        for stack in self.exit_stacks:
            await exit_stack.aclose()
        self.exit_stacks.clear()

    async def stream(self, query, session_id) -> AsyncIterable[Dict[str, Any]]:
        await self.open()
        session = await self._runner.session_service.get_session(
            app_name=self.cfg.app_name, user_id=self.cfg.user_id, session_id=session_id
        )
        content = types.Content(
            role="user", parts=[types.Part.from_text(text=query)]
        )
        if session is None:
            session = await self._runner.session_service.create_session(
                app_name=self.cfg.app_name,
                user_id=self.cfg.user_id,
                state={
                    "author": "leon",
                },
                session_id=session_id,
            )
        async for event in self._runner.run_async(
            user_id=self.cfg.user_id, session_id=session.id, new_message=content
        ):
            await self.executor.on_event(session, event)

            # 不管有没有完成
            # 都生成一个 item
            response = ""
            if (
                event.content
                and event.content.parts
                and event.content.parts[0].text
            ):
                response = "\n".join([p.text for p in event.content.parts if p.text])
            elif (
                event.content
                and event.content.parts
                and any([True for p in event.content.parts if p.function_response])):
                response = next((p.function_response.model_dump() for p in event.content.parts))
            yield {
                "is_task_complete": event.is_final_response(),
                "content": response,
            }
