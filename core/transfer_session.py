# server/core/transfer_session.py
import asyncio
import logging
import uuid
import os # 新增
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from utils.database import db_manager
from utils import protocol as proto

if TYPE_CHECKING:
    from .session import ClientSession
    from .file import FileManager
    from server import Server

class TransferSession:
    # ... (__init__, start, handle_connection) ...
    def __init__(self, file_manager: 'FileManager', client_session: 'ClientSession', transfer_type: str, file_info: dict):
        self.file_manager = file_manager
        self.client_session = client_session
        self.transfer_type = transfer_type
        self.file_info = file_info
        self.transfer_id = str(uuid.uuid4())
        self.server: asyncio.Server | None = None

    async def start(self, host: str) -> tuple[int, str]:
        self.server = await asyncio.start_server(self.handle_connection, host, 0)
        port = self.server.sockets[0].getsockname()[1]
        logging.info(f"[{self.transfer_id[:8]}] 文件传输监听器已在端口 {port} 启动")
        return port, self.transfer_id

    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peername = writer.get_extra_info('peername')
        logging.info(f"[{self.transfer_id[:8]}] 收到来自 {peername} 的数据连接")
        try:
            received_id = (await asyncio.wait_for(reader.readexactly(36), timeout=5.0)).decode()
            if received_id != self.transfer_id:
                raise ValueError("传输ID不匹配")

            if self.transfer_type == "upload":
                await self.handle_upload(reader, writer)
            elif self.transfer_type == "download":
                await self.handle_download(reader, writer)
        except Exception as e:
            logging.error(f"[{self.transfer_id[:8]}] 传输失败: {e}")
        finally:
            writer.close()
            try: await writer.wait_closed()
            except Exception: pass
            self.file_manager.active_transfers.pop(self.transfer_id, None)
            if self.server: self.server.close()
            logging.info(f"[{self.transfer_id[:8]}] 传输会话已关闭")
            
    async def handle_upload(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理文件上传"""
        stored_filename = str(uuid.uuid4())
        # 添加: 双重保险，确保目录存在
        os.makedirs("uploads", exist_ok=True)
        filepath = f"uploads/{stored_filename}"
        bytes_written = 0
        
        with open(filepath, "wb") as f:
            while True:
                chunk = await reader.read(8192)
                if not chunk:
                    break
                f.write(chunk)
                bytes_written += len(chunk)

        if bytes_written != self.file_info['filesize']:
            os.remove(filepath)
            raise ValueError(f"文件大小不匹配: 预期 {self.file_info['filesize']}, 收到 {bytes_written}")

        upload_time = datetime.now(timezone.utc).isoformat()
        # 将文件信息和聊天消息一起存入数据库
        await db_manager.execute(
            """INSERT INTO files (channel_id, uploader_id, original_filename, stored_filename, filesize, upload_time)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (self.client_session.current_channel.id, self.client_session.user.id, self.file_info['filename'], stored_filename, bytes_written, upload_time)
        )
        file_id = await db_manager.fetchval("SELECT last_insert_rowid()")
        
        # 广播文件消息
        file_message_content = f"上传了文件: {self.file_info['filename']} (ID: {file_id}, 大小: {bytes_written} bytes)"
        await db_manager.add_message(
            self.client_session.current_channel.id,
            self.client_session.user.id,
            self.client_session.user.username,
            f"[文件] {self.file_info['filename']}"
        )
        broadcast_json = proto.create_message(proto.MSG_TYPE_FILE_BROADCAST, {"message": file_message_content})
        await self.file_manager.server.broadcast_to_channel(self.client_session.current_channel.id, broadcast_json)
        logging.info(f"[{self.transfer_id[:8]}] 文件 '{self.file_info['filename']}' 上传成功")

    async def handle_download(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理文件下载"""
        filepath = f"uploads/{self.file_info['stored_filename']}"
        if not os.path.exists(filepath):
            raise FileNotFoundError("服务器磁盘上找不到文件")
            
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                writer.write(chunk)
                await writer.drain()
        logging.info(f"[{self.transfer_id[:8]}] 文件 '{self.file_info['original_filename']}' 下载发送完成")