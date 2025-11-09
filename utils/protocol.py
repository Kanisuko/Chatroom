# server/utils/protocol.py
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# C2S (Client to Server)
MSG_TYPE_AUTH_REQUEST = "auth_request"
MSG_TYPE_CHAT_MESSAGE = "chat_message"
MSG_TYPE_COMMAND = "command"
# 移除: MSG_TYPE_UPLOAD_REQUEST 不再通过 WebSocket 发送
# MSG_TYPE_UPLOAD_REQUEST = "upload_request"
MSG_TYPE_DOWNLOAD_REQUEST = "download_request"
# 添加: WebRTC 信令消息类型 (C2S)
MSG_TYPE_JOIN_VOICE = "join_voice"
MSG_TYPE_LEAVE_VOICE = "leave_voice"
MSG_TYPE_WEBRTC_SIGNAL = "webrtc_signal"


# S2C (Server to Client)
MSG_TYPE_AUTH_SUCCESS = "auth_success"
MSG_TYPE_AUTH_FAILURE = "auth_failure"
MSG_TYPE_AUTH_RESUME = "auth_resume"
MSG_TYPE_CHAT_BROADCAST = "chat_broadcast"
MSG_TYPE_SYSTEM_MESSAGE = "system_message"
MSG_TYPE_ERROR_MESSAGE = "error_message"
MSG_TYPE_USER_LIST_UPDATE = "user_list_update"
MSG_TYPE_USER_LIST = "user_list"
MSG_TYPE_WHOAMI_RESPONSE = "whoami_response"
MSG_TYPE_CHANNEL_LIST = "channel_list"
MSG_TYPE_JOIN_SUCCESS = "join_channel_success"
MSG_TYPE_COMMAND_RESPONSE = "command_response"
# 移除: MSG_TYPE_UPLOAD_READY 不再通过 WebSocket 发送
# MSG_TYPE_UPLOAD_READY = "upload_ready"
MSG_TYPE_DOWNLOAD_READY = "download_ready"
MSG_TYPE_FILE_BROADCAST = "file_broadcast"
# 添加: WebRTC 信令消息类型 (S2C)
MSG_TYPE_JOIN_VOICE_SUCCESS = "join_voice_success"
MSG_TYPE_USER_JOINED_VOICE = "user_joined_voice"
MSG_TYPE_USER_LEFT_VOICE = "user_left_voice"

# 移除: 重复定义
# MSG_TYPE_UPLOAD_REQUEST = "upload_request"
# MSG_TYPE_DOWNLOAD_REQUEST = "download_request"
# MSG_TYPE_UPLOAD_READY = "upload_ready"
# MSG_TYPE_DOWNLOAD_READY = "download_ready"
# MSG_TYPE_FILE_BROADCAST = "file_broadcast"

def create_message(msg_type: str, payload: Optional[Dict[str, Any]] = None) -> str:
    if payload is None: payload = {}
    return json.dumps({"type": msg_type, "payload": payload})

def parse_message(message_str: str) -> Optional[Dict[str, Any]]:
    try: return json.loads(message_str)
    except json.JSONDecodeError: return None

def create_system_message(text: str, level: str = "info") -> str:
    """创建系统消息"""
    return create_message(MSG_TYPE_SYSTEM_MESSAGE, {"message": text, "level": level})

def create_error_message(text: str, code: Optional[str] = None) -> str:
    """创建错误消息"""
    payload = {"message": text}
    if code: payload["code"] = code
    return create_message(MSG_TYPE_ERROR_MESSAGE, payload)