from __future__ import annotations
from typing import List
from pydantic import BaseModel, Field

class AISpeakerLine(BaseModel):
    speaker: str = Field(description="说话者的名字，如果是旁白则填'旁白'")
    line: str = Field(description="台词或旁白原文")
    intent: str = Field(description="这句话在剧作中的潜台词、动机或潜在线索")

class AISceneBeat(BaseModel):
    order: int = Field(description="情节节拍的序号，从1开始")
    action: str = Field(description="该节拍发生的核心动作或核心事件描写（从文学转为剧本视觉动作）")
    emotional_shift: str = Field(description="该节拍带来的情感转变或冲突推进方向")

class AIScene(BaseModel):
    location: str = Field(description="基于语义理解提炼出的具体场景地点，如'陈旧的客厅'、'深夜的无名荒山'")
    time: str = Field(description="场景发生的时间描述，如'深夜'、'正午'、'暴雨倾盆的午后'")
    goal: str = Field(description="本场戏核心人物的主要推进目标")
    conflict: str = Field(description="阻碍目标实现的外部或内部冲突是什么")
    beats: List[AISceneBeat] = Field(description="梳理出的核心剧情发展节拍列表（通常3-5个）")
    characters: List[str] = Field(description="本场戏中真正出场或被强烈提及的核心角色姓名列表")
    dialogue_candidates: List[AISpeakerLine] = Field(description="挑选出最具戏剧张力或关键推动作用的台词/对白，最多3条")

class AICharacter(BaseModel):
    name: str = Field(description="角色名字")
    role: str = Field(description="角色定位，如 'protagonist'(主角), 'antagonist'(反派), 'supporting'(配角)")
    description: str = Field(description="基于全剧语义理解总结的人物小传或身份说明")
    traits: List[str] = Field(description="性格特质、标签列表")

class AIAct(BaseModel):
    title: str = Field(description="章节标题")
    summary: str = Field(description="本章剧情语义梗概")
    purpose: str = Field(description="本章在整体剧作骨架中的核心功能与存在目的")
    scenes: List[AIScene] = Field(description="本章包含的场景列表")

class AIScriptDraft(BaseModel):
    logline: str = Field(description="一句话故事核心梗概（全面概括输入文本）")
    theme: str = Field(description="AI根据文本语义提炼出的底层核心主题（如：复仇、命运的无常、人性的救赎）")
    setting: str = Field(description="故事的整体背景世界观或舞台时空设定")
    tone: str = Field(description="故事的整体基调（如：悬疑冷峻、轻喜剧、宏大史诗）")
    characters: List[AICharacter] = Field(description="全文本提炼出的核心人物卡片（最多12人）")
    acts: List[AIAct] = Field(description="按章节切分后的剧作幕/场序列")