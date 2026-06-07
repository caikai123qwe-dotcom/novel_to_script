import os
import sys
from typing import Any, Dict
from google import genai
from google.genai import types
from models import AIScriptDraft

def analyze_novel_with_gemini(text: str) -> Dict[str, Any]:
    client = genai.Client()
    system_instruction = (
        "你是一个资深的电影编剧和戏剧结构专家。你的任务是阅读用户输入的小说文本，"
        "摒弃表面浮躁的字面匹配，通过深层语义理解，将其重构转化为一套结构化的剧本大纲草稿。\n"
        "你需要做的是：\n"
        "1. 自动识别章节并理清全文本的故事主线，提炼一句话梗概（Logline）、核心主题（Theme）、基调（Tone）。\n"
        "2. 提取文本中真正有剧作意义的核心人物，输出其人物小传、性格和角色定位（杜绝错字别字和无意义名词）。\n"
        "3. 将每个章节视作一个剧作单元（幕/场），深入挖掘其发生的时间、真实的戏剧地点（根据描写提炼）、人物的隐秘目标和冲突核心。\n"
        "4. 将散落的叙事转化为具有镜头感和戏剧张力的'情节节拍(Beats)'，并筛选出最具潜台词(Intent)的灵魂对白。\n"
        "请严格按照指定的 Schema 格式返回结果。"
    )
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.2,
        response_mime_type="application/json",
        response_schema=AIScriptDraft,
    )
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=f"以下是需要改编的小说文本，请立刻研判并重构为剧本大纲：\n\n{text}",
            config=config
        )
        clean_json_str = response.text
        parsed_obj = AIScriptDraft.model_validate_json(clean_json_str)
        return parsed_obj.model_dump()
    except Exception as e:
        print(f"Gemini AI 解析过程中发生错误: {e}", file=sys.stderr)
        raise