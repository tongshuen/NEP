from abc import ABC, abstractmethod
from typing import List, Optional

from models.mail import EmailMessage
from models.user import User

class BaseStorage(ABC):
    """存储抽象基类"""
    
    @abstractmethod
    async def store_email(self, email: EmailMessage) -> str:
        """存储邮件"""
        pass
        
    @abstractmethod
    async def get_email(self, message_id: str) -> Optional[EmailMessage]:
        """获取单个邮件"""
        pass
        
    @abstractmethod
    async def list_emails(self, email: str, mailbox: str, limit: int, offset: int) -> List[EmailMessage]:
        """列出邮件"""
        pass
        
    @abstractmethod
    async def update_email_flags(self, message_id: str, flags: Dict[str, bool]) -> bool:
        """更新邮件标记"""
        pass
        
    @abstractmethod
    async def create_user(self, user: User) -> bool:
        """创建用户"""
        pass
        
    @abstractmethod
    async def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        pass
        
    @abstractmethod
    async def authenticate(self, username: str, password: str) -> Optional[User]:
        """认证用户"""
        pass
