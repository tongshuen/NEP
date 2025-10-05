import asyncio
import logging
from typing import Dict, Any

from utils.auth import authenticate
from utils.rate_limiter import RateLimiter
from models.mail import EmailMessage

logger = logging.getLogger(__name__)

class NEPServer:
    def __init__(self, config: Dict[str, Any], storage):
        self.config = config
        self.storage = storage
        self.rate_limiter = RateLimiter(config['rate_limits'])
        self.server = None

    async def handle_client(self, reader, writer):
        """处理客户端连接"""
        client_addr = writer.get_extra_info('peername')
        logger.info(f"New NEP connection from {client_addr}")
        
        try:
            # 认证
            auth_data = await reader.read(1024)
            session = await authenticate(auth_data, self.storage)
            if not session:
                writer.write(b"AUTH_FAILED")
                await writer.drain()
                writer.close()
                return
            
            writer.write(b"AUTH_OK")
            await writer.drain()
            
            # 处理客户端请求
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                    
                await self.process_request(data, session, writer)
                
        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def process_request(self, data: bytes, session: Dict[str, Any], writer):
        """处理客户端请求"""
        try:
            # 解析请求 (这里简化为JSON，实际可以使用更高效的二进制协议)
            import json
            request = json.loads(data.decode())
            
            # 检查速率限制
            if not self.rate_limiter.check_limit(session['user_id'], request['type']):
                response = {'status': 'error', 'code': 'rate_limit_exceeded'}
                writer.write(json.dumps(response).encode())
                await writer.drain()
                return
                
            # 处理不同类型的请求
            if request['type'] == 'send':
                await self.handle_send(request, session, writer)
            elif request['type'] == 'list':
                await self.handle_list(request, session, writer)
            elif request['type'] == 'fetch':
                await self.handle_fetch(request, session, writer)
            elif request['type'] == 'update':
                await self.handle_update(request, session, writer)
            else:
                response = {'status': 'error', 'code': 'invalid_request'}
                writer.write(json.dumps(response).encode())
                await writer.drain()
                
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            response = {'status': 'error', 'code': 'server_error'}
            writer.write(json.dumps(response).encode())
            await writer.drain()

    async def handle_send(self, request: Dict[str, Any], session: Dict[str, Any], writer):
        """处理发送邮件请求"""
        # 验证请求数据
        if not all(k in request for k in ['to', 'subject', 'body']):
            response = {'status': 'error', 'code': 'invalid_data'}
            writer.write(json.dumps(response).encode())
            await writer.drain()
            return
            
        # 创建邮件对象
        email = EmailMessage(
            from_addr=session['email'],
            to_addrs=request['to'],
            subject=request['subject'],
            body=request['body'],
            attachments=request.get('attachments', [])
        )
        
        # 存储邮件
        try:
            await self.storage.store_email(email)
            response = {'status': 'ok', 'message_id': email.message_id}
        except Exception as e:
            logger.error(f"Error storing email: {e}")
            response = {'status': 'error', 'code': 'storage_error'}
            
        writer.write(json.dumps(response).encode())
        await writer.drain()

    async def handle_list(self, request: Dict[str, Any], session: Dict[str, Any], writer):
        """处理列出邮件请求"""
        mailbox = request.get('mailbox', 'INBOX')
        limit = request.get('limit', 50)
        offset = request.get('offset', 0)
        
        try:
            emails = await self.storage.list_emails(session['email'], mailbox, limit, offset)
            response = {
                'status': 'ok',
                'emails': [email.to_dict() for email in emails]
            }
        except Exception as e:
            logger.error(f"Error listing emails: {e}")
            response = {'status': 'error', 'code': 'storage_error'}
            
        writer.write(json.dumps(response).encode())
        await writer.drain()

    async def start(self):
        """启动NEP服务器"""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.config['host'],
            self.config['port']
        )
        
        logger.info(f"NEP server started on {self.config['host']}:{self.config['port']}")
        
        async with self.server:
            await self.server.serve_forever()
