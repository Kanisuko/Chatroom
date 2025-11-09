# server/migrations/versions/0003_create_files_table.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.database import DatabaseManager

async def upgrade(db: 'DatabaseManager'):
    """
    创建 files 表用于文件传输 (版本 3)
    """
    await db.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            uploader_id INTEGER NOT NULL,
            original_filename TEXT NOT NULL,
            stored_filename TEXT UNIQUE NOT NULL,
            filesize INTEGER NOT NULL,
            upload_time TEXT NOT NULL,
            FOREIGN KEY (channel_id) REFERENCES channels (id) ON DELETE CASCADE,
            FOREIGN KEY (uploader_id) REFERENCES users (id) ON DELETE SET NULL
        );
    """)