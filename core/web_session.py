# server/core/web_session.py
import asyncio
from typing import Optional, TYPE_CHECKING
from aiohttp import web

from utils import protocol as proto
from .session import ClientSession # 我们将复用大部分 ClientSession 的逻辑

if TYPE_CHECKING:
    from server import Server

class WebSession:
    """
    适配 aiohttp WebSocket 连接到我们现有会话模型的包装器
    """
    def __init__(self, server: 'Server', request: web.Request):
        self.server = server
        self.request = request
        self.ws: Optional[web.WebSocketResponse] = None
        self.session: Optional[ClientSession] = None # 内部持有一个 ClientSession 实例

    async def handle(self) -> web.WebSocketResponse:
        """处理 WebSocket 连接的完整生命周期"""
        self.ws = web.WebSocketResponse()
        await self.ws.prepare(self.request)

        # 创建一个模拟的 StreamReader/StreamWriter
        # 这允许我们将 WebSocket 接入到现有的 ClientSession 逻辑中
        # aiohttp 的 WebSocket 接口更高级，我们直接使用它
        
        # 创建一个 ClientSession 来管理状态
        # 我们需要一个“假的” reader/writer，因为我们不直接用它们
        class FakeStream:
            def get_extra_info(self, name, default=None): return self.request.remote
            def is_closing(self): return self.ws.closed if self.ws else True
            async def wait_closed(self): pass
            def close(self): pass

        self.session = ClientSession(self.server, FakeStream(), FakeStream())
        self.session.writer.is_closing = self.ws.closed # 动态绑定
        
        # 关键：重写 send 方法，使其通过 WebSocket 发送
        async def websocket_send(message: str):
            if self.ws and not self.ws.closed:
                try:
                    await self.ws.send_str(message)
                except ConnectionResetError:
                    await self.close() # 如果发送时连接已断开
        self.session.send = websocket_send
        
        # 将会话添加到服务器管理列表
        self.server.add_session(self.session)

        try:
            # 同样的处理循环，但数据来自 WebSocket
            async for msg in self.ws:
                if msg.type == web.WSMsgType.TEXT:
                    # 将 WebSocket 消息传递给 ClientSession 的处理逻辑
                    await self.session.handle_message_data(msg.data)
                elif msg.type == web.WSMsgType.ERROR:
                    break
        finally:
            await self.session.close()

        return self.ws