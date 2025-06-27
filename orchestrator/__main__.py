import logging
import os
import traceback

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from dotenv import load_dotenv

import hydra
from hydra.utils import instantiate

from orchestrator_executor import OrchestratorAgentExecutor, build_orchestrator_executor
from orchestrator import Orchestrator

load_dotenv()

logger = logging.getLogger('orchestrator')
class MissingAPIKeyError(Exception):
    """Exception for missing API key."""

    pass

@hydra.main(version_base=None, config_path="../conf", config_name="orchestrator")
def main(cfg):
    try:
        logger.info("cfg: %s %s", type(cfg), cfg)
        host = cfg.a2a.orchestrator.host
        port = cfg.a2a.orchestrator.port
        capabilities = AgentCapabilities(streaming=True)
        skill = AgentSkill(
            id="orchestrator",
            name="orchestrator",
            description="智能体协调员，负责协调多个智能体完成复杂任务，是值班机器人对外的总接口。",
            tags=["orchestrator"],
            examples=["开机","关机","1号机组当前状态是否正常？"],
        )
        agent_card = AgentCard(
            name="orchestrator",
            description="智能体协调员，负责协调多个智能体完成复杂任务，是值班机器人对外的总接口。",
            url=f"http://{host.connect_to}:{port}/",
            version="1.0.0",
            defaultInputModes=Orchestrator.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=Orchestrator.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        obj = instantiate(cfg.orchestrator)
        logger.info("obj: ", obj)
        request_handler = DefaultRequestHandler(
            agent_executor=build_orchestrator_executor(obj),
            task_store=InMemoryTaskStore(),
        )
        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )
        import uvicorn

        uvicorn.run(server.build(), host=host.listen_on, port=port, log_config=None)
    except MissingAPIKeyError as e:
        logger.error(f"Error: {e}")
        logger.error("traceback: %s", traceback.format_exc())
        exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        logger.error("traceback: %s", traceback.format_exc())
        exit(1)
    
if __name__ == "__main__":
    main()

