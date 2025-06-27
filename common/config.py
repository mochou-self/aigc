"""
此模块定义了项目的配置类，包含数据库、服务端口和数据存储路径等配置。
"""
import os

class Config:
    def __init__(self):
        # 代码根目录
        script_path = os.path.abspath(__file__)
        conf_dir = os.path.dirname(script_path)
        self.project_dir = os.path.dirname(conf_dir)

        # 数据库配置
        self.db_dir = os.path.join(self.project_dir, '.db')
        os.makedirs(self.db_dir, exist_ok=True)
        self.db_url = "sqlite+aiosqlite:///{}/news.db".format(self.db_dir)

        # 服务端口配置
        self.db_service_port = 8001
        self.news_service_port = 8004
        self.image_service_port = 8002
        self.video_service_port = 8003

        # 数据存储目录配置
        self.data_dir = os.path.join(self.project_dir, 'data')
        os.makedirs(self.data_dir, exist_ok=True)

    def get_session_dir(self, session_id: str) -> str:
        """
        获取指定 session id 的数据目录路径，如果不存在则创建

        :param session_id: 会话 ID
        :return: 会话数据目录的绝对路径
        """
        session_dir = os.path.join(self.data_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)
        return session_dir

    def get_shot_dir(self, session_id: str, shot_index: int) -> str:
        """
        获取指定 session id 和镜头索引的镜头目录路径，如果不存在则创建

        :param session_id: 会话 ID
        :param shot_index: 镜头索引
        :return: 镜头数据目录的绝对路径
        """
        session_dir = self.get_session_dir(session_id)
        shot_dir = os.path.join(session_dir, f'{shot_index:06d}')
        os.makedirs(shot_dir, exist_ok=True)
        return shot_dir

config = Config()