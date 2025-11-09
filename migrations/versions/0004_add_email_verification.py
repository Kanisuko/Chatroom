# server/migrations/versions/0004_add_email_verification.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.database import DatabaseManager

async def upgrade(db: 'DatabaseManager'):
    """为 users 表添加邮件验证和登录OTP字段，并创建 settings 表 (版本 4)"""
    # 1. 重命名旧表
    await db.execute("ALTER TABLE users RENAME TO users_old;")

    # 2. 创建新表，包含所有新字段和正确的默认值
    await db.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')), -- 修正: 加上 DEFAULT
            email TEXT UNIQUE,
            is_verified INTEGER NOT NULL DEFAULT 0,
            verification_token TEXT UNIQUE,
            login_otp_enabled INTEGER NOT NULL DEFAULT 0,
            login_otp TEXT,
            login_otp_expiry TEXT
        );
    """)

    # 3. 从旧表复制数据到新表
    await db.execute("""
        INSERT INTO users (id, username, hashed_password, created_at)
        SELECT id, username, hashed_password, created_at FROM users_old;
    """)

    # 4. 删除旧表
    await db.execute("DROP TABLE users_old;")

    # 5. 创建 settings 表
    await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)