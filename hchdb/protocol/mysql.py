"""
MySQL协议处理器
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable, Awaitable
from io import BytesIO

from .packet import Packet, PacketBuilder, PacketParser, PacketType
from ..common.exceptions import ProtocolError, AuthenticationError
from ..common.config import get_config


logger = logging.getLogger(__name__)


class MySQLProtocolHandler:
    """MySQL协议处理器"""
    
    def __init__(self, 
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter,
                 connection_id: int = 1):
        self.reader = reader
        self.writer = writer
        self.connection_id = connection_id
        self.packet_builder = PacketBuilder()
        
        # 连接状态
        self.authenticated = False
        self.username = ""
        self.database = ""
        self.client_capabilities = 0
        
        # 配置
        self.config = get_config()
        
        # 查询处理回调
        self.query_handler: Optional[Callable[[str], Awaitable[Dict[str, Any]]]] = None
    
    async def handle_connection(self) -> None:
        """处理客户端连接"""
        try:
            logger.info(f"New MySQL client connection: {self.connection_id}")
            
            # 发送握手包
            await self._send_handshake()
            
            # 处理认证
            await self._handle_authentication()
            
            # 处理客户端命令
            await self._handle_commands()
            
        except Exception as e:
            logger.error(f"Error handling connection {self.connection_id}: {e}")
            await self._send_error(1105, f"Internal error: {str(e)}")
        finally:
            await self._close_connection()
    
    async def _send_handshake(self) -> None:
        """发送握手包"""
        handshake_packet = self.packet_builder.build_handshake(
            server_version=self.config.server_version,
            connection_id=self.connection_id
        )
        
        await self._write_packet(handshake_packet)
        logger.debug(f"Sent handshake packet to connection {self.connection_id}")
    
    async def _handle_authentication(self) -> None:
        """处理认证"""
        # 接收握手响应包
        auth_packet = await self._read_packet()
        if not auth_packet:
            raise ProtocolError("No authentication packet received")
        
        # 解析认证信息
        try:
            auth_info = PacketParser.parse_handshake_response(auth_packet)
        except Exception as e:
            raise ProtocolError(f"Failed to parse authentication packet: {e}")
        
        self.username = auth_info['username']
        self.database = auth_info['database']
        self.client_capabilities = auth_info['capabilities']
        
        logger.debug(f"Authentication attempt: user={self.username}, db={self.database}")
        
        # 验证用户
        if not await self._authenticate_user(auth_info):
            await self._send_error(1045, f"Access denied for user '{self.username}'")
            raise AuthenticationError(f"Authentication failed for user: {self.username}")
        
        # 发送认证成功
        ok_packet = self.packet_builder.build_ok()
        await self._write_packet(ok_packet)
        
        self.authenticated = True
        logger.info(f"User '{self.username}' authenticated successfully on connection {self.connection_id}")
    
    async def _authenticate_user(self, auth_info: Dict[str, Any]) -> bool:
        """验证用户认证"""
        username = auth_info['username']
        
        # 从配置中获取用户信息
        users_config = self.config.get('authentication.users', {})
        
        if username not in users_config:
            logger.warning(f"Unknown user: {username}")
            return False
        
        user_config = users_config[username]
        
        # 简化的认证逻辑 (生产环境需要实现完整的密码验证)
        # 这里只检查配置中是否存在用户
        expected_password = user_config.get('password', '')
        
        # TODO: 实现完整的MySQL认证算法
        # 目前简化处理，允许空密码或配置的密码
        if expected_password == '':
            return True
        
        # 这里应该验证auth_info['auth_data']与expected_password的匹配
        # 暂时简化为允许所有配置用户
        logger.debug(f"User {username} authentication passed (simplified)")
        return True
    
    async def _handle_commands(self) -> None:
        """处理客户端命令"""
        while True:
            try:
                packet = await self._read_packet()
                if not packet:
                    logger.debug(f"Connection {self.connection_id} closed by client")
                    break
                
                await self._process_command(packet)
                
            except asyncio.CancelledError:
                logger.debug(f"Connection {self.connection_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Error processing command on connection {self.connection_id}: {e}")
                await self._send_error(1105, f"Internal error: {str(e)}")
    
    async def _process_command(self, packet: Packet) -> None:
        """处理单个命令"""
        if len(packet.payload) == 0:
            await self._send_error(1064, "Empty command packet")
            return
        
        command = packet.payload[0]
        
        if command == PacketType.COM_QUIT:
            logger.debug(f"Client quit command on connection {self.connection_id}")
            return
        
        elif command == PacketType.COM_QUERY:
            await self._handle_query(packet)
        
        elif command == PacketType.COM_PING:
            await self._handle_ping()
        
        elif command == PacketType.COM_INIT_DB:
            await self._handle_init_db(packet)
        
        elif command == PacketType.COM_FIELD_LIST:
            await self._handle_field_list(packet)
        
        else:
            await self._send_error(1047, f"Unknown command: {command}")
    
    async def _handle_query(self, packet: Packet) -> None:
        """处理查询命令"""
        try:
            query = PacketParser.parse_query(packet)
            logger.debug(f"Query on connection {self.connection_id}: {query[:100]}...")
            
            # 调用查询处理器
            if self.query_handler:
                result = await self.query_handler(query)
                await self._send_query_result(result)
            else:
                # 默认的简单响应
                await self._send_simple_result(query)
                
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            await self._send_error(1064, f"Query error: {str(e)}")
    
    async def _handle_ping(self) -> None:
        """处理PING命令"""
        ok_packet = self.packet_builder.build_ok()
        await self._write_packet(ok_packet)
        logger.debug(f"Responded to ping on connection {self.connection_id}")
    
    async def _handle_init_db(self, packet: Packet) -> None:
        """处理USE数据库命令"""
        if len(packet.payload) < 2:
            await self._send_error(1064, "Invalid USE command")
            return
        
        database = packet.payload[1:].decode('utf-8')
        self.database = database
        
        ok_packet = self.packet_builder.build_ok()
        await self._write_packet(ok_packet)
        logger.debug(f"Changed database to '{database}' on connection {self.connection_id}")
    
    async def _handle_field_list(self, packet: Packet) -> None:
        """处理字段列表命令"""
        # 简化实现：直接返回EOF
        eof_packet = self.packet_builder.build_eof()
        await self._write_packet(eof_packet)
    
    async def _send_simple_result(self, query: str) -> None:
        """发送简单的查询结果"""
        query_upper = query.upper().strip()
        
        if query_upper.startswith('SELECT'):
            # 模拟SELECT结果
            await self._send_select_result(query)
        elif query_upper.startswith(('INSERT', 'UPDATE', 'DELETE')):
            # 模拟DML结果
            ok_packet = self.packet_builder.build_ok(affected_rows=1)
            await self._write_packet(ok_packet)
        elif query_upper.startswith('SHOW'):
            # 模拟SHOW命令结果
            await self._send_show_result(query)
        else:
            # 其他命令返回OK
            ok_packet = self.packet_builder.build_ok()
            await self._write_packet(ok_packet)
    
    async def _send_select_result(self, query: str) -> None:
        """发送SELECT查询结果"""
        # 字段数量包
        field_count_packet = Packet(b'\\x01', self.packet_builder.next_sequence_id())
        await self._write_packet(field_count_packet)
        
        # 字段定义包
        field_def = BytesIO()
        field_def.write(b'def\\x00')          # catalog
        field_def.write(b'hchdb\\x00')        # schema
        field_def.write(b'demo\\x00')         # table
        field_def.write(b'demo\\x00')         # org_table
        field_def.write(b'message\\x00')      # name
        field_def.write(b'message\\x00')      # org_name
        field_def.write(b'\\x0c')             # filler
        field_def.write(b'\\x21\\x00')        # charset
        field_def.write(b'\\x14\\x00\\x00\\x00')  # length
        field_def.write(b'\\xfd')             # type (VAR_STRING)
        field_def.write(b'\\x00\\x00')        # flags
        field_def.write(b'\\x00')             # decimals
        field_def.write(b'\\x00\\x00')        # filler
        
        field_packet = Packet(field_def.getvalue(), self.packet_builder.next_sequence_id())
        await self._write_packet(field_packet)
        
        # EOF包 (字段定义结束)
        eof1_packet = self.packet_builder.build_eof()
        await self._write_packet(eof1_packet)
        
        # 数据行包
        message = f"Hello from HchDB! Query: {query[:50]}..."
        row_data = bytes([len(message)]) + message.encode('utf-8')
        row_packet = Packet(row_data, self.packet_builder.next_sequence_id())
        await self._write_packet(row_packet)
        
        # EOF包 (数据结束)
        eof2_packet = self.packet_builder.build_eof()
        await self._write_packet(eof2_packet)
    
    async def _send_show_result(self, query: str) -> None:
        """发送SHOW命令结果"""
        query_upper = query.upper().strip()
        
        if 'DATABASES' in query_upper:
            await self._send_databases_result()
        elif 'TABLES' in query_upper:
            await self._send_tables_result()
        elif 'VERSION' in query_upper or 'VARIABLES' in query_upper:
            await self._send_variables_result()
        else:
            # 默认空结果
            eof_packet = self.packet_builder.build_eof()
            await self._write_packet(eof_packet)
    
    async def _send_databases_result(self) -> None:
        """发送SHOW DATABASES结果"""
        # 简化实现：返回几个示例数据库
        databases = ['information_schema', 'hchdb', 'test']
        
        # 字段数量
        field_count_packet = Packet(b'\\x01', self.packet_builder.next_sequence_id())
        await self._write_packet(field_count_packet)
        
        # 字段定义 (Database)
        field_def = (b'def\\x00information_schema\\x00SCHEMATA\\x00SCHEMATA\\x00'
                    b'SCHEMA_NAME\\x00SCHEMA_NAME\\x00\\x0c!\\x00\\x00\\x02\\x00\\x00'
                    b'\\xfd\\x01\\x00\\x1f\\x00\\x00')
        field_packet = Packet(field_def, self.packet_builder.next_sequence_id())
        await self._write_packet(field_packet)
        
        # EOF (字段结束)
        eof1_packet = self.packet_builder.build_eof()
        await self._write_packet(eof1_packet)
        
        # 数据行
        for db in databases:
            row_data = bytes([len(db)]) + db.encode('utf-8')
            row_packet = Packet(row_data, self.packet_builder.next_sequence_id())
            await self._write_packet(row_packet)
        
        # EOF (数据结束)
        eof2_packet = self.packet_builder.build_eof()
        await self._write_packet(eof2_packet)
    
    async def _send_tables_result(self) -> None:
        """发送SHOW TABLES结果"""
        tables = ['users', 'orders', 'products']
        
        # 字段数量
        field_count_packet = Packet(b'\\x01', self.packet_builder.next_sequence_id())
        await self._write_packet(field_count_packet)
        
        # 字段定义
        table_name = f"Tables_in_{self.database or 'hchdb'}"
        field_def = (f'def\\x00{self.database or "hchdb"}\\x00\\x00\\x00'
                    f'{table_name}\\x00{table_name}\\x00').encode('utf-8')
        field_def += b'\\x0c!\\x00\\x00\\x02\\x00\\x00\\xfd\\x01\\x00\\x1f\\x00\\x00'
        field_packet = Packet(field_def, self.packet_builder.next_sequence_id())
        await self._write_packet(field_packet)
        
        # EOF (字段结束)
        eof1_packet = self.packet_builder.build_eof()
        await self._write_packet(eof1_packet)
        
        # 数据行
        for table in tables:
            row_data = bytes([len(table)]) + table.encode('utf-8')
            row_packet = Packet(row_data, self.packet_builder.next_sequence_id())
            await self._write_packet(row_packet)
        
        # EOF (数据结束)
        eof2_packet = self.packet_builder.build_eof()
        await self._write_packet(eof2_packet)
    
    async def _send_variables_result(self) -> None:
        """发送变量查询结果"""
        variables = [
            ('version', self.config.server_version),
            ('version_comment', 'HchDB distributed database'),
            ('max_connections', str(self.config.max_connections)),
        ]
        
        # 字段数量 (2个字段: Variable_name, Value)
        field_count_packet = Packet(b'\\x02', self.packet_builder.next_sequence_id())
        await self._write_packet(field_count_packet)
        
        # 字段定义1: Variable_name
        field_def1 = (b'def\\x00\\x00\\x00\\x00Variable_name\\x00Variable_name\\x00'
                     b'\\x0c!\\x00\\x00\\x02\\x00\\x00\\xfd\\x01\\x00\\x1f\\x00\\x00')
        field_packet1 = Packet(field_def1, self.packet_builder.next_sequence_id())
        await self._write_packet(field_packet1)
        
        # 字段定义2: Value
        field_def2 = (b'def\\x00\\x00\\x00\\x00Value\\x00Value\\x00'
                     b'\\x0c!\\x00\\x00\\x02\\x00\\x00\\xfd\\x01\\x00\\x1f\\x00\\x00')
        field_packet2 = Packet(field_def2, self.packet_builder.next_sequence_id())
        await self._write_packet(field_packet2)
        
        # EOF (字段结束)
        eof1_packet = self.packet_builder.build_eof()
        await self._write_packet(eof1_packet)
        
        # 数据行
        for name, value in variables:
            row_data = (bytes([len(name)]) + name.encode('utf-8') +
                       bytes([len(value)]) + value.encode('utf-8'))
            row_packet = Packet(row_data, self.packet_builder.next_sequence_id())
            await self._write_packet(row_packet)
        
        # EOF (数据结束)
        eof2_packet = self.packet_builder.build_eof()
        await self._write_packet(eof2_packet)
    
    async def _send_query_result(self, result: Dict[str, Any]) -> None:
        """发送查询结果"""
        # 这个方法用于处理来自查询处理器的结果
        # TODO: 实现完整的结果集处理
        ok_packet = self.packet_builder.build_ok()
        await self._write_packet(ok_packet)
    
    async def _send_error(self, error_code: int, message: str, sql_state: str = "HY000") -> None:
        """发送错误包"""
        error_packet = self.packet_builder.build_error(error_code, message, sql_state)
        await self._write_packet(error_packet)
        logger.debug(f"Sent error {error_code}: {message}")
    
    async def _read_packet(self) -> Optional[Packet]:
        """从连接读取一个包"""
        try:
            # 读取包头 (4字节)
            header_data = await self.reader.readexactly(4)
            if len(header_data) < 4:
                return None
            
            # 解析长度
            length_bytes = header_data[:3] + b'\\x00'
            length = int.from_bytes(length_bytes, 'little')
            sequence_id = header_data[3]
            
            # 读取载荷
            if length > 0:
                payload = await self.reader.readexactly(length)
            else:
                payload = b''
            
            return Packet(payload, sequence_id)
            
        except asyncio.IncompleteReadError:
            return None
        except Exception as e:
            logger.error(f"Error reading packet: {e}")
            return None
    
    async def _write_packet(self, packet: Packet) -> None:
        """向连接写入一个包"""
        try:
            data = packet.to_bytes()
            self.writer.write(data)
            await self.writer.drain()
            logger.debug(f"Sent packet: length={packet.length}, sequence_id={packet.sequence_id}")
        except Exception as e:
            logger.error(f"Error writing packet: {e}")
            raise ProtocolError(f"Failed to write packet: {e}")
    
    async def _close_connection(self) -> None:
        """关闭连接"""
        try:
            if not self.writer.is_closing():
                self.writer.close()
                await self.writer.wait_closed()
            logger.info(f"Connection {self.connection_id} closed")
        except Exception as e:
            logger.error(f"Error closing connection {self.connection_id}: {e}")
    
    def set_query_handler(self, handler: Callable[[str], Awaitable[Dict[str, Any]]]) -> None:
        """设置查询处理器"""
        self.query_handler = handler