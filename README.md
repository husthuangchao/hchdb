# HchDB - Python分布式数据库

基于Python实现的类PolarDB-X分布式数据库。

## 🏗️ 项目结构

```
hchdb/
├── hchdb/                  # 核心代码包
│   ├── protocol/          # 协议处理层
│   │   ├── mysql.py       # MySQL协议实现
│   │   ├── xprotocol.py   # X-Protocol实现
│   │   └── packet.py      # 协议包处理
│   ├── connection/        # 连接管理
│   │   ├── pool.py        # 连接池管理
│   │   ├── manager.py     # 连接生命周期
│   │   └── health.py      # 健康检查
│   ├── session/           # 会话管理
│   │   ├── session.py     # 会话状态
│   │   ├── auth.py        # 认证授权
│   │   └── context.py     # 上下文管理
│   ├── routing/           # 路由和负载均衡
│   │   ├── router.py      # 请求路由
│   │   ├── balancer.py    # 负载均衡
│   │   └── rules.py       # 路由规则
│   ├── storage/           # 存储层接口
│   │   ├── backend.py     # 后端存储接口
│   │   ├── mysql_backend.py  # MySQL后端实现
│   │   └── metadata.py    # 元数据管理
│   ├── common/            # 公共组件
│   │   ├── config.py      # 配置管理
│   │   ├── logging.py     # 日志系统
│   │   ├── exceptions.py  # 异常定义
│   │   └── utils.py       # 工具函数
│   └── monitoring/        # 监控和指标
│       ├── metrics.py     # 指标收集
│       ├── health.py      # 健康检查
│       └── profiler.py    # 性能分析
├── config/                # 配置文件
│   ├── development.yaml   # 开发环境配置
│   ├── production.yaml    # 生产环境配置
│   └── test.yaml          # 测试环境配置
├── tests/                 # 测试用例
│   ├── unit/              # 单元测试
│   ├── integration/       # 集成测试
│   └── performance/       # 性能测试
├── docs/                  # 文档
│   ├── design/            # 设计文档
│   ├── api/               # API文档
│   └── deployment/        # 部署文档
├── tools/                 # 开发工具
│   ├── benchmark.py       # 性能基准测试
│   ├── client.py          # 测试客户端
│   └── migration.py       # 数据迁移工具
├── examples/              # 示例代码
│   ├── basic_usage.py     # 基础使用示例
│   └── advanced_demo.py   # 高级功能演示
├── requirements.txt       # 依赖包列表
├── setup.py              # 安装脚本
├── main.py               # 服务器启动入口
└── README.md             # 项目说明
```

## 🚀 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动服务器
```bash
python main.py --config config/development.yaml
```

### 测试连接
```bash
mysql -h localhost -P 3306 -u root
```

## 📅 开发进度

- [x] Day 1: MySQL协议层和连接管理
- [ ] Day 2: SQL解析器实现
- [ ] Day 3: 路由规则引擎
- [ ] Day 4: 查询优化器
- [ ] Day 5: 分布式执行引擎
- ...

## 🛠️ 技术栈

- **Python**: 3.8+
- **异步框架**: asyncio
- **网络库**: asyncio + socket
- **配置管理**: PyYAML
- **日志**: structlog
- **监控**: prometheus_client
- **测试**: pytest

## 📖 文档

详细文档请查看 [docs/](docs/) 目录。
