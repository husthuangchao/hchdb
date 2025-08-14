#!/usr/bin/env python3
"""
HchDB 基础使用示例
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from hchdb.common.config import init_config
from hchdb.connection.manager import ConnectionManager
from hchdb.server import HchDBServer


async def main():
    """基础使用示例"""
    print("🚀 Starting HchDB basic usage example...")
    
    try:
        # 初始化配置
        config = init_config('config/development.yaml')
        print(f"✅ Configuration loaded: MySQL port {config.mysql_port}")
        
        # 创建连接管理器
        connection_manager = ConnectionManager()
        await connection_manager.start()
        print("✅ Connection manager started")
        
        # 创建服务器
        server = HchDBServer(connection_manager)
        await server.start()
        print("✅ HchDB server started")
        
        print("\n" + "="*50)
        print("🎉 HchDB is now running!")
        print("💡 You can connect using:")
        print(f"   mysql -h {config.server_host} -P {config.mysql_port} -u root")
        print("\n📝 Try these commands:")
        print("   SHOW DATABASES;")
        print("   SHOW TABLES;")
        print("   SELECT 'Hello HchDB' as message;")
        print("="*50)
        
        # 运行30秒后自动停止 (用于测试)
        print("\n⏰ Server will auto-stop in 30 seconds...")
        await asyncio.sleep(30)
        
        # 停止服务器
        print("\n🛑 Stopping HchDB server...")
        await server.stop()
        await connection_manager.stop()
        print("✅ HchDB server stopped")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())