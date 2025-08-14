"""
HchDB 异常定义
"""

from typing import Optional, Dict, Any


class HchDBError(Exception):
    """HchDB 基础异常类"""
    
    def __init__(self, message: str, error_code: int = 1000, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"[{self.error_code}] {self.message} (details: {self.details})"
        return f"[{self.error_code}] {self.message}"


class ProtocolError(HchDBError):
    """协议相关错误"""
    
    def __init__(self, message: str, error_code: int = 1001, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code, details)


class ConnectionError(HchDBError):
    """连接相关错误"""
    
    def __init__(self, message: str, error_code: int = 1002, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code, details)


class AuthenticationError(HchDBError):
    """认证相关错误"""
    
    def __init__(self, message: str, error_code: int = 1003, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code, details)


class RoutingError(HchDBError):
    """路由相关错误"""
    
    def __init__(self, message: str, error_code: int = 1004, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code, details)


class StorageError(HchDBError):
    """存储相关错误"""
    
    def __init__(self, message: str, error_code: int = 1005, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code, details)


class ConfigurationError(HchDBError):
    """配置相关错误"""
    
    def __init__(self, message: str, error_code: int = 1006, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code, details)


# MySQL 错误码映射
MYSQL_ERROR_CODES = {
    # 连接相关
    1040: "Too many connections",
    1045: "Access denied for user",
    1049: "Unknown database",
    1251: "Client does not support authentication protocol",
    
    # SQL相关
    1064: "SQL syntax error",
    1146: "Table doesn't exist",
    1062: "Duplicate entry",
    1452: "Cannot add or update a child row: a foreign key constraint fails",
    
    # 系统相关
    1205: "Lock wait timeout exceeded",
    1213: "Deadlock found when trying to get lock",
}


def create_mysql_error(error_code: int, custom_message: Optional[str] = None) -> ProtocolError:
    """创建MySQL兼容的错误"""
    message = custom_message or MYSQL_ERROR_CODES.get(error_code, "Unknown MySQL error")
    return ProtocolError(
        message=message,
        error_code=error_code,
        details={"mysql_error_code": error_code}
    )