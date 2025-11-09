# server/migrations/versions/0005_remove_email_unique_constraint.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.database import DatabaseManager

async def upgrade(db: 'DatabaseManager'):
    """
    移除 users.email 的 UNIQUE 约束以支持多账户共享邮箱 (版本 5)
    """
    # 1. 重命名旧表
    await db.execute("ALTER TABLE users RENAME TO users_old_v4;")

    # 2. 创建新表，移除 email 的 UNIQUE 约束
    await db.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            email TEXT, -- 移除了 UNIQUE
            is_verified INTEGER NOT NULL DEFAULT 0,
            verification_token TEXT UNIQUE,
            login_otp_enabled INTEGER NOT NULL DEFAULT 0,
            login_otp TEXT,
            login_otp_expiry TEXT
        );
    """)

    # 3. 从旧表复制所有数据到新表
    await db.execute("""
        INSERT INTO users (id, username, hashed_password, created_at, email, is_verified, 
                           verification_token, login_otp_enabled, login_otp, login_otp_expiry)
        SELECT id, username, hashed_password, created_at, email, is_verified,
               verification_token, login_otp_enabled, login_otp, login_otp_expiry
        FROM users_old_v4;
    """)

    # 4. 删除旧表
    await db.execute("DROP TABLE users_old_v4;")