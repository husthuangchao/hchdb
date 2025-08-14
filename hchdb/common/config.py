"""
HchDB 配置管理
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

from .exceptions import ConfigurationError


class Config:
    """配置管理类"""
    
    def __init__(self, config_file: Optional[str] = None):
        self._data: Dict[str, Any] = {}
        self._config_file = config_file
        if config_file:
            self.load_from_file(config_file)
    
    def load_from_file(self, config_file: str) -> None:
        """从文件加载配置"""
        config_path = Path(config_file)
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_file}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse configuration file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration file: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的嵌套键"""
        keys = key.split('.')
        value = self._data
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        keys = key.split('.')
        data = self._data
        
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        
        data[keys[-1]] = value
    
    def update(self, other_config: Dict[str, Any]) -> None:
        """更新配置"""
        self._merge_dict(self._data, other_config)
    
    def _merge_dict(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        """递归合并字典"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_dict(base[key], value)
            else:
                base[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self._data.copy()
    
    # 常用配置项的快捷访问
    @property
    def server_host(self) -> str:
        return self.get('server.host', '0.0.0.0')
    
    @property
    def mysql_port(self) -> int:
        return self.get('server.ports.mysql', 3306)
    
    @property
    def management_port(self) -> int:
        return self.get('server.ports.management', 3307)
    
    @property
    def internal_port(self) -> int:
        return self.get('server.ports.internal', 3308)
    
    @property
    def xprotocol_port(self) -> int:
        return self.get('server.ports.xprotocol', 33060)
    
    @property
    def server_version(self) -> str:
        return self.get('server.server_version', '8.0.0-hchdb')
    
    @property
    def max_connections(self) -> int:
        return self.get('connection.pool.max_connections', 1000)
    
    @property
    def connection_timeout(self) -> int:
        return self.get('connection.pool.connection_timeout', 30)
    
    @property
    def log_level(self) -> str:
        return self.get('logging.level', 'INFO')
    
    @property
    def debug_mode(self) -> bool:
        return self.get('development.debug', False)


# 全局配置实例
_global_config: Optional[Config] = None


def init_config(config_file: Optional[str] = None) -> Config:
    """初始化全局配置"""
    global _global_config
    
    if config_file is None:
        # 尝试自动查找配置文件
        possible_paths = [
            'config/development.yaml',
            'config/production.yaml', 
            'hchdb.yaml',
            'config.yaml'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                config_file = path
                break
    
    _global_config = Config(config_file)
    return _global_config


def get_config() -> Config:
    """获取全局配置实例"""
    if _global_config is None:
        raise ConfigurationError("Configuration not initialized. Call init_config() first.")
    return _global_config


# 环境变量覆盖支持
def apply_env_overrides(config: Config) -> None:
    """应用环境变量覆盖"""
    env_mappings = {
        'HCHDB_HOST': 'server.host',
        'HCHDB_MYSQL_PORT': 'server.ports.mysql',
        'HCHDB_LOG_LEVEL': 'logging.level',
        'HCHDB_MAX_CONNECTIONS': 'connection.pool.max_connections',
        'HCHDB_DEBUG': 'development.debug',
    }
    
    for env_var, config_key in env_mappings.items():
        value = os.getenv(env_var)
        if value is not None:
            # 尝试转换类型
            if config_key.endswith('.debug'):
                value = value.lower() in ('true', '1', 'yes', 'on')
            elif 'port' in config_key or 'connections' in config_key:
                try:
                    value = int(value)
                except ValueError:
                    continue
            
            config.set(config_key, value)