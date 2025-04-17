# utils.py
import sys
import os
from pathlib import Path
import logging

def get_data_dir():
    """
    获取数据存储目录（兼容打包和开发模式）
    返回: Path对象，指向数据目录
    """
    try:
        if getattr(sys, 'frozen', False):
            # 打包后的exe模式
            base_path = Path(sys.executable).parent
            logging.info("[工具函数] 检测到打包模式，基础路径: %s", base_path)
        else:
            # 开发模式
            base_path = Path(__file__).resolve().parent
            logging.info("[工具函数] 检测到开发模式，基础路径: %s", base_path)
        
        # 确保目录存在
        base_path.mkdir(exist_ok=True)
        logging.info("[工具函数] 确保数据目录存在: %s", base_path)
        return base_path
    except Exception as e:
        logging.error("!!! 获取数据目录失败: %s !!!", e)
        return Path(".")  # 退回当前目录