# server/migrations/versions/0002_add_username_to_messages.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.database import DatabaseManager

async def upgrade(db: 'DatabaseManager'):
    """
    为 messages 表添加 username 列以优化查询 (版本 2)
    """
    # SQLite 的 ALTER TABLE 功能有限，通常不能一次性添加带 NOT NULL 的列
    # 但由于我们是冗余存储，可以允许它为 NULL，或者分步操作
    # 这里我们简化处理
    await db.execute("""
        ALTER TABLE messages ADD COLUMN username TEXT;
    """)