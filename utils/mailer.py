# server/utils/mailer.py
import asyncio
import logging
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr # 新增: 导入专门处理地址格式的工具
import aiosmtplib

from .config import config
from .database import db_manager

async def get_smtp_password() -> str:
    password_row = await db_manager.fetchone("SELECT value FROM settings WHERE key = 'smtp_password'")
    return password_row['value'] if password_row else ""

async def send_email(to_email: str, subject: str, content: str) -> bool:
    if not config.get('security.email_verification.enabled'):
        return False

    host = config.get('security.email_verification.smtp_host')
    port = config.get('security.email_verification.smtp_port')
    use_ssl = config.get('security.email_verification.smtp_use_ssl')
    username = config.get('security.email_verification.smtp_username')
    sender_email = config.get('security.email_verification.sender_email')
    password = await get_smtp_password()

    if not all([host, port, username, password, sender_email]):
        logging.error("SMTP 配置不完整，无法发送邮件")
        return False

    message = MIMEText(content, 'html', 'utf-8')
    
    # 修改: 使用 formataddr 来创建最安全、最符合 RFC 标准的 From 头
    # 第一个参数是显示名，第二个是邮箱地址
    message['From'] = formataddr((str(Header("ChatRoom", 'utf-8')), sender_email))
    
    message['To'] = to_email
    message['Subject'] = Header(subject, 'utf-8')

    try:
        await aiosmtplib.send(
            message,
            sender=sender_email,
            recipients=[to_email],
            hostname=host,
            port=port,
            use_tls=use_ssl,
            username=username,
            password=password
        )
        logging.info(f"邮件已成功发送至 {to_email}")
        return True
    except aiosmtplib.SMTPException as e:
        logging.error(f"发送邮件至 {to_email} 失败 (SMTP Error): {e.code} - {e.message}")
        return False
    except Exception as e:
        logging.error(f"发送邮件至 {to_email} 失败 (General Error): {e}")
        return False