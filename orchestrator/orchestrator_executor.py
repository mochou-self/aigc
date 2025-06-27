import base64
import logging
import os
import json
import datetime
import uuid
from typing import List, Dict, Optional, Any, Tuple, Union

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import Event, EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    DataPart,
    FilePart,
    FileWithBytes,
    Part,
    Task,
    TaskState,
    TaskStatus,
    Message,
    Role,
    TextPart,
    TaskStatusUpdateEvent,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_parts_message,
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError
from typing_extensions import override
from omegaconf import DictConfig, open_dict
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from google.adk.models import LlmRequest
from google.adk.models import LlmResponse
from google.adk.tools import BaseTool
from google.adk.sessions import Session
from google.adk.events import Event

from common.recorder import recorder
from common.callbacks import (
    before_agent,
    after_agent,
    before_model,
    after_model,
    before_tool,
    after_tool,
    on_event,
)

from orchestrator import Orchestrator

logger = logging.getLogger('orchestrator')

class OrchestratorAgentExecutor(AgentExecutor):
    """Orchestrator AgentExecutor Example."""

    def __init__(self, cfg:DictConfig):
        logger.info("Initializing OrchestratorAgentExecutor: %s", cfg)
        self.cfg = cfg
        self._messages = []
        self.orchestrator = Orchestrator(cfg, self)

    def append_message(self, message: str):
        timestamp = datetime.datetime.now()
        self._messages.append((timestamp, message))

    def get_callbacks(self):
        return {
            "before_agent_callback": self.before_agent,
            "after_agent_callback": self.after_agent,
            "before_model_callback": self.before_model,
            "after_model_callback": self.after_model,
            "before_tool_callback": self.before_tool,
            "after_tool_callback": self.after_tool,
        }

    async def before_agent(self, callback_context: CallbackContext):
        await before_agent(callback_context)
        self.append_message(f'{callback_context.agent_name} 智能体启动')

    async def after_agent(self, callback_context: CallbackContext):
        await after_agent(callback_context)
        self.append_message(f'{callback_context.agent_name} 智能体完成')

    async def before_model(self, callback_context: CallbackContext, llm_request):
        await before_model(callback_context, llm_request)
        self.append_message(f'{callback_context.agent_name} 开始调用大模型')

    async def after_model(self, callback_context: CallbackContext, llm_response: LlmResponse):
        await after_model(callback_context, llm_response)
        self.append_message(f'{callback_context.agent_name} 完成调用大模型')

    async def before_tool(self, tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext):
        await before_tool(tool, args, tool_context)
        if tool.name == 'transfer_to_agent':
            agent_name = args['agent_name']
            self.append_message(f'{tool_context.agent_name} 调用 {agent_name}')
        else:
            self.append_message(f'{tool_context.agent_name} 开始调用工具 {tool.name}, 参数: {args}')

    async def after_tool(self, tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: dict):
        await after_tool(tool, args, tool_context, tool_response)
        if tool.name == 'transfer_to_agent':
            pass
        else:
            self.append_message(f'{tool_context.agent_name} 结束调用工具 {tool.name}, 返回值: {tool_response}')
    
    async def on_event(self, session:Session, event: Event):
        await on_event(session, event)
        
    async def _find_and_add_images(self, content, updater):
        async def traverse(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, str):
                        try:
                            # 尝试解析 JSON 字符串
                            v = json.loads(v)
                        except json.JSONDecodeError:
                            pass
                        if isinstance(v, (dict, list)):
                            await traverse(v)
                        elif isinstance(v, str) and os.path.isfile(v) and os.path.splitext(v)[1] in ('.png', '.jpg', '.jpeg'):
                            logger.info('file: %s', v)
                            try:
                                with open(v, 'rb') as f:
                                    file_content = f.read()
                                bs = base64.b64encode(file_content)
                                image = FilePart(type="file", 
                                    file=FileWithBytes(
                                        mimeType=f"image/{os.path.splitext(v)[1][1:]}",
                                        bytes=bs,
                                        name=os.path.basename(v),
                                    ), 
                                    metadata=None
                                )
                                await updater.add_artifact(
                                    parts=[image.model_dump()], name=k
                                )
                            except Exception as e:
                                logger.error('Failed to read image file %s: %s', v, e)
                    else:
                        await traverse(v)
            elif isinstance(obj, list):
                for item in obj:
                    await traverse(item)

        if 'response' in content:
            response = content['response']
            await traverse(response)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        query = context.get_user_input()
        task = context.current_task

        # This agent always produces Task objects. If this request does
        # not have current task, create a new one and use it.
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.contextId)
        # invoke the underlying agent, using streaming results. The streams
        # now are update events.
        async for item in self.orchestrator.stream(query, task.contextId):
            # 先把 callback 记录的消息返回
            contents = list(self._messages)
            self._messages.clear()
            for timestamp, content in contents:
                await updater.event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        taskId=task.id,
                        contextId=task.contextId,
                        final=False,
                        status=TaskStatus(
                            state=TaskState.working,
                            message=Message(
                                role=Role.agent,
                                parts=[Part(root=TextPart(text=content))],
                                messageId=str(uuid.uuid4()),
                                taskId=task.id,
                                contextId=task.contextId,
                            ),
                            timestamp=timestamp.isoformat(),
                        ),
                    )
                )

            is_task_complete = item['is_task_complete']
            artifacts = None
            if not is_task_complete:
                # await updater.update_status(
                #     TaskState.working,
                #     new_agent_text_message(
                #         str(item['content']), task.contextId, task.id
                #     ),
                # )
                await self._find_and_add_images(item['content'], updater)
                continue
            # If the response is a dictionary, assume its a form
            if isinstance(item['content'], dict):
                # Verify it is a valid form
                if (
                    'response' in item['content']
                    and 'result' in item['content']['response']
                ):
                    data = json.loads(item['content']['response']['result'])
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_parts_message(
                            [Part(root=DataPart(data=data))],
                            task.contextId,
                            task.id,
                        ),
                        final=True,
                    )
                    continue
                else:
                    await updater.update_status(
                        TaskState.failed,
                        new_agent_text_message(
                            'Reaching an unexpected state',
                            task.contextId,
                            task.id,
                        ),
                        final=True,
                    )
                    break
            else:
                # Emit the appropriate events
                await updater.add_artifact(
                    [Part(root=TextPart(text=item['content']))], name='form'
                )
                await updater.complete()
                break

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())

_executor: OrchestratorAgentExecutor|None = None

def build_orchestrator_executor(cfg) -> OrchestratorAgentExecutor:
    global _executor
    if _executor is None:
        _executor = OrchestratorAgentExecutor(cfg)
        return _executor
    else:
        return _executor

async def _before_agent(callback_context: CallbackContext):
    await before_agent(callback_context)
    if _executor is not None:
        await _executor.before_agent(callback_context)

async def _after_agent(callback_context: CallbackContext):
    await after_agent(callback_context)
    if _executor is not None:
        await _executor.after_agent(callback_context)

async def _before_model(callback_context: CallbackContext, llm_request):
    await before_model(callback_context, llm_request)
    if _executor is not None:
        await _executor.before_model(callback_context, llm_request)

async def _after_model(callback_context: CallbackContext, llm_response: LlmResponse):
    await after_model(callback_context, llm_response)
    if _executor is not None:
        await _executor.after_model(callback_context, llm_response)

async def _before_tool(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext):
    await before_tool(tool, args, tool_context)
    if _executor is not None:
        await _executor.before_tool(tool, args, tool_context)

async def _after_tool(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: dict):
    await after_tool(tool, args, tool_context, tool_response)
    if _executor is not None:
        await _executor.after_tool(tool, args, tool_context, tool_response)

async def _on_event(session:Session, event: Event):
    await on_event(session, event)
    if _executor is not None:
        await _executor.on_event(session, event)

# hydra 只支持可以序列化的数据
def build_callbacks():
    return {
        "before_agent_callback": _before_agent,
        "after_agent_callback": _after_agent,
        "before_model_callback": _before_model,
        "after_model_callback": _after_model,
        "before_tool_callback": _before_tool,
        "after_tool_callback": _after_tool,
    }
