import asyncio
import logging
from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone
from abc import ABC, abstractmethod

from utils import protocol as proto
from utils.config import config
from utils.database import db_manager
from core.user import User

if TYPE_CHECKING:
    from server import Server
    from core.channel import Channel
    from aiohttp import web
    from aiortc import RTCPeerConnection, RTCSessionDescription # 添加

from aiohttp import web_ws

class BaseSession(ABC):
    def __init__(self, server: 'Server', peername: str, session_type: str):
        self.server = server
        self.user: Optional[User] = None
        self.current_channel: Optional[Channel] = None
        self.current_voice_channel: Optional[Channel] = None 
        self.rtc_peer_connection: Optional['RTCPeerConnection'] = None # 添加
        self.peername = peername 
        self.lang = config.get('server.language', 'en_US')
        self.is_resumed_session = False
        self.session_type = session_type
        self._main_loop_task: Optional[asyncio.Task] = None

    @abstractmethod
    async def handle_session(self):
        """处理会话的主循环"""
        pass

    @abstractmethod
    async def send(self, message: str):
        """向客户端发送消息"""
        pass

    @abstractmethod
    async def close(self):
        """关闭会话"""
        pass

    async def _handle_message_data(self, message_data: str):
        json_msg = proto.parse_message(message_data)
        if not json_msg: return

        msg_type, payload = json_msg.get("type"), json_msg.get("payload", {})
        
        if not self.user:
            if msg_type == proto.MSG_TYPE_AUTH_REQUEST:
                success, reason, user, token, is_resume = await self._handle_authentication(payload)
                if success:
                    if user: 
                        self.user = user
                        self.is_resumed_session = is_resume
                    
                    response_payload = {"message": reason}
                    if token: response_payload["token"] = token
                    if user:
                        user_info_with_roles = self.server._format_user_info(user)
                        response_payload["user"] = user_info_with_roles
                    
                    await self.send(proto.create_message(proto.MSG_TYPE_AUTH_SUCCESS, response_payload))
                    
                    if self.user:
                        all_channels = self.server.channel_manager.get_all_channels()
                        await self.send(proto.create_message("channel_list_update", {"channels": all_channels}))
                        await self.server.join_default_channel(self)
                    else:
                        await self.close()

                else:
                    await self.send(create_auth_failure_message(reason))
            else:
                await self.send(proto.create_error_message("请先登录或验证"))
        else:
            log_user_name = self.user.display_name if self.user.display_name else self.user.username
            log_channel_name = self.current_channel.name if self.current_channel else 'N/A'
            log_prefix = f"[#{log_channel_name}] [{log_user_name}]:"
            
            if msg_type == proto.MSG_TYPE_COMMAND:
                if config.get('logging.show_user_commands'): logging.info(f"{log_prefix} [命令] {payload}")
                await self.server.command_handler.handle(self, payload)
            elif msg_type == proto.MSG_TYPE_CHAT_MESSAGE:
                content = payload.get("message", "")
                if not content: return 
                if config.get('logging.show_user_chats'): logging.info(f"{log_prefix} [聊天] {content}")
                if self.current_channel and self.user:
                    await db_manager.add_message(self.current_channel.id, self.user.id, self.user.username, content)
                    
                    client_msg_id = payload.get("client_msg_id")
                    broadcast_payload = {
                        "sender_username": self.user.username,
                        "sender_display_name": self.user.display_name if self.user.display_name else self.user.username,
                        "message": content,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "avatar_url": self.server._format_user_info(self.user).get("avatar_url")
                    }
                    if client_msg_id:
                        broadcast_payload["client_msg_id"] = client_msg_id
                        
                    broadcast = proto.create_message(proto.MSG_TYPE_CHAT_BROADCAST, broadcast_payload)
                    await self.server.broadcast_to_channel(self.current_channel.id, broadcast)
            
            # 修改: 语音信令处理逻辑
            elif msg_type == proto.MSG_TYPE_JOIN_VOICE:
                channel_id = payload.get("channel_id")
                channel = self.server.channel_manager.get_channel_by_id(channel_id)
                if channel:
                    await self.server.join_voice_channel(self, channel)

            elif msg_type == proto.MSG_TYPE_LEAVE_VOICE:
                if self.current_voice_channel:
                    await self.server.leave_voice_channel(self, self.current_voice_channel)

            elif msg_type == proto.MSG_TYPE_WEBRTC_SIGNAL:
                if self.rtc_peer_connection:
                    from aiortc import RTCSessionDescription
                    signal_data = payload.get("data")
                    if signal_data and signal_data.get("type") == "offer":
                        try:
                            offer = RTCSessionDescription(sdp=signal_data["sdp"], type=signal_data["type"])
                            await self.rtc_peer_connection.setRemoteDescription(offer)
                            answer = await self.rtc_peer_connection.createAnswer()
                            await self.rtc_peer_connection.setLocalDescription(answer)
                            
                            response_payload = {
                                "data": {"sdp": self.rtc_peer_connection.localDescription.sdp, "type": self.rtc_peer_connection.localDescription.type}
                            }
                            await self.send(proto.create_message(proto.MSG_TYPE_WEBRTC_SIGNAL, response_payload))
                        except Exception as e:
                            logging.error(f"[SFU] 处理 offer 时出错: {e}", exc_info=True)
                            await self.send(proto.create_error_message(f"WebRTC Offer Error: {e}"))
                    elif signal_data and signal_data.get("type") == "ice_candidate":
                        # 在 aiortc 中，ICE candidate 通常由库自动处理，客户端无需手动发送
                        pass
            
            elif msg_type == proto.MSG_TYPE_DOWNLOAD_REQUEST:
                await self.server.file_manager.request_download(self, payload.get('file_id',0))

    async def _handle_authentication(self, payload: dict) -> tuple[bool, str, Optional[User], Optional[str], bool]:
        action = payload.get("action")
        username = payload.get("username")
        password = payload.get("password")
        email = payload.get("email")
        token = payload.get("token")
        
        if action == "resume":
            if not token: return False, "缺少会话令牌", None, None, False
            success, reason, user, new_token = await self.server.user_manager.resume_session(token, self)
            return success, reason, user, new_token, True
        elif action == "register":
            if not all([username, password, email]):
                return False, "注册信息不完整", None, None, False
            success, reason = await self.server.user_manager.register(username, password, email)
            return success, reason, None, None, False
        elif action == "login":
            if not all([username, password]):
                return False, "登录信息不完整", None, None, False
            success, reason, user, new_token = await self.server.user_manager.login(username, password, self)
            return success, reason, user, new_token, False
        elif action == "verify":
            if not all([username, token]):
                return False, "验证信息不完整", None, None, False
            success, reason = await self.server.action_handler.verify_email_token(username, token)
            return success, reason, None, None, False
        else:
            return False, f"未知认证动作: {action}", None, None, False
    
class WebSocketClientSession(BaseSession):
    def __init__(self, server: 'Server', ws: 'web.WebSocketResponse', peername: str):
        super().__init__(server, peername, session_type='websocket')
        self.ws = ws

    async def handle_session(self):
        self._main_loop_task = asyncio.current_task()
        try:
            async for msg in self.ws:
                if msg.type == web_ws.WSMsgType.TEXT:
                    await self._handle_message_data(msg.data)
                elif msg.type == web_ws.WSMsgType.PING:
                    if config.get('logging.debug'): logging.debug(f"收到来自 {self.peername} 的 WebSocket PING")
                    pass 
                elif msg.type == web_ws.WSMsgType.PONG:
                    if config.get('logging.debug'): logging.debug(f"收到来自 {self.peername} 的 WebSocket PONG")
                elif msg.type == web_ws.WSMsgType.ERROR:
                    logging.error(f"WebSocket 连接错误 {self.peername}: {self.ws.exception()}", exc_info=True)
                    break
                elif msg.type == web_ws.WSMsgType.CLOSE:
                    break
        except asyncio.CancelledError:
            logging.info(f"会话任务 {self.peername} 已取消")
        except ConnectionError as e:
            logging.info(f"会话连接错误 {self.peername}: {e}")
        except Exception as e:
            logging.error(f"会话处理中发生未知错误 {self.peername}: {e}", exc_info=True)
        finally:
            await self.close()

    async def send(self, message: str):
        try:
            if not self.ws.closed:
                if config.get('logging.debug'): logging.debug(f"发送消息到 {self.peername}: {message[:100]}...")
                await self.ws.send_str(message)
        except ConnectionError:
            logging.warning(f"发送消息到 {self.peername} 失败: 连接已关闭")
        except Exception as e:
            logging.error(f"发送消息到 {self.peername} 时发生错误: {e}", exc_info=True)

    async def close(self):
        if config.get('logging.debug'): logging.debug(f"ClientSession.close() 被调用 for {self.peername}")
        self.server.remove_session(self) 
        if not self.ws.closed:
            if config.get('logging.debug'): logging.debug(f"正在关闭 WebSocket 连接 for {self.peername}")
            await self.ws.close()
        
        if self._main_loop_task and not self._main_loop_task.done():
            if config.get('logging.debug'): logging.debug(f"正在取消主循环任务 for {self.peername}")
            self._main_loop_task.cancel()
            try:
                await self._main_loop_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logging.error(f"取消会话任务 {self.peername} 时发生错误: {e}")
        
def create_auth_failure_message(reason: str) -> str:
    return proto.create_message(proto.MSG_TYPE_AUTH_FAILURE, {"message": reason})

class TcpClientSession(BaseSession):
    def __init__(self, server: 'Server', reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peername: str):
        super().__init__(server, peername, session_type='tcp')
        self.reader = reader
        self.writer = writer

    async def handle_session(self):
        self._main_loop_task = asyncio.current_task()
        try:
            auth_timeout_end = asyncio.get_running_loop().time() + 60 
            
            while not self.reader.at_eof():
                try:
                    timeout = None
                    if not self.user:
                        timeout = auth_timeout_end - asyncio.get_running_loop().time()
                        if timeout <= 0:
                            logging.info(f"TCP 认证超时，关闭连接 {self.peername}")
                            await self.send(proto.create_error_message("认证超时"))
                            break
                    else:
                        timeout = 305

                    message_bytes = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
                except asyncio.TimeoutError:
                    if self.user:
                        logging.info(f"TCP 用户 '{self.user.display_name if self.user.display_name else self.user.username}' 空闲超时，关闭连接")
                    else:
                        logging.info(f"TCP 认证超时，关闭连接 {self.peername}")
                    break
                except ConnectionResetError:
                    logging.info(f"TCP 客户端 {self.peername} 连接重置，主动关闭会话")
                    break

                if not message_bytes:
                    if self.user:
                        logging.info(f"TCP 用户 '{self.user.display_name if self.user.display_name else self.user.username}' 优雅断开连接")
                    else:
                        logging.info(f"未认证 TCP 客户端 {self.peername} 优雅断开连接")
                    break

                await self._handle_message_data(message_bytes.decode())
        except asyncio.CancelledError:
            logging.info(f"TCP 会话任务 {self.peername} 已取消")
        except ConnectionError as e:
            logging.info(f"TCP 会话连接错误 {self.peername}: {e}")
        except Exception as e:
            logging.error(f"TCP 会话处理中发生未知错误 {self.peername}: {e}", exc_info=True)
        finally:
            await self.close()

    async def send(self, message: str):
        try:
            if self.writer.is_closing():
                return
            if not message.endswith('\n'):
                message += '\n'
            if config.get('logging.debug'): logging.debug(f"发送消息到 TCP {self.peername}: {message[:100]}...")
            await self.writer.write(message.encode('utf-8'))
            if hasattr(self.writer, 'drain'):
                await self.writer.drain()
        except (ConnectionError, BrokenPipeError, asyncio.CancelledError):
            logging.warning(f"发送消息到 TCP {self.peername} 失败: 连接已关闭")
        except Exception as e:
            logging.error(f"发送消息到 TCP {self.peername} 时发生错误: {e}", exc_info=True)

    async def close(self):
        if config.get('logging.debug'): logging.debug(f"TcpClientSession.close() 被调用 for {self.peername}")
        self.server.remove_session(self)
        if hasattr(self.writer, 'close'):
            if config.get('logging.debug'): logging.debug(f"正在关闭 TCP 连接 for {self.peername}")
            self.writer.close()
        try:
            if hasattr(self.writer, 'wait_closed'):
                await self.writer.wait_closed()
        except Exception:
            pass

        if self._main_loop_task and not self._main_loop_task.done():
            if config.get('logging.debug'): logging.debug(f"正在取消 TCP 主循环任务 for {self.peername}")
            self._main_loop_task.cancel()
            try:
                await self._main_loop_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logging.error(f"取消 TCP 会话任务 {self.peername} 时发生错误: {e}")