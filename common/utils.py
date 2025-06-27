import os
import sys
import asyncio
import logging
from typing import Tuple
import yaml
import time
import datetime
import cv2
import numpy as np
import json

# 用于 Windows 系统
try:
    import msvcrt
except Exception as e:
    pass

# 用于 Unix/Linux 系统
try:
    import termios
    import tty
except Exception as e:
    pass

logger = logging.getLogger('utils')


async def get_user_input(prompt:str="请输入内容: ") -> str:
    '''获取用户输入'''
    loop = asyncio.get_running_loop()
    try:
        user_input = await loop.run_in_executor(None, input, prompt)
        return user_input
    except EOFError:
        print("输入结束。")
        return ""

async def get_key(prompt:str):
    '''获取用户按键'''
    logger.info('prompt: %s', prompt)
    loop = asyncio.get_running_loop()
    if sys.platform.startswith('win'):
        # Windows 系统
        key = await loop.run_in_executor(None, msvcrt.getch)
        try:
            key = key.decode()
        except Exception as e:
            logger.info('decode failed: %s', key)
            key = ''
        return key
    else:
        # Unix/Linux 系统
        def get_char():
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch
        return await loop.run_in_executor(None, get_char)

def str_to_bool(s:str) -> bool:
    s = str(s).strip().lower()
    if s in ('true', 'yes', '1', 'y'):
        return True
    elif s in ('false', 'no', '0', 'n'):
        return False
    return False

class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)

def save_json(filename, obj, encoding='utf-8', indent=2, escape=False):
    logger.info('save to: %s', filename)
    with open(filename, 'wb') as f:
        json_content = json.dumps(obj, ensure_ascii=False, indent=indent, cls=SetEncoder)
        if escape: # 提示词一般都是较长的换行文本
            json_content = json_content.replace('\\n', '\n')
        json_content = json_content.encode(encoding)
        f.write(json_content)

def load_json(filename, encoding='utf-8'): 
    # logger.info('load from: %s', filename)
    if not os.path.isfile(filename):
        raise FileNotFoundError(f'load json, file not found: {filename}')
    with open(filename, 'rb') as f:
        json_content = f.read().decode(encoding)
        obj = json.loads(json_content)
    return obj

def dump_json(data):
    return json.dumps(data, indent=2, ensure_ascii=False)

def save_yaml(filename, obj, encoding='utf-8'):
    logger.info('save to: %s', filename)
    with open(filename, 'wb') as f:
        yaml_content = yaml.dump(obj, allow_unicode=True).encode(encoding)
        f.write(yaml_content)

def load_yaml(filename, encoding='utf-8'):
    if not os.path.isfile(filename):
        raise FileNotFoundError(f'load yaml, file not found: {filename}')
    with open(filename, 'rb') as f:
        yaml_content = f.read().decode(encoding)
        obj = yaml.safe_load(yaml_content)
    return obj

def dump_yaml(data):
    return yaml.dump(data, allow_unicode=True)

def save_text(filename, content, encoding='utf-8'):
    logger.info('save to: %s', filename)
    with open(filename, 'wb') as f:
        text_content = content.encode(encoding)
        f.write(text_content)

def load_text(filename, encoding='utf-8'):
    if not os.path.isfile(filename):
        raise FileNotFoundError(f'load text, file not found: {filename}')
    with open(filename, 'rb') as f:
        text_content = f.read().decode(encoding)
    return text_content
    
_begin = None
def time_ms():
    '''获取当前时间，单位为毫秒'''
    global _begin
    if _begin is None:
        _begin = time.time()
    return int((time.time() - _begin) * 1000)

def check_dir(d):
    '''确保文件夹存在'''
    if d == '':
        return
    if not os.path.isdir(d):
        os.makedirs(d)
    return

def check_file_dir(file):
    '''确保文件所在的文件夹存在'''
    d = os.path.dirname(file)
    check_dir(d)

def to_dict(obj):
    if hasattr(obj, 'model_dump'):
        return obj.model_dump(exclude_none=True)
    elif isinstance(obj, dict):
        return {key: to_dict(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [to_dict(item) for item in obj]
    return obj

def fix_arguments_json(obj):
    '''openai 会把 arguments 转换为字符串，
    这里把它转换为 json 对象
    不影响实际交互的 messages，只是为了保存方便查看
    直接修改 obj，返回的也是obj
    '''
    if isinstance(obj, list):
        for item in obj:
            fix_arguments_json(item)
    elif isinstance(obj, dict):
        if 'tool_calls' in obj and obj['tool_calls'] is not None:
            for tc in obj['tool_calls']:
                if 'function' in tc and tc['function'] is not None:
                    if 'arguments' in tc['function'] and tc['function']['arguments'] is not None:
                        tc['function']['arguments'] = json.loads(tc['function']['arguments'])
        for key, value in obj.items():
            fix_arguments_json(value)
    return obj

def stime():
    """
    获取当前时间并格式化为"时:分:秒.毫秒"的字符串
    
    返回:
        str: 格式化后的时间字符串，例如"17:03:11.123"
    """
    now = datetime.datetime.now()
    # return now.strftime("%M:%S.%f")[:-3]
    return now.strftime("%M:%S")