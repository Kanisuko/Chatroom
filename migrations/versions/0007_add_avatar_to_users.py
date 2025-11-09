# server/migrations/versions/0007_add_avatar_to_users.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.database import DatabaseManager

async def upgrade(db: 'DatabaseManager'):
    """为 users 表添加 avatar_filename 字段 (版本 7)"""
    try:
        # 检查列是否已存在，增强脚本的可重入性
        user_columns = await db.fetchall("PRAGMA table_info(users);")
        if not any(col['name'] == 'avatar_filename' for col in user_columns):
            await db.execute("""
                ALTER TABLE users ADD COLUMN avatar_filename TEXT;
            """)
            print("Column 'avatar_filename' added to 'users' table.")
        else:
            print("Column 'avatar_filename' already exists in 'users' table.")
    except Exception as e:
        print(f"An error occurred during migration 0007: {e}")
        # 在某些 SQLite 版本中，直接 ALTER TABLE 可能会有问题
        # 如果出错，这里可以回退到更安全的 "重命名-创建-复制" 模式
        # 但对于添加可为 NULL 的列，这通常是安全的。