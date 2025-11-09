# server/core/sfu.py
import asyncio
import logging
from typing import Dict, Set, Optional
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaRelay

# 移除: 不再使用全局 relay

class VoiceRoom:
    """管理单个语音频道内的所有参与者和媒体轨道"""
    def __init__(self, room_id: int):
        self.room_id = room_id
        self.participants: Dict[int, RTCPeerConnection] = {} 
        self.relays: Dict[str, MediaRelay] = {} # 修改: 管理每个轨道的 relay

    async def add_participant(self, user_id: int, pc: RTCPeerConnection):
        """添加一个新的参与者到房间"""
        self.participants[user_id] = pc

        @pc.on("track")
        async def on_track(track):
            logging.info(f"[SFU Room {self.room_id}] 用户 {user_id} 的轨道 {track.kind} (id: {track.id}) 到达")
            
            # 修改: 为这个新轨道创建一个专属的 MediaRelay
            relay = MediaRelay()
            relayed_track = relay.subscribe(track)
            self.relays[track.id] = relay # 存储它以便后续清理
            
            # 将这个轨道转发给房间内所有其他的参与者
            for other_user_id, other_pc in self.participants.items():
                if other_user_id != user_id:
                    try:
                        other_pc.addTrack(relayed_track)
                        logging.info(f"[SFU Room {self.room_id}] 已将用户 {user_id} 的轨道 {track.id} 转发给用户 {other_user_id}")
                    except Exception as e:
                        logging.error(f"[SFU Room {self.room_id}] 转发轨道给 {other_user_id} 失败: {e}")

    async def remove_participant(self, user_id: int):
        """从房间移除一个参与者"""
        if user_id in self.participants:
            pc = self.participants.pop(user_id)
            
            # 清理与该用户相关的所有 relay
            # 注意：这是一个简化的清理，更复杂的场景可能需要跟踪哪个用户产生了哪个track
            # 但在当前 SFU 模型中，当用户离开时，其轨道会自动停止，关联的 relay 也就无用了。
            
            if pc.connectionState != "closed":
                await pc.close()
            logging.info(f"[SFU Room {self.room_id}] 用户 {user_id} 已从房间移除")


class SFUServer:
    """管理所有的语音房间"""
    def __init__(self, host_ip: str = None, ip_family: str = 'any'):
        self.rooms: Dict[int, VoiceRoom] = {}
        self.rtc_configuration = RTCConfiguration(
            iceServers=[
                RTCIceServer(urls="stun:stun.l.google.com:19302")
            ]
        )

    def get_or_create_room(self, room_id: int) -> VoiceRoom:
        """获取或创建一个语音房间"""
        if room_id not in self.rooms:
            logging.info(f"[SFU] 创建新的语音房间: {room_id}")
            self.rooms[room_id] = VoiceRoom(room_id)
        return self.rooms[room_id]

    async def join_room(self, room_id: int, user_id: int) -> RTCPeerConnection:
        """处理用户加入房间的逻辑，返回一个新的 PeerConnection"""
        room = self.get_or_create_room(room_id)
        
        pc = RTCPeerConnection(configuration=self.rtc_configuration)
        
        await room.add_participant(user_id, pc)
        
        return pc

    async def leave_room(self, room_id: int, user_id: int):
        """处理用户离开房间的逻辑"""
        if room_id in self.rooms:
            room = self.rooms[room_id]
            await room.remove_participant(user_id)
            if not room.participants:
                logging.info(f"[SFU] 房间 {room_id} 已空，将被移除")
                del self.rooms[room_id]