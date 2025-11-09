import logging
import os
import uuid
import json
from typing import TYPE_CHECKING, Dict, Tuple, Any, Optional
from datetime import datetime, timezone

from .transfer_session import TransferSession
from utils import protocol as proto
from utils.database import db_manager
from aiohttp import web
from utils import config

if TYPE_CHECKING:
    from server import Server
    from .session import BaseSession
    from .user import UserManager

class FileManager:
    def __init__(self, server: 'Server' ):
        self.server = server
        self.active_transfers: Dict[str, TransferSession] = {}
        os.makedirs("uploads", exist_ok=True)
        os.makedirs("uploads/avatars", exist_ok=True)

    async def request_download(self, session: 'BaseSession', file_id: int):
        if not all([session.user, session.current_channel]):
            await session.send(proto.create_error_message("无效会话")); return
            
        file_data = await db_manager.fetchone("SELECT * FROM files WHERE id = ? AND channel_id = ?", (file_id, session.current_channel.id))
        if not file_data:
            await session.send(proto.create_error_message(f"文件ID {file_id} 在当前频道不存在"))
            return
            
        transfer = TransferSession(self, session, "download", dict(file_data))
        try:
            server_host = config.get('server.web_server.host', '0.0.0.0')
            port, transfer_id = await transfer.start(server_host)
            self.active_transfers[transfer_id] = transfer 

            payload = {"transfer_id": transfer_id, "port": port, "filename": file_data['original_filename'], "filesize": file_data['filesize']}
            await session.send(proto.create_message(proto.MSG_TYPE_DOWNLOAD_READY, payload))
        except Exception as e:
            logging.error(f"启动下载监听器失败: {e}")
            await session.send(proto.create_error_message("无法准备下载"))

    async def list_files(self, session: 'BaseSession'):
        if not session.current_channel: return
        files_data = await db_manager.fetchall("SELECT id, original_filename, filesize, uploader_id FROM files WHERE channel_id = ?", (session.current_channel.id,))
        await session.send(proto.create_message("file_list_response", {"files": files_data}))

    async def delete_file(self, session: 'BaseSession', file_id: int) -> Tuple[bool, str]:
        if not all([session.user, session.current_channel]):
            return False, "无效会话"
            
        file_data = await db_manager.fetchone("SELECT * FROM files WHERE id = ? AND channel_id = ?", (file_id, session.current_channel.id))
        if not file_data:
            return False, f"文件ID {file_id} 在当前频道不存在"

        try:
            filepath = f"uploads/{file_data['stored_filename']}"
            if os.path.exists(filepath):
                os.remove(filepath)
                logging.info(f"用户 {session.user.display_name or session.user.username} 删除了物理文件: {filepath}")
        except OSError as e:
            logging.error(f"删除物理文件 {filepath} 失败: {e}")
            return False, "删除文件时发生磁盘错误"

        await db_manager.execute("DELETE FROM files WHERE id = ?", (file_id,))
        
        uploader_display_name = session.user.display_name or session.user.username
        delete_msg = f"{uploader_display_name} 删除了文件: {file_data['original_filename']}"
        await self.server.broadcast_to_channel(
            session.current_channel.id,
            proto.create_message(proto.MSG_TYPE_SYSTEM_MESSAGE, {"message": delete_msg})
        )
        return True, f"文件ID {file_id} 已成功删除"

    # 修改: 函数签名添加 client_msg_id
    async def handle_http_upload(self, user_id: int, current_channel_id: int, original_filename: str, file_data: bytes, client_msg_id: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        if not original_filename or not file_data:
            return False, "文件名或文件数据为空。", None
        
        os.makedirs("uploads", exist_ok=True)
        
        stored_filename = f"{uuid.uuid4().hex}_{original_filename}"
        filepath = os.path.join('uploads', stored_filename)
        
        try:
            with open(filepath, 'wb') as f:
                f.write(file_data)
            
            filesize = len(file_data)
            upload_time = datetime.now(timezone.utc).isoformat()

            await db_manager.execute(
                """INSERT INTO files (channel_id, uploader_id, original_filename, stored_filename, filesize, upload_time)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (current_channel_id, user_id, original_filename, stored_filename, filesize, upload_time)
            )
            file_id = await db_manager.fetchval("SELECT last_insert_rowid()")
            
            uploader_user = await self.server.user_manager.get_user_by_id(user_id)
            if not uploader_user:
                return False, "上传用户不存在", None

            message_content = json.dumps({
                "type": "file",
                "file_id": file_id,
                "name": original_filename,
                "size": filesize,
                "url": f"/uploads/{stored_filename}"
            })

            await db_manager.add_message(
                channel_id=current_channel_id,
                user_id=user_id,
                username=uploader_user.username,
                content=message_content
            )

            broadcast_payload = {
                "sender_username": uploader_user.username,
                "sender_display_name": uploader_user.display_name or uploader_user.username,
                "message": message_content,
                "timestamp": upload_time,
                "avatar_url": self.server._format_user_info(uploader_user).get("avatar_url")
            }
            
            # 添加: 将 client_msg_id 添加到广播 payload 中
            if client_msg_id:
                broadcast_payload["client_msg_id"] = client_msg_id

            await self.server.broadcast_to_channel(
                current_channel_id,
                proto.create_message(proto.MSG_TYPE_CHAT_BROADCAST, broadcast_payload)
            )

            logging.info(f"用户 {uploader_user.display_name or uploader_user.username} 成功上传了文件: {original_filename}")
            return True, "文件上传成功", {"id": file_id, "filename": original_filename, "filesize": filesize}

        except Exception as e:
            logging.error(f"处理文件上传失败: {e}", exc_info=True)
            if os.path.exists(filepath):
                os.remove(filepath)
            return False, f"文件上传失败: {e}", None