# agents

- 智能体总目录
- 每个智能体占一个目录

## 单个智能体的文件结构

- agent.py 这个是必须有的
    - 需要实现 async def build_agent() -> Agent
    - 由 orchestrator 统一调用
    - 带上统一的 callbacks
- prompt.py
    - 建议提示词独立文件
    - 由 agent.py 引用
- tools.py
    - 可选

## 增加智能体的步骤

1. 在 core/agents 目录下创建一个目录，目录名就是智能体的名字
2. 在目录下创建 agent.py 文件，实现 async def build_agent() -> Agent
3. 在目录下创建 prompt.py 文件，实现提示词
4. 修改 `core/agents/__init__.py` 中 build_sub_agents 函数，添加对应的 agent