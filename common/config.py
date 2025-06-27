import os

class Config:
    def __init__(self):
        # git 中的目录
        script_path = os.path.abspath(__file__)
        common_dir = os.path.dirname(script_path)

        # 代码根目录
        self.core_dir = os.path.dirname(common_dir)

        #　git 根目录，对应 robot
        self.project_dir = os.path.dirname(self.core_dir)

        # 关键数据记录的位置
        self.with_record = True
        self.record_dir = os.path.join(self.project_dir, '.record')
        os.makedirs(self.record_dir, exist_ok=True)

        # 数据库
        self.db_dir = os.path.join(self.project_dir, '.db')
        os.makedirs(self.db_dir, exist_ok=True)
        self.dialogue_history_db = f"sqlite+aiosqlite:///{self.db_dir}/dialogue_history.db"

        # 模型
        # Ryan 提供的代理
        self.model = 'openai/claude-3'
        self.api_key = 'ipanel'
        self.base_url = 'http://192.168.101.8:8100'

        # 本地大模型
        self.ollama_base_url = 'http://192.168.101.131:11434'
        self.ollama_model = 'ollama_chat/MFDoom/deepseek-r1-tool-calling:latest'
        self.ollama_api_key = 'local'

        # mcp monitor server
        self.monitor_control_agent_mcp_server_host = '192.168.64.199' # 更新到adk1.0.0之后，windows下的linux子系统访问mcp必须指定windwos的局域网ip才能访问，不能用localhost。
        self.monitor_control_agent_mcp_server_port = 8996
        # health_check_server
        self.health_check_server_port = 8989
        # ocr_server
        self.ocr_server_port = 8990
        # monitor control mcp server
        self.monitor_control_server_port = 8996

        # playwright
        self.playwright_port = 10010
        
        # context_agent依赖embedding模型
        self.embed_model    = 'bge-large-zh'
        self.embed_base_url = 'http://192.168.101.131:9997/v1'

config = Config()
