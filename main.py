#!/usr/bin/env python3
"""
HchDB 分布式数据库服务器启动入口

这是HchDB项目的主启动文件，负责：
1. 解析命令行参数
2. 初始化配置系统
3. 启动数据库服务器
4. 处理优雅关闭

Author: husthuangchao
Date: 2024-08-14
Version: v0.1.0-day1
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

import click

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from hchdb.common.config import init_config, get_config, apply_env_overrides
from hchdb.common.exceptions import ConfigurationError
from hchdb.connection.manager import ConnectionManager
from hchdb.server import HchDBServer


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HchDBApplication:
    """HchDB 应用程序主类"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.config = None
        self.server: Optional[HchDBServer] = None
        self.connection_manager: Optional[ConnectionManager] = None
        self._shutdown_event = asyncio.Event()
    
    async def start(self) -> None:
        """启动应用程序"""
        try:
            # 初始化配置
            self._init_config()
            
            # 设置日志级别
            self._setup_logging()
            
            logger.info("🚀 Starting HchDB distributed database server")
            logger.info(f"📊 Version: {self._get_version()}")
            logger.info(f"⚙️  Config file: {self.config_file or 'auto-detected'}")
            
            # 创建组件
            self.connection_manager = ConnectionManager()
            self.server = HchDBServer(self.connection_manager)
            
            # 启动服务
            await self.connection_manager.start()
            await self.server.start()
            
            logger.info("✅ HchDB server started successfully!")
            self._print_server_info()
            
            # 等待关闭信号
            await self._shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"❌ Failed to start HchDB server: {e}")
            raise
    
    async def stop(self) -> None:
        """停止应用程序"""
        logger.info("🛑 Stopping HchDB server...")
        
        try:
            if self.server:
                await self.server.stop()
            
            if self.connection_manager:
                await self.connection_manager.stop()
            
            logger.info("✅ HchDB server stopped successfully!")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")
    
    def _init_config(self) -> None:
        """初始化配置"""
        try:
            self.config = init_config(self.config_file)
            apply_env_overrides(self.config)
            
            logger.info(f"📝 Configuration loaded successfully")
            if self.config.debug_mode:
                logger.info("🐛 Debug mode enabled")
                
        except ConfigurationError as e:
            logger.error(f"Configuration error: {e}")
            raise
    
    def _setup_logging(self) -> None:
        """设置日志"""
        log_level = self.config.log_level.upper()
        numeric_level = getattr(logging, log_level, logging.INFO)
        
        # 设置根日志级别
        logging.getLogger().setLevel(numeric_level)
        
        # 设置各模块日志级别
        loggers_config = self.config.get('logging.loggers', {})
        for logger_name, level in loggers_config.items():
            logging.getLogger(logger_name).setLevel(getattr(logging, level.upper(), numeric_level))
        
        logger.info(f"📊 Log level set to: {log_level}")
    
    def _print_server_info(self) -> None:
        """打印服务器信息"""
        print("\n" + "="*60)
        print("🎉 HchDB Distributed Database Server")
        print("="*60)
        print(f"📡 MySQL Protocol: {self.config.server_host}:{self.config.mysql_port}")
        print(f"⚙️  Management Port: {self.config.server_host}:{self.config.management_port}")
        print(f"🔗 Internal Port: {self.config.server_host}:{self.config.internal_port}")
        print(f"⚡ X-Protocol: {self.config.server_host}:{self.config.xprotocol_port}")
        print(f"🔒 Max Connections: {self.config.max_connections}")
        print(f"🐛 Debug Mode: {'ON' if self.config.debug_mode else 'OFF'}")
        print("\n💡 Connect using:")
        print(f"   mysql -h {self.config.server_host} -P {self.config.mysql_port} -u root")
        print("\n📚 Documentation: https://github.com/hch/hchdb")
        print("="*60 + "\n")
    
    def _get_version(self) -> str:
        """获取版本信息"""
        try:
            from hchdb import __version__
            return __version__
        except ImportError:
            return "unknown"
    
    def shutdown(self) -> None:
        """触发关闭"""
        self._shutdown_event.set()


# 全局应用实例
app: Optional[HchDBApplication] = None


def signal_handler(signum, frame):
    """信号处理器"""
    global app
    logger.info(f"Received signal {signum}")
    if app:
        app.shutdown()


@click.command()
@click.option('--config', '-c', 
              help='Configuration file path',
              type=click.Path(exists=True))
@click.option('--host', '-h',
              help='Server host address')
@click.option('--port', '-p',
              help='MySQL protocol port',
              type=int)
@click.option('--debug', '-d',
              is_flag=True,
              help='Enable debug mode')
@click.option('--version', '-v',
              is_flag=True,
              help='Show version and exit')
def main(config: Optional[str] = None,
         host: Optional[str] = None,
         port: Optional[int] = None,
         debug: bool = False,
         version: bool = False) -> None:
    """HchDB 分布式数据库服务器"""
    
    if version:
        try:
            from hchdb import __version__
            print(f"HchDB version {__version__}")
        except ImportError:
            print("HchDB version unknown")
        return
    
    global app
    
    try:
        # 创建应用实例
        app = HchDBApplication(config_file=config)
        
        # 应用命令行参数覆盖
        if host or port or debug:
            # 先初始化配置
            app._init_config()
            
            if host:
                app.config.set('server.host', host)
            if port:
                app.config.set('server.ports.mysql', port)
            if debug:
                app.config.set('development.debug', True)
        
        # 设置信号处理
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 启动应用
        asyncio.run(app.start())
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
    finally:
        if app:
            try:
                asyncio.run(app.stop())
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


if __name__ == '__main__':
    main()