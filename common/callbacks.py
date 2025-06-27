from typing import List, Dict, Optional, Any
from datetime import datetime
import logging
from pydantic import BaseModel

from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from google.adk.models import LlmRequest
from google.adk.models import LlmResponse
from google.adk.tools import BaseTool
from google.adk.sessions import Session
from google.adk.events import Event

from common.recorder import recorder
from common.dialogue_history import DialogueHistory, DialogueRecord
from common.config import config
from common.utils import to_dict

logger = logging.getLogger('callback')

_dialogue_history: DialogueHistory | None = None

async def initialize_callbacks() -> DialogueHistory:
    global _dialogue_history
    if _dialogue_history is None:
        _dialogue_history = DialogueHistory(config.dialogue_history_db)
        await _dialogue_history.open()
    return _dialogue_history

async def finalize_callbacks():
    global _dialogue_history
    if _dialogue_history is not None:
        await _dialogue_history.close()
        _dialogue_history = None

async def before_agent(callback_context: CallbackContext):
    ctx = callback_context
    logger.info("before_agent: %s, %s", ctx.invocation_id, ctx.agent_name)
    state_dict = ctx.state.to_dict()
    recorder.save_json(f"{ctx.invocation_id[-6:]}.BA.{ctx.agent_name}.state.json", state_dict)
    if _dialogue_history is not None:
        await _dialogue_history.append(DialogueRecord(
            timestamp=datetime.now(),
            user_id=ctx._invocation_context.session.user_id,
            session_id=ctx._invocation_context.session.id,
            app_name=ctx._invocation_context.session.app_name,
            invocation_id=ctx.invocation_id,
            agent_name=ctx.agent_name,
            tag='before_agent',
            name='state',
            data=state_dict,
        ))

async def after_agent(callback_context: CallbackContext):
    ctx = callback_context
    logger.info("after_agent: %s, %s", ctx.invocation_id, ctx.agent_name)
    state_dict = ctx.state.to_dict()
    recorder.save_json(f"{ctx.invocation_id[-6:]}.AA.{ctx.agent_name}.state.json", state_dict)
    if _dialogue_history is not None:
        await _dialogue_history.append(DialogueRecord(
            timestamp=datetime.now(),
            user_id=ctx._invocation_context.session.user_id,
            session_id=ctx._invocation_context.session.id,
            app_name=ctx._invocation_context.session.app_name,
            invocation_id=ctx.invocation_id,
            agent_name=ctx.agent_name,
            tag='after_agent',
            name='state',
            data=state_dict,
        ))

async def before_model(callback_context: CallbackContext, llm_request: LlmRequest):
    ctx = callback_context
    logger.info("before_model: %s, %s", ctx.invocation_id, ctx.agent_name)
    state_dict = ctx.state.to_dict()
    recorder.save_json(f"{ctx.invocation_id[-6:]}.BM.{ctx.agent_name}.state.json", state_dict)
    if _dialogue_history is not None:
        await _dialogue_history.append(DialogueRecord(
            timestamp=datetime.now(),
            user_id=ctx._invocation_context.session.user_id,
            session_id=ctx._invocation_context.session.id,
            app_name=ctx._invocation_context.session.app_name,
            invocation_id=ctx.invocation_id,
            agent_name=ctx.agent_name,
            tag='before_model',
            name='state',
            data=state_dict,
        ))
    request_dict = llm_request.model_dump(exclude_none=True)
    # if 'llm_request' not in ctx.state:
    #     ctx.state['llm_request'] = []
    # ctx.state['llm_request'].append(request_dict)
    recorder.save_json(f"{ctx.invocation_id[-6:]}.BM.{ctx.agent_name}.request.0.json", request_dict, escape=False)
    recorder.save_json(f"{ctx.invocation_id[-6:]}.BM.{ctx.agent_name}.request.1.json", request_dict, escape=True)
    if _dialogue_history is not None:
        await _dialogue_history.append(DialogueRecord(
            timestamp=datetime.now(),
            user_id=ctx._invocation_context.session.user_id,
            session_id=ctx._invocation_context.session.id,
            app_name=ctx._invocation_context.session.app_name,
            invocation_id=ctx.invocation_id,
            agent_name=ctx.agent_name,
            tag='before_model',
            name='llm_request',
            data=request_dict,
        ))

async def after_model(callback_context: CallbackContext, llm_response: LlmResponse):
    ctx = callback_context
    logger.info("after_model: %s, %s", ctx.invocation_id, ctx.agent_name)
    state_dict = ctx.state.to_dict()
    recorder.save_json(f"{ctx.invocation_id[-6:]}.AM.{ctx.agent_name}.state.json", state_dict)
    if _dialogue_history is not None:
        await _dialogue_history.append(DialogueRecord(
            timestamp=datetime.now(),
            user_id=ctx._invocation_context.session.user_id,
            session_id=ctx._invocation_context.session.id,
            app_name=ctx._invocation_context.session.app_name,
            invocation_id=ctx.invocation_id,
            agent_name=ctx.agent_name,
            tag='after_model',
            name='state',
            data=state_dict,
        ))
    response_dict = llm_response.model_dump(exclude_none=True)
    # if 'llm_response' not in ctx.state:
    #     ctx.state['llm_response'] = []
    # ctx.state['llm_response'].append(response_dict)
    recorder.save_json(f"{ctx.invocation_id[-6:]}.AM.{ctx.agent_name}.response.0.json", response_dict, escape=False)
    recorder.save_json(f"{ctx.invocation_id[-6:]}.AM.{ctx.agent_name}.response.1.json", response_dict, escape=True)
    if _dialogue_history is not None:
        await _dialogue_history.append(DialogueRecord(
            timestamp=datetime.now(),
            user_id=ctx._invocation_context.session.user_id,
            session_id=ctx._invocation_context.session.id,
            app_name=ctx._invocation_context.session.app_name,
            invocation_id=ctx.invocation_id,
            agent_name=ctx.agent_name,
            tag='after_model',
            name='llm_response',
            data=response_dict,
        ))

async def before_tool(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext):
    ctx = tool_context
    logger.info("before_tool: %s, %s, %s", ctx.invocation_id, ctx.agent_name, tool.name)
    logger.info("before_tool: %s", args)
    recorder.save_json(f"{ctx.invocation_id[-6:]}.BT.{ctx.agent_name}.{tool.name}.args.json", args)
    if _dialogue_history is not None:
        await _dialogue_history.append(DialogueRecord(
            timestamp=datetime.now(),
            user_id=ctx._invocation_context.session.user_id,
            session_id=ctx._invocation_context.session.id,
            app_name=ctx._invocation_context.session.app_name,
            invocation_id=ctx.invocation_id,
            agent_name=ctx.agent_name,
            tag='before_tool',
            name=tool.name,
            data=args,
        ))

async def after_tool(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: dict):
    ctx = tool_context
    logger.info("after_tool: %s, %s, %s", ctx.invocation_id, ctx.agent_name, tool.name)
    logger.info("after_tool: %s", tool_response)
    tool_response = to_dict(tool_response)
    recorder.save_json(f"{ctx.invocation_id[-6:]}.AT.{ctx.agent_name}.{tool.name}.response.json", tool_response)
    if _dialogue_history is not None:
        await _dialogue_history.append(DialogueRecord(
            timestamp=datetime.now(),
            user_id=ctx._invocation_context.session.user_id,
            session_id=ctx._invocation_context.session.id,
            app_name=ctx._invocation_context.session.app_name,
            invocation_id=ctx.invocation_id,
            agent_name=ctx.agent_name,
            tag='after_tool',
            name=tool.name,
            data=tool_response,
        ))

async def on_event(session:Session, event: Event):
    logger.info('event: %s', event)
    recorder.save_json(f"{event.invocation_id[-6:]}.E.{event.author}.json", event.model_dump(exclude_none=True))
    if _dialogue_history is not None:
        await _dialogue_history.append(DialogueRecord(
            timestamp=datetime.now(),
            user_id=session.user_id,
            session_id=session.id,
            app_name=session.app_name,
            invocation_id=event.invocation_id,
            agent_name=event.author,
            tag='event',
            name='event',
            data=event.model_dump(exclude_none=True),
        ))

def build_callbacks():
    return {
        "before_agent_callback": before_agent,
        "after_agent_callback": after_agent,
        "before_model_callback": before_model,
        "after_model_callback": after_model,
        "before_tool_callback": before_tool,
        "after_tool_callback": after_tool,
    }
