# server/migrations/versions/0009_add_channel_type.py
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from utils.database import DatabaseManager

async def upgrade(db: 'DatabaseManager'):
    """
    为 channels 表添加 type 字段以支持语音频道 (版本 9)
    """
    try:
        # 1. 检查列是否已存在，增强脚本的可重入性
        channel_columns = await db.fetchall("PRAGMA table_info(channels);")
        if not any(col['name'] == 'type' for col in channel_columns):
            # 2. 添加 type 列，默认为 'text' 以兼容现有数据
            await db.execute("""
                ALTER TABLE channels ADD COLUMN type TEXT NOT NULL DEFAULT 'text';
            """)
            logging.info("列 'type' 已成功添加到 'channels' 表。")
        else:
            logging.info("列 'type' 已存在于 'channels' 表中，无需操作。")
            
    except Exception as e:
        logging.critical(f"应用迁移版本 9 (0009_add_channel_type.py) 失败: {e}", exc_info=True)
        raise