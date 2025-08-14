"""
连接管理器
"""

import asyncio
import logging
import time
from typing import Dict, Set, Optional
from dataclasses import dataclass

from ..protocol.mysql import MySQLProtocolHandler
from ..common.exceptions import ConnectionError as HchDBConnectionError
from ..common.config import get_config


logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """连接信息"""
    connection_id: int
    client_address: tuple
    username: str
    database: str
    connected_at: float
    last_activity: float
    query_count: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0


class ConnectionManager:
    """连接管理器"""
    
    def __init__(self):
        self.config = get_config()
        
        # 连接跟踪
        self._connections: Dict[int, ConnectionInfo] = {}
        self._active_handlers: Dict[int, MySQLProtocolHandler] = {}
        self._next_connection_id = 1
        
        # 连接限制
        self._max_connections = self.config.max_connections
        
        # 监控任务
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self.total_connections = 0
        self.rejected_connections = 0
        self.start_time = time.time()
    
    async def start(self) -> None:
        """启动连接管理器"""
        logger.info("Starting connection manager")
        
        # 启动清理任务
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(f"Connection manager started (max_connections={self._max_connections})")
    
    async def stop(self) -> None:
        """停止连接管理器"""
        logger.info("Stopping connection manager")
        
        # 取消清理任务
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有活动连接
        if self._active_handlers:
            logger.info(f"Closing {len(self._active_handlers)} active connections")
            tasks = []
            for handler in self._active_handlers.values():
                tasks.append(asyncio.create_task(self._close_handler(handler)))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("Connection manager stopped")
    
    async def handle_new_connection(self, 
                                  reader: asyncio.StreamReader,
                                  writer: asyncio.StreamWriter) -> None:
        """处理新连接"""
        client_address = writer.get_extra_info('peername')
        
        # 检查连接限制
        if len(self._connections) >= self._max_connections:
            self.rejected_connections += 1
            logger.warning(f"Connection limit reached, rejecting connection from {client_address}")
            writer.close()
            await writer.wait_closed()
            return
        
        # 分配连接ID
        connection_id = self._next_connection_id
        self._next_connection_id += 1
        
        # 创建连接信息
        connection_info = ConnectionInfo(
            connection_id=connection_id,
            client_address=client_address,
            username="",  # 将在认证后更新
            database="",  # 将在认证后更新
            connected_at=time.time(),
            last_activity=time.time()
        )
        
        self._connections[connection_id] = connection_info
        self.total_connections += 1
        
        logger.info(f"New connection {connection_id} from {client_address}")
        
        # 创建协议处理器
        handler = MySQLProtocolHandler(reader, writer, connection_id)
        self._active_handlers[connection_id] = handler
        
        # 异步处理连接
        asyncio.create_task(self._handle_connection(handler, connection_info))
    
    async def _handle_connection(self, 
                               handler: MySQLProtocolHandler,
                               connection_info: ConnectionInfo) -> None:
        """处理单个连接"""
        connection_id = connection_info.connection_id
        
        try:
            await handler.handle_connection()
            
        except Exception as e:
            logger.error(f"Error handling connection {connection_id}: {e}")
            
        finally:
            # 清理连接
            await self._cleanup_connection(connection_id)
    
    async def _cleanup_connection(self, connection_id: int) -> None:
        """清理连接"""
        if connection_id in self._connections:
            connection_info = self._connections[connection_id]
            duration = time.time() - connection_info.connected_at
            
            logger.info(f"Connection {connection_id} closed after {duration:.2f}s, "
                       f"queries: {connection_info.query_count}")
            
            del self._connections[connection_id]
        
        if connection_id in self._active_handlers:
            handler = self._active_handlers[connection_id]
            await self._close_handler(handler)
            del self._active_handlers[connection_id]
    
    async def _close_handler(self, handler: MySQLProtocolHandler) -> None:
        """关闭处理器"""
        try:
            if not handler.writer.is_closing():
                handler.writer.close()
                await handler.writer.wait_closed()
        except Exception as e:
            logger.error(f"Error closing handler: {e}")
    
    async def _cleanup_loop(self) -> None:
        """清理循环"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self._cleanup_idle_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_idle_connections(self) -> None:
        """清理空闲连接"""
        now = time.time()
        idle_timeout = self.config.get('connection.pool.idle_timeout', 300)  # 5分钟
        
        idle_connections = []
        for connection_id, info in self._connections.items():
            if now - info.last_activity > idle_timeout:
                idle_connections.append(connection_id)
        
        if idle_connections:
            logger.info(f"Cleaning up {len(idle_connections)} idle connections")
            for connection_id in idle_connections:
                await self._cleanup_connection(connection_id)
    
    def update_connection_activity(self, connection_id: int, 
                                 query_count: int = 0,
                                 bytes_sent: int = 0,
                                 bytes_received: int = 0) -> None:
        """更新连接活动信息"""
        if connection_id in self._connections:
            info = self._connections[connection_id]
            info.last_activity = time.time()
            info.query_count += query_count
            info.bytes_sent += bytes_sent
            info.bytes_received += bytes_received
    
    def update_connection_auth(self, connection_id: int, username: str, database: str) -> None:
        """更新连接认证信息"""
        if connection_id in self._connections:
            info = self._connections[connection_id]
            info.username = username
            info.database = database
    
    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self._connections)
    
    def get_connection_info(self, connection_id: int) -> Optional[ConnectionInfo]:
        """获取连接信息"""
        return self._connections.get(connection_id)
    
    def get_all_connections(self) -> Dict[int, ConnectionInfo]:
        """获取所有连接信息"""
        return self._connections.copy()
    
    def get_statistics(self) -> Dict[str, any]:
        """获取统计信息"""
        now = time.time()
        uptime = now - self.start_time
        
        return {
            'current_connections': len(self._connections),
            'max_connections': self._max_connections,
            'total_connections': self.total_connections,
            'rejected_connections': self.rejected_connections,
            'uptime_seconds': uptime,
            'connection_rate': self.total_connections / uptime if uptime > 0 else 0,
            'rejection_rate': self.rejected_connections / uptime if uptime > 0 else 0,
        }