import asyncio
import logging
import email
from email.message import EmailMessage as SMTPEmailMessage

from utils.converter import nep_to_smtp, smtp_to_nep
from utils.auth import authenticate_smtp
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class NEPTServer:
    """NEP-T服务器，兼容传统SMTP协议"""
    
    def __init__(self, config: Dict[str, Any], storage):
        self.config = config
        self.storage = storage
        self.rate_limiter = RateLimiter(config['rate_limits'])
        self.server = None

    async def handle_client(self, reader, writer):
        """处理SMTP客户端连接"""
        client_addr = writer.get_extra_info('peername')
        logger.info(f"New NEP-T connection from {client_addr}")
        
        try:
            # SMTP欢迎消息
            writer.write(b"220 NEP-T Server ready\r\n")
            await writer.drain()
            
            # SMTP协议处理
            await self.process_smtp(reader, writer)
                
        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def process_smtp(self, reader, writer):
        """处理SMTP协议"""
        current_email = {
            'from': None,
            'to': [],
            'data': None
        }
        
        while True:
            data = await reader.readuntil(b'\r\n')
            if not data:
                break
                
            line = data.decode().strip()
            logger.debug(f"SMTP command: {line}")
            
            if line.upper().startswith('HELO') or line.upper().startswith('EHLO'):
                writer.write(b"250 Hello\r\n")
                await writer.drain()
                
            elif line.upper().startswith('AUTH'):
                if await self.handle_smtp_auth(line, reader, writer):
                    writer.write(b"235 Authentication successful\r\n")
                else:
                    writer.write(b"535 Authentication failed\r\n")
                await writer.drain()
                
            elif line.upper().startswith('MAIL FROM:'):
                current_email['from'] = line[10:].strip('<> ')
                writer.write(b"250 OK\r\n")
                await writer.drain()
                
            elif line.upper().startswith('RCPT TO:'):
                current_email['to'].append(line[8:].strip('<> '))
                writer.write(b"250 OK\r\n")
                await writer.drain()
                
            elif line.upper() == 'DATA':
                writer.write(b"354 End data with <CR><LF>.<CR><LF>\r\n")
                await writer.drain()
                
                # 读取邮件数据
                email_data = await self.read_email_data(reader)
                current_email['data'] = email_data
                
                # 存储邮件
                await self.store_smtp_email(current_email)
                
                writer.write(b"250 OK\r\n")
                await writer.drain()
                current_email = {'from': None, 'to': [], 'data': None}
                
            elif line.upper() == 'QUIT':
                writer.write(b"221 Bye\r\n")
                await writer.drain()
                break
                
            else:
                writer.write(b"500 Command not recognized\r\n")
                await writer.drain()

    async def handle_smtp_auth(self, auth_line: str, reader, writer) -> bool:
        """处理SMTP认证"""
        # 简化实现，实际应该支持多种认证机制
        parts = auth_line.split()
        if len(parts) < 2:
            return False
            
        mechanism = parts[1].upper()
        if mechanism == 'PLAIN':
            # 读取认证数据
            auth_data = await reader.readuntil(b'\r\n')
            return await authenticate_smtp(auth_data.decode().strip(), self.storage)
            
        return False

    async def read_email_data(self, reader) -> str:
        """读取完整的SMTP邮件数据"""
        data = []
        while True:
            line = await reader.readuntil(b'\r\n')
            line_str = line.decode()
            
            # 检查结束标记
            if line_str == '.\r\n':
                break
                
            # 处理转义点
            if line_str.startswith('..'):
                line_str = line_str[1:]
                
            data.append(line_str)
            
        return ''.join(data)

    async def store_smtp_email(self, email_data: Dict[str, Any]):
        """存储SMTP格式的邮件"""
        # 解析SMTP邮件
        msg = email.message_from_string(email_data['data'])
        
        # 转换为NEP格式
        nep_email = smtp_to_nep(msg, email_data['from'], email_data['to'])
        
        # 存储邮件
        await self.storage.store_email(nep_email)

    async def start(self):
        """启动NEP-T服务器"""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.config['host'],
            self.config['port']
        )
        
        logger.info(f"NEP-T server started on {self.config['host']}:{self.config['port']}")
        
        async with self.server:
            await self.server.serve_forever()
