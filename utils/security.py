# server/utils/security.py
import bcrypt
import ssl
import logging
import os
from typing import Optional

from .config import config

def hash_password(password: str) -> Optional[str]:
    try:
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_bytes = bcrypt.hashpw(password_bytes, salt)
        return hashed_bytes.decode('utf-8')
    except Exception as e:
        logging.error(f"密码哈希失败: {e}")
        return None

def check_password(password: str, hashed_password: str) -> bool:
    try:
        password_bytes = password.encode('utf-8')
        hashed_password_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_password_bytes)
    except Exception:
        return False

# 新增: 将 SSL 上下文创建逻辑移到这里
def create_ssl_context_from_path(tls_config_path: str) -> ssl.SSLContext | None:
    """根据配置文件中的路径创建 SSL 上下文"""
    if not config.get(f"{tls_config_path}.enabled", False):
        return None
    cert_path = config.get(f"{tls_config_path}.cert_path")
    key_path = config.get(f"{tls_config_path}.key_path")
    
    if not all([cert_path, key_path]) or not os.path.exists(cert_path) or not os.path.exists(key_path):
        logging.error(f"TLS 在 {tls_config_path} 中启用，但证书或密钥文件无效/缺失")
        return None
    
    try:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        logging.info(f"为 {tls_config_path} 成功加载 TLS 证书: {cert_path}")
        return context
    except ssl.SSLError as e:
        logging.critical(f"为 {tls_config_path} 加载 TLS 证书时发生严重错误: {e}")
        return None