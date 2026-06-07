import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List

def build_final_output(ai_result: Dict[str, Any], text: str, source_name: str, mode: str | None = None) -> Dict[str, Any]:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return {
        "schema_version": "2.0_gemini",
        "meta": {
            "title": Path(source_name).stem,
            "source_type": "novel",
            "source_chapter_count": len(ai_result.get("acts", [])),
            "language": "zh",
            "input_digest": digest,
        },
        "story": {
            "logline": ai_result.get("logline"),
            "theme": ai_result.get("theme"),
            "setting": ai_result.get("setting"),
            "tone": ai_result.get("tone"),
            "premise": "Google Gemini 模型根据全文深度语义理解生成的结构化剧本骨架。",
            "characters": ai_result.get("characters"),
        },
        "acts": ai_result.get("acts"),
        "generation": {
            "tool": "novel_to_script_gemini",
            "mode": ("gemini_rag_chapter" if mode == "rag" else "gemini_semantic_draft"),
            "notes": (
                [
                    "本结果由 Gemini RAG 分章检索分析生成。",
                    "长文本通过向量检索选取相关片段后逐章生成。",
                    "场景与对白为 AI 草案，需人工润色。",
                ]
                if mode == "rag"
                else [
                    "当前版本基于 Google Gemini 结构化输出技术生成。",
                    "角色动机、场景潜台词及节拍由 AI 提炼，可直接作为高质量改编参考。",
                ]
            ),
        },
    }

def yaml_escape(value: str) -> str:
    if value == "":
        return '""'
    if re.fullmatch(r"[A-Za-z0-9_./:-]+", value):
        return value
    if "\n" in value:
        lines = value.splitlines()
        return "|\n" + "\n".join(f"  {line}" for line in lines)
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'

def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return yaml_escape(str(value))

def to_yaml(data: Any, indent: int = 0) -> str:
    spaces = "  " * indent
    if isinstance(data, dict):
        if not data:
            return f"{spaces}{{}}"
        lines = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                if not value:
                    empty_repr = "{}" if isinstance(value, dict) else "[]"
                    lines.append(f"{spaces}{key}: {empty_repr}")
                    continue
                lines.append(f"{spaces}{key}:")
                lines.append(to_yaml(value, indent + 1))
            else:
                lines.append(f"{spaces}{key}: {yaml_scalar(value)}")
        return "\n".join(lines)
    if isinstance(data, list):
        if not data:
            return f"{spaces}[]"
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                # 确保列表中的对象或列表正确缩进
                lines.append(f"{spaces}-")
                lines.append(to_yaml(item, indent + 1))
            else:
                lines.append(f"{spaces}- {yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{spaces}{yaml_scalar(data)}"