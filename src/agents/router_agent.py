"""
RouterAgent

将用户输入topic标准化为内部topic id。
"""

import re
from typing import Dict, Any, Optional
from dataclasses import dataclass

from ..deepseek_client import get_deepseek_client, TaskComplexity
from ..loader import DataLoader
from ..physics.topic_mapping import (
    CN_TO_EN, infer_node_type, infer_domain, infer_domain_hint
)


@dataclass
class RouterOutput:
    normalized_topic: str
    domain: str
    node_type: str
    confidence: float
    original_input: str
    suggestions: Optional[list] = None


_VALID_DOMAINS = {"mechanics", "thermodynamics", "electromagnetism", "optics",
                  "modern_physics", "math_tools"}
_VALID_TYPES = {"concept", "quantity", "definition", "law", "equation", "model",
                "assumption", "math_tool", "application", "experiment", "warning", "intuition_card"}

_LLM_SYSTEM_PROMPT = """你是一个专业的物理知识图谱路由器，负责将用户输入的主题精确映射为系统内部ID。

你的核心能力：
1. 识别物理主题的类型（定律、方程、概念、物理量等）
2. 判断主题所属的物理学科域
3. 生成符合系统规范的标准化ID

主题类型识别规则：
- law: 物理定律（如牛顿定律、热力学定律）— 自然界的基本规律
- equation: 物理方程（如伯努利方程、薛定谔方程）— 描述物理量之间关系的数学表达式
- concept: 物理概念（如能量、动量）— 物理学中的基本概念
- quantity: 物理量（如速度、加速度）— 可测量的物理属性
- definition: 定义（如力的定义）— 对物理概念的精确定义
- assumption: 假设（如理想气体假设）— 推导中所需的前提条件
- math_tool: 数学工具（如微积分、矢量分析）— 物理推导中使用的数学方法
- model: 物理模型（如质点模型）— 对物理系统的简化描述
- application: 应用（如流体力学应用）— 物理规律的实际应用
- experiment: 实验（如双缝干涉实验）— 验证物理规律的实验

学科域分类：
- mechanics: 力学（运动学、动力学、流体力学）
- thermodynamics: 热力学（热力学定律、统计力学）
- electromagnetism: 电磁学（电场、磁场、电磁波）
- optics: 光学（几何光学、物理光学）
- modern_physics: 近代物理（相对论、量子力学）

ID生成规则：
- 格式: {类型前缀}.{英文简称}
- 类型前缀: law/equation/concept/quantity/assumption/math_tool/model/application/experiment
- 英文简称使用小写字母和下划线，如: newton_second, bernoulli, kinetic_energy

示例：
- "牛顿第二定律" → {"normalized_topic": "law.newton_second", "domain": "mechanics", "node_type": "law", "confidence": 0.95}
- "伯努利方程" → {"normalized_topic": "equation.bernoulli", "domain": "mechanics", "node_type": "equation", "confidence": 0.95}
- "动能" → {"normalized_topic": "quantity.kinetic_energy", "domain": "mechanics", "node_type": "quantity", "confidence": 0.9}
- "理想气体假设" → {"normalized_topic": "assumption.ideal_gas", "domain": "thermodynamics", "node_type": "assumption", "confidence": 0.9}

输出必须是严格的JSON格式：
{
  "normalized_topic": "标准主题ID",
  "domain": "学科域",
  "node_type": "节点类型",
  "confidence": 0.0到1.0的置信度,
  "explanation": "简要解释分类理由和ID选择依据"
}

如果主题模糊或跨领域，给出最合理的猜测并适当降低置信度。"""


class RouterAgent:

    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or DataLoader()
        self.client = get_deepseek_client()
        self._alias_to_id = None

    @property
    def alias_to_id(self) -> Dict[str, str]:
        if self._alias_to_id is None:
            self._alias_to_id = {}
            aliases = self.loader.load_aliases()
            for topic_id, alias_list in aliases.items():
                for alias in alias_list:
                    self._alias_to_id[alias.lower()] = topic_id
                self._alias_to_id[topic_id.lower()] = topic_id
        return self._alias_to_id

    def run(self, topic_text: str) -> RouterOutput:
        cn_match = self._try_cn_mapping(topic_text)
        if cn_match:
            return cn_match

        local_match = self._try_local_match(topic_text)
        if local_match and local_match.confidence >= 0.9:
            return local_match

        return self._call_llm_for_routing(topic_text)

    def _try_cn_mapping(self, topic_text: str) -> Optional[RouterOutput]:
        text = topic_text.strip()
        en_name = CN_TO_EN.get(text, "")
        if not en_name:
            for cn, en in CN_TO_EN.items():
                if cn in text or text in cn:
                    en_name = en
                    break
        if not en_name:
            return None

        node_type = infer_node_type(text)
        domain = infer_domain(text)
        return RouterOutput(
            normalized_topic=f"{node_type}.{en_name}",
            domain=domain,
            node_type=node_type,
            confidence=0.95,
            original_input=topic_text
        )

    def _try_local_match(self, topic_text: str) -> Optional[RouterOutput]:
        text_lower = topic_text.lower().strip()

        if text_lower in self.alias_to_id:
            topic_id = self.alias_to_id[text_lower]
            domain, node_type = self._parse_topic_id(topic_id)
            return RouterOutput(
                normalized_topic=topic_id, domain=domain, node_type=node_type,
                confidence=1.0, original_input=topic_text
            )

        suggestions = []
        for alias, topic_id in self.alias_to_id.items():
            if text_lower in alias or alias in text_lower:
                confidence = self._calculate_match_confidence(text_lower, alias)
                suggestions.append({'topic_id': topic_id, 'alias': alias, 'confidence': confidence})

        if suggestions:
            best = max(suggestions, key=lambda x: x['confidence'])
            domain, node_type = self._parse_topic_id(best['topic_id'])
            return RouterOutput(
                normalized_topic=best['topic_id'], domain=domain, node_type=node_type,
                confidence=best['confidence'], original_input=topic_text,
                suggestions=[s['topic_id'] for s in suggestions[:3]]
            )

        return None

    def _call_llm_for_routing(self, topic_text: str) -> RouterOutput:
        try:
            response = self.client.chat_json(
                messages=[
                    {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": f"将以下主题标准化：{topic_text}"}
                ],
                temperature=0.0,
                complexity=TaskComplexity.SIMPLE  # 路由是简单任务
            )

            normalized_topic = response.get("normalized_topic", "")
            domain = response.get("domain", "mechanics")
            node_type = response.get("node_type", "concept")
            confidence = max(0.0, min(1.0, float(response.get("confidence", 0.5))))

            if domain not in _VALID_DOMAINS:
                domain = "mechanics"
            if node_type not in _VALID_TYPES:
                node_type = "concept"

            if not re.match(r'^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$', normalized_topic):
                normalized_topic = self._fallback_topic_id(topic_text, node_type)

            return RouterOutput(
                normalized_topic=normalized_topic, domain=domain, node_type=node_type,
                confidence=confidence, original_input=topic_text
            )

        except Exception as e:
            print(f"[ERROR] RouterAgent LLM调用失败: {e}")
            return self._build_fallback_output(topic_text)

    @staticmethod
    def _fallback_topic_id(topic_text: str, node_type: str) -> str:
        en_name = re.sub(r'[^\x00-\x7F]+', '', topic_text.lower().replace(' ', '_')).strip('_')
        en_name = re.sub(r'[^a-z0-9_]', '', en_name).strip('_')
        if not en_name:
            en_name = "unknown_topic"
        return f"{node_type}.{en_name}"

    def _build_fallback_output(self, topic_text: str) -> RouterOutput:
        en_name = CN_TO_EN.get(topic_text, "")
        if not en_name:
            for cn, en in CN_TO_EN.items():
                if cn in topic_text or topic_text in cn:
                    en_name = en
                    break
        if not en_name:
            en_name = re.sub(r'[^\x00-\x7F]+', '', topic_text.lower().replace(' ', '_')).strip('_')
            en_name = re.sub(r'[^a-z0-9_]', '', en_name).strip('_')
            if not en_name:
                en_name = "unknown_topic"

        node_type = infer_node_type(topic_text)
        domain = infer_domain(topic_text)
        return RouterOutput(
            normalized_topic=f"{node_type}.{en_name}",
            domain=domain, node_type=node_type,
            confidence=0.3, original_input=topic_text
        )

    @staticmethod
    def _parse_topic_id(topic_id: str) -> tuple:
        parts = topic_id.split('.')
        node_type = parts[0] if len(parts) >= 2 else "concept"
        domain = infer_domain(topic_id)
        return domain, node_type

    @staticmethod
    def _calculate_match_confidence(input_text: str, alias: str) -> float:
        if input_text == alias:
            return 1.0
        if input_text in alias or alias in input_text:
            return 0.8
        return 0.5
