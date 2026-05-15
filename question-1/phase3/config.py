import os

# LLM provider configuration
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "deepseek")  # deepseek | openai | anthropic

# DeepSeek
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-v4-flash"

# OpenAI
#OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
#OPENAI_BASE_URL = "https://api.openai.com/v1"
#OPENAI_MODEL = "gpt-4o"

# Anthropic
#ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
#ANTHROPIC_MODEL = "claude-sonnet-4-6"

# File catalog — tells the Agent what SOPs exist
FILE_CATALOG = """| 文件名 | 部门 | 涵盖内容 |
| sop-001.html | 后端服务 | OOM内存溢出排查、服务超时处理、熔断降级策略、故障分级响应 |
| sop-002.html | 数据库DBA | MySQL主从复制延迟、慢查询优化、数据库连接池耗尽、数据备份恢复 |
| sop-003.html | 前端 | 页面白屏排查、CDN资源加载失败、浏览器兼容性、JS错误率、页面性能劣化 |
| sop-004.html | SRE基础设施 | K8s集群问题、监控告警配置、服务器容量规划、生产故障应急响应 |
| sop-005.html | 安全团队 | 安全事件定级响应、入侵行为检测、系统漏洞修复、DDoS攻击防护 |
| sop-006.html | 数据平台 | ETL数据管道故障、Spark离线计算任务失败、大数据报表延迟 |
| sop-007.html | 移动客户端 | App崩溃率突增、热修复补丁下发、推送服务到达率、移动端OOM |
| sop-008.html | AI算法 | 模型推理延迟、推荐系统质量下降、GPU集群算力调度、特征数据异常 |
| sop-009.html | QA质量保障 | 测试环境故障、自动化测试失败、CI/CD流水线卡点、发版质量门禁 |
| sop-010.html | 网络与CDN | CDN节点故障、DNS域名解析异常、网络链路连通性、DDoS流量清洗 |"""
