# server/core/actions.py
import logging
from typing import TYPE_CHECKING, Tuple
from datetime import datetime, timezone, timedelta

from utils.i18n import translator
from utils import protocol as proto, database as db
from utils.config import config
from .constants import *

if TYPE_CHECKING:
    from core.session import BaseSession # 修改
    from server import Server

class ActionHandler:
    def __init__(self, server: 'Server'):
        self.server = server

    async def list_channel_users(self, session: 'BaseSession'): # 修改
        if session.current_channel:
            # 修改: list_channel_users 现在依赖于 broadcast_all_registered_users_status
            # 因此这里直接调用广播，让所有客户端更新用户列表 (包括当前会话)
            await self.server.broadcast_all_registered_users_status(exclude_session=None)
            await session.send(proto.create_system_message("用户列表已刷新。"))
        else:
            await session.send(proto.create_error_message("请先加入一个频道"))


    async def show_whoami(self, session: 'BaseSession'): # 修改
        if session.user:
            # 修改: 使用统一格式化函数，包含 display_name
            user_info = self.server._format_user_info(session.user) 
            # 同时返回 username，以防前端需要做特殊处理
            user_info['username'] = session.user.username
            await session.send(proto.create_message(proto.MSG_TYPE_WHOAMI_RESPONSE, user_info))

    async def show_help(self, session: 'BaseSession'): # 修改
        help_text = "Commands: /help, /list, /whoami, /channels, /join <channel>\n"
        help_text += "File Commands: /files, /upload <path>, /download <id>"
        if session.user and any(role in [ROLE_MODERATOR, ROLE_OPERATOR, ROLE_OWNER, ROLE_SUPERUSER] for role in session.user.roles):
            help_text += ", /deletefile <id>"
        if session.user and any(role in [ROLE_OWNER, ROLE_SUPERUSER] for role in session.user.roles):
             help_text += "\nAdmin-Chan: /createchannel, /deletechannel"
        if session.user and any(role in [ROLE_OPERATOR, ROLE_OWNER, ROLE_SUPERUSER] for role in session.user.roles):
            help_text += "\nAdmin-User: /kick"
        await session.send(proto.create_system_message(help_text))

    async def kick_user(self, actor_session: 'BaseSession', target_username: str): # 修改
        required_roles = [ROLE_OPERATOR, ROLE_OWNER, ROLE_SUPERUSER]
        if not actor_session.user or not any(role in required_roles for role in actor_session.user.roles):
            await actor_session.send(proto.create_error_message(translator.t('permission_denied', command='kick')))
            return
        if actor_session.user and target_username.lower() == actor_session.user.username.lower():
            await actor_session.send(proto.create_error_message("You cannot kick yourself"))
            return
        target_session = await self.server.get_session_by_username(target_username)
        if not target_session or not target_session.user:
            await actor_session.send(proto.create_error_message(translator.t('user_not_found', username=target_username)))
            return
        # 修改: 使用 display_name
        actor_display_name = actor_session.user.display_name if actor_session.user.display_name else actor_session.user.username
        target_display_name = target_session.user.display_name if target_session.user.display_name else target_session.user.username

        kick_notification = translator.t('kick_notification', admin=actor_display_name)
        await target_session.send(proto.create_system_message(kick_notification, level="warning"))
        target_channel_id = target_session.current_channel.id if target_session.current_channel else None
        await target_session.close()
        if target_channel_id and actor_session.user:
            kick_broadcast = translator.t('kick_broadcast', target_user=target_display_name, admin=actor_display_name)
            await self.server.broadcast_to_channel(target_channel_id, proto.create_system_message(kick_broadcast, level="warning"))
        logging.info(f"用户 '{target_display_name}' (username: {target_username}) 已被 '{actor_display_name}' 踢出") # 修改: 记录 display_name 和 username

    async def create_channel(self, session: 'BaseSession', channel_name: str): # 修改
        required_roles = [ROLE_OWNER, ROLE_SUPERUSER]
        if not session.user or not any(role in required_roles for role in session.user.roles):
            await session.send(proto.create_error_message(translator.t('permission_denied', command='createchannel')))
            return
        success, message, new_channel = await self.server.channel_manager.create_channel(channel_name)
        if success and new_channel:
            self.server.add_channel_to_session_manager(new_channel)
            # 创建成功后，向所有人广播新的频道列表
            all_channels = self.server.channel_manager.get_all_channels()
            await self.server.broadcast_to_all(proto.create_message("channel_list_update", {"channels": all_channels}))
        
        await session.send(proto.create_system_message(message))

    async def create_voice_channel(self, session: 'BaseSession', channel_name: str): # 添加
        """处理创建语音频道的动作"""
        required_roles = [ROLE_OWNER, ROLE_SUPERUSER]
        if not session.user or not any(role in required_roles for role in session.user.roles):
            await session.send(proto.create_error_message(translator.t('permission_denied', command='createvoicechannel')))
            return
        
        # 调用 channel_manager 并指定类型为 'voice'
        success, message, new_channel = await self.server.channel_manager.create_channel(
            name=channel_name, 
            channel_type='voice'
        )
        
        if success and new_channel:
            self.server.add_channel_to_session_manager(new_channel)
            # 广播新的频道列表给所有用户
            all_channels = self.server.channel_manager.get_all_channels()
            await self.server.broadcast_to_all(proto.create_message("channel_list_update", {"channels": all_channels}))
        
        await session.send(proto.create_system_message(message))

    async def delete_channel(self, session: 'BaseSession', channel_name: str): # 修改
        required_roles = [ROLE_OWNER, ROLE_SUPERUSER]
        if not session.user or not any(role in required_roles for role in session.user.roles):
            await session.send(proto.create_error_message(translator.t('permission_denied', command='deletechannel')))
            return
        channel_to_delete = self.server.channel_manager.get_channel(channel_name)
        if not channel_to_delete:
            await session.send(proto.create_error_message(f"频道 #{channel_name} 不存在"))
            return
        success, message = await self.server.channel_manager.delete_channel(channel_name)
        if success:
            await self.server.remove_channel_from_session_manager(channel_to_delete)
        await session.send(proto.create_system_message(message))

    async def join_channel(self, session: 'BaseSession', channel_name: str): # 修改
        channel = self.server.channel_manager.get_channel(channel_name)
        if not channel:
            await session.send(proto.create_error_message(f"频道 #{channel_name} 不存在"))
            return
        await self.server.join_channel(session, channel)

    async def list_channels(self, session: 'BaseSession'): # 修改
        channels = self.server.channel_manager.get_all_channels()
        payload = {"channels": channels}
        await session.send(proto.create_message(proto.MSG_TYPE_CHANNEL_LIST, payload))

    async def list_files(self, session: 'BaseSession'): # 修改
        await self.server.file_manager.list_files(session)

    async def delete_file(self, session: 'BaseSession', file_id: int): # 修改
        required_roles = [ROLE_MODERATOR, ROLE_OPERATOR, ROLE_OWNER, ROLE_SUPERUSER]
        if not session.user or not any(role in required_roles for role in session.user.roles):
            await session.send(proto.create_error_message(translator.t('permission_denied', command='deletefile')))
            return
        success, message = await self.server.file_manager.delete_file(session, file_id)
        response_func = proto.create_system_message if success else proto.create_error_message
        await session.send(response_func(message))

    async def verify_email_token(self, username: str, token: str) -> Tuple[bool, str]:
        # 修改: 查询时包含 display_name
        user = await db.db_manager.fetchone("SELECT id, username, hashed_password, email, is_verified, login_otp_enabled, avatar_filename, display_name, verification_token, created_at FROM users WHERE username = ?", (username,))
        if not user: return False, "用户不存在"
        if user['is_verified']: return False, "账户已经验证过了"
        
        expiry_minutes = config.get('security.email_verification.token_expiry_minutes', 5)
        if expiry_minutes > 0:
            token_creation_time = datetime.fromisoformat(user['created_at'].replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > token_creation_time + timedelta(minutes=expiry_minutes):
                return False, "验证令牌已过期，请重新注册或联系管理员"

        if user['verification_token'] and user['verification_token'] == token:
            await db.db_manager.execute("UPDATE users SET is_verified = 1, verification_token = NULL WHERE id = ?", (user['id'],))
            # 修改: 日志中优先显示 display_name
            user_display_name = user['display_name'] if user['display_name'] else user['username']
            logging.info(f"用户 '{user_display_name}' (username: {username}) 已成功通过邮件验证")
            return True, "邮箱验证成功！您现在可以登录了"
        else:
            return False, "验证令牌无效"
    
    async def verify_email_token_by_token(self, token: str) -> Tuple[bool, str]:
        if not token: return False, "无效的令牌"

        # 修改: 查询时包含 display_name
        user = await db.db_manager.fetchone("SELECT id, username, hashed_password, email, is_verified, login_otp_enabled, avatar_filename, display_name, verification_token, created_at FROM users WHERE verification_token = ?", (token,))
        if not user: return False, "验证令牌无效或已使用"
        if user['is_verified']: return False, "账户已经验证过了"
        
        expiry_minutes = config.get('security.email_verification.token_expiry_minutes', 5)
        if expiry_minutes > 0:
            token_creation_time = datetime.fromisoformat(user['created_at'].replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > token_creation_time + timedelta(minutes=expiry_minutes):
                return False, "验证令牌已过期"

        await db.db_manager.execute("UPDATE users SET is_verified = 1, verification_token = NULL WHERE id = ?", (user['id'],))
        # 修改: 日志中优先显示 display_name
        user_display_name = user['display_name'] if user['display_name'] else user['username']
        logging.info(f"用户 '{user_display_name}' (username: {user['username']}) 已成功通过邮件链接验证")
        return True, "邮箱验证成功！您现在可以关闭此页面并登录了"