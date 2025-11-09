# server/utils/config.py
import os
import yaml
import logging
from typing import Dict, Any, Optional, List

DEFAULT_CONFIG = {
    'server': {
        'tcp_server': {
            'enabled': True,
            'host': '0.0.0.0',
            'port': 5126,
            'tls': {
                'enabled': True,
                'cert_path': 'cert.pem',
                'key_path': 'key.pem',
            }
        },
        'web_server': {
            'enabled': True,
            'host': '0.0.0.0',
            'port': 5127,
            'tls': {
                'enabled': True,
                'cert_path': 'cert.pem',
                'key_path': 'key.pem',
            }
        },
        # 添加: WebRTC 网络配置
        'webrtc': {
            'force_ip': 'auto',
            'ip_family': 'any'
        },
        'language': 'en_US',
        'max_connections': 20,
        'message_history_on_join': 20,
        'message_history_retention': '7d'
    },
    'security': {
        # 移除: 冗余的 TLS 配置块
        'builtin_admins': {
            'enabled': True,
            'users': ['SuperAdmin', 'QinShenYu'],
            'permission': 5,
            'passwords': ''
        },
        'email_verification': {
            'enabled': True,
            'smtp_host': "smtp.example.com",
            'smtp_port': 465,
            'smtp_use_ssl': True,
            'smtp_username': "noreply@example.com",
            'smtp_password': "",
            'sender_email': "noreply@example.com",
            'max_accounts_per_email': 1,
            'token_expiry_minutes': 5,
            'domain_filter': {
                'mode': "",
                'domains': "qq.com,gmail.com"
            }
        }
    },
    'logging': { 'level': 'INFO', 'dir': 'logs', 'debug': False, 'show_user_commands': True, 'show_user_chats': True }
}
CONFIG_FILE_PATH = 'config.yml'

class Config:
    def __init__(self):
        self._config = self._load_or_create_config()
        self.builtin_admin_passwords: List[str] = self._load_initial_passwords('security.builtin_admins.passwords')
        self.smtp_password: Optional[str] = self._load_initial_passwords('security.email_verification.smtp_password', single=True)
        self.debug = self.get('logging.debug', False)

    def _load_or_create_config(self) -> Dict[str, Any]:
        if not os.path.exists(CONFIG_FILE_PATH):
            try:
                with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                    yaml.dump(DEFAULT_CONFIG, f, allow_unicode=True, sort_keys=False)
                logging.info(f"配置文件 '{CONFIG_FILE_PATH}' 不存在，已自动创建。")
                return DEFAULT_CONFIG
            except IOError as e:
                logging.error(f"无法创建默认配置文件 '{CONFIG_FILE_PATH}': {e}")
                return DEFAULT_CONFIG
        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f) or {}
                config_data = DEFAULT_CONFIG.copy()
                for key, value in user_config.items():
                    if isinstance(value, dict) and key in config_data:
                        if isinstance(config_data[key], dict):
                            # 修改: 深度合并字典，以支持新的 webrtc 子配置
                            for sub_key, sub_value in value.items():
                                if sub_key in config_data[key] and isinstance(sub_value, dict):
                                     config_data[key][sub_key].update(sub_value)
                                else:
                                     config_data[key][sub_key] = sub_value
                        else:
                            config_data[key] = value
                    else: config_data[key] = value
                return config_data
        except (IOError, yaml.YAMLError) as e:
            logging.error(f"读取配置文件 '{CONFIG_FILE_PATH}' 失败: {e}，将使用默认配置")
            return DEFAULT_CONFIG

    def _load_initial_passwords(self, key_path: str, single: bool = False) -> Any:
        passwords_str = self.get(key_path, '')
        if not passwords_str or not isinstance(passwords_str, str):
            return None if single else []
        return passwords_str if single else passwords_str.split(',')

    def clear_initial_passwords(self, key_path: str):
        if not self.get(key_path): return
        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f: data = yaml.safe_load(f)
            keys = key_path.split('.'); d = data
            for key in keys[:-1]: d = d.get(key, {})
            if keys[-1] in d: d[keys[-1]] = ''
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)
            logging.info(f"已清空 '{CONFIG_FILE_PATH}' 中的 {key_path} 字段以确保安全")
        except Exception as e:
            logging.error(f"清空配置文件中的密码字段时发生错误: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        keys = key_path.split('.')
        value = self._config
        try:
            for key in keys:
                if not isinstance(value, dict): return default
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

config = Config()