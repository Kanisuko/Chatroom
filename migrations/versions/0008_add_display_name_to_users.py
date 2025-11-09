# server/migrations/versions/0008_add_display_name_to_users.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils.database import DatabaseManager

async def upgrade(db: 'DatabaseManager'):
    """
    为 users 表添加 display_name 字段，并用 username 填充默认值 (版本 8)
    """
    try:
        # 1. 检查列是否已存在，增强脚本的可重入性
        user_columns = await db.fetchall("PRAGMA table_info(users);")
        if not any(col['name'] == 'display_name' for col in user_columns):
            # 2. 添加 display_name 列，允许为 NULL
            await db.execute("""
                ALTER TABLE users ADD COLUMN display_name TEXT;
            """)
            print("Column 'display_name' added to 'users' table.")
            
            # 3. 将现有的 username 值复制到 display_name
            await db.execute("""
                UPDATE users SET display_name = username WHERE display_name IS NULL;
            """)
            print("Existing 'username' values copied to 'display_name'.")
        else:
            print("Column 'display_name' already exists in 'users' table.")
            
    except Exception as e:
        print(f"An error occurred during migration 0008: {e}")
        raise # 重新抛出异常，阻止服务器启动，确保数据库一致性