#!/usr/bin/env python3
"""
HchDB 测试客户端
"""

import socket
import struct
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def create_mysql_client():
    """创建简单的MySQL测试客户端"""
    
    # 连接到服务器
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        print("🔌 Connecting to HchDB server...")
        sock.connect(('localhost', 3306))
        print("✅ Connected successfully!")
        
        # 接收握手包
        handshake_data = receive_packet(sock)
        if handshake_data:
            print(f"📦 Received handshake packet: {len(handshake_data)} bytes")
            parse_handshake(handshake_data)
        
        # 发送认证响应
        print("🔐 Sending authentication response...")
        auth_response = create_auth_response("root", "", "hchdb")
        send_packet(sock, auth_response, 1)
        
        # 接收认证结果
        auth_result = receive_packet(sock)
        if auth_result and auth_result[0] == 0x00:
            print("✅ Authentication successful!")
        else:
            print(f"❌ Authentication failed: {auth_result}")
            return
        
        # 发送测试查询
        test_queries = [
            "SELECT 'Hello HchDB' as message",
            "SHOW DATABASES",
            "SHOW TABLES",
            "SELECT VERSION()"
        ]
        
        for query in test_queries:
            print(f"\n📝 Executing query: {query}")
            
            # 发送查询包
            query_packet = create_query_packet(query)
            send_packet(sock, query_packet, 0)
            
            # 接收查询结果
            result_packets = receive_query_result(sock)
            print(f"📊 Received {len(result_packets)} result packets")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        sock.close()
        print("🔌 Connection closed")


def receive_packet(sock):
    """接收一个MySQL协议包"""
    # 接收包头 (4字节)
    header = sock.recv(4)
    if len(header) < 4:
        return None
    
    # 解析长度和序号
    length = struct.unpack('<I', header[:3] + b'\x00')[0]
    sequence_id = header[3]
    
    # 接收载荷
    payload = b''
    remaining = length
    while remaining > 0:
        chunk = sock.recv(min(remaining, 8192))
        if not chunk:
            break
        payload += chunk
        remaining -= len(chunk)
    
    return payload


def send_packet(sock, payload, sequence_id):
    """发送一个MySQL协议包"""
    # 创建包头
    length = len(payload)
    header = struct.pack('<I', length)[:3] + struct.pack('<B', sequence_id)
    
    # 发送包
    sock.send(header + payload)


def parse_handshake(handshake_data):
    """解析握手包"""
    offset = 0
    
    # 协议版本
    protocol_version = handshake_data[offset]
    offset += 1
    print(f"📡 Protocol version: {protocol_version}")
    
    # 服务器版本
    version_end = handshake_data.find(b'\x00', offset)
    server_version = handshake_data[offset:version_end].decode('utf-8')
    offset = version_end + 1
    print(f"🏷️  Server version: {server_version}")
    
    # 连接ID
    connection_id = struct.unpack('<I', handshake_data[offset:offset+4])[0]
    offset += 4
    print(f"🔗 Connection ID: {connection_id}")


def create_auth_response(username, password, database=""):
    """创建认证响应包"""
    payload = b''
    
    # 客户端能力标志 (4字节)
    capabilities = (
        0x00000001 |  # CLIENT_LONG_PASSWORD
        0x00000002 |  # CLIENT_FOUND_ROWS  
        0x00000004 |  # CLIENT_LONG_FLAG
        0x00000008 |  # CLIENT_CONNECT_WITH_DB
        0x00000200 |  # CLIENT_PROTOCOL_41
        0x00008000 |  # CLIENT_SECURE_CONNECTION
        0x00080000    # CLIENT_PLUGIN_AUTH
    )
    payload += struct.pack('<I', capabilities)
    
    # 最大包长度 (4字节)
    payload += struct.pack('<I', 16777216)
    
    # 字符集 (1字节)
    payload += struct.pack('<B', 33)  # utf8_general_ci
    
    # 保留字段 (23字节)
    payload += b'\x00' * 23
    
    # 用户名 (null-terminated)
    payload += username.encode('utf-8') + b'\x00'
    
    # 认证数据长度和数据 (简化处理，使用空密码)
    payload += struct.pack('<B', 0)  # 认证数据长度为0
    
    # 数据库名 (null-terminated)
    if database:
        payload += database.encode('utf-8') + b'\x00'
    
    # 认证插件名
    payload += b'mysql_native_password\x00'
    
    return payload


def create_query_packet(query):
    """创建查询包"""
    payload = struct.pack('<B', 0x03)  # COM_QUERY
    payload += query.encode('utf-8')
    return payload


def receive_query_result(sock):
    """接收查询结果"""
    packets = []
    
    while True:
        packet = receive_packet(sock)
        if not packet:
            break
        
        packets.append(packet)
        
        # 检查是否是EOF包或错误包
        if packet[0] == 0xfe:  # EOF
            break
        elif packet[0] == 0xff:  # ERROR
            error_code = struct.unpack('<H', packet[1:3])[0]
            error_message = packet[3:].decode('utf-8', errors='ignore')
            print(f"❌ Query error {error_code}: {error_message}")
            break
    
    return packets


if __name__ == '__main__':
    print("🧪 HchDB Test Client")
    print("=" * 40)
    create_mysql_client()