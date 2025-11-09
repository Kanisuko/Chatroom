# server/utils/logger.py
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
import os

# 添加: 日志模块 (Issue #17)

def setup_logger(log_dir: str, level: str = 'INFO', debug: bool = False):
    """
    配置全局日志记录器
    """
    if debug:
        level = 'DEBUG'

    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # 获取根 logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if debug else logging.INFO) # 修改: 根logger级别设为最低，由handler控制输出

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    os.makedirs(log_dir, exist_ok=True)
    
    formatter = logging.Formatter(
        '%(asctime)s - [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件 Handler (按天轮转)
    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, 'server.log'),
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    # 文件handler总是记录INFO及以上级别，除非开启debug
    file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logging.info(f"日志记录器已设置，级别: {level}")