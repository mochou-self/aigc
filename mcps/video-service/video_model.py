"""
此模块实现了 Doubao 的 Doubao-Seedance-1.0-lite-i2v 模型类，用于调用火山引擎 API 进行图生视频操作。

目录结构说明：
- {data_dir}
  - {session_id}          # 每个任务以 session_id 为目录名
    - toutiao.html        # 头条的 HTML 文件
    - news_content.md     # 新闻正文的 Markdown 文件
    - shot_info.json      # 分镜的 JSON 文件
    - {shot_index}        # 每个镜头以镜头索引为目录名，6 位对齐，如 000001
      - image.md          # 镜头对应的图片描述 Markdown 文件
      - video.md          # 镜头对应的视频描述 Markdown 文件
      - image.jpg         # 镜头对应的图片文件
      - {shot_index}.mp4  # 镜头对应的视频文件，6 位对齐，如 000001.mp4
"""
import os
import httpx
import base64
import logging
from typing import Optional
from conf.common_config import config

# API 常量
API_URL = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"

class VideoModel:
    """
    模拟 Doubao 的 Doubao-Seedance-1.0-lite-i2v 模型类，用于调用火山引擎 API 进行图生视频操作。
    """
    def __init__(self, model_name: str, api_key: str):
        """
        初始化模型实例

        :param model_name: 模型名称
        :param api_key: 火山引擎 API 密钥
        """
        self.model_name = model_name
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    # 图像转视频
    async def image_to_video(
        self,
        session_id: str,
        shot_index: int,
        output_format: str = "mp4",
        fps: int = 24,
        resolution: str = "720p",
        ratio: str = "adaptive",
        duration: int = 5,
        watermark: bool = False,
        seed: int = -1,
        camera_fixed: bool = False,
        text_prompt: Optional[str] = None
    ) -> str:
        """
        根据输入的图像生成视频，调用火山引擎 API
        :param session_id: 任务的会话 ID
        :param shot_index: 镜头索引
        :param output_format: 生成视频的格式，默认为 mp4
        :param fps: 视频帧率，默认为 24
        :param resolution: 视频分辨率，默认为 720p
        :param ratio: 视频宽高比，默认为 adaptive
        :param duration: 生成视频时长，单位秒，默认为 5
        :param watermark: 是否添加水印，默认为 False
        :param seed: 随机数种子，默认为 -1
        :param camera_fixed: 是否固定摄像头，默认为 False
        :param text_prompt: 文本提示词，默认为 None
        :return: 生成视频的文件路径
        """
        # 构建任务和镜头目录
        shot_dir = config.get_shot_dir(session_id, shot_index)
        video_path = os.path.join(shot_dir, f'{shot_index:06d}.{output_format}')
        image_path = os.path.join(shot_dir, f'{shot_index:06d}.jpg')
        logging.info(f"Begin image_path:{image_path}, video_path:{video_path}")
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # 转换图片路径为 base64 数据 URL
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
            image_url = f"data:image/png;base64,{image_data}"

        # 构建请求参数
        parameters = f"--rs {resolution} --rt {ratio} --dur {duration} --fps {fps} --wm {str(watermark).lower()} --seed {seed} --cf {str(camera_fixed).lower()}"
        if text_prompt:
            text_content = f"{text_prompt} {parameters}".strip()
        else:
            text_content = parameters.strip()

        payload = {
            "model": self.model_name,
            "content": [
                {
                    "type": "text",
                    "text": text_content
                },
                {
                    "type": "image_url",
                    "image_url": {"url": image_url}
                }
            ]
        }

        # 调用火山引擎 API 创建任务
        async with httpx.AsyncClient() as client:
            response = await client.post(API_URL, headers=self.headers, json=payload)
            response.raise_for_status()
            task_data = response.json()
            task_id = task_data.get("task_id")
            logging.info(f"任务已创建，任务 ID: {task_id}")

            # 轮询任务状态
            video_url = await self._poll_task_status(client, task_id)

        # 下载视频
        await self._download_video(video_url, video_path)
        logging.info(f"视频已下载到 {video_path}")

        return video_path

    async def _poll_task_status(self, client: httpx.AsyncClient, task_id: str) -> str:
        """
        轮询任务状态，直到任务完成或失败

        :param client: httpx 异步客户端
        :param task_id: 任务 ID
        :return: 视频 URL
        """
        retry_interval = 5  # 初始重试间隔（秒）
        while True:
            # https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{id}
            response = await client.get(f"{API_URL}/{task_id}", headers=self.headers)
            response.raise_for_status()
            task_data = response.json()
            status = task_data.get("status")

            if status == "succeeded":
                """
                    //状态为succeeded时：
                    {
                    "id": "cgt-2025******-****",
                    "model": "doubao-seedance-1-0-lite-t2v-250428",
                    "status": "succeeded",
                    "content": {
                        "video_url": "https://ark-content-generation-cn-beijing.tos-cn-beijing.volces.com/****"
                    },
                    "usage": {
                        "completion_tokens": 108900,
                        "total_tokens": 108900
                    },
                    "created_at": 1743414619,
                    "updated_at": 1743414673
                    }
                """
                logging.info(f"任务 {task_id} 已成功完成")
                video_url = task_data.get("result", {}).get("video_url")
                if not video_url:
                    raise ValueError(f"任务 {task_id} 完成但未返回视频 URL")
                return video_url
            elif status == "queued":
                """
                    // 状态为queued时：
                    {
                        "id": "cgt-2025******-****",
                        "model": "doubao-seedance-1-0-lite-t2v-250428",
                        "status": "queued",
                        "created_at": 1745899232,
                        "updated_at": 1745899232
                    }
                """
                created_at = task_data.get("created_at", -1)
                updated_at = task_data.get("updated_at", -1)
                await asyncio.sleep(retry_interval)
                logging.info(f"任务 {task_id} 已等待 {updated_at - created_at} 秒, updated_at:{updated_at}, created_at:{created_at}")
            elif status == "running":
                """
                //状态为running时：
                {
                    "id": "cgt-2025******-****",
                    "model": "doubao-seedance-1-0-lite-t2v-250428",
                    "status": "running",
                    "created_at": 1745910851,
                    "updated_at": 1745910851
                }
                """
                created_at = task_data.get("created_at", -1)
                updated_at = task_data.get("updated_at", -1)
                logging.info(f"任务 {task_id} 生成中 {updated_at - created_at} 秒, updated_at:{updated_at}, created_at:{created_at}")
                await asyncio.sleep(retry_interval)
            else:
                logging.error(f"任务 {task_id} 未知状态: {status}")
                raise

    # 下载视频到指定路径
    async def _download_video(self, video_url: str, save_path: str) -> None:
        """
        下载视频到指定路径
        :param video_url: 视频 URL
        :param save_path: 保存路径
        """
        async with httpx.AsyncClient() as client:
            logging.info(f"开始下载视频: {video_url}")
            response = await client.get(video_url)
            response.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(response.content)