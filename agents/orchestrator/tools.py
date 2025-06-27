from typing import List

# 下面两个例子仅用于验证 orchestrator 可以同时带 tools 和 sub agents
# 实际运行时可以屏蔽掉
def get_generator_list() -> List[str]:
    """获取发电机机组列表"""
    return {
      "generator_list": ["1G", "2G", "3G"]
    }

def get_generator_info(generator_id: str) -> str:
    """获取发电机机组信息"""
    return {
      "generator_id": generator_id,
      "generator_info": f"Task {generator_id} info",
    }
