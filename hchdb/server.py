"""
HchDB 服务器主类
"""

import asyncio
import logging
from typing import Optional, List

from .common.config import get_config
from .common.exceptions import HchDBError
from .connection.manager import ConnectionManager


logger = logging.getLogger(__name__)


class HchDBServer:
    """HchDB 分布式数据库服务器"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.config = get_config()
        
        # 服务器列表
        self._servers: List[asyncio.Server] = []
        self._running = False
    
    async def start(self) -> None:
        """启动服务器"""
        if self._running:
            raise HchDBError("Server is already running")
        
        logger.info("Starting HchDB servers...")
        
        try:
            # 启动MySQL协议服务器
            await self._start_mysql_server()
            
            # 启动管理端口服务器
            await self._start_management_server()
            
            # 启动内部通信服务器
            await self._start_internal_server()
            
            # 启动X-Protocol服务器 (可选)
            if self.config.get('server.ports.xprotocol'):
                await self._start_xprotocol_server()
            
            self._running = True
            logger.info("All HchDB servers started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start servers: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """停止服务器"""
        if not self._running:
            return
        
        logger.info("Stopping HchDB servers...")
        
        # 停止所有服务器
        for server in self._servers:
            server.close()
        
        # 等待所有服务器关闭
        for server in self._servers:
            await server.wait_closed()
        
        self._servers.clear()
        self._running = False
        
        logger.info("All HchDB servers stopped")
    
    async def _start_mysql_server(self) -> None:
        """启动MySQL协议服务器"""
        host = self.config.server_host
        port = self.config.mysql_port
        
        server = await asyncio.start_server(
            self._handle_mysql_connection,
            host=host,
            port=port,
            reuse_address=True,
            backlog=1000  # 连接队列长度
        )
        
        self._servers.append(server)
        logger.info(f"MySQL protocol server listening on {host}:{port}")
    
    async def _start_management_server(self) -> None:
        """启动管理端口服务器"""
        host = self.config.server_host
        port = self.config.management_port
        
        server = await asyncio.start_server(
            self._handle_management_connection,
            host=host,
            port=port,
            reuse_address=True
        )
        
        self._servers.append(server)
        logger.info(f"Management server listening on {host}:{port}")
    
    async def _start_internal_server(self) -> None:
        """启动内部通信服务器"""
        host = self.config.server_host
        port = self.config.internal_port
        
        server = await asyncio.start_server(
            self._handle_internal_connection,
            host=host,
            port=port,
            reuse_address=True
        )
        
        self._servers.append(server)
        logger.info(f"Internal communication server listening on {host}:{port}")
    
    async def _start_xprotocol_server(self) -> None:
        """启动X-Protocol服务器"""
        host = self.config.server_host
        port = self.config.xprotocol_port
        
        server = await asyncio.start_server(
            self._handle_xprotocol_connection,
            host=host,
            port=port,
            reuse_address=True
        )
        
        self._servers.append(server)
        logger.info(f"X-Protocol server listening on {host}:{port}")
    
    async def _handle_mysql_connection(self, 
                                     reader: asyncio.StreamReader,
                                     writer: asyncio.StreamWriter) -> None:
        """处理MySQL协议连接"""
        await self.connection_manager.handle_new_connection(reader, writer)
    
    async def _handle_management_connection(self, 
                                          reader: asyncio.StreamReader,
                                          writer: asyncio.StreamWriter) -> None:
        """处理管理端口连接"""
        # 管理端口使用相同的MySQL协议，但可能有不同的权限和功能
        await self.connection_manager.handle_new_connection(reader, writer)
    
    async def _handle_internal_connection(self, 
                                        reader: asyncio.StreamReader,
                                        writer: asyncio.StreamWriter) -> None:
        """处理内部通信连接"""
        # TODO: 实现集群内部通信协议
        client_address = writer.get_extra_info('peername')
        logger.debug(f"Internal connection from {client_address}")
        
        # 暂时关闭连接
        writer.close()
        await writer.wait_closed()
    
    async def _handle_xprotocol_connection(self, 
                                         reader: asyncio.StreamReader,
                                         writer: asyncio.StreamWriter) -> None:
        """处理X-Protocol连接"""
        # TODO: 实现X-Protocol处理
        client_address = writer.get_extra_info('peername')
        logger.debug(f"X-Protocol connection from {client_address}")
        
        # 暂时关闭连接
        writer.close()
        await writer.wait_closed()
    
    def is_running(self) -> bool:
        """检查服务器是否运行中"""
        return self._running
    
    def get_server_info(self) -> dict:
        """获取服务器信息"""
        return {
            'running': self._running,
            'servers_count': len(self._servers),
            'mysql_port': self.config.mysql_port,
            'management_port': self.config.management_port,
            'internal_port': self.config.internal_port,
            'xprotocol_port': self.config.xprotocol_port,
            'host': self.config.server_host,
        }