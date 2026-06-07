# 小说剧本转换器 · Novel → Script

> 将包含 3 个或以上章节的中文（或英文）小说文本，通过 Google Gemini 进行深度语义分析，自动重构为结构化剧本大纲，并以 YAML 格式输出，供作者直接编辑打磨。

---

## 目录

- [项目结构](#项目结构)
- [快速开始](#快速开始)
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
│   ├── main.py             # FastAPI 服务入口，路由 + 异步任务队列
│   ├── gemini_analyzer.py  # Gemini API 调用与结构化输出解析
│   ├── models.py           # Pydantic Schema 定义（核心数据结构）
│   ├── yaml_utils.py       # 结果后处理 + 自定义 YAML 序列化
│   ├── config.py           # 环境变量加载
│   ├── cli.py              # 命令行入口（原始脚本，保留备用）
│   └── requirements.txt
├── frontend/
│   ├── app.py              # Streamlit 前端
│   └── requirements.txt
├── .env.example
└── README.md
```

---

## 快速开始

### 1. 配置 API 密钥

复制示例文件并填写密钥：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
GEMINI_API_KEY=your_google_gemini_api_key
GEMINI_MODEL_NAME=gemini-2.5-flash   # 可选，默认值
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
uvicorn main:app --reload --port 8000
```

交互式 API 文档：http://localhost:8000/docs

**终端 2 — 前端（Streamlit）**

```bash
cd frontend
streamlit run app.py --server.port 8501
```

浏览器访问：http://localhost:8501

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

### 异步任务流程

由于 Gemini 分析长篇小说通常耗时 30–120 秒，接口采用异步设计：

```
POST /analyze  →  立即返回 job_id
     ↓
轮询 GET /jobs/{job_id}
     ↓  status: pending → running → done
GET /jobs/{job_id}/yaml  →  下载结果
```

### POST /analyze 请求示例

```json
{
  "text": "第一章 ...\n第二章 ...\n第三章 ...",
  "source_name": "我的小说"
}
```

返回（立即）：

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "progress": "已加入队列",
  "created_at": 1700000000.0
}
```

完成后轮询结果：

```json
{
  "job_id": "550e8400-...",
  "status": "done",
  "progress": "完成",
  "result": { ... },
  "yaml_output": "schema_version: ...",
  "finished_at": 1700000087.3
}
```

---

## Schema 设计说明

Schema 定义在 `backend/models.py`，是本项目的核心。它不是简单的数据容器，而是一套将**文学叙事语言**映射为**剧作专业语言**的转译规范。以下说明每一层的设计意图。

---

### 顶层：`AIScriptDraft`

```python
class AIScriptDraft(BaseModel):
    logline:    str
    theme:      str
    setting:    str
    tone:       str
    characters: List[AICharacter]
    acts:       List[AIAct]
```

**设计原因**

小说和剧本在叙事层面存在根本性差异：小说可以大段内心独白、散漫叙事；剧本必须在开机前让导演、演员、制片人在几分钟内对故事达成共识。顶层的四个字段（`logline` / `theme` / `setting` / `tone`）正是好莱坞开发流程中"一页纸提案"的标准要素，强制 AI 在展开结构之前先完成整体定性，避免后续场景分析缺乏统一方向。`characters` 置于顶层而非各章之内，是因为剧本人物的性格弧线贯穿全局，不应被切分进章节局部视角中。

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

`role` 使用受控词汇（protagonist / antagonist / supporting）而非自由文本，是为了让下游工具（前端渲染、导出脚本）能够直接做条件判断，无需再做自然语言解析。`traits` 设计为列表而非长文本，便于后续打标签、检索，也能防止 AI 输出冗长的散文式描述。上限 12 人的约束写在 prompt 中，源自剧本写作的实践经验——超过 12 个核心人物会导致观众难以追踪人物关系。

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

`summary` 和 `purpose` 看似重复，实则区分了两个维度：`summary` 回答"发生了什么"（情节层），`purpose` 回答"为什么需要这一幕"（结构层）。这一区分来自编剧理论中"故事事件"与"叙事功能"的分离——例如"主角被陷害入狱"是情节，而"通过最低点考验主角意志"才是其在三幕剧结构中的功能。两者并存，能帮助改编者在调整章节顺序时快速判断是否影响整体结构。

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

- **`location` + `time`**：剧本场头（Scene Heading）的直接来源，如 `INT. 陈旧的客厅 - 深夜`，要求 AI 从小说描写中提炼具体地点而非笼统概念（"某处"之类无效）。
- **`goal` + `conflict`**：来自编剧理论中"每场戏必须有人物目标和阻碍"的铁律。这两个字段强制 AI 识别每场戏的戏剧引擎，过滤掉小说中大量无戏剧功能的过渡性叙述段落。
- **`beats`**：情节节拍是小说与剧本转换中损耗最大的信息。小说用铺垫、回忆、内心描写构建张力，剧本只有可拍摄的动作。`beats` 字段要求 AI 将叙事流拆解为离散的可视化动作单元，每个节拍对应一次摄影机需要捕捉的"变化"。
- **`dialogue_candidates`**：不要求提取全部对话（那会导致输出过长且噪声极大），只筛选最多 3 条"最具戏剧张力或关键推动作用"的台词，配合 `intent`（潜台词）字段，帮助编剧快速找到值得保留的原著对白。

---

### 节拍层：`AISceneBeat`

```python
class AISceneBeat(BaseModel):
    order:          int
    action:         str
    emotional_shift: str
```

**设计原因**

`action` 要求用"镜头感"的语言描写动作，而非文学性的内心叙述。`emotional_shift` 记录每个节拍带来的情感或力量对比变化（如"主角从主动转为被动"），这是好莱坞节拍表（Beat Sheet）方法论的直接体现——一个没有情感转变的节拍在剧本中是无效的，应当删除或合并。两个字段的分离，让改编者能独立评估"动作够不够有力"和"情感节奏是否合理"。

---

### 台词层：`AISpeakerLine`

```python
class AISpeakerLine(BaseModel):
    speaker: str
    line:    str
    intent:  str
```

**设计原因**

`intent`（潜台词）是这个三元组中最关键的字段。优秀剧本台词的特征是"说的是一件事，意思是另一件事"。要求 AI 为每条筛选出的台词标注潜台词，一方面能验证 AI 是否真正理解了对话的戏剧功能，另一方面也为改编者提供了改写方向——当原著台词过于直白时，`intent` 告诉编剧这句话真正需要表达什么。

---

### Schema 整体层级关系

```
AIScriptDraft
├── logline / theme / setting / tone   ← 全局定性
├── characters: List[AICharacter]      ← 全局人物
│   └── name / role / description / traits
└── acts: List[AIAct]                  ← 按章节划分
    ├── title / summary / purpose
    └── scenes: List[AIScene]          ← 可拍摄的最小单元
        ├── location / time            → 场头（Scene Heading）
        ├── goal / conflict            → 戏剧引擎
        ├── characters                 → 出场人物
        ├── beats: List[AISceneBeat]   → 动作序列
        │   └── order / action / emotional_shift
        └── dialogue_candidates        → 精选台词
            └── speaker / line / intent
```

---

## YAML 输出示例

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
  mode: "gemini_semantic_draft"
```

---

## 章节识别规则

提交的小说必须包含**至少 3 个**可识别的章节标记，否则接口返回 422 错误。

支持的格式：

| 格式 | 示例 |
|------|------|
| 中文章节 | `第一章`、`第2章`、`第三节`、`第一幕` |
| 英文章节 | `Chapter 1`、`Chapter One`、`Act I`、`Act 2` |
| Markdown 标题 | `## 第一章`、`# 序章` |

---

## 常见问题

**Q：提示 503 UNAVAILABLE，分析失败？**

这是 Gemini 服务端临时过载，与代码无关。建议：
1. 稍等几分钟后点击「重新分析」重试
2. 在 `.env` 中改用 `GEMINI_MODEL_NAME=gemini-2.5-pro`
3. 在 `gemini_analyzer.py` 中加入自动重试逻辑（指数退避）

**Q：输出的章节数量和原著不一致？**

AI 会根据语义对章节进行合并或拆分，以符合剧作幕次结构（通常为三幕或五幕），而非严格对应小说章节编号。这是有意为之的改编行为。

**Q：人物名字出现错字或混淆？**

Prompt 中已要求 AI "杜绝错字别字"，但长文本中仍可能出现。建议在 YAML 中使用文本编辑器全局搜索替换后再使用。

**Q：如何在生产环境部署？**

- 将内存任务队列替换为 Redis + Celery
- 在 FastAPI 前加 Nginx 反向代理
- Streamlit 可通过 `streamlit run --server.address 0.0.0.0` 对外服务，或改用 React 前端调用 API

---

## 注意事项

- 单次建议输入不超过 **15 万字**，过长文本可能导致 Gemini API 超时
- 任务结果仅保存在**内存**中，服务重启后丢失；生产环境建议持久化至数据库
- 默认模型为 `gemini-2.5-flash`（速度优先）；追求更高质量可改用 `gemini-2.5-pro`
- 生成结果为剧本**初稿**，AI 对人物动机和场景细节的判断仍需人工审校

