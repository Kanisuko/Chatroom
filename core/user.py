import logging
import asyncio
import secrets
import re
from asyncio import Lock
from typing import Dict, Optional, Tuple, List, Any, TYPE_CHECKING
from datetime import datetime, timezone, timedelta

from utils import security, mailer
from utils.config import config
from utils.database import db_manager
from utils.i18n import translator
from .constants import *

if TYPE_CHECKING:
    from core.session import BaseSession

class User:
    def __init__(self, id: int, username: str, hashed_password: str, roles: List[str], email: Optional[str], is_verified: bool, login_otp_enabled: bool, avatar_filename: Optional[str] = None, status: str = 'offline', display_name: Optional[str] = None):
        self.id = id
        self.username = username
        self.hashed_password = hashed_password
        self.roles = roles
        self.email = email
        self.is_verified = bool(is_verified)
        self.login_otp_enabled = bool(login_otp_enabled)
        self.avatar_filename = avatar_filename
        self.status = status
        self.display_name = display_name if display_name is not None else username

class UserManager:
    def __init__(self):
        self.online_users: Dict[str, 'BaseSession'] = {} 
        self._lock = Lock()

    async def initialize_roles_and_admins(self):
        defined_roles = [ROLE_SUPERUSER, ROLE_OWNER, ROLE_OPERATOR, ROLE_MODERATOR, ROLE_MEMBER]
        for role_name in defined_roles:
            if not await db_manager.fetchone("SELECT id FROM roles WHERE name = ?", (role_name,)):
                await db_manager.execute("INSERT INTO roles (name) VALUES (?)", (role_name,))
                logging.info(f"角色 '{role_name}' 已创建")
        
        smtp_pass = config.smtp_password
        if smtp_pass:
            await db_manager.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("smtp_password", smtp_pass))
            config.clear_initial_passwords('security.email_verification.smtp_password')
        
        if not config.get('security.builtin_admins.enabled'): return
        admin_users = config.get('security.builtin_admins.users', [])
        passwords = config.builtin_admin_passwords
        superuser_role_id = await db_manager.fetchval("SELECT id FROM roles WHERE name = ?", (ROLE_SUPERUSER,))
        loop = asyncio.get_running_loop()

        for i, username in enumerate(admin_users):
            password = passwords[i] if i < len(passwords) else None
            user_data = await db_manager.fetchone("SELECT id, username, hashed_password, email, display_name FROM users WHERE username = ?", (username,))
            
            if not user_data and not password:
                hashed_pass = "!"
                await db_manager.execute("INSERT INTO users (username, display_name, hashed_password, email) VALUES (?, ?, ?, ?)", (username, username, hashed_pass, f"{username.lower()}@localhost.local"))
                logging.info(f"内置管理员 '{username}' 已创建但无法登录")
            elif user_data and not password: 
                logging.info(f"内置管理员 '{username}' 密码未提供，保留现有密码")
            else:
                hashed_pass = await loop.run_in_executor(None, security.hash_password, password)
                if not hashed_pass: continue
                if user_data:
                    await db_manager.execute("UPDATE users SET hashed_password = ?, display_name = COALESCE(display_name, ?) WHERE id = ?", (hashed_pass, username, user_data['id']))
                else:
                    await db_manager.execute("INSERT INTO users (username, display_name, hashed_password, email) VALUES (?, ?, ?, ?)", (username, username, hashed_pass, f"{username.lower()}@localhost.local"))
                logging.info(f"内置管理员 '{username}' 已就绪")

            user_data_for_role = await db_manager.fetchone("SELECT id, username, hashed_password, email, display_name FROM users WHERE username = ?", (username,))
            if user_data_for_role and superuser_role_id:
                await db_manager.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)", (user_data_for_role['id'], superuser_role_id))
                await db_manager.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user_data_for_role['id'],))
        
        config.clear_initial_passwords('security.builtin_admins.passwords')

    async def register(self, username: str, password: str, email: str) -> Tuple[bool, str]:
        if not (3 <= len(username) <= 16 and re.fullmatch(r'^[a-zA-Z0-9_\u4e00-\u9fff]+$', username)):
            return False, translator.t('register_failed_invalid')
        if not email: return False, "邮箱不能为空"

        domain_filter = config.get('security.email_verification.domain_filter')
        if domain_filter and domain_filter.get('mode') and domain_filter.get('domains'):
            user_domain = email.split('@')[-1].lower()
            allowed_domains = {d.strip().lower() for d in domain_filter['domains'].split(',')}
            if domain_filter['mode'] == 'whitelist' and user_domain not in allowed_domains: return False, "该邮箱域名不被允许注册"
            elif domain_filter['mode'] == 'blacklist' and user_domain in allowed_domains: return False, "该邮箱域名已被禁止注册"
        
        existing_user = await db_manager.fetchone("SELECT id, username, hashed_password, email, is_verified, display_name FROM users WHERE username = ?", (username,))
        if existing_user:
            if existing_user['is_verified']:
                return False, f"注册失败：用户名 '{username}' 已被占用"
            else:
                logging.info(f"用户 '{username}' 已存在但未验证，重新发送验证邮件至 {existing_user['email']}")
                token = secrets.token_urlsafe(32)
                expiry_minutes = config.get('security.email_verification.token_expiry_minutes', 5)
                await db_manager.execute("UPDATE users SET verification_token = ?, created_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?", (token, existing_user['id']))
                asyncio.create_task(mailer.send_email(existing_user['email'], "重新发送验证邮件", f"您的新验证令牌是: {token}，有效期 {expiry_minutes} 分钟。"))
                return True, "该用户名已注册但未验证，新的验证邮件已发送，请查收。"

        max_accounts = config.get('security.email_verification.max_accounts_per_email')
        if max_accounts and max_accounts > 0:
            count = await db_manager.fetchval("SELECT COUNT(id) FROM users WHERE email = ?", (email,))
            if count is not None and count >= max_accounts:
                return False, f"该邮箱已达到最大注册数量 ({max_accounts})"
        
        try:
            loop = asyncio.get_running_loop()
            hashed_password = await loop.run_in_executor(None, security.hash_password, password)
            if not hashed_password: return False, translator.t('internal_error')
            
            await db_manager.execute("INSERT INTO users (username, display_name, hashed_password, email) VALUES (?, ?, ?, ?)", (username, username, hashed_password, email))
            user_id = await db_manager.fetchval("SELECT id FROM users WHERE username = ?", (username,))
            member_role_id = await db_manager.fetchval("SELECT id FROM roles WHERE name = ?", (ROLE_MEMBER,))
            if user_id and member_role_id:
                await db_manager.execute("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)", (user_id, member_role_id))
        except Exception as e:
            logging.error(f"注册用户 '{username}' 时数据库出错: {e}")
            return False, "注册时发生数据库错误"

        if config.get('security.email_verification.enabled'):
            token = secrets.token_urlsafe(32)
            expiry_minutes = config.get('security.email_verification.token_expiry_minutes', 5)
            await db_manager.execute("UPDATE users SET verification_token = ?, created_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?", (token, user_id))
            await mailer.send_email(email, "欢迎注册 - 请验证您的邮箱", f"这是一个模拟验证邮件。您的验证令牌是: {token}，有效期 {expiry_minutes} 分钟。")
            return True, "注册成功！一封验证邮件已发送至您的邮箱，请查收后重新登录。"
        else:
            await db_manager.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user_id,))
            return True, translator.t('register_success', username=username)

    async def _handle_session_takeover(self, username: str):
        username_lower = username.lower()
        if username_lower in self.online_users:
            logging.info(f"用户 '{username}' 已在线，正在执行会话顶替...")
            old_session: 'BaseSession' = self.online_users.pop(username_lower, None)
            if old_session and old_session.user: 
                await old_session.server.handle_takeover_cleanup(old_session)
            else:
                 logging.warning(f"尝试顶替用户'{username}'，但在 online_users 中未找到有效的会话对象")

    def _create_user_from_data(self, user_data: dict, roles: List[str], status: str = 'offline') -> User:
        return User(
            id=user_data['id'],
            username=user_data['username'],
            hashed_password=user_data['hashed_password'],
            roles=roles, 
            email=user_data['email'],
            is_verified=user_data['is_verified'],
            login_otp_enabled=user_data['login_otp_enabled'],
            avatar_filename=user_data.get('avatar_filename'),
            status=status,
            display_name=user_data.get('display_name')
        )

    async def login(self, username: str, password: str, session: 'BaseSession') -> Tuple[bool, str, Optional[User], Optional[str]]:
        user_data = await db_manager.fetchone("SELECT id, username, hashed_password, email, is_verified, login_otp_enabled, avatar_filename, display_name FROM users WHERE username = ?", (username,))
        if not user_data: return False, translator.t('login_failed_not_found', username=username), None, None
        
        roles = await self.get_user_roles(user_data['id'])
        is_superuser = ROLE_SUPERUSER in roles
        if not is_superuser and config.get('security.email_verification.enabled') and not user_data['is_verified']:
            return False, "您的账户尚未通过邮箱验证，请在登录界面选择 [3]验证邮箱", None, None
            
        async with self._lock:
            await self._handle_session_takeover(username)
        
        if user_data['hashed_password'] == "!" or not await asyncio.get_running_loop().run_in_executor(None, security.check_password, password, user_data['hashed_password']):
            return False, translator.t('login_failed_password'), None, None
        
        user = self._create_user_from_data(user_data, roles, status='online')
        
        session_token = secrets.token_urlsafe(32)
        await db_manager.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (session_token, user.id))
        
        async with self._lock: self.online_users[username.lower()] = session
        return True, translator.t('login_success'), user, session_token

    async def resume_session(self, token: str, session: 'BaseSession') -> Tuple[bool, str, Optional[User], Optional[str]]:
        session_data = await db_manager.fetchone("SELECT user_id FROM sessions WHERE token = ?", (token,))
        if not session_data:
            return False, "无效的会话令牌", None, None
            
        user_data = await db_manager.fetchone("SELECT id, username, hashed_password, email, is_verified, login_otp_enabled, avatar_filename, display_name FROM users WHERE id = ?", (session_data['user_id'],))
        if not user_data:
            return False, "与令牌关联的用户不存在", None, None
            
        username = user_data['username']
        async with self._lock:
            await self._handle_session_takeover(username)

        roles = await self.get_user_roles(user_data['id'])
        user = self._create_user_from_data(user_data, roles, status='online')
        
        async with self._lock: self.online_users[username.lower()] = session
        return True, "会话已恢复", user, token

    async def logout(self, username: str):
        async with self._lock:
            self.online_users.pop(username.lower(), None)

    async def get_all_registered_users(self) -> List[Dict[str, Any]]:
        query = """
            SELECT u.id, u.username, u.display_name, u.avatar_filename, r.name as role_name
            FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            JOIN roles r ON ur.role_id = r.id
            ORDER BY u.username
        """
        registered_users_data = await db_manager.fetchall(query)
        
        unique_users: Dict[int, Dict[str, Any]] = {}

        for user_data in registered_users_data:
            user_id = user_data['id']
            username = user_data['username']
            display_name = user_data['display_name']
            avatar_filename = user_data['avatar_filename']
            role_name = user_data['role_name']

            if user_id not in unique_users:
                unique_users[user_id] = {
                    "id": user_id, 
                    "username": username,
                    "display_name": display_name if display_name else username,
                    "roles": [],
                    "avatar_url": f"/uploads/avatars/{avatar_filename}" if avatar_filename else None
                }
            unique_users[user_id]["roles"].append(role_name)
        
        users_list = []
        for user_id, info in unique_users.items():
            is_online = info["username"].lower() in self.online_users
            info["status"] = 'online' if is_online else 'offline'
            users_list.append(info)

        return users_list

    async def get_user_roles(self, user_id: int) -> List[str]:
        query = "SELECT r.name FROM roles r JOIN user_roles ur ON r.id = ur.role_id WHERE ur.user_id = ?"
        rows = await db_manager.fetchall(query, (user_id,)); return [row['name'] for row in rows]
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """通过用户 ID 获取 User 对象"""
        user_data = await db_manager.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        if not user_data:
            return None
        roles = await self.get_user_roles(user_id)
        is_online = user_data['username'].lower() in self.online_users
        status = 'online' if is_online else 'offline'
        
        return self._create_user_from_data(user_data, roles, status=status)