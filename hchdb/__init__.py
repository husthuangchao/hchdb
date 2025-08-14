"""
HchDB - Python分布式数据库

基于Python实现的类PolarDB-X分布式数据库，用于学习分布式数据库核心原理。
"""

__version__ = "0.1.0"
__author__ = "hch"
__email__ = "hch@example.com"

from .common.exceptions import (
    HchDBError,
    ProtocolError,
    ConnectionError,
    AuthenticationError,
    RoutingError,
    StorageError,
)

__all__ = [
    "__version__",
    "__author__", 
    "__email__",
    "HchDBError",
    "ProtocolError", 
    "ConnectionError",
    "AuthenticationError",
    "RoutingError",
    "StorageError",
]