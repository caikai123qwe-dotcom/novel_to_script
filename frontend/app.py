from __future__ import annotations

import io
import os
import time
import requests
import streamlit as st

# ── Session State 初始化（必须放在最顶部，防止变量丢失） ─────────────────────────
if "api_base" not in st.session_state:
    st.session_state.api_base = "http://127.0.0.1:8000"
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "job_result" not in st.session_state:
    st.session_state.job_result = None

POLL_INTERVAL = 2  # 轮询间隔 (秒)

st.set_page_config(
    page_title="小说剧本转换器",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 样式 ──────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=JetBrains+Mono:wght@400;500&family=Playfair+Display:ital,wght@0,700;1,400&display=swap');

:root {
  --ink:         #1a1108;
  --parchment:   #f5f0e8;
  --gold:        #c8960c;
  --gold-light:  #e8c84a;
  --red-seal:    #a83225;
  --fade:        #7a6e5f;
  --card-bg:     #fdfaf4;
  --border:      #d4c9a8;
  --success:     #2d6a2d;
}

html, body, [class*="css"] {
  font-family: 'Noto Serif SC', serif;
  background-color: var(--parchment);
  color: var(--ink);
}

/* ── 大标题 ── */
.hero-title {
  font-family: 'Playfair Display', 'Noto Serif SC', serif;
  font-size: 3rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  background: linear-gradient(135deg, var(--ink) 40%, var(--gold) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 0;
  line-height: 1.15;
}
.hero-sub {
  color: var(--fade);
  font-size: 1rem;
  letter-spacing: 0.08em;
  margin-top: 0.25rem;
  font-style: italic;
}
.divider-gold {
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--gold), transparent);
  margin: 1.5rem 0;
  border: none;
}

/* ── 卡片 ── */
.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.card-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--gold);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  margin-bottom: 0.6rem;
}

/* ── 章节 badge ── */
.act-badge {
  display: inline-block;
  background: var(--ink);
  color: var(--gold-light);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 2px 10px;
  border-radius: 2px;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
}

/* ── 角色标签 ── */
.char-tag {
  display: inline-block;
  background: #f0ead8;
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 2px 8px;
  margin: 2px 4px 2px 0;
  font-size: 0.82rem;
  color: var(--ink);
}
.role-protagonist { border-left: 3px solid var(--gold); }
.role-antagonist  { border-left: 3px solid var(--red-seal); }
.role-supporting  { border-left: 3px solid var(--fade); }

/* ── 台词 ── */
.dialogue-block {
  border-left: 3px solid var(--gold);
  padding: 0.4rem 0.8rem;
  margin: 0.5rem 0;
  background: #faf6ec;
  border-radius: 0 4px 4px 0;
  font-size: 0.92rem;
}
.dialogue-speaker {
  font-weight: 700;
  color: var(--red-seal);
  margin-right: 0.4em;
}
.dialogue-intent {
  font-size: 0.78rem;
  color: var(--fade);
  font-style: italic;
  margin-top: 0.2rem;
}

/* ── 节拍 ── */
.beat-row {
  display: flex;
  gap: 0.8rem;
  align-items: flex-start;
  margin: 0.4rem 0;
  font-size: 0.9rem;
}
.beat-num {
  min-width: 22px;
  height: 22px;
  background: var(--gold);
  color: var(--ink);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 700;
  flex-shrink: 0;
}

/* ── 状态指示器 ── */
.status-running {
  display: inline-block;
  color: var(--gold);
  font-size: 0.9rem;
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.35} }

/* ── 按钮覆盖 ── */
div.stButton > button {
  background: var(--ink) !important;
  color: var(--gold-light) !important;
  border: 1px solid var(--gold) !important;
  border-radius: 3px !important;
  font-family: 'Noto Serif SC', serif !important;
  letter-spacing: 0.06em;
  padding: 0.5rem 1.6rem !important;
  font-weight: 600 !important;
}
div.stButton > button:hover {
  background: var(--gold) !important;
  color: var(--ink) !important;
}

/* ── YAML 代码块 ── */
.yaml-wrap pre {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.8rem !important;
  background: #1a1108 !important;
  color: #e8c84a !important;
  border-radius: 4px;
  padding: 1rem !important;
}

/* ── 侧边栏 ── */
section[data-testid="stSidebar"] {
  background: #1a1108 !important;
}
section[data-testid="stSidebar"] * {
  color: #d4c9a8 !important;
}
section[data-testid="stSidebar"] .stMarkdown h3 {
  color: var(--gold-light) !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def api_url(path: str) -> str:
    # 使用托管在 session_state 里的地址，防止刷新被重置
    return f"{st.session_state.api_base}{path}"


def poll_job(job_id: str) -> dict:
    # 轮询获取状态也强制绕过本地代理，防止抓瞎
    r = requests.get(api_url(f"/jobs/{job_id}"), timeout=15, proxies={"http": None, "https": None})
    r.raise_for_status()
    return r.json()


def submit_text(text: str, name: str, use_rag: bool | None = None) -> str:
    # 💡 核心修复：锁定 proxies 彻底禁止流量走本地 7890 翻墙代理，放宽 timeout
    r = requests.post(
        api_url("/analyze"), 
        json={"text": text, "source_name": name, "use_rag": use_rag}, 
        timeout=30,
        proxies={"http": None, "https": None}
    )
    if r.status_code == 422:
        raise ValueError(r.json().get("detail", "验证失败"))
    r.raise_for_status()
    return r.json()["job_id"]


def submit_file(file_bytes: bytes, filename: str, use_rag: bool | None = None) -> str:
    files = {"file": (filename, io.BytesIO(file_bytes), "text/plain")}
    # 💡 核心修复：上传文件同理禁止走本地翻墙代理
    r = requests.post(
        api_url("/analyze/upload"), 
        files=files,
        data={"use_rag": str(use_rag).lower()} if use_rag is not None else None,
        timeout=30,
        proxies={"http": None, "https": None}
    )
    if r.status_code == 422:
        raise ValueError(r.json().get("detail", "验证失败"))
    r.raise_for_status()
    return r.json()["job_id"]


def render_characters(chars: list):
    for ch in chars:
        role_class = f"role-{ch.get('role','supporting')}"
        st.markdown(
            f"""
<div class="card">
  <div class="char-tag {role_class}">
    <strong>{ch['name']}</strong>
    &nbsp;·&nbsp;<span style="color:var(--fade);font-size:0.8rem">{ch.get('role','')}</span>
  </div>
  <div style="font-size:0.9rem;margin:0.4rem 0">{ch.get('description','')}</div>
  <div style="margin-top:0.4rem">{''.join(f'<span class="char-tag">{t}</span>' for t in ch.get("traits",[]))}</div>
</div>""",
            unsafe_allow_html=True,
        )


def render_acts(acts: list):
    for i, act in enumerate(acts, 1):
        with st.expander(f"第 {i} 幕 · {act.get('title','')}", expanded=(i == 1)):
            st.markdown(
                f"""
<div class="act-badge">幕 {i}</div>
<div style="margin-bottom:0.6rem;font-size:0.95rem"><strong>梗概：</strong>{act.get('summary','')}</div>
<div style="color:var(--fade);font-size:0.85rem;margin-bottom:1rem"><strong>剧作功能：</strong>{act.get('purpose','')}</div>
""",
                unsafe_allow_html=True,
            )
            for j, scene in enumerate(act.get("scenes", []), 1):
                st.markdown(
                    f"""
<div class="card">
  <div class="card-title">场景 {j} · {scene.get('location','')} · {scene.get('time','')}</div>
  <div style="font-size:0.88rem;margin-bottom:0.5rem">
    🎯 <strong>目标</strong>：{scene.get('goal','')}
  </div>
  <div style="font-size:0.88rem;margin-bottom:0.8rem">
    ⚡ <strong>冲突</strong>：{scene.get('conflict','')}
  </div>
  <div style="font-size:0.85rem;color:var(--fade);margin-bottom:0.3rem">出场人物：
    {''.join(f'<span class="char-tag">{c}</span>' for c in scene.get('characters',[]))}
  </div>
""",
                    unsafe_allow_html=True,
                )
                # Beats
                st.markdown("**情节节拍**")
                for beat in scene.get("beats", []):
                    st.markdown(
                        f"""<div class="beat-row">
  <div class="beat-num">{beat['order']}</div>
  <div>
    <div>{beat.get('action','')}</div>
    <div style="font-size:0.78rem;color:var(--fade);font-style:italic">{beat.get('emotional_shift','')}</div>
  </div>
</div>""",
                        unsafe_allow_html=True,
                    )
                # Dialogue
                if scene.get("dialogue_candidates"):
                    st.markdown("**灵魂对白**")
                    for dl in scene["dialogue_candidates"]:
                        st.markdown(
                            f"""<div class="dialogue-block">
  <span class="dialogue-speaker">{dl.get('speaker','')}</span>{dl.get('line','')}
  <div class="dialogue-intent">潜台词：{dl.get('intent','')}</div>
</div>""",
                            unsafe_allow_html=True,
                        )
                st.markdown("</div>", unsafe_allow_html=True)


# ── 侧边栏 ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎬 Novel → Script")
    st.markdown("---")
    st.markdown(
        """
**使用说明**

1. 粘贴小说文本或上传 `.txt` 文件
2. 小说须包含 **3 个或以上章节**
3. 点击「开始转换」，等待 AI 分析
4. 在结果页查看剧本结构并下载 YAML

---
**支持的章节标记**

- `第一章 / 第1章`
- `Chapter 1 / Act I`
- `## 标题`（Markdown）

---
**注意事项**

- 建议单次输入不超过 **15 万字**
- 结果基于 Gemini 2.5 Flash 生成
- YAML 文件可直接作为剧本初稿
"""
    )

    st.markdown("---")
    st.markdown("### ⚙️ 设置")
    
    # 💡 核心修复：把变量持久化绑定到 session_state.api_base
    api_base_input = st.text_input("API 地址", value=st.session_state.api_base)
    if api_base_input != st.session_state.api_base:
        st.session_state.api_base = api_base_input


# ── 主界面 ────────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">小说剧本转换器</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Novel → Structured Screenplay · Powered by Gemini</div>',
    unsafe_allow_html=True,
)
st.markdown('<hr class="divider-gold">', unsafe_allow_html=True)


# ── 输入区 ────────────────────────────────────────────────────────────────────
use_rag_mode = st.checkbox(
    "启用 RAG 模式（长文本分块检索分析，建议超过 5 万字或章节很多时开启）",
    value=False,
    key="use_rag_mode",
)

tab_text, tab_file = st.tabs(["📝 粘贴文本", "📂 上传文件"])

with tab_text:
    novel_name = st.text_input("作品名称", placeholder="例：三体（用于输出文件命名）", value="")
    novel_text = st.text_area(
        "在此粘贴小说文本",
        height=300,
        placeholder='请确保文本中包含章节标题，如"第一章 ..."、"Chapter 1" 等……',
    )
    col1, col2 = st.columns([1, 4])
    with col1:
        submit_text_btn = st.button("🚀 开始转换", key="btn_text")
    if submit_text_btn:
        if not novel_text.strip():
            st.error("请先输入小说文本。")
        else:
            with st.spinner("提交中…"):
                try:
                    jid = submit_text(novel_text, novel_name or "novel", use_rag=use_rag_mode or None)
                    st.session_state.job_id = jid
                    st.session_state.job_result = None
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"提交失败：{e}")

with tab_file:
    uploaded = st.file_uploader("上传 .txt 小说文件", type=["txt"])
    file_name_input = st.text_input("作品名称（可选）", key="file_name")
    col_f1, _ = st.columns([1, 4])
    with col_f1:
        submit_file_btn = st.button("🚀 开始转换", key="btn_file")
    if submit_file_btn:
        if uploaded is None:
            st.error("请先上传文件。")
        else:
            with st.spinner("上传并提交中…"):
                try:
                    jid = submit_file(
                        uploaded.getvalue(),
                        uploaded.name,
                        use_rag=use_rag_mode or None,
                    )
                    st.session_state.job_id = jid
                    st.session_state.job_result = None
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"提交失败：{e}")

# ── 状态轮询与结果展示 ────────────────────────────────────────────────────────
if st.session_state.job_id:
    st.markdown('<hr class="divider-gold">', unsafe_allow_html=True)

    job_id = st.session_state.job_id

    # 💡 核心修复：彻底消灭 while True 死循环！改用“查一次，等两秒，主动重刷页面”的非阻塞单轮设计
    if st.session_state.job_result is None:
        try:
            job = poll_job(job_id)
            progress_msg = job.get("progress") or job.get("status")
            
            st.markdown(
                f'<div class="status-running">⏳ {progress_msg}</div>',
                unsafe_allow_html=True,
            )

            if job["status"] == "done":
                st.session_state.job_result = job
                st.rerun()
            elif job["status"] == "error":
                st.error(f"❌ 分析失败：{job.get('error','未知错误')}")
            else:
                # 任务还在运行中：休眠 2 秒后，主动要求 Streamlit 从头重新渲染本页，释放主线程
                time.sleep(POLL_INTERVAL)
                st.rerun()

        except Exception as e:
            st.error(f"轮询失败：{e}")

    # 展示已完成结果
    if st.session_state.job_result:
        job = st.session_state.job_result
        result = job.get("result", {})
        story = result.get("story", {})
        meta = result.get("meta", {})

        st.success("✅ 剧本大纲生成完毕！")

        # ── 基本信息 ──────────────────────────────────────────────────────────
        st.markdown("## 📖 故事概要")
        info_cols = st.columns(3)
        with info_cols[0]:
            st.markdown(
                f'<div class="card"><div class="card-title">Logline</div>{story.get("logline","")}</div>',
                unsafe_allow_html=True,
            )
        with info_cols[1]:
            st.markdown(
                f'<div class="card"><div class="card-title">核心主题</div>{story.get("theme","")}</div>',
                unsafe_allow_html=True,
            )
        with info_cols[2]:
            st.markdown(
                f'<div class="card"><div class="card-title">基调 · 世界观</div>'
                f'{story.get("tone","")} · {story.get("setting","")}</div>',
                unsafe_allow_html=True,
            )

        # ── 人物 ──────────────────────────────────────────────────────────────
        st.markdown("## 🎭 核心人物")
        chars = story.get("characters") or []
        if chars:
            n_cols = min(3, len(chars))
            char_cols = st.columns(n_cols)
            for idx, ch in enumerate(chars):
                with char_cols[idx % n_cols]:
                    role_class = f"role-{ch.get('role','supporting')}"
                    st.markdown(
                        f"""<div class="card">
<div class="char-tag {role_class}">
  <strong>{ch['name']}</strong>&nbsp;·&nbsp;<span style="color:var(--fade);font-size:0.8rem">{ch.get('role','')}</span>
</div>
<div style="font-size:0.88rem;margin:0.4rem 0">{ch.get('description','')}</div>
<div>{''.join(f'<span class="char-tag">{t}</span>' for t in ch.get("traits",[]))}</div>
</div>""",
                        unsafe_allow_html=True,
                    )

        # ── 剧本结构 ──────────────────────────────────────────────────────────
        st.markdown("## 🎬 剧本结构")
        acts = result.get("acts") or []
        render_acts(acts)

        # ── 下载区 ────────────────────────────────────────────────────────────
        st.markdown('<hr class="divider-gold">', unsafe_allow_html=True)
        st.markdown("## 💾 导出")
        yaml_text = job.get("yaml_output", "")
        dl_cols = st.columns([2, 3])
        with dl_cols[0]:
            title_stem = meta.get("title", "script")
            st.download_button(
                label="⬇️ 下载 YAML 剧本",
                data=yaml_text.encode("utf-8"),
                file_name=f"{title_stem}_script.yaml",
                mime="text/yaml",
            )
        with dl_cols[1]:
            if st.checkbox("预览 YAML 原始内容"):
                st.markdown('<div class="yaml-wrap">', unsafe_allow_html=True)
                st.code(yaml_text[:6000] + ("\n# ... (truncated)" if len(yaml_text) > 6000 else ""), language="yaml")
                st.markdown("</div>", unsafe_allow_html=True)

        # ── 重置 ──────────────────────────────────────────────────────────────
        st.markdown("")
        if st.button("🔄 重新分析另一部作品"):
            st.session_state.job_id = None
            st.session_state.job_result = None
            st.rerun()