import logging
from typing import List,Tuple,Optional
import importlib
from contextlib import AsyncExitStack
from google.adk import Agent

logger = logging.getLogger('agent')

async def build_sub_agents(cfg) -> List:
    logger.info('cfg: %s %s', type(cfg), cfg)
    package_name = __name__.rsplit('.', 1)[0]
    agents = []
    for name, agent_config in cfg.agents.items():
        logger.info('agent: name=%s, config=%s', name, agent_config)
        module = importlib.import_module(f".{name}_agent.agent", package=package_name)
        func_name = 'build_agent'
        assert hasattr(module, func_name), f"{module} from .{name}.agent does not have {func_name}"
        func = getattr(module, func_name)
        agent = await func(agent_config)
        agents.append(agent)
    return agents
    
