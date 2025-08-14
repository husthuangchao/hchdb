"""
MySQL协议包处理
"""

import struct
from enum import IntEnum
from typing import Optional, Tuple, Union
from io import BytesIO

from ..common.exceptions import ProtocolError


class PacketType(IntEnum):
    """MySQL协议包类型"""
    
    # 客户端命令
    COM_SLEEP = 0x00
    COM_QUIT = 0x01
    COM_INIT_DB = 0x02
    COM_QUERY = 0x03
    COM_FIELD_LIST = 0x04
    COM_CREATE_DB = 0x05
    COM_DROP_DB = 0x06
    COM_REFRESH = 0x07
    COM_SHUTDOWN = 0x08
    COM_STATISTICS = 0x09
    COM_PROCESS_INFO = 0x0a
    COM_CONNECT = 0x0b
    COM_PROCESS_KILL = 0x0c
    COM_DEBUG = 0x0d
    COM_PING = 0x0e
    COM_TIME = 0x0f
    COM_DELAYED_INSERT = 0x10
    COM_CHANGE_USER = 0x11
    COM_BINLOG_DUMP = 0x12
    COM_TABLE_DUMP = 0x13
    COM_CONNECT_OUT = 0x14
    COM_REGISTER_SLAVE = 0x15
    COM_STMT_PREPARE = 0x16
    COM_STMT_EXECUTE = 0x17
    COM_STMT_SEND_LONG_DATA = 0x18
    COM_STMT_CLOSE = 0x19
    COM_STMT_RESET = 0x1a
    COM_SET_OPTION = 0x1b
    COM_STMT_FETCH = 0x1c
    COM_DAEMON = 0x1d
    COM_BINLOG_DUMP_GTID = 0x1e
    COM_RESET_CONNECTION = 0x1f
    
    # 服务器响应
    OK_PACKET = 0x00
    EOF_PACKET = 0xfe
    ERR_PACKET = 0xff


class Packet:
    """MySQL协议包"""
    
    def __init__(self, payload: bytes = b'', sequence_id: int = 0):
        self.payload = payload
        self.sequence_id = sequence_id
    
    @property
    def length(self) -> int:
        """包长度"""
        return len(self.payload)
    
    def to_bytes(self) -> bytes:
        """转换为字节流"""
        if len(self.payload) > 0xffffff:
            raise ProtocolError(f"Packet too large: {len(self.payload)} bytes")
        
        # 包头: 长度(3字节) + 序号(1字节)
        header = struct.pack('<I', len(self.payload))[:3]  # 取前3字节
        header += struct.pack('<B', self.sequence_id)
        
        return header + self.payload
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Packet':
        """从字节流创建包"""
        if len(data) < 4:
            raise ProtocolError("Incomplete packet header")
        
        # 解析包头
        length_bytes = data[:3] + b'\x00'  # 补齐4字节
        length = struct.unpack('<I', length_bytes)[0]
        sequence_id = struct.unpack('<B', data[3:4])[0]
        
        if len(data) < 4 + length:
            raise ProtocolError(f"Incomplete packet: expected {4 + length}, got {len(data)}")
        
        payload = data[4:4 + length]
        return cls(payload, sequence_id)
    
    @classmethod
    def read_from_stream(cls, stream: BytesIO) -> Optional['Packet']:
        """从流中读取一个完整的包"""
        # 读取包头
        header_data = stream.read(4)
        if len(header_data) < 4:
            return None
        
        # 解析长度和序号
        length_bytes = header_data[:3] + b'\x00'
        length = struct.unpack('<I', length_bytes)[0]
        sequence_id = struct.unpack('<B', header_data[3:4])[0]
        
        # 读取载荷
        payload = stream.read(length)
        if len(payload) < length:
            return None
        
        return cls(payload, sequence_id)
    
    def __repr__(self) -> str:
        return f"Packet(length={self.length}, sequence_id={self.sequence_id})"


class PacketBuilder:
    """MySQL协议包构建器"""
    
    def __init__(self):
        self.sequence_id = 0
    
    def next_sequence_id(self) -> int:
        """获取下一个序号"""
        seq_id = self.sequence_id
        self.sequence_id = (self.sequence_id + 1) % 256
        return seq_id
    
    def reset_sequence(self) -> None:
        """重置序号"""
        self.sequence_id = 0
    
    def build_handshake(self, 
                       server_version: str = "8.0.0-hchdb",
                       connection_id: int = 1,
                       auth_plugin: str = "mysql_native_password") -> Packet:
        """构建握手包"""
        payload = BytesIO()
        
        # 协议版本
        payload.write(struct.pack('<B', 10))
        
        # 服务器版本 (null-terminated string)
        payload.write(server_version.encode('utf-8') + b'\x00')
        
        # 连接ID
        payload.write(struct.pack('<I', connection_id))
        
        # 认证种子第一部分 (8字节)
        auth_seed_1 = b'12345678'
        payload.write(auth_seed_1)
        payload.write(b'\x00')  # 分隔符
        
        # 服务器能力标志 (2字节)
        capabilities_low = (
            0x0001 |  # CLIENT_LONG_PASSWORD
            0x0002 |  # CLIENT_FOUND_ROWS
            0x0004 |  # CLIENT_LONG_FLAG
            0x0008 |  # CLIENT_CONNECT_WITH_DB
            0x0010 |  # CLIENT_NO_SCHEMA
            0x0020 |  # CLIENT_COMPRESS
            0x0040 |  # CLIENT_ODBC
            0x0080 |  # CLIENT_LOCAL_FILES
            0x0100 |  # CLIENT_IGNORE_SPACE
            0x0200 |  # CLIENT_PROTOCOL_41
            0x0400 |  # CLIENT_INTERACTIVE
            0x0800 |  # CLIENT_SSL
            0x1000 |  # CLIENT_IGNORE_SIGPIPE
            0x2000 |  # CLIENT_TRANSACTIONS
            0x4000 |  # CLIENT_RESERVED
            0x8000    # CLIENT_SECURE_CONNECTION
        )
        payload.write(struct.pack('<H', capabilities_low))
        
        # 字符集
        payload.write(struct.pack('<B', 33))  # utf8_general_ci
        
        # 状态标志
        payload.write(struct.pack('<H', 2))  # SERVER_STATUS_AUTOCOMMIT
        
        # 服务器能力标志 (高2字节)
        capabilities_high = (
            0x0001 |  # CLIENT_MULTI_STATEMENTS
            0x0002 |  # CLIENT_MULTI_RESULTS
            0x0004 |  # CLIENT_PS_MULTI_RESULTS
            0x0008 |  # CLIENT_PLUGIN_AUTH
            0x0010 |  # CLIENT_CONNECT_ATTRS
            0x0020 |  # CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA
            0x0040 |  # CLIENT_CAN_HANDLE_EXPIRED_PASSWORDS
            0x0080 |  # CLIENT_SESSION_TRACK
            0x0100    # CLIENT_DEPRECATE_EOF
        )
        payload.write(struct.pack('<H', capabilities_high))
        
        # 认证插件数据长度
        auth_plugin_data_len = 21
        payload.write(struct.pack('<B', auth_plugin_data_len))
        
        # 保留字段 (10字节)
        payload.write(b'\x00' * 10)
        
        # 认证种子第二部分
        auth_seed_2 = b'901234567890'
        payload.write(auth_seed_2 + b'\x00')
        
        # 认证插件名称
        payload.write(auth_plugin.encode('utf-8') + b'\x00')
        
        return Packet(payload.getvalue(), self.next_sequence_id())
    
    def build_ok(self, 
                 affected_rows: int = 0,
                 last_insert_id: int = 0,
                 status_flags: int = 2,
                 warnings: int = 0,
                 info: str = "") -> Packet:
        """构建OK包"""
        payload = BytesIO()
        
        # OK标志
        payload.write(struct.pack('<B', 0x00))
        
        # 受影响的行数 (length-encoded integer)
        payload.write(self._encode_length_encoded_int(affected_rows))
        
        # 最后插入的ID (length-encoded integer)
        payload.write(self._encode_length_encoded_int(last_insert_id))
        
        # 状态标志
        payload.write(struct.pack('<H', status_flags))
        
        # 警告数量
        payload.write(struct.pack('<H', warnings))
        
        # 信息字符串
        if info:
            payload.write(info.encode('utf-8'))
        
        return Packet(payload.getvalue(), self.next_sequence_id())
    
    def build_error(self, 
                   error_code: int = 1064,
                   error_message: str = "Unknown error",
                   sql_state: str = "42000") -> Packet:
        """构建错误包"""
        payload = BytesIO()
        
        # 错误标志
        payload.write(struct.pack('<B', 0xff))
        
        # 错误码
        payload.write(struct.pack('<H', error_code))
        
        # SQL状态标记
        payload.write(b'#')
        
        # SQL状态
        payload.write(sql_state.encode('ascii'))
        
        # 错误消息
        payload.write(error_message.encode('utf-8'))
        
        return Packet(payload.getvalue(), self.next_sequence_id())
    
    def build_eof(self, 
                  warnings: int = 0,
                  status_flags: int = 2) -> Packet:
        """构建EOF包"""
        payload = BytesIO()
        
        # EOF标志
        payload.write(struct.pack('<B', 0xfe))
        
        # 警告数量
        payload.write(struct.pack('<H', warnings))
        
        # 状态标志
        payload.write(struct.pack('<H', status_flags))
        
        return Packet(payload.getvalue(), self.next_sequence_id())
    
    def _encode_length_encoded_int(self, value: int) -> bytes:
        """编码长度编码整数"""
        if value < 251:
            return struct.pack('<B', value)
        elif value < 65536:
            return struct.pack('<BH', 0xfc, value)
        elif value < 16777216:
            return struct.pack('<BI', 0xfd, value)[:4]  # 取前4字节
        else:
            return struct.pack('<BQ', 0xfe, value)


class PacketParser:
    """MySQL协议包解析器"""
    
    @staticmethod
    def parse_handshake_response(packet: Packet) -> dict:
        """解析握手响应包"""
        if len(packet.payload) < 4:
            raise ProtocolError("Invalid handshake response packet")
        
        stream = BytesIO(packet.payload)
        
        # 客户端能力标志 (4字节)
        capabilities = struct.unpack('<I', stream.read(4))[0]
        
        # 最大包长度 (4字节)
        max_packet_size = struct.unpack('<I', stream.read(4))[0]
        
        # 字符集 (1字节)
        charset = struct.unpack('<B', stream.read(1))[0]
        
        # 保留字段 (23字节)
        stream.read(23)
        
        # 用户名 (null-terminated string)
        username = b''
        while True:
            byte = stream.read(1)
            if not byte or byte == b'\x00':
                break
            username += byte
        username = username.decode('utf-8')
        
        # 认证数据长度和数据
        auth_data = b''
        if capabilities & 0x00200000:  # CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA
            auth_len = PacketParser._decode_length_encoded_int(stream)
            if auth_len > 0:
                auth_data = stream.read(auth_len)
        else:
            # 读取null-terminated认证数据
            while True:
                byte = stream.read(1)
                if not byte or byte == b'\x00':
                    break
                auth_data += byte
        
        # 数据库名 (可选)
        database = ''
        if capabilities & 0x00000008:  # CLIENT_CONNECT_WITH_DB
            db_bytes = b''
            while True:
                byte = stream.read(1)
                if not byte or byte == b'\x00':
                    break
                db_bytes += byte
            database = db_bytes.decode('utf-8')
        
        # 认证插件名 (可选)
        auth_plugin = ''
        if capabilities & 0x00080000:  # CLIENT_PLUGIN_AUTH
            plugin_bytes = b''
            while True:
                byte = stream.read(1)
                if not byte or byte == b'\x00':
                    break
                plugin_bytes += byte
            auth_plugin = plugin_bytes.decode('utf-8')
        
        return {
            'username': username,
            'auth_data': auth_data,
            'database': database,
            'auth_plugin': auth_plugin,
            'capabilities': capabilities,
            'max_packet_size': max_packet_size,
            'charset': charset
        }
    
    @staticmethod
    def parse_query(packet: Packet) -> str:
        """解析查询包"""
        if len(packet.payload) < 1:
            raise ProtocolError("Invalid query packet")
        
        command = struct.unpack('<B', packet.payload[:1])[0]
        if command != PacketType.COM_QUERY:
            raise ProtocolError(f"Not a query packet: {command}")
        
        return packet.payload[1:].decode('utf-8')
    
    @staticmethod
    def _decode_length_encoded_int(stream: BytesIO) -> int:
        """解码长度编码整数"""
        first_byte = stream.read(1)
        if not first_byte:
            return 0
        
        value = struct.unpack('<B', first_byte)[0]
        if value < 251:
            return value
        elif value == 0xfc:
            return struct.unpack('<H', stream.read(2))[0]
        elif value == 0xfd:
            return struct.unpack('<I', stream.read(3) + b'\x00')[0]
        elif value == 0xfe:
            return struct.unpack('<Q', stream.read(8))[0]
        else:
            raise ProtocolError(f"Invalid length-encoded integer: {value}")