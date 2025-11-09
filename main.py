# server/main.py
import asyncio
import logging
import os
import ssl

from server import Server
from utils.logger import setup_logger
from utils.config import config
from utils.migration import run_migrations
from utils.database import db_manager
from core.web_server import setup_web_server
from aiohttp import web
from utils import security

# 添加: 导入 BaseSession 和 WebSocketClientSession
from core.session import BaseSession, WebSocketClientSession, TcpClientSession

async def main():
    setup_logger(
        log_dir=config.get('logging.dir'),
        level=config.get('logging.level'),
        debug=config.get('logging.debug')
    )
    
    await run_migrations(db_manager)

    server = Server()
    await server.initialize()

    tasks = []
    web_runner = None
    
    main_tasks = []

    if config.get('server.web_server.enabled'):
        web_app = setup_web_server(server)
        web_runner = web.AppRunner(web_app)
        await web_runner.setup()
        web_host = config.get('server.web_server.host')
        web_port = config.get('server.web_server.port')
        web_ssl_context = security.create_ssl_context_from_path('server.web_server.tls')
        web_site = web.TCPSite(web_runner, web_host, web_port, ssl_context=web_ssl_context)
        main_tasks.append(web_site.start())
        
        web_protocol = "https" if web_ssl_context else "http"
        display_host = 'localhost' if web_host == '0.0.0.0' else web_host
        logging.info(f"Web 服务器准备就绪，请访问 {web_protocol}://{display_host}:{web_port}")

    if config.get('server.tcp_server.enabled'):
        # 修正: TCP 服务器的启动逻辑，现在它将启动并处理 TCP 连接
        main_tasks.append(server.start_tcp_server())
        logging.info("TCP 服务器已启用。")


    if not main_tasks:
        logging.error("所有服务器均未在 config.yml 中启用，程序退出。")
        return

    try:
        await asyncio.gather(*main_tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logging.info("开始关闭所有服务...")
        if web_runner:
            await web_runner.cleanup()
        await server.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    logging.info("程序已退出")