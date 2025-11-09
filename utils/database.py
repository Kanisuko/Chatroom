import aiosqlite
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

DB_PATH = 'data/chat.db'

class DatabaseManager:
    """
    负责所有与 SQLite 数据库的异步交互
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    async def execute(self, query: str, params: tuple = ()):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, params)
            await db.commit()

    async def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def fetchval(self, query: str, params: tuple = ()):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            return row[0] if row else None

    async def add_message(self, channel_id: int, user_id: int, username: str, content: str):
        """将一条新消息插入数据库"""
        timestamp = datetime.now(timezone.utc).isoformat()
        query = "INSERT INTO messages (channel_id, user_id, username, content, timestamp) VALUES (?, ?, ?, ?, ?)"
        await self.execute(query, (channel_id, user_id, username, content, timestamp))
        # 添加: 返回新插入消息的 ID
        return await self.fetchval("SELECT last_insert_rowid()")


    # 修改: get_latest_messages 现在返回更丰富的用户信息
    async def get_latest_messages(self, channel_id: int, limit: int) -> List[Dict[str, Any]]:
        """获取频道的最新消息，包含发送者的 display_name 和 avatar"""
        query = """
            SELECT 
                m.id,
                m.content, 
                m.timestamp,
                u.username as sender_username,
                u.display_name as sender_display_name,
                u.avatar_filename
            FROM messages m
            JOIN users u ON m.user_id = u.id
            WHERE m.channel_id = ?
            ORDER BY m.timestamp DESC
            LIMIT ?
        """
        rows = await self.fetchall(query, (channel_id, limit))
        
        # 格式化数据以匹配 chat_broadcast 的 payload
        formatted_rows = []
        for row in rows:
            formatted_rows.append({
                "sender_username": row['sender_username'],
                "sender_display_name": row['sender_display_name'] or row['sender_username'],
                "message": row['content'],
                "timestamp": row['timestamp'],
                "avatar_url": f"/uploads/avatars/{row['avatar_filename']}" if row['avatar_filename'] else None
            })
        
        return list(reversed(formatted_rows)) # 仍然反转，以保持时间顺序

    async def clear_old_messages(self, retention_seconds: int):
        """根据保留时长（秒）清理旧消息"""
        if retention_seconds <= 0: return
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=retention_seconds)
        cutoff_iso = cutoff_time.isoformat()
        
        query = "DELETE FROM messages WHERE timestamp < ?"
        await self.execute(query, (cutoff_iso,))
        logging.info(f"已清理 {cutoff_iso} 之前的旧消息")

db_manager = DatabaseManager()