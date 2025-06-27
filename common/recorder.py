import os
import cv2
import datetime
from common.utils import (
    save_json,
    save_yaml,
    time_ms,
)
from common.config import config

class Recorder:
    def __init__(self):
        # 同一毫秒内的计数
        self.last_formatted_time = None
        self.idx = 0
        self.tags = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        self.max = len(self.tags)
        current_time = datetime.datetime.now()
        d = current_time.strftime('%Y-%m-%d')
        t = current_time.strftime('%H-%M-%S.%f')[:-3]
        self.root = os.path.join(config.record_dir, d, t)

    def set_name(self, name:str):
        '''设置目录名称
        server 与 agent 都用了这个模块
        '''
        current_time = datetime.datetime.now()
        d = current_time.strftime('%Y-%m-%d')
        t = current_time.strftime('%H-%M-%S.%f')[-3]
        if name != '':
            self.root = os.path.join(config.record_dir, d, t, name)
        else:
            self.root = os.path.join(config.record_dir, d, t)

    def get_formatted_time(self):
        '''获取当前时间'''
        current_time = datetime.datetime.now()
        # 按照指定格式将当前时间转换为字符串，增加三位毫秒
        formatted_time = current_time.strftime("%m%d-%H%M%S.%f")[:-3]
        return formatted_time

    def ensure_root_exist(self):
        '''确保目录存在'''
        if not os.path.exists(self.root):
            os.makedirs(self.root)

    def make_filename(self, filename:str):
        '''按统一格式生成记录文件名'''
        formatted_time = self.get_formatted_time()
        if self.last_formatted_time == formatted_time:
            self.idx += 1
            self.idx %= self.max
        else:
            self.idx = 0
            self.last_formatted_time = formatted_time
        tag = self.tags[self.idx]
        full_name = f'{formatted_time}.{tag}-{filename}'
        return os.path.join(self.root, full_name)

    def save_text(self, filename, text):
        '''保存文本'''
        if not config.with_record:
            return
        self.ensure_root_exist()
        with open(self.make_filename(filename), 'w', encoding='utf-8') as f:
            f.write(text)

    def save_image(self, filename, image):
        '''保存图片'''
        if not config.with_record:
            return
        self.ensure_root_exist()
        cv2.imwrite(self.make_filename(filename), image)

    def save_yaml(self, filename, data):
        '''保存yaml'''
        if not config.with_record:
            return
        self.ensure_root_exist()
        save_yaml(self.make_filename(filename), data)

    def save_json(self, filename, data, escape=False):
        '''保存json'''
        if not config.with_record:
            return
        self.ensure_root_exist()
        save_json(self.make_filename(filename), data, escape=escape)

recorder = Recorder()