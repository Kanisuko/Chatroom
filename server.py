import asyncio
import logging
import os
import socket
from typing import Set, Optional, Dict, List, Any

from utils.config import config
from utils import protocol as proto, database as db, security
from core.session import BaseSession, WebSocketClientSession, TcpClientSession
from core.user import UserManager, User
from core.channel import ChannelManager, Channel
from core.commands import CommandHandler
from core.actions import ActionHandler
from core.file import FileManager
from core.sfu import SFUServer

class Server:
    def __init__(self):
        self.sessions: Set[BaseSession] = set()
        self.channel_sessions: Dict[int, Set[BaseSession]] = {}
        self.user_manager = UserManager()
        self.channel_manager = ChannelManager()
        self.action_handler = ActionHandler(self)
        self.command_handler = CommandHandler(self)
        self.file_manager = FileManager(self)
        
        # 修改: 以最简单的方式初始化 SFUServer
        self.sfu_server = SFUServer()
        
        self._tcp_server: Optional[asyncio.Server] = None
        os.makedirs("uploads", exist_ok=True)
        os.makedirs("uploads/avatars", exist_ok=True)

    async def initialize(self):
        await self.user_manager.initialize_roles_and_admins()
        await self.channel_manager.initialize_channels()
        
        for channel in self.channel_manager.channels_by_name.values():
            self.channel_sessions[channel.id] = set()
            
        logging.info("核心服务已初始化")

    async def start_tcp_server(self):
        host, port = config.get('server.tcp_server.host'), config.get('server.tcp_server.port')
        ssl_context = security.create_ssl_context_from_path('server.tcp_server.tls')
        if not host or not port:
            logging.error("TCP 服务器的 host 或 port 未在 config.yml 中正确配置"); return
        self._tcp_server = await asyncio.start_server(self.handle_tcp_connection, host, port, ssl=ssl_context)
        addr, tls_status = self._tcp_server.sockets[0].getsockname(), "已启用" if ssl_context else "已禁用"
        logging.info(f"TCP 服务器已启动，监听于 {addr[0]}:{addr[1]} (TLS: {tls_status})")
        await self._tcp_server.serve_forever()

    async def handle_tcp_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peername = writer.get_extra_info('peername')
        logging.info(f"收到新的 TCP 连接来自 {peername}")
        session = TcpClientSession(self, reader, writer, peername)
        self.add_session(session)
        await session.handle_session()

    def add_session(self, session: BaseSession):
        self.sessions.add(session)
        logging.info(f"新连接: {session.peername}, 当前总连接数: {len(self.sessions)}")

    def remove_session(self, session: BaseSession):
        if session in self.sessions:
            self.sessions.remove(session)
            logging.info(f"连接已关闭: {session.peername}, 当前总连接数: {len(self.sessions)}")
            asyncio.create_task(self.handle_disconnection(session))
    
    async def handle_disconnection(self, session: BaseSession):
        if session.user:
            logging.info(f"用户 '{session.user.username}' 断开连接，正在更新用户列表...")
            
            if session.current_channel and session.current_channel.id in self.channel_sessions:
                self.channel_sessions[session.current_channel.id].discard(session)

            if session.current_voice_channel: 
                await self.leave_voice_channel(session, session.current_voice_channel, is_disconnecting=True) 

            await self.user_manager.logout(session.user.username)
            
            await self.broadcast_all_registered_users_status()
        else:
            logging.info(f"未认证或未登录用户 {session.peername} 断开连接，无需特殊清理。")
    
    async def shutdown(self):
        logging.info("正在关闭核心服务...")
        if self._tcp_server:
            self._tcp_server.close(); await self._tcp_server.wait_closed()
        if self.sessions:
            sessions_copy = list(self.sessions)
            tasks = [s.close() for s in sessions_copy]
            await asyncio.gather(*tasks, return_exceptions=True)
        logging.info("核心服务已关闭")

    def _format_user_info(self, user: User) -> Dict[str, Any]:
        info = {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "roles": user.roles,
            "status": user.status
        }
        if user.avatar_filename:
            info["avatar_url"] = f"/uploads/avatars/{user.avatar_filename}"
        return info

    def add_channel_to_session_manager(self, channel: Channel):
        if channel.id not in self.channel_sessions:
            self.channel_sessions[channel.id] = set()
            
    async def remove_channel_from_session_manager(self, channel: Channel):
        if channel.id in self.channel_sessions:
            sessions_to_move = list(self.channel_sessions[channel.id])
            del self.channel_sessions[channel.id]
            
            for session in sessions_to_move:
                await session.send(proto.create_message(proto.MSG_TYPE_SYSTEM_MESSAGE, {"message": f"你所在的频道 #{channel.name} 已被删除，你已被移回默认频道。", "level": "warning"}))
                await self.join_default_channel(session)
    
    async def join_default_channel(self, session: BaseSession):
        default_channel = self.channel_manager.default_channel
        if default_channel:
            await self.join_channel(session, default_channel)

    async def join_channel(self, session: BaseSession, channel: Channel):
        if session.current_channel:
            await self.leave_channel(session, session.current_channel)
            
        session.current_channel = channel
        self.channel_sessions[channel.id].add(session)
        
        if session.user:
            history_limit = config.get('server.message_history_on_join', 20)
            history = await db.db_manager.get_latest_messages(channel.id, history_limit)
            
            all_registered_users_status = await self.user_manager.get_all_registered_users()

            payload = {
                "channel_id": channel.id,
                "channel_name": channel.name,
                "channel_topic": channel.topic,
                "history": history,
                "users": all_registered_users_status
            }
            await session.send(proto.create_message(proto.MSG_TYPE_JOIN_SUCCESS, payload))
            
            if not session.is_resumed_session:
                join_msg = f"{session.user.display_name or session.user.username} 加入了频道"
                await self.broadcast_to_channel(
                    channel.id, 
                    proto.create_message(proto.MSG_TYPE_SYSTEM_MESSAGE, {"message": join_msg}), 
                    exclude_session=session
                )
            
            await self.broadcast_all_registered_users_status()

        logging.info(f"用户 {session.user.display_name if session.user else ''} 加入了频道 #{channel.name}")
        
    async def leave_channel(self, session: BaseSession, channel: Channel):
        if session in self.channel_sessions.get(channel.id, set()):
            self.channel_sessions[channel.id].discard(session) 
            if session.user:
                await self.broadcast_all_registered_users_status()
            logging.info(f"用户 {session.user.display_name if session.user else ''} 离开了频道 #{channel.name}")
    
    async def join_voice_channel(self, session: BaseSession, channel: Channel):
        if not session.user: return
        if channel.type != 'voice':
            await session.send(proto.create_error_message(f"频道 #{channel.name} 不是一个语音频道。"))
            return

        if session.current_voice_channel:
            if session.current_voice_channel.id == channel.id: return
            await self.leave_voice_channel(session, session.current_voice_channel)

        session.current_voice_channel = channel
        
        pc = await self.sfu_server.join_room(channel.id, session.user.id)
        session.rtc_peer_connection = pc

        await session.send(proto.create_message(
            proto.MSG_TYPE_JOIN_VOICE_SUCCESS,
            {"channel_id": channel.id}
        ))
        
        logging.info(f"用户 {session.user.display_name or session.user.username} 加入了语音频道 #{channel.name} (SFU)")

    async def leave_voice_channel(self, session: BaseSession, channel: Channel, is_disconnecting: bool = False):
        if not session.user: return
        
        await self.sfu_server.leave_room(channel.id, session.user.id)
        session.current_voice_channel = None
        session.rtc_peer_connection = None
        
        if not is_disconnecting:
            logging.info(f"用户 {session.user.display_name or session.user.username} 离开了语音频道 #{channel.name} (SFU)")
        
    async def handle_takeover_cleanup(self, old_session: BaseSession):
        if old_session.user:
            if old_session.current_channel:
                self.channel_sessions[old_session.current_channel.id].discard(old_session)
            
            if old_session.current_voice_channel: 
                await self.leave_voice_channel(old_session, old_session.current_voice_channel, is_disconnecting=True) 

            self.remove_session(old_session) 
            
            if isinstance(old_session, WebSocketClientSession) and not old_session.ws.closed:
                if config.get('logging.debug'): logging.debug(f"正在关闭被顶替的 WebSocket 连接 for {old_session.peername}")
                await old_session.ws.close()
            logging.info(f"为用户 '{old_session.user.display_name or old_session.user.username}' 的会话顶替完成了清理")

    async def broadcast_to_channel(self, channel_id: int, message: str, exclude_session: Optional[BaseSession] = None):
        if channel_id in self.channel_sessions:
            tasks = [
                s.send(message) 
                for s in self.channel_sessions[channel_id] 
                if s != exclude_session and s.user and isinstance(s, WebSocketClientSession) and not s.ws.closed
            ]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    
    async def broadcast_to_all(self, message: str, exclude_session: Optional[BaseSession] = None):
        tasks = [
            s.send(message) 
            for s in self.sessions 
            if s != exclude_session and s.user and isinstance(s, WebSocketClientSession) and not s.ws.closed
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_all_registered_users_status(self, exclude_session: Optional[BaseSession] = None):
        all_users_with_status = await self.user_manager.get_all_registered_users()
        msg = proto.create_message(proto.MSG_TYPE_USER_LIST_UPDATE, {"users": all_users_with_status})
        await self.broadcast_to_all(msg, exclude_session=exclude_session)
        
    async def get_session_by_username(self, username: str) -> Optional[BaseSession]:
        for session in self.sessions:
            if session.user and session.user.username.lower() == username.lower():
                return session
        return None

    async def get_session_by_user_id(self, user_id: int) -> Optional[BaseSession]: 
        for session in self.sessions:
            if session.user and session.user.id == user_id:
                return session
        return None