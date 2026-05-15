# On-Call 助手 — 项目设计文档

## 项目概述

为 10 份部门 On-Call SOP 文档构建一个完整的 On-Call 助手系统，包含三个独立阶段：

| 阶段 | 路由 | 端口 | 功能 |
|---|---|---|---|
| Phase 1 | `/v1` | 8001 | 关键词搜索引擎 |
| Phase 2 | `/v2` | 8002 | 语义搜索引擎 |
| Phase 3 | `/v3` | 8003 | On-Call 助手 Agent |

---

## Phase 1：关键词搜索引擎

### 算法选型

- **索引结构**：倒排索引（Inverted Index）
- **分词**：jieba（中文）+ 英文保留原词
- **HTML 解析**：BeautifulSoup4，删除 `<script>` / `<style>` 标签，解码 HTML 实体
- **评分**：BM25（k1=1.5, b=0.75），替代最初的简单 TF/length

### BM25 评分公式

```
score(Q, D) = Σ IDF(qi) × BM25_TF(qi, D)

IDF(qi) = log((N - df + 0.5) / (df + 0.5) + 1)

BM25_TF = (tf × (k1 + 1)) / (tf + k1 × (1 - b + b × dl / avgdl))
```

### 字段加权

| 字段 | 权重 | 说明 |
|---|---|---|
| key_content | ×3 | 文档核心场景描述 |
| title | ×2 | 标题命中强信号 |
| body | ×1 | 正文基准 |

### 为什么选 BM25 而不是简单 TF

1. **IDF**：稀有词权重高，"OOM" 比"服务"更有区分度
2. **TF 饱和**：词出现 5 次不是 1 次的 5 倍重要
3. **长度归一化**：`b` 参数控制长文档惩罚

### 为什么不是 AND 语义

BM25 不要求所有查询词都出现在文档中。查询词在文档中不出现则该项贡献 0，不影响其他词的打分。这解决了口语查询中 "怎么办"、"了" 等噪声词导致全军覆没的问题。

### 验证用例

| 查询 | 期望 | 结果 |
|---|---|---|
| `OOM` | sop-001 | ✅ |
| `故障` | 多文档 | ✅ |
| `replication` | 空（仅 script 内） | ✅ |
| `CDN` | sop-003, sop-010 | ✅ |
| `&` | 含 & 的文档 | ✅ |

---

## Phase 2：语义搜索引擎

### 模型选型

使用 `BAAI/bge-base-zh-v1.5`（1024 token），替代最初的 `bge-small`（512 token）。

### 文档表示（Early Fusion）

```python
doc_repr = (
    f"部门：{dept_original}。部门说明：{dept_expanded}。"
    f"部门：{dept_original}。部门说明：{dept_expanded}。"   # 重复 2x 提高权重
    f"关键内容：{key_content}。关键内容：{key_content}。"    # 重复 2x
    f"标题：{title}。"
    f"正文：{text[:1200]}"
)
embedding = model.encode(doc_repr, normalize=True)
```

### 部门描述（三段式）

每份 SOP 的部门描述包含三个部分：部门标签行、职责陈述、用户场景衔接。

```
"后端服务" → "接口与后端服务 后端团队\n
  后端服务团队是公司所有后端接口和服务端问题的唯一负责团队。\n
  我们负责后端服务的稳定性保障、接口性能优化、服务超时排查和OOM内存溢出问题处理。\n
  如果遇到接口报错、接口响应慢、服务不可用、后端服务崩溃、OOM内存不足等问题，请联系后端服务团队。"
```

### 查询预处理（主语加权）

剥离通用故障词（挂了、崩了、出问题...），主语重复 3 倍。

```python
FAIL_WORDS = {"挂了", "崩了", "坏了", "打不开", "出问题", ...}

def weight_query(query):
    subject = query
    for w in FAIL_WORDS:
        subject = subject.replace(w, "")
    if not subject or subject == query:
        return query
    return f"{subject} {subject} {subject} {query}"

# 效果："服务器挂了" → "服务器 服务器 服务器 服务器挂了"
#        主语占 75%，故障词只占 25%
```

### 为什么 Late Fusion 不如 Early Fusion

短字段（如部门名 "SRE" 仅 3 个字母）独立编码时噪声太大。单向量中通过文本重复自然加权，模型在统一空间中编码，更稳定。

### 放弃的尝试

- **HyDE**：LLM 编假文档再匹配，10 份文档规模下收益不抵延迟
- **查询改写**：LLM 改写口语→技术词，但 DeepSeek 思考模式下短回复不稳定
- **混合检索**：P1 关键词 + P2 语义加权，最终在 Phase 3 中整合

### 验证用例

| 查询 | 期望 | P1 结果 | P2 结果 |
|---|---|---|---|
| 服务器挂了 | sop-001, sop-004 靠前 | 0 个结果 | sop-001 #1 |
| 黑客攻击 | sop-005 靠前 | 0 个结果 | sop-005 #1 |
| 机器学习模型出问题 | sop-008 靠前 | 0 个结果 | sop-008 #1 |

---

## Phase 3：On-Call 助手 Agent

### 架构

```
用户问题
  │
  ├─→ 检索层 (retrieve.py)
  │     ├─ P1 BM25 × 101 chunks → 关键词命中
  │     ├─ P2 Embedding × 101 chunks → 语义匹配
  │     ├─ 归一化 → 加权合并 (W1=0.3, W2=0.7)
  │     ├─ 阈值过滤 (≥0.35)
  │     ├─ max+bonus 聚合到父文档
  │     └─ 返回 Top-3 文档 ID
  │
  ├─→ Agent (agent.py)
  │     ├─ System Prompt 含检索到的文档列表
  │     ├─ readFile 工具读取完整文档
  │     └─ LLM 综合回答
  │
  └─→ 前端 (chat.html)
        ├─ 用户消息
        ├─ 📄 读取 sop-001.html  (一行，不展开内容)
        └─ Agent 回答
```

### Chunk 策略

每份 SOP 按 H2/H3 标题结构切分，生成 101 个 chunk。

```
sop-001.html (3437 chars)
├─ sop-001_chunk-000  一、值班职责
├─ sop-001_chunk-001  二、监控指标
├─ sop-001_chunk-002  场景一：服务大面积超时
├─ sop-001_chunk-003  场景二：单服务OOM崩溃    ← "OOM" 查询锚点
├─ sop-001_chunk-004  场景三：数据库连接池耗尽
├─ ...
└─ sop-001_chunk-010  六、工具与命令参考
```

### 父子 Chunk 结构

**检索用 Chunk（精细匹配），交付用全文（完整上下文）**。

```
Chunk 级检索 → 找到最相关的 chunk
  → 映射到父文档 (sop-001_chunk-003 → sop-001)
  → max+bonus 聚合父文档分数
  → 返回完整文档 ID
  → Agent readFile 读取完整文件，非 chunk
```

### 文档聚合：max+bonus

```python
doc_score = max_chunk_score + 0.02 × sqrt(count_above_threshold - 1)
```

- 一个 chunk 高分 → 靠 max 取胜
- 多个 chunk 中高分 → bonus 加持（√ 压制多 chunk 优势）
- 大量低分 chunk → 无影响

### RRF → 加权归一化转换

最初用 RRF（Reciprocal Rank Fusion），但 RRF 只有排名没有分数，无法做阈值过滤。改为加权归一化后可设置阈值 0.35，并实现动态 k。

### 为什么去掉了 Reranker

`BAAI/bge-reranker-base` 在 10 份文档规模下收益不明确——额外加载 400MB 模型，对 "主从延迟" 查询反而起了反作用（sop-002 从 #1 降到 #3）。

### LLM 配置

| 参数 | 值 |
|---|---|
| Provider | DeepSeek |
| Model | deepseek-v4-flash |
| API | OpenAI 兼容格式 |
| Base URL | https://api.deepseek.com/v1 |
| Max tokens | 4096（2048→4096 解决截断） |

### 职责分离

```
config.py   → API Key / 模型 / 文件目录（纯配置）
llm.py      → LLM 抽象层（DeepSeek/OpenAI/Anthropic 统一接口）
agent.py    → Agent 循环 + readFile（只依赖 llm 接口）
retrieve.py → P1+P2+加权+阈值+max+bonus
chunker.py  → H2/H3 切 chunk
parser.py   → HTML 解析（共用）
```

### 前端修复

| 问题 | 修复 |
|---|---|
| 回答被截断 | max_tokens 2048→4096 |
| 看不到读了什么文件 | 显示 `📄 读取 sop-001.html` 一行 |
| 返回了完整文件内容 | API 只返回文件名，不返回内容 |

### 验证用例

| 查询 | 检索结果 | 命中 |
|---|---|---|
| 服务 OOM 了怎么办 | sop-001, sop-007 | 1/1 ✅ |
| 数据库主从延迟超过30秒 | sop-002, sop-010, sop-001 | 1/1 ✅ |
| 怀疑有人入侵了系统 | sop-005, sop-010 | 1/1 ✅ |
| 推荐结果质量下降了 | sop-008, sop-003, sop-006 | 1/1 ✅ |
| P0 故障的响应流程 | sop-004, sop-005, sop-001 | 3/3 ✅ |

---

## 项目文件结构

```
question-1/
├── config.py             # API Key + 模型 + 文件目录
├── parser.py             # HTML 解析（共用）
├── chunker.py            # H2/H3 切 chunk
│
├── engine.py             # P1 BM25 倒排索引引擎
├── app.py                # P1 FastAPI :8001
│
├── engine_v2.py          # P2 BGE embedding 引擎（1024 token）
├── app_v2.py             # P2 FastAPI :8002
│
├── retrieve.py           # P1+P2 混合检索 + 阈值 + max+bonus
├── agent.py              # Agent 循环 + readFile 工具
├── llm.py                # LLM 抽象层
├── app_v3.py             # P3 FastAPI :8003
│
├── templates/
│   ├── search.html       # P1 搜索页
│   ├── search_v2.html    # P2 搜索页
│   └── chat.html         # P3 对话页
│
├── data/                 # 10 份原始 SOP
├── data/chunks/          # 101 个 chunk 片段
│
├── requirements.txt
└── DESIGN.md             # 本文档
```

## 启动

```bash
pip install -r requirements.txt

python -m uvicorn app:app    --port 8001   # Phase 1
python -m uvicorn app_v2:app --port 8002   # Phase 2
python -m uvicorn app_v3:app --port 8003   # Phase 3
```
