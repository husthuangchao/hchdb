# HchDB 快速开始

## 🚀 第一天成果

恭喜！你已经完成了HchDB分布式数据库的第一天开发，实现了：

✅ **MySQL协议处理器** - 完整的协议包处理和握手流程  
✅ **连接管理系统** - 连接池和生命周期管理  
✅ **配置管理** - YAML配置文件和环境变量支持  
✅ **服务器框架** - 多端口服务器架构  
✅ **基础测试** - 可以真正运行和连接的数据库！

## 📦 安装依赖

```bash
cd hchdb
pip install -r requirements.txt
```

## 🏃‍♂️ 运行数据库

### 方法1: 使用main.py启动
```bash
python main.py --config config/development.yaml
```

### 方法2: 使用示例程序
```bash
python examples/basic_usage.py
```

## 🧪 测试连接

### 使用MySQL客户端连接
```bash
mysql -h localhost -P 3306 -u root
```

### 使用内置测试客户端
```bash
python tools/client.py
```

### 测试SQL命令
连接成功后，试试这些命令：
```sql
-- 查看数据库列表
SHOW DATABASES;

-- 查看表列表  
SHOW TABLES;

-- 执行简单查询
SELECT 'Hello HchDB!' as message;

-- 查看版本信息
SELECT VERSION();

-- 查看系统变量
SHOW VARIABLES LIKE 'version%';
```

## 📊 监控和调试

### 查看日志
服务器启动后会输出详细的日志信息，包括：
- 连接建立/断开
- 协议包收发
- 查询执行过程
- 错误信息

### 配置调试模式
在 `config/development.yaml` 中设置：
```yaml
development:
  debug: true

logging:
  level: "DEBUG"
```

## 🔧 配置说明

主要配置项：
```yaml
server:
  host: "0.0.0.0"
  ports:
    mysql: 3306        # MySQL协议端口
    management: 3307   # 管理端口  
    internal: 3308     # 内部通信端口

connection:
  pool:
    max_connections: 1000
    idle_timeout: 300

authentication:
  users:
    root:
      password: ""     # 空密码
      privileges: ["ALL"]
```

## 🎯 今天实现的核心功能

### 1. MySQL协议兼容
- ✅ 握手包处理
- ✅ 认证流程
- ✅ COM_QUERY查询处理
- ✅ COM_PING心跳检测
- ✅ 结果集封装

### 2. 连接管理  
- ✅ 连接池化
- ✅ 连接限制
- ✅ 空闲连接清理
- ✅ 连接统计

### 3. 基础查询支持
- ✅ SELECT查询
- ✅ SHOW DATABASES
- ✅ SHOW TABLES  
- ✅ SHOW VARIABLES
- ✅ 错误处理

## 🚧 当前限制

作为第一天的实现，有以下限制：
- 🔸 认证简化（只检查用户存在）
- 🔸 查询结果是模拟数据
- 🔸 不支持复杂SQL解析
- 🔸 没有真正的存储后端
- 🔸 单机运行（未实现分布式）

## 📈 性能测试

### 连接测试
```bash
# 测试并发连接（需要安装mysqlslap）
mysqlslap --host=localhost --port=3306 --user=root \
  --concurrency=10 --iterations=100 \
  --query="SELECT 'Hello HchDB' as message"
```

### 预期性能
基于配置的性能指标：
- 🎯 最大连接数: 1000
- 🎯 单连接QPS: >1000  
- 🎯 连接建立延迟: <10ms
- 🎯 内存使用: <100MB (100连接)

## 🐛 故障排除

### 常见问题

**1. 端口被占用**
```
Error: [Errno 48] Address already in use
```
解决：修改配置文件中的端口号或停止占用端口的进程

**2. 配置文件未找到**  
```
Configuration file not found
```
解决：确保config/development.yaml文件存在，或指定正确的配置文件路径

**3. MySQL客户端连接失败**
```
ERROR 2003 (HY000): Can't connect to MySQL server
```
解决：确认服务器已启动，端口配置正确

### 调试技巧

1. **启用DEBUG日志**：设置日志级别为DEBUG查看详细信息
2. **使用测试客户端**：`tools/client.py`可以看到原始协议交互
3. **检查连接统计**：观察服务器日志中的连接统计信息

## 🎉 成就解锁

🏆 **协议大师**: 实现了完整的MySQL协议处理  
🏆 **连接专家**: 建立了高效的连接管理系统  
🏆 **架构师**: 设计了可扩展的服务器架构  
🏆 **测试达人**: 创建了完整的测试框架  

## 📚 下一步计划

**Day 2 预览**：
- 🎯 SQL解析器实现
- 🎯 查询路由逻辑  
- 🎯 后端存储连接
- 🎯 元数据管理
- 🎯 性能监控完善

准备好继续构建这个分布式数据库了吗？🚀