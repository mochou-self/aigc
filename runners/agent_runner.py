import importlib
import inspect
import logging
import asyncio

from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types # For creating message Content/Parts
from google.adk.agents import BaseAgent
from google.adk.tools.base_toolset import BaseToolset
from google.adk.agents.llm_agent import LlmAgent

from common.callbacks import on_event

logger = logging.getLogger('runner')

class AgentRunner:
    def __init__(self, args):
        logger.info("Initializing AgentRunner, args=%s", args)
        self.args = args
        self.agent = None
        self.session = None
        self.runner = None

        # Define constants for identifying the interaction context
        self.APP_NAME = "test_agent_app"
        self.USER_ID = "user_1"
        self.SESSION_ID = "session_001" # Using a fixed ID for simplicity

        self.exit_stacks = []
        self.interaction_record = []
        logger.info('AgentRunner init')

    async def run(self):
        logger.info('run args: %s', self.args)
        self.agent = await self._build_agent()
        await self._prepare_runner()

        turns = self.args.get("turns", [])
        
        for turn in turns:
            print("turn:", type(turn))
            query = turn.user
            assistant = turn.assistant if hasattr(turn, "assistant") else ""

            response = await self.call_agent_async(query)
            self.interaction_record.append({
                "query": turn.user,
                "response": response,
                "expected": assistant,
            })
            print("-"*50, "\n"*3)
            for d in self.interaction_record:
                print(f"Query: {d['query']}")
                print(f"Response: {d['response']}")
                print(f"Expected: {d['expected']}")
                print("-"*50)
            print("-"*50, "\n"*3)

        await self.session_service.delete_session(
            app_name=self.APP_NAME, user_id=self.USER_ID, session_id=self.SESSION_ID
        )
        logger.info("Closing MCP server connection...")
        for exit_stack in self.exit_stacks:
            # Crucial Cleanup: Ensure the MCP server process connection is closed.
            await exit_stack.aclose()
        self.exit_stacks.clear()
        logger.info("Cleanup complete.")

        # tool 安全关闭
        # 参考adk源码中的
        # src/google/adk/cli/fast_api.py
        # 先获取所有 toolsets
        def _get_all_toolsets(agent: BaseAgent) -> set[BaseToolset]:
            toolsets = set()
            if isinstance(agent, LlmAgent):
                for tool_union in agent.tools:
                    if isinstance(tool_union, BaseToolset):
                        toolsets.add(tool_union)
                for sub_agent in agent.sub_agents:
                    toolsets.update(_get_all_toolsets(sub_agent))
            return toolsets

        async def close_toolset_safely(toolset):
            """Safely close a toolset with error handling."""
            try:
                logger.info(f"Closing toolset: {type(toolset).__name__}")
                await toolset.close()
                logger.info(f"Successfully closed toolset: {type(toolset).__name__}")
            except Exception as e:
                logger.error(f"Error closing toolset {type(toolset).__name__}: {e}")

        toolsets = _get_all_toolsets(self.agent)
        for toolset in toolsets:
            await close_toolset_safely(toolset)
            task = asyncio.create_task(close_toolset_safely(toolset))
        
    async def _build_agent(self):
        agent = self.args.agent
        if type(agent) is str:
            part1, part2 = self.args.agent.rsplit(".", 1)
            module = importlib.import_module(part1)
            assert hasattr(module, part2), f"{module} from {part1} does not have {part2}"
            obj = getattr(module, part2)
            if callable(obj) or inspect.isclass(obj):
                agent = obj()
                logger.info('agent: %s', agent)
                return agent
            else:
                logger.info('obj: %s', obj)
                raise ValueError(f"invalid agent: {self.args.agent}")
        else:
            if inspect.iscoroutine(agent):
                logger.info('agent is coroutine')
                result = await agent
                if type(result) is tuple:
                    agent, exit_stack = result
                    if type(exit_stack) is list:
                        self.exit_stacks += exit_stack
                    else:
                        self.exit_stacks.append(exit_stack)
                else:
                    agent = result
            return agent

    async def _prepare_runner(self):
        # @title Setup Session Service and Runner

        # --- Session Management ---
        # Key Concept: SessionService stores conversation history & state.
        # InMemorySessionService is simple, non-persistent storage for this tutorial.
        self.session_service = InMemorySessionService()

        # Create the specific session where the conversation will happen
        session = await self.session_service.create_session(
            app_name=self.APP_NAME,
            user_id=self.USER_ID,
            session_id=self.SESSION_ID
        )
        logger.info(f"Session created: App='{self.APP_NAME}', User='{self.USER_ID}', Session='{self.SESSION_ID}'")

        # --- Runner ---
        # Key Concept: Runner orchestrates the agent execution loop.
        runner = Runner(
            agent=self.agent, # The agent we want to run
            app_name=self.APP_NAME,   # Associates runs with our app
            session_service=self.session_service # Uses our session manager
        )
        logger.info(f"Runner created for agent '{self.agent.name}'.")

        self.runner = runner
        self.session = session
    
    async def call_agent_async(self, query: str):
        """Sends a query to the agent and debugs the final response."""
        runner = self.runner
        user_id = self.session.user_id
        session_id = self.SESSION_ID

        logger.info(f">>> User Query: {query}")

        # Prepare the user's message in ADK format
        content = types.Content(role='user', parts=[types.Part(text=query)])

        final_response_text = "Agent did not produce a final response." # Default

        # Key Concept: run_async executes the agent logic and yields Events.
        # We iterate through events to find the final answer.
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            # You can uncomment the line below to see *all* events during execution
            # logger.info(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")
            await on_event(self.session, event)
            
            # Key Concept: is_final_response() marks the concluding message for the turn.
            if event.is_final_response():
                if event.content and event.content.parts:
                    # Assuming text response in the first part
                    final_response_text = event.content.parts[0].text
                elif event.actions and event.actions.escalate: # Handle potential errors/escalations
                    final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
                # Add more checks here if needed (e.g., specific error codes)
                
                # sub agents 模式下会有多次 final，这里不能中断
                # break # Stop processing events once the final response is found

        logger.info(f"<<< Agent Response: {final_response_text}")
        return final_response_text
        

