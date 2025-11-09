from typing import TYPE_CHECKING, Dict, Callable, List
import logging

from utils.i18n import translator
from utils import protocol as proto
from .constants import *

if TYPE_CHECKING:
    from core.session import BaseSession
    from server import Server

class CommandHandler:
    def __init__(self, server: 'Server'):
        self.server = server
        self.command_to_action_map = {
            "kick": "kick_user",
            "createchannel": "create_channel",
            "createvoicechannel": "create_voice_channel", # 添加
            "deletechannel": "delete_channel",
            "join": "join_channel",
            "deletefile": "delete_file",
        }
        self.commands: Dict[str, Callable] = {
            "help": self.server.action_handler.show_help,
            "list": self.server.action_handler.list_channel_users,
            "whoami": self.server.action_handler.show_whoami,
            "channels": self.server.action_handler.list_channels,
            "files": self.server.action_handler.list_files,
            # 移除: "verify": self.handle_verify_command,
            **{cmd: self.handle_generic_command for cmd in self.command_to_action_map.keys()}
        }
    
    async def handle_generic_command(self, session: 'BaseSession', command: str, args: List[str]):
        """一个通用的处理器，用于需要参数的动作"""
        action_name = self.command_to_action_map.get(command)
        if not action_name:
            await session.send(proto.create_error_message(f"未知命令: {command}"))
            return
            
        action = getattr(self.server.action_handler, action_name, None)
        if not action:
            logging.error(f"Action '{action_name}' not found in ActionHandler for command '{command}'")
            await session.send(proto.create_error_message("执行命令时发生内部错误"))
            return

        # 参数数量检查
        if command in ["kick", "createchannel", "deletechannel", "join", "createvoicechannel"] and len(args) == 1: # 修改
            await action(session, args[0])
        elif command == "deletefile" and len(args) == 1:
            try:
                await action(session, int(args[0]))
            except ValueError:
                await session.send(proto.create_error_message("文件ID必须是数字"))
        else:
             await session.send(proto.create_error_message(f"'{command}' 命令的参数数量不正确"))

    # 移除: handle_verify_command 方法，因为逻辑已移至 session.py
    # async def handle_verify_command(self, session: 'BaseSession', args: List[str]):
    #     if len(args) != 2:
    #         usage = "/verify <username> <token>"
    #         await session.send(proto.create_error_message(f"用法: {usage}"))
    #         return
    #     username, token = args[0], args[1]
    #     success, message = await self.server.action_handler.verify_email_token(username, token)
    #     response_func = proto.create_system_message if success else proto.create_error_message
    #     await session.send(response_func(message))

    async def handle(self, session: 'BaseSession', payload: dict):
        command = payload.get("command", "").lower()
        args = payload.get("args", [])
        
        # 移除: 对 verify 命令的特殊处理
        # if command == 'verify':
        #     await self.handle_verify_command(session, args)
        #     return
            
        if not session.user:
            await session.send(proto.create_error_message("请先登录")); return

        handler = self.commands.get(command)
        if not handler:
            await session.send(proto.create_error_message(translator.t('command_not_found', command=command))); return
        
        try:
            if command in self.command_to_action_map:
                await handler(session, command, args)
            else:
                await handler(session)
        except Exception as e:
            logging.error(f"执行命令 '{command}' 时出错: {e}", exc_info=True)
            await session.send(proto.create_error_message(f"执行命令时发生内部错误"))