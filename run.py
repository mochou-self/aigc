#!/usr/bin/env python
import os
import inspect
import sys
import asyncio
import logging
import hydra
from pathlib import Path
from hydra.utils import instantiate
from dotenv import load_dotenv
from typing import Any, Dict, List, Optional, Union
from omegaconf import DictConfig, OmegaConf


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(lineno)d - %(levelname)s- %(message)s')
logger = logging.getLogger(__name__)


def recursively_instantiate(cfg: DictConfig) -> Dict[str, Any]:
    """
    递归遍历配置并实例化所有可实例化的节点,收集所有包含run方法的对象
    """
    instances = {}
    runnable_instances = {}
    
    def _recursive_instantiate(node: Union[DictConfig, Any], path: List[str] = []) -> None:
        logger.debug(path)
        logger.debug(node)
        if isinstance(node, DictConfig):
            # 检查当前节点是否可实例化
            if "_target_" in node:
                full_path = ".".join(path)
                try:
                    obj = instantiate(node)
                    instances[full_path] = obj
                    logger.info(f"已实例化对象: {full_path} -> {obj}")
                    
                    # 检查实例是否有run方法
                    if hasattr(obj, "run") and callable(getattr(obj, "run")):
                        runnable_instances[full_path] = obj
                        logger.info(f"找到可运行实例: {full_path}")
                except Exception as e:
                    logger.exception(f"实例化对象失败: {full_path}, 错误: {e}")
            # 递归遍历所有子节点
            for key, value in node.items():
                _recursive_instantiate(value, path + [key])
    
    _recursive_instantiate(cfg)
    return instances, runnable_instances

@hydra.main(version_base=None, config_path="conf", config_name="run")
def my_app(cfg: DictConfig) -> Optional[Any]:
    logger.info('完整配置: %s', cfg)
    
    # 递归实例化所有可实例化的节点，并收集可运行实例
    instances, runnable_instances = recursively_instantiate(cfg)
    
    if not runnable_instances:
        logger.info('未找到可运行的实例')
        logger.info('配置YAML: %s', OmegaConf.to_yaml(cfg))
        return None
    
    logger.info(f"找到 {len(runnable_instances)} 个可运行实例")
    
    # 执行所有可运行实例（按配置文件中的顺序）
    results = {}
    for path, obj in runnable_instances.items():
        logger.info(f"执行实例: {path}")
        run_method = getattr(obj, "run")
        
        try:
            if inspect.iscoroutinefunction(run_method):
                result = asyncio.run(run_method())
            else:
                result = run_method()
            results[path] = result
            logger.info(f"实例 {path} 执行完成，结果: {result}")
        except Exception as e:
            logger.exception(f"实例 {path} 执行失败，错误: {e}")



if __name__ == "__main__":
    load_dotenv()
    my_app()
