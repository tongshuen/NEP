import asyncio
import logging
from typing import Optional

from core.nep import NEPServer
from core.nept import NEPTServer
from core.neph import NEPServer
from web.app import create_app
from config import load_config

logger = logging.getLogger(__name__)

class NEPService:
    def __init__(self, config_path: Optional[str] = None):
        self.config = load_config(config_path)
        self._setup_logging()
        
        # 初始化存储
        self.storage = self._init_storage()
        
        # 初始化服务
        self.nep_server = NEPServer(self.config['nep'], self.storage)
        self.nept_server = NEPTServer(self.config['nept'], self.storage)
        self.neph_server = NEPServer(self.config['neph'], self.storage)
        
        # 初始化Web应用
        self.web_app = create_app(self.config['web'], self.storage)

    def _setup_logging(self):
        logging.basicConfig(
            level=self.config['logging']['level'],
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _init_storage(self):
        storage_type = self.config['storage']['type']
        if storage_type == 'file':
            from storage.file import FileStorage
            return FileStorage(self.config['storage']['file'])
        elif storage_type == 'mysql':
            from storage.mysql import MySQLStorage
            return MySQLStorage(self.config['storage']['mysql'])
        elif storage_type == 'redis':
            from storage.redis import RedisStorage
            return RedisStorage(self.config['storage']['redis'])
        else:
            raise ValueError(f"Unknown storage type: {storage_type}")

    async def start(self):
        """启动所有服务"""
        try:
            # 启动NEP服务器
            nep_task = asyncio.create_task(self.nep_server.start())
            
            # 启动NEP-T服务器
            nept_task = asyncio.create_task(self.nept_server.start())
            
            # 启动NEP-H服务器
            neph_task = asyncio.create_task(self.neph_server.start())
            
            # 启动Web服务器
            web_task = asyncio.create_task(self.web_app.run_task())
            
            await asyncio.gather(nep_task, nept_task, neph_task, web_task)
        except Exception as e:
            logger.error(f"Service error: {e}")
            raise

if __name__ == '__main__':
    service = NEPService()
    asyncio.run(service.start())
