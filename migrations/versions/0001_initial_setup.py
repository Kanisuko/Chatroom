# server/migrations/versions/0001_initial_setup.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.database import DatabaseManager

async def upgrade(db: 'DatabaseManager'):
    """
    创建项目的初始表结构 (版本 1)
    """
    # 修改: 为所有 CREATE TABLE 语句添加 IF NOT EXISTS，增强脚本的健壮性
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        );
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER,
            role_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, role_id)
        );
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            topic TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        );
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER,
            user_id INTEGER,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (channel_id) REFERENCES channels (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        );
    """)
    
    # 修改: 使用 INSERT OR IGNORE 确保即使版本号已存在也不会报错
    await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (0)")
    await db.execute("UPDATE schema_version SET version = 1")