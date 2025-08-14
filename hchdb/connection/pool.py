"""
连接池管理
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager

from ..common.exceptions import ConnectionError as HchDBConnectionError
from ..common.config import get_config


logger = logging.getLogger(__name__)


@dataclass
class PoolConnection:
    """池化连接"""
    connection_id: str
    connection: Any  # 实际的数据库连接对象
    created_at: float
    last_used: float
    in_use: bool = False
    query_count: int = 0


class ConnectionPool:
    """连接池"""
    
    def __init__(self, 
                 name: str,
                 min_connections: int = 5,
                 max_connections: int = 20,
                 connection_timeout: int = 30,
                 idle_timeout: int = 300,
                 max_lifetime: int = 3600):
        self.name = name
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout
        self.max_lifetime = max_lifetime
        
        # 连接存储
        self._pool: List[PoolConnection] = []
        self._pool_lock = asyncio.Lock()
        
        # 等待队列
        self._waiting_queue: asyncio.Queue = asyncio.Queue()
        
        # 连接工厂
        self._connection_factory = None
        
        # 状态
        self._closed = False
        self._maintenance_task: Optional[asyncio.Task] = None
        
        # 统计
        self.created_connections = 0
        self.borrowed_connections = 0
        self.returned_connections = 0
        self.failed_connections = 0
        
        logger.info(f"Created connection pool '{name}' "
                   f"(min={min_connections}, max={max_connections})")
    
    async def start(self, connection_factory) -> None:
        """启动连接池"""
        if self._closed:
            raise HchDBConnectionError("Cannot start a closed connection pool")
        
        self._connection_factory = connection_factory
        
        # 创建最小连接数
        await self._create_initial_connections()
        
        # 启动维护任务
        self._maintenance_task = asyncio.create_task(self._maintenance_loop())
        
        logger.info(f"Connection pool '{self.name}' started")
    
    async def stop(self) -> None:
        """停止连接池"""
        if self._closed:
            return
        
        self._closed = True
        
        # 停止维护任务
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有连接
        async with self._pool_lock:
            for pool_conn in self._pool:
                await self._close_connection(pool_conn)
            self._pool.clear()
        
        logger.info(f"Connection pool '{self.name}' stopped")
    
    async def _create_initial_connections(self) -> None:
        """创建初始连接"""
        for i in range(self.min_connections):
            try:
                await self._create_connection()
            except Exception as e:
                logger.error(f"Failed to create initial connection {i}: {e}")
    
    async def _create_connection(self) -> PoolConnection:
        """创建新连接"""
        if not self._connection_factory:
            raise HchDBConnectionError("Connection factory not set")
        
        try:
            connection = await self._connection_factory()
            connection_id = f"{self.name}_{self.created_connections}"
            
            pool_conn = PoolConnection(
                connection_id=connection_id,
                connection=connection,
                created_at=time.time(),
                last_used=time.time()
            )
            
            self.created_connections += 1
            return pool_conn
            
        except Exception as e:
            self.failed_connections += 1
            raise HchDBConnectionError(f"Failed to create connection: {e}")
    
    async def get_connection(self, timeout: Optional[float] = None) -> PoolConnection:
        """获取连接"""
        if self._closed:
            raise HchDBConnectionError("Connection pool is closed")
        
        timeout = timeout or self.connection_timeout
        
        try:
            # 尝试从池中获取连接
            async with asyncio.timeout(timeout):
                return await self._get_connection_from_pool()
                
        except asyncio.TimeoutError:
            raise HchDBConnectionError(f"Connection timeout after {timeout}s")
    
    async def _get_connection_from_pool(self) -> PoolConnection:
        """从池中获取连接"""
        while not self._closed:
            async with self._pool_lock:
                # 查找可用连接
                for pool_conn in self._pool:
                    if not pool_conn.in_use and await self._is_connection_valid(pool_conn):
                        pool_conn.in_use = True
                        pool_conn.last_used = time.time()
                        self.borrowed_connections += 1
                        return pool_conn
                
                # 如果没有可用连接且未达到最大连接数，创建新连接
                if len(self._pool) < self.max_connections:
                    try:
                        pool_conn = await self._create_connection()
                        pool_conn.in_use = True
                        self._pool.append(pool_conn)
                        self.borrowed_connections += 1
                        return pool_conn
                    except Exception as e:
                        logger.error(f"Failed to create connection: {e}")
            
            # 等待连接释放
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise HchDBConnectionError("Connection acquisition cancelled")
        
        raise HchDBConnectionError("Connection pool is closed")
    
    async def return_connection(self, pool_conn: PoolConnection) -> None:
        """归还连接"""
        if not pool_conn.in_use:
            logger.warning(f"Returning connection {pool_conn.connection_id} that is not in use")
            return
        
        async with self._pool_lock:
            pool_conn.in_use = False
            pool_conn.last_used = time.time()
            self.returned_connections += 1
            
            # 检查连接是否需要被移除
            if await self._should_remove_connection(pool_conn):
                self._pool.remove(pool_conn)
                await self._close_connection(pool_conn)
    
    @asynccontextmanager
    async def connection(self, timeout: Optional[float] = None):
        """连接上下文管理器"""
        pool_conn = await self.get_connection(timeout)
        try:
            yield pool_conn.connection
        finally:
            await self.return_connection(pool_conn)
    
    async def _is_connection_valid(self, pool_conn: PoolConnection) -> bool:
        """检查连接是否有效"""
        now = time.time()
        
        # 检查连接生命周期
        if now - pool_conn.created_at > self.max_lifetime:
            return False
        
        # 检查空闲时间
        if now - pool_conn.last_used > self.idle_timeout:
            return False
        
        # TODO: 添加连接健康检查
        # 可以通过发送ping命令或执行简单查询来验证连接状态
        
        return True
    
    async def _should_remove_connection(self, pool_conn: PoolConnection) -> bool:
        """检查连接是否应该被移除"""
        # 如果连接无效，应该移除
        if not await self._is_connection_valid(pool_conn):
            return True
        
        # 如果池中连接数超过最小连接数，可以移除
        if len([c for c in self._pool if not c.in_use]) > self.min_connections:
            return True
        
        return False
    
    async def _close_connection(self, pool_conn: PoolConnection) -> None:
        """关闭连接"""
        try:
            # TODO: 根据具体的连接类型实现关闭逻辑
            if hasattr(pool_conn.connection, 'close'):
                await pool_conn.connection.close()
            logger.debug(f"Closed connection {pool_conn.connection_id}")
        except Exception as e:
            logger.error(f"Error closing connection {pool_conn.connection_id}: {e}")
    
    async def _maintenance_loop(self) -> None:
        """维护循环"""
        while not self._closed:
            try:
                await asyncio.sleep(30)  # 每30秒维护一次
                await self._maintain_pool()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in maintenance loop: {e}")
    
    async def _maintain_pool(self) -> None:
        """维护连接池"""
        async with self._pool_lock:
            connections_to_remove = []
            
            # 检查并移除无效连接
            for pool_conn in self._pool:
                if not pool_conn.in_use and not await self._is_connection_valid(pool_conn):
                    connections_to_remove.append(pool_conn)
            
            # 移除无效连接
            for pool_conn in connections_to_remove:
                self._pool.remove(pool_conn)
                await self._close_connection(pool_conn)
            
            # 确保最小连接数
            active_connections = len(self._pool)
            if active_connections < self.min_connections:
                needed = self.min_connections - active_connections
                for _ in range(needed):
                    try:
                        pool_conn = await self._create_connection()
                        self._pool.append(pool_conn)
                    except Exception as e:
                        logger.error(f"Failed to create maintenance connection: {e}")
                        break
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        active_connections = len(self._pool)
        in_use_connections = len([c for c in self._pool if c.in_use])
        idle_connections = active_connections - in_use_connections
        
        return {
            'name': self.name,
            'active_connections': active_connections,
            'in_use_connections': in_use_connections,
            'idle_connections': idle_connections,
            'min_connections': self.min_connections,
            'max_connections': self.max_connections,
            'created_connections': self.created_connections,
            'borrowed_connections': self.borrowed_connections,
            'returned_connections': self.returned_connections,
            'failed_connections': self.failed_connections,
            'is_closed': self._closed,
        }


class PoolManager:
    """连接池管理器"""
    
    def __init__(self):
        self._pools: Dict[str, ConnectionPool] = {}
        self.config = get_config()
    
    def create_pool(self, 
                   name: str,
                   min_connections: Optional[int] = None,
                   max_connections: Optional[int] = None,
                   **kwargs) -> ConnectionPool:
        """创建连接池"""
        if name in self._pools:
            raise ValueError(f"Pool '{name}' already exists")
        
        # 使用配置的默认值
        min_connections = min_connections or self.config.get('connection.pool.min_connections', 10)
        max_connections = max_connections or self.config.get('connection.pool.max_connections', 100)
        
        pool = ConnectionPool(
            name=name,
            min_connections=min_connections,
            max_connections=max_connections,
            connection_timeout=self.config.get('connection.pool.connection_timeout', 30),
            idle_timeout=self.config.get('connection.pool.idle_timeout', 300),
            max_lifetime=self.config.get('connection.pool.max_lifetime', 3600),
            **kwargs
        )
        
        self._pools[name] = pool
        return pool
    
    def get_pool(self, name: str) -> Optional[ConnectionPool]:
        """获取连接池"""
        return self._pools.get(name)
    
    async def start_all(self) -> None:
        """启动所有连接池"""
        for pool in self._pools.values():
            if hasattr(pool, 'start') and not pool._closed:
                # 这里需要为每个池设置适当的连接工厂
                # TODO: 实现具体的连接工厂
                pass
    
    async def stop_all(self) -> None:
        """停止所有连接池"""
        for pool in self._pools.values():
            await pool.stop()
        self._pools.clear()
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有连接池的统计信息"""
        return {name: pool.get_pool_stats() for name, pool in self._pools.items()}