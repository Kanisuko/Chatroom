# server/utils/migration.py
import os
import importlib.util
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .database import DatabaseManager

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'migrations', 'versions')

async def run_migrations(db_manager: 'DatabaseManager'):
    logging.info("开始检查数据库迁移...")
    await db_manager.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL PRIMARY KEY);
    """)
    current_version_row = await db_manager.fetchone("SELECT version FROM schema_version")
    if not current_version_row:
        await db_manager.execute("INSERT INTO schema_version (version) VALUES (0)")
        current_version = 0
    else:
        current_version = current_version_row['version']
    logging.info(f"当前数据库版本: {current_version}")

    available_migrations = []
    for filename in sorted(os.listdir(MIGRATIONS_DIR)):
        if filename.endswith('.py') and not filename.startswith('__'):
            try:
                version = int(filename.split('_')[0])
                available_migrations.append((version, filename))
            except (ValueError, IndexError):
                logging.warning(f"无法解析迁移文件名: {filename}")
    
    for version, filename in available_migrations:
        if version > current_version:
            logging.info(f"准备应用迁移版本 {version}: {filename}")
            try:
                module_name = filename[:-3]
                filepath = os.path.join(MIGRATIONS_DIR, filename)
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                migration_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration_module)
                
                if hasattr(migration_module, 'upgrade'):
                    await migration_module.upgrade(db_manager)
                    await db_manager.execute("UPDATE schema_version SET version = ?", (version,))
                    logging.info(f"成功应用迁移版本 {version}")
                    current_version = version
                else:
                    logging.error(f"迁移脚本 {filename} 中缺少 upgrade 函数")
            except Exception as e:
                logging.critical(f"应用迁移版本 {version} ({filename}) 失败: {e}", exc_info=True)
                raise
    logging.info("数据库迁移检查完成")