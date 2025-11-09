import logging
from typing import Dict, Optional, List, Any, Tuple

from utils.database import db_manager

class Channel:
    def __init__(self, id: int, name: str, topic: Optional[str] = None, created_at: Optional[str] = None, type: str = 'text'): # 修改
        self.id = id
        self.name = name
        self.topic = topic
        self.created_at = created_at
        self.type = type # 添加

class ChannelManager:
    """
    负责从数据库加载和管理频道
    """
    def __init__(self):
        # 修改: 增加一个按 ID 索引的字典，以提高查找效率
        self.channels_by_name: Dict[str, Channel] = {}
        self.channels_by_id: Dict[int, Channel] = {}
        self.default_channel: Optional[Channel] = None

    async def initialize_channels(self):
        """从数据库加载频道，如果为空则创建默认频道"""
        all_channels_data = await db_manager.fetchall("SELECT * FROM channels")
        if not all_channels_data:
            logging.info("数据库中没有频道，正在创建默认的 '#general' 频道")
            await self.create_channel("general", "默认聊天频道")
            all_channels_data = await db_manager.fetchall("SELECT * FROM channels")

        for channel_data in all_channels_data:
            channel = Channel(**channel_data)
            # 同时在两个字典中存储
            self.channels_by_name[channel.name.lower()] = channel
            self.channels_by_id[channel.id] = channel
        
        if self.channels_by_name:
            self.default_channel = list(self.channels_by_name.values())[0]
            logging.info(f"已加载 {len(self.channels_by_name)} 个频道，默认频道: #{self.default_channel.name}")

    async def create_channel(self, name: str, topic: Optional[str] = None, channel_type: str = 'text') -> Tuple[bool, str, Optional[Channel]]: # 修改
        """创建新频道，并返回 Channel 对象"""
        name = name.lower()
        if not (2 <= len(name) <= 20 and name.isalnum()):
            return False, "频道名称必须为2-20位的字母和数字", None
        if name in self.channels_by_name:
            return False, f"频道 #{name} 已存在", None
            
        await db_manager.execute("INSERT INTO channels (name, topic, type) VALUES (?, ?, ?)", (name, topic, channel_type)) # 修改
        new_channel_data = await db_manager.fetchone("SELECT * FROM channels WHERE name = ?", (name,))
        if new_channel_data:
            channel = Channel(**new_channel_data)
            self.channels_by_name[name] = channel
            self.channels_by_id[channel.id] = channel
            logging.info(f"新频道 #{name} (类型: {channel_type}) 已创建") # 修改
            return True, f"频道 #{name} 已成功创建", channel
        return False, "创建频道失败", None

    async def delete_channel(self, name: str) -> Tuple[bool, str]:
        name = name.lower()
        if name not in self.channels_by_name:
            return False, f"频道 #{name} 不存在"
        if self.default_channel and name == self.default_channel.name.lower():
            return False, "不能删除默认频道"
        
        channel = self.channels_by_name[name]
        await db_manager.execute("DELETE FROM channels WHERE id = ?", (channel.id,))
        del self.channels_by_name[name]
        del self.channels_by_id[channel.id]
        logging.info(f"频道 #{name} 已被删除")
        return True, f"频道 #{name} 已成功删除"

    def get_channel(self, name: str) -> Optional[Channel]:
        """通过名称获取频道"""
        return self.channels_by_name.get(name.lower())

    # **修复点：添加一个通过 ID 获取频道的新方法**
    def get_channel_by_id(self, channel_id: int) -> Optional[Channel]:
        """通过 ID 获取频道"""
        return self.channels_by_id.get(channel_id)

    def get_all_channels(self) -> List[Dict[str, Any]]:
        return [{"id": ch.id, "name": ch.name, "topic": ch.topic, "type": ch.type} for ch in self.channels_by_name.values()] # 修改