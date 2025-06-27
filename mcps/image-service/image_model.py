"""
此模块使用 Doubao 的模型，根据输入的文本描述生成对应的静态图像。
目录结构说明：
- {data_dir}
  - {session_id}          # 每个任务以 session_id 为目录名
    - toutiao.html        # 头条的 HTML 文件
    - news_content.md     # 新闻正文的 Markdown 文件
    - shot_info.json      # 分镜的 JSON 文件
    - {shot_index}        # 每个镜头以镜头索引为目录名，6 位对齐，如 000001
      - image.md          # 镜头对应的图片描述 Markdown 文件
      - video.md          # 镜头对应的视频描述 Markdown 文件
      - {shot_index}.jpg  # 镜头对应的图片文件，6 位对齐，如 000001.jpg
      - {shot_index}.mp4  # 镜头对应的视频文件，6 位对齐，如 000001.mp4
"""

import os
import httpx
from fastapi import HTTPException
from conf.common_config import config

# API 常量
API_URL = 'https://ark.cn-beijing.volces.com/api/v3/images/generations'


class ImageModel:
    """
    调用 Doubao 模型生成图像的类。
    """
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def generate_image(
        self,
        session_id: str,
        shot_index: int,
        text: str,
        response_format: str = 'url',
        size: str = '1024x1024',
        seed: int = -1,
        guidance_scale: float = 2.5,
        watermark: bool = True
    ) -> str:
        """
        根据文本描述调用火山引擎 API 生成图像。
        :param session_id: 任务的会话 ID
        :param shot_index: 镜头索引
        :param text: 图像的文本描述。
        :param response_format: 生成图像的返回格式，可选 'url' 或 'b64_json'。
        :param size: 生成图像的宽高像素，要求介于 [512 x 512, 2048 x 2048] 之间。
        :param seed: 随机数种子，取值范围为 [-1, 2147483647]。
        :param guidance_scale: 模型输出与提示词的一致程度，取值范围 [1, 10]。
        :param watermark: 是否添加水印。
        :return: 生成图像的本地文件路径。
        """

        # 构建任务和镜头目录
        shot_dir = config.get_shot_dir(session_id, shot_index)
        image_path = os.path.join(shot_dir, f'{shot_index:06d}.jpg')
        logging.info(f"Begin image_path:{image_path}")

        payload = {
            'model': self.model_name,
            'prompt': text,
            'response_format': response_format,
            'size': size,
            'seed': seed,
            'guidance_scale': guidance_scale,
            'watermark': watermark
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(API_URL, headers=self.headers, json=payload)
                response.raise_for_status()
                result = response.json()

                if 'data' in result and result['data']:
                    if response_format == 'url':
                        image_url = result['data'][0]['url']
                        # 下载图像
                        image_response = await client.get(image_url)
                        image_response.raise_for_status()
                        with open(image_path, 'wb') as f:
                            f.write(image_response.content)
                        return image_path
                    else:
                        raise ValueError("当前仅支持 'url' 格式的返回值")
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"图像生成失败: {result.get('error', {}).get('message', '未知错误')}"
                    )
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"API 请求失败: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"图像生成过程中出错: {str(e)}")