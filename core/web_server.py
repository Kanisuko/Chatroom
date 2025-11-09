import asyncio
import logging
import os
import base64
import uuid
from aiohttp import web
import aiohttp_jinja2
import jinja2
from typing import TYPE_CHECKING, Optional

from utils.database import db_manager
from core.user import User
from core.session import WebSocketClientSession
from utils.config import config

if TYPE_CHECKING:
    from server import Server

DEFAULT_AVATAR_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
DEFAULT_AVATAR_DATA = base64.b64decode(DEFAULT_AVATAR_BASE64 )

async def default_avatar_handler(request: web.Request):
    try:
        avatar_path = 'web/static/assets/default_avatar.png'
        if not os.path.exists(avatar_path):
             os.makedirs(os.path.dirname(avatar_path), exist_ok=True)
             with open(avatar_path, 'wb') as f:
                 f.write(DEFAULT_AVATAR_DATA)
        
        with open(avatar_path, 'rb') as f:
            return web.Response(body=f.read(), content_type="image/png")
    except FileNotFoundError:
         return web.Response(body=DEFAULT_AVATAR_DATA, content_type="image/png")


async def get_user_from_request(request: web.Request) -> Optional[User]:
    """
    从请求的 Authorization 头、Cookie 或查询参数中获取 session token 并验证用户。
    """
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    if not token:
        token = request.cookies.get("session_token")

    if not token:
        token = request.query.get("token")

    if not token:
        return None

    session_data = await db_manager.fetchone("SELECT user_id FROM sessions WHERE token = ?", (token,))
    if not session_data:
        return None
        
    user_data = await db_manager.fetchone("SELECT id, username, hashed_password, email, is_verified, login_otp_enabled, avatar_filename, display_name FROM users WHERE id = ?", (session_data['user_id'],))
    if not user_data:
        return None
    
    roles = await request.app['server'].user_manager.get_user_roles(user_data['id'])
    return request.app['server'].user_manager._create_user_from_data(user_data, roles)


async def upload_avatar_handler(request: web.Request):
    server: Server = request.app['server']
    user = await get_user_from_request(request)
    if not user:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    try:
        data = await request.post()
        avatar_file = data.get('avatar')
        if not avatar_file or not avatar_file.file:
            return web.json_response({"error": "No file uploaded"}, status=400)
        
        max_size = 2 * 1024 * 1024
        avatar_file.file.seek(0, 2) 
        if avatar_file.file.tell() > max_size:
            return web.json_response({"error": "File size exceeds 2MB"}, status=413)
        avatar_file.file.seek(0)
        
        allowed_types = ['image/jpeg', 'image/png', 'image/gif']
        if avatar_file.content_type not in allowed_types:
            return web.json_response({"error": "Invalid file type. Only JPEG, PNG, GIF are allowed."}, status=400)
        
        ext = os.path.splitext(avatar_file.filename)[1]
        stored_filename = f"{user.id}_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join('uploads', 'avatars', stored_filename)
        
        with open(filepath, 'wb') as f:
            f.write(avatar_file.file.read())
        
        await db_manager.execute("UPDATE users SET avatar_filename = ? WHERE id = ?", (stored_filename, user.id))
        
        session = await server.get_session_by_username(user.username)
        if session and session.user:
            session.user.avatar_filename = stored_filename
            await server.broadcast_all_registered_users_status() 

        avatar_url = f"/uploads/avatars/{stored_filename}"
        logging.info(f"用户 '{user.display_name or user.username}' 成功上传了新头像: {stored_filename}")
        
        return web.json_response({"success": True, "avatar_url": avatar_url}, status=200)

    except Exception as e:
        logging.error(f"处理头像上传时出错: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)

async def upload_file_handler(request: web.Request):
    server: Server = request.app['server']
    user = await get_user_from_request(request)
    if not user:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    try:
        data = await request.post()
        file_part = data.get('file')
        channel_id_str = data.get('channel_id')
        client_msg_id = data.get('client_msg_id')

        if not file_part or not hasattr(file_part, 'file'):
            return web.json_response({"error": "未找到文件部分。"}, status=400)
        if not channel_id_str:
            return web.json_response({"error": "未指定频道ID。"}, status=400)

        try:
            channel_id = int(channel_id_str)
        except ValueError:
            return web.json_response({"error": "无效的频道ID格式。"}, status=400)

        target_channel = server.channel_manager.get_channel_by_id(channel_id)
        if not target_channel:
            return web.json_response({"error": "目标频道不存在。"}, status=404)
        
        original_filename = file_part.filename
        file_data = file_part.file.read()

        if not file_data:
            return web.json_response({"error": "文件内容为空。"}, status=400)

        success, message, file_info = await server.file_manager.handle_http_upload(
            user_id=user.id, 
            current_channel_id=channel_id, 
            original_filename=original_filename, 
            file_data=file_data,
            client_msg_id=client_msg_id
         )

        if success:
            return web.json_response({"success": True, "message": message, "file_info": file_info}, status=200)
        else:
            return web.json_response({"error": message}, status=500)

    except Exception as e:
        logging.error(f"处理文件上传时出错 (HTTP): {e}", exc_info=True)
        return web.json_response({"error": "内部服务器错误"}, status=500)


async def websocket_handler(request: web.Request):
    server: Server = request.app['server']
    
    peername = request.remote 
    ws = web.WebSocketResponse(heartbeat=10)
    await ws.prepare(request)
    
    session = WebSocketClientSession(server, ws, peername) 
    server.add_session(session)
    
    await session.handle_session()

    logging.info(f"WebSocket 处理器完成 {session.peername}")
    return ws

async def index_handler(request: web.Request):
    user = await get_user_from_request(request)
    if user:
        return web.HTTPFound('/app')
    else:
        return web.HTTPFound('/login')

@aiohttp_jinja2.template('login.html')
async def login_page_handler(request: web.Request):
    user = await get_user_from_request(request)
    if user:
        return web.HTTPFound('/app')
    ws_protocol = "wss" if config.get('server.web_server.tls.enabled') else "ws"
    # 修改: 不再传递 host 和 port
    return {"ws_protocol": ws_protocol}

@aiohttp_jinja2.template('app.html')
async def app_page_handler(request: web.Request):
    user = await get_user_from_request(request)
    if not user:
        return web.HTTPFound('/login')
    ws_protocol = "wss" if config.get('server.web_server.tls.enabled') else "ws"
    # 修改: 不再传递 host 和 port
    return {"ws_protocol": ws_protocol}


def setup_web_server(server: 'Server') -> web.Application:
    app = web.Application(); app['server'] = server
    
    web_dir = 'web'
    static_dir = os.path.join(web_dir, 'static')
    os.makedirs(os.path.join(static_dir, 'assets'), exist_ok=True)
    os.makedirs(os.path.join(static_dir, 'css'), exist_ok=True)
    os.makedirs(os.path.join(static_dir, 'js'), exist_ok=True)
    
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(web_dir ))
    
    app.router.add_get('/', index_handler)
    app.router.add_get('/login', login_page_handler)
    app.router.add_get('/app', app_page_handler)
    app.router.add_get('/ws', websocket_handler)

    app.router.add_post('/api/user/avatar', upload_avatar_handler)
    app.router.add_post('/api/files/upload', upload_file_handler)
    
    app.router.add_get('/static/assets/default_avatar.png', default_avatar_handler)
    app.router.add_static('/static/', path=static_dir, name='static')
    app.router.add_static('/uploads/', path='uploads', name='uploads')
    
    logging.info("aiohttp Web 服务器路由已设置" )
    return app