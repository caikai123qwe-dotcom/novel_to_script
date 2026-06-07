# 小说剧本转换器 · Novel → Script

> 将包含 3 个或以上章节的中文（或英文）小说文本，通过 Google Gemini 进行深度语义分析，自动重构为结构化剧本大纲，并以 YAML 格式输出，供作者直接编辑打磨。
>
> 短篇（≤5 万字）走**全文直送**模式；长篇（>5 万字）自动切换 **RAG 分章检索**模式，理论上无字数上限。

---

## 目录

- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [两种分析模式](#两种分析模式)
- [API 接口说明](#api-接口说明)
- [Schema 设计说明](#schema-设计说明)
- [YAML 输出示例](#yaml-输出示例)
- [章节识别规则](#章节识别规则)
- [常见问题](#常见问题)
- [注意事项](#注意事项)

---

## 项目结构

```
novel2script/
├── backend/
│   ├── Main.py               # FastAPI 服务入口，路由 + 异步任务队列
│   ├── gemini_analyzer.py    # 分析路由：自动选择全文或 RAG 模式
│   ├── models.py             # Pydantic Schema 定义（核心数据结构）
│   ├── yaml_utils.py         # 结果后处理 + 自定义 YAML 序列化
│   ├── config.py             # 环境变量加载
│   ├── cli.py                # 命令行入口（保留备用）
│   ├── rag/
│   │   ├── embeddings.py     # Gemini 向量嵌入（gemini-embedding-001）
│   │   ├── vector_store.py   # 内存余弦相似度向量库
│   │   ├── pipeline.py       # RAG 流水线：分块 → 索引 → 全局分析 → 逐章分析
│   │   └── text_chunker.py   # 章节切分 + 子块生成（1500字/块，overlap=200）
│   └── requirements.txt
├── frontend/
│   ├── app.py                # Streamlit 前端
│   └── requirements.txt
├── .env.example
└── README.md
```

---

## 快速开始

### 1. 配置 API 密钥

```bash
cp .env.example .env
```

编辑 `.env`：

```env
GEMINI_API_KEY=your_google_gemini_api_key
GEMINI_MODEL_NAME=gemini-2.5-flash    # 可选，默认值
GEMINI_EMBED_MODEL=gemini-embedding-001  # 可选，RAG 向量嵌入模型
```

> 申请 Gemini API 密钥：https://aistudio.google.com/

---

### 2. 安装依赖

```bash
# 后端
cd backend
pip install -r requirements.txt

# 前端（新开一个终端）
cd frontend
pip install -r requirements.txt
```

---

### 3. 启动服务

**终端 1 — 后端（FastAPI）**

```bash
cd backend
uvicorn Main:app --reload --port 8000
```

交互式 API 文档：http://localhost:8000/docs

**终端 2 — 前端（Streamlit）**

```bash
cd frontend
streamlit run app.py --server.port 8501
```

浏览器访问：http://localhost:8501

---

## 两种分析模式

本项目根据输入文本长度自动选择分析策略，也可通过 `use_rag` 参数手动指定。

### 全文模式（默认，≤5 万字）

将完整小说文本一次性送入 Gemini，由模型完成章节识别、人物提取、场景拆解的全部工作。适合短中篇小说，速度快，上下文连贯性最佳。

```
小说文本 → Gemini（单次调用）→ AIScriptDraft → YAML
```

### RAG 分章模式（自动触发，>5 万字）

对长篇小说进行分块向量化，通过检索增强的方式逐章生成剧本结构，避免超出模型上下文窗口。流程如下：

```
小说文本
  ↓ text_chunker：按章节切分 + 1500字子块（overlap 200字）
  ↓ embeddings：调用 gemini-embedding-001 批量生成向量
  ↓ vector_store：存入内存余弦相似度向量库
  ↓ pipeline.analyze_global()：检索全局相关片段 → 生成 AIGlobalDraft
  ↓ pipeline.analyze_chapter() × N：逐章检索上下文 → 生成 AIAct
  → 合并输出 → YAML
```

**两种模式的对比：**

| | 全文模式 | RAG 分章模式 |
|---|---|---|
| 自动触发条件 | 文本 ≤ 5 万字 | 文本 > 5 万字 |
| LLM 调用次数 | 1 次 | 1 次全局 + N 次（每章 1 次） |
| 上下文来源 | 完整原文 | 向量检索最相关片段 |
| 支持参考文档注入 | ✗ | ✓ |
| 长篇小说适配 | 受上下文窗口限制 | 理论上无长度上限 |
| `generation.mode` 字段 | `gemini_semantic_draft` | `gemini_rag_chapter` |

### 参考文档注入（RAG 专属）

RAG 模式支持在分析前上传外部参考文本（如人物关系说明、风格参考、世界观设定），注入向量库后参与检索，帮助 AI 在改编时保持一致性：

```bash
# 上传参考文档
curl -X POST http://localhost:8000/rag/references \
  -H "Content-Type: application/json" \
  -d '{"ref_id": "worldbuilding", "text": "此世界中魔法来源于..."}'

# 提交分析时指定参考文档 ID
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "...", "source_name": "我的小说", "use_rag": true, "reference_ids": ["worldbuilding"]}'
```

---

## API 接口说明

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/health` | 服务健康检查 |
| POST | `/analyze` | 提交文本（JSON body） |
| POST | `/analyze/upload` | 上传 `.txt` 文件 |
| GET  | `/jobs/{job_id}` | 查询任务状态 + 完整结果 |
| GET  | `/jobs/{job_id}/yaml` | 直接获取 YAML 纯文本 |
| GET  | `/jobs` | 列出所有历史任务 |
| POST | `/rag/references` | 上传参考文档（RAG 模式） |
| GET  | `/rag/references` | 列出已上传的参考文档 |

### 异步任务流程

由于 Gemini 分析长篇小说通常耗时 30–120 秒（RAG 模式耗时更长），接口采用异步设计：

```
POST /analyze  →  立即返回 job_id
     ↓
轮询 GET /jobs/{job_id}
     ↓  status: pending → running → done
     ↓  progress 字段实时反映当前步骤（如"RAG: 章节分析 3/12 — 第三章"）
GET /jobs/{job_id}/yaml  →  下载结果
```

### POST /analyze 请求体

```json
{
  "text": "第一章 ...\n第二章 ...\n第三章 ...",
  "source_name": "我的小说",
  "use_rag": null,
  "reference_ids": ["worldbuilding"]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | 小说正文，必填 |
| `source_name` | string | 作品名，用于输出文件命名，默认 `"novel"` |
| `use_rag` | bool \| null | `true` 强制 RAG，`false` 强制全文，`null` 自动判断 |
| `reference_ids` | list \| null | 注入 RAG 检索库的参考文档 ID 列表 |

---

## Schema 设计说明

Schema 定义在 `backend/models.py`，是本项目的核心。它不是简单的数据容器，而是一套将**文学叙事语言**映射为**剧作专业语言**的转译规范。

---

### 两套顶层 Schema 的分工

新版引入了两套顶层 Schema，对应两种不同的分析场景：

**`AIScriptDraft`（全文模式）**

```python
class AIScriptDraft(BaseModel):
    logline:    str
    theme:      str
    setting:    str
    tone:       str
    characters: List[AICharacter]
    acts:       List[AIAct]          # 包含完整幕结构
```

用于短文本的单次调用，一次性返回全局定性和所有章节结构。

**`AIGlobalDraft`（RAG 模式第一步）**

```python
class AIGlobalDraft(BaseModel):
    logline:    str
    theme:      str
    setting:    str
    tone:       str
    characters: List[AICharacter]   # 无 acts 字段
```

RAG 模式下，全局分析和逐章分析是两次独立的 LLM 调用。第一次只需要提炼故事全局定性，不需要生成章节结构，因此拆出了这个轻量 Schema——减少单次调用的输出负担，也避免 AI 在缺乏足够上下文时强行生成章节内容。`AIAct` 在后续每章的独立调用中逐一生成，并在 `pipeline.run()` 中合并回完整结构。

---

### 顶层字段：`logline / theme / setting / tone`

**设计原因**

小说和剧本在叙事层面存在根本性差异：小说可以大段内心独白、散漫叙事；剧本必须在开机前让导演、演员、制片人在几分钟内对故事达成共识。这四个字段正是好莱坞开发流程中"一页纸提案"的标准要素，强制 AI 在展开结构之前先完成整体定性，避免后续场景分析缺乏统一方向。

---

### 人物层：`AICharacter`

```python
class AICharacter(BaseModel):
    name:        str
    role:        str   # protagonist / antagonist / supporting
    description: str
    traits:      List[str]
```

**设计原因**

`characters` 置于顶层（而非各章之内），因为剧本人物的性格弧线贯穿全局，不应被切分进章节局部视角。`role` 使用受控词汇而非自由文本，让前端渲染和下游工具可以直接条件判断。`traits` 设计为列表防止 AI 输出冗长散文描述，同时便于标签检索。上限 12 人的约束写在 prompt 中，源自剧本实践——超过 12 个核心人物会导致观众难以追踪人物关系。

---

### 幕层：`AIAct`

```python
class AIAct(BaseModel):
    title:   str
    summary: str
    purpose: str
    scenes:  List[AIScene]
```

**设计原因**

`summary` 和 `purpose` 区分了两个维度：`summary` 回答"发生了什么"（情节层），`purpose` 回答"为什么需要这一幕"（结构层）。例如"主角被陷害入狱"是情节，"通过最低点考验主角意志"才是其在三幕剧结构中的功能。两者并存，帮助改编者在调整章节顺序时快速判断是否影响整体结构。在 RAG 模式下，`AIAct` 是每章独立调用的产物，`pipeline.run()` 将所有章节的 `AIAct` 收集后统一拼装进最终输出。

---

### 场景层：`AIScene`

```python
class AIScene(BaseModel):
    location:            str
    time:                str
    goal:                str
    conflict:            str
    beats:               List[AISceneBeat]
    characters:          List[str]
    dialogue_candidates: List[AISpeakerLine]
```

**设计原因**

这是整个 Schema 最重要的层级，对应剧本中的"场"（Scene）。

- **`location` + `time`**：剧本场头（Scene Heading）的直接来源，如 `INT. 陈旧的客厅 - 深夜`，要求 AI 从小说描写中提炼具体地点，而非"某处"之类的笼统概念。
- **`goal` + `conflict`**：来自编剧理论中"每场戏必须有人物目标和阻碍"的铁律。这两个字段强制 AI 识别每场戏的戏剧引擎，过滤掉小说中大量无戏剧功能的过渡性叙述段落。
- **`beats`**：情节节拍是小说与剧本转换中损耗最大的信息。小说用铺垫、回忆、内心描写构建张力，剧本只有可拍摄的动作。`beats` 字段要求 AI 将叙事流拆解为离散的可视化动作单元，每个节拍对应一次摄影机需要捕捉的"变化"。
- **`dialogue_candidates`**：只筛选最多 3 条最具戏剧张力的台词，配合 `intent`（潜台词）字段，帮助编剧快速找到值得保留的原著对白，而不是把全部对话一股脑输出。

---

### 节拍层：`AISceneBeat`

```python
class AISceneBeat(BaseModel):
    order:           int
    action:          str
    emotional_shift: str
```

**设计原因**

`action` 要求用"镜头感"的语言描写动作，而非文学性的内心叙述。`emotional_shift` 记录每个节拍带来的情感或力量对比变化，是好莱坞节拍表（Beat Sheet）方法论的直接体现——一个没有情感转变的节拍在剧本中是无效的，应当删除或合并。两个字段的分离让改编者能独立评估"动作够不够有力"和"情感节奏是否合理"。

---

### 台词层：`AISpeakerLine`

```python
class AISpeakerLine(BaseModel):
    speaker: str
    line:    str
    intent:  str
```

**设计原因**

`intent`（潜台词）是这个三元组中最关键的字段。优秀剧本台词的特征是"说的是一件事，意思是另一件事"。要求 AI 为每条台词标注潜台词，一方面能验证 AI 是否真正理解了对话的戏剧功能，另一方面也为改编者提供改写方向——当原著台词过于直白时，`intent` 告诉编剧这句话真正需要表达什么。

---

### Schema 整体层级关系

```
全文模式                          RAG 模式
─────────────────────────         ─────────────────────────────────────
AIScriptDraft                     AIGlobalDraft (第1次调用)
├── logline / theme / setting / tone    ├── logline / theme / setting / tone
├── characters: List[AICharacter]       └── characters: List[AICharacter]
└── acts: List[AIAct]  ◄──────────────────── AIAct × N (每章独立调用)
                                              │
共同的子结构                                   │
─────────────────────────                    ▼
AIAct                             title / summary / purpose
└── scenes: List[AIScene]
    ├── location / time           →  场头（Scene Heading）
    ├── goal / conflict           →  戏剧引擎
    ├── characters                →  出场人物
    ├── beats: List[AISceneBeat]  →  动作序列
    │   └── order / action / emotional_shift
    └── dialogue_candidates       →  精选台词
        └── speaker / line / intent
```

---

## YAML 输出示例

RAG 模式的输出会在 `generation` 字段中标注：

```yaml
schema_version: "2.0_gemini"
meta:
  title: "三体"
  source_type: novel
  source_chapter_count: 8
  language: zh
  input_digest: "a3f1c2b4d5e6"
story:
  logline: "物理学家叶文洁在文革创伤中向三体星系发出信号，引发人类文明生死存亡的危机。"
  theme: "文明的脆弱与人性在绝望中的极端选择"
  setting: "1960年代中国文革至近未来，横跨地球与三体星系"
  tone: "悬疑冷峻、宏大史诗"
  characters:
    - name: "叶文洁"
      role: protagonist
      description: "天体物理学家，经历文革至亲之死后对人类文明彻底失望，成为引狼入室的关键人物。"
      traits: ["理性冷静", "内心创伤", "决绝"]
acts:
  - title: "第一章 · 陨落年代"
    summary: "文革运动中，叶文洁目睹父亲被批斗致死，对人类的善意彻底破灭。"
    purpose: "建立主角的核心创伤与动机，为后续背叛人类埋下心理根源。"
    scenes:
      - location: "北京某大学批斗会现场"
        time: "1966年，烈日正午"
        goal: "叶文洁试图在人群中保护父亲"
        conflict: "她无力对抗集体暴力，任何举动都会加重父亲的处境"
        characters: ["叶文洁", "叶哲泰"]
        beats:
          - order: 1
            action: "叶哲泰被押上台，颈挂黑板，学生大声宣读罪状"
            emotional_shift: "叶文洁从恐惧转为压抑的愤怒"
          - order: 2
            action: "叶文洁试图上前，被人群挡回，与父亲四目相对"
            emotional_shift: "父女无声诀别，绝望凝固"
        dialogue_candidates:
          - speaker: "叶哲泰"
            line: "不要过来。"
            intent: "父亲用最后的权威保护女儿，同时接受了自己的命运。"
generation:
  tool: "novel_to_script_gemini"
  mode: "gemini_rag_chapter"   # 全文模式为 gemini_semantic_draft
  notes:
    - "本结果由 Gemini RAG 分章检索分析生成。"
    - "长文本通过向量检索选取相关片段后逐章生成。"
    - "场景与对白为 AI 草案，需人工润色。"
```

---

## 章节识别规则

提交的小说必须包含**至少 3 个**可识别的章节标记，否则接口返回 422 错误。RAG 模式的分块也依赖同一套规则。

| 格式 | 示例 |
|------|------|
| 中文章节 | `第一章`、`第2章`、`第三节`、`第一幕` |
| 英文章节 | `Chapter 1`、`Chapter One`、`Act I`、`Act 2` |
| Markdown 标题 | `## 第一章`、`# 序章` |

---

## 常见问题

**Q：提示 503 UNAVAILABLE，分析失败？**

Gemini 服务端临时过载，与代码无关。建议：
1. 稍等几分钟后点击「重新分析」重试
2. 在 `.env` 中改用 `GEMINI_MODEL_NAME=gemini-2.5-pro`
3. 在 `gemini_analyzer.py` 中加入自动重试逻辑（指数退避）

**Q：我的小说超过 5 万字，应该用哪种模式？**

超过 5 万字会自动切换 RAG 模式，无需手动设置。如果你的小说恰好在边界附近且希望强制使用某种模式，在请求中显式传入 `"use_rag": true` 或 `"use_rag": false` 即可。

**Q：RAG 模式比全文模式慢多少？**

RAG 模式的耗时约为 `全局分析（1次）+ 章节数 × 单次分析时间`，章节越多耗时越长。12章的小说大约需要 3–8 分钟。前端进度条会实时显示当前正在处理的章节（如"RAG: 章节分析 5/12 — 第五章"）。

**Q：输出的章节数量和原著不一致？**

全文模式下，AI 可能根据语义对章节进行合并或拆分以符合剧作结构。RAG 模式严格按照检测到的章节标记逐章处理，与原著章节一一对应。

**Q：人物名字出现错字或混淆？**

Prompt 中已要求"杜绝错字别字"，但长文本中仍可能出现。建议在 YAML 中用文本编辑器全局搜索替换后再使用。RAG 模式中，通过 `/rag/references` 上传包含标准人名的角色表，可有效减少此问题。

**Q：如何在生产环境部署？**

- 将内存任务队列替换为 Redis + Celery
- 在 FastAPI 前加 Nginx 反向代理
- Streamlit 可通过 `streamlit run --server.address 0.0.0.0` 对外服务，或改用 React 前端调用 API
- RAG 的 `InMemoryVectorStore` 可替换为 Qdrant / Chroma 等持久化向量数据库

---

## 注意事项

- **全文模式**建议单次输入不超过 **5 万字**；超过此长度应使用 RAG 模式
- **RAG 模式**理论上无字数上限，但章节越多 API 调用次数越多，请注意 Gemini 的速率限制（RPM）
- 任务结果仅保存在**内存**中，服务重启后丢失；生产环境建议持久化至数据库
- 默认模型为 `gemini-2.5-flash`（速度优先）；追求更高质量可改用 `gemini-2.5-pro`
- 国内网络环境下，`Main.py` 的 `lifespan` 函数中已配置本地代理（默认 `127.0.0.1:7890`），如使用其他端口请修改对应配置
- 生成结果为剧本**初稿**，AI 对人物动机和场景细节的判断仍需人工审校
