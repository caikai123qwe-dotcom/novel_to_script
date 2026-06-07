import sys
import os
import uuid
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

# In-memory job store (use Redis in production)
jobs: Dict[str, Dict[str, Any]] = {}
reference_docs: Dict[str, str] = {}



@asynccontextmanager
async def lifespan(app: FastAPI):
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    os.environ.setdefault("GEMINI_MODEL_NAME", "gemini-2.5-flash")
    
    # 💡 核心修复：不要 pop 它们，而是直接给它们赋上你本地 Clash 的 7890 代理地址！
    # 这样无论是全文本模式，还是 RAG 的 Embedding 生成和 Pipeline 调用，都能统一顺利走代理翻墙。
    proxy_url = "http://127.0.0.1:7890"  # 如果你本地的代理是其他端口，请修改这里
    
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url
    os.environ["http_proxy"] = proxy_url
    os.environ["https_proxy"] = proxy_url
    
    # 注意：NO_PROXY 不能设为 "*"，否则等于把刚设的代理又给内网禁用了。
    # 我们应该让它只对本地环回不走代理，从而确保前端和 FastAPI 互相通信不卡顿。
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    
    yield


app = FastAPI(
    title="Novel to Script API",
    description="将小说文本转换为结构化剧本的 API 服务",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str
    source_name: Optional[str] = "novel"
    use_rag: Optional[bool] = None
    reference_ids: Optional[List[str]] = None


class ReferenceDocRequest(BaseModel):
    ref_id: str
    text: str


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending | running | done | error
    progress: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    yaml_output: Optional[str] = None
    error: Optional[str] = None
    created_at: float
    finished_at: Optional[float] = None


def validate_novel(text: str) -> None:
    """Ensure text has at least 3 detectable chapters."""
    import re
    # common chapter markers: 第X章, Chapter N, 第X节, 幕, Act
    patterns = [
        r"第[零一二三四五六七八九十百千\d]+[章节幕]",
        r"Chapter\s+\d+",
        r"Act\s+[IVX\d]+",
        r"\n#{1,3}\s+.{2,}",  # markdown headings
    ]
    combined = "|".join(patterns)
    matches = re.findall(combined, text, re.IGNORECASE)
    if len(matches) < 3:
        raise ValueError(
            f"检测到的章节数不足（仅找到 {len(matches)} 个章节标记）。"
            "本工具要求小说至少包含 3 个明确的章节。"
        )


def run_analysis(job_id: str, text: str, source_name: str, use_rag: Optional[bool] = None, reference_ids: Optional[List[str]] = None) -> None:
    """Blocking analysis — run in thread pool via BackgroundTasks."""
    from gemini_analyzer import analyze_novel
    from yaml_utils import build_final_output, to_yaml

    jobs[job_id]["status"] = "running"
    jobs[job_id]["progress"] = "正在连接 Gemini 进行深度语义分析..."

    def on_progress(msg: str) -> None:
        jobs[job_id]["progress"] = msg

    ref_texts = None
    if reference_ids:
        ref_texts = [reference_docs[r] for r in reference_ids if r in reference_docs]

    try:
        ai_raw = analyze_novel(text, use_rag=use_rag, progress_callback=on_progress, reference_texts=ref_texts)
        jobs[job_id]["progress"] = "AI 分析完成，正在构建剧本结构..."
        rag_mode = use_rag if use_rag is not None else len(text) > 50000
        script_data = build_final_output(ai_raw, text, source_name, mode="rag" if rag_mode else None)
        yaml_text = to_yaml(script_data) + "\n"

        jobs[job_id].update(
            {
                "status": "done",
                "progress": "完成",
                "result": script_data,
                "yaml_output": yaml_text,
                "finished_at": time.time(),
            }
        )
    except Exception as exc:
        jobs[job_id].update(
            {
                "status": "error",
                "error": str(exc),
                "finished_at": time.time(),
            }
        )


# ── Routes ────────────────────────────────────────────────────────────────────



@app.post("/rag/references")
def upload_reference(doc: ReferenceDocRequest):
    reference_docs[doc.ref_id] = doc.text
    return {"ref_id": doc.ref_id, "chars": len(doc.text)}


@app.get("/rag/references")
def list_references():
    return [{"ref_id": k, "chars": len(v)} for k, v in reference_docs.items()]

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=JobStatus)
async def analyze(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """Submit a novel text for asynchronous analysis."""
    try:
        validate_novel(request.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": "已加入队列",
        "result": None,
        "yaml_output": None,
        "error": None,
        "created_at": time.time(),
        "finished_at": None,
    }
    background_tasks.add_task(run_analysis, job_id, request.text, request.source_name, request.use_rag, request.reference_ids)
    return JobStatus(**jobs[job_id])


@app.post("/analyze/upload", response_model=JobStatus)
async def analyze_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_name: Optional[str] = Form(None),
    use_rag: Optional[bool] = Form(None),
):
    """Upload a .txt file for analysis."""
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="仅支持 .txt 文件")

    raw = await file.read()
    text = raw.decode("utf-8", errors="replace")
    name = source_name or Path(file.filename).stem

    try:
        validate_novel(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": "已加入队列",
        "result": None,
        "yaml_output": None,
        "error": None,
        "created_at": time.time(),
        "finished_at": None,
    }
    background_tasks.add_task(run_analysis, job_id, text, name, use_rag, None)
    return JobStatus(**jobs[job_id])


@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**jobs[job_id])


@app.get("/jobs/{job_id}/yaml", response_class=PlainTextResponse)
def get_yaml(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail=f"Job 状态为 {job['status']}，尚未完成")
    return PlainTextResponse(content=job["yaml_output"], media_type="text/plain; charset=utf-8")


@app.get("/jobs")
def list_jobs():
    return [
        {"job_id": j["job_id"], "status": j["status"], "created_at": j["created_at"]}
        for j in jobs.values()
    ]