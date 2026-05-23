"""
DeepSeek API客户端

基于OpenAI兼容接口的DeepSeek API客户端实现。
支持基于任务复杂度的智能模型选择 (V4 Flash vs V4 Pro)。
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from openai import OpenAI


class TaskComplexity(str, Enum):
    """任务复杂度级别，用于模型选择"""
    TRIVIAL = "trivial"        # 极其简单：关键词匹配、格式转换等本地操作
    SIMPLE = "simple"          # 简单：主题分类、简短响应
    MODERATE = "moderate"      # 中等：子图组装、基本推导
    COMPLEX = "complex"        # 复杂：多阶段扩展、深度推导
    VERY_COMPLEX = "very_complex"  # 极复杂：高难度方程推导、大图扩展


@dataclass
class DeepSeekConfig:
    api_key: str
    base_url: str
    beta_base_url: str
    # V4 模型
    model_flash: str   # deepseek-v4-flash — 快速、便宜，用于简单任务
    model_pro: str     # deepseek-v4-pro — 强力推理，用于复杂任务
    timeout_seconds: int = 120
    max_retries: int = 3

    # 复杂度阈值：超过此节点数自动使用 Pro 模型
    complexity_threshold_nodes: int = 40
    # 复杂度阈值：超过此扩展阶段数自动使用 Pro 模型
    complexity_threshold_stages: int = 2


class DeepSeekClient:
    """DeepSeek API 客户端，带智能模型选择"""

    def __init__(self, cfg: DeepSeekConfig):
        self.cfg = cfg
        self.client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        self.beta_client = OpenAI(api_key=cfg.api_key, base_url=cfg.beta_base_url)

    @classmethod
    def from_env(cls) -> "DeepSeekClient":
        cfg = DeepSeekConfig(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            beta_base_url=os.getenv("DEEPSEEK_BETA_BASE_URL", "https://api.deepseek.com/beta"),
            model_flash=os.getenv("DEEPSEEK_MODEL_FLASH", "deepseek-chat"),
            model_pro=os.getenv("DEEPSEEK_MODEL_PRO", "deepseek-reasoner"),
            timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            complexity_threshold_nodes=int(os.getenv("COMPLEXITY_THRESHOLD_NODES", "40")),
            complexity_threshold_stages=int(os.getenv("COMPLEXITY_THRESHOLD_STAGES", "2")),
        )
        return cls(cfg)

    # ── 智能模型选择 ──

    @staticmethod
    def estimate_complexity(
        *,
        task_type: str = "general",
        max_nodes: int = 20,
        expansion_stage: int = 0,
        candidate_count: int = 0,
        requires_derivation: bool = False,
        is_fallback: bool = False,
    ) -> TaskComplexity:
        """
        基于任务参数估算复杂度，遵循性价比原则：
        - 简单处理 → Flash（快、便宜）
        - 复杂推导 → Pro（强推理、贵）
        - 避免性能溢出：绝不用 Pro 做 Flash 就能完成的事
        """
        score = 0

        # 任务类型因子
        task_scores = {
            "routing": 1,         # 主题标准化 — 简单
            "planning": 2,        # 规划 — 简单到中等
            "classification": 1,  # 分类
            "assembly": 4,        # 子图组装 — 中等
            "expansion": 5,       # 扩展 — 复杂
            "derivation": 6,      # 推导步骤生成 — 复杂
            "ranking": 3,         # 路径排名 — 中等
            "fallback": 1,        # 回退 — 简单
        }
        score += task_scores.get(task_type, 2)

        # 规模因子
        if max_nodes > 60:
            score += 4
        elif max_nodes > 40:
            score += 2
        elif max_nodes > 25:
            score += 1

        # 扩展阶段因子（后续阶段更需要精确性）
        if expansion_stage >= 3:
            score += 3
        elif expansion_stage >= 2:
            score += 1

        # 候选节点多 → 需要更好的筛选能力
        if candidate_count > 50:
            score += 2
        elif candidate_count > 30:
            score += 1

        # 需要完整推导步骤 → 需要更强推理
        if requires_derivation:
            score += 2

        # 回退模式 → 尽量节省成本
        if is_fallback:
            score = min(score, 2)

        # 映射到复杂度级别
        if score <= 2:
            return TaskComplexity.SIMPLE
        elif score <= 4:
            return TaskComplexity.MODERATE
        elif score <= 6:
            return TaskComplexity.COMPLEX
        else:
            return TaskComplexity.VERY_COMPLEX

    def select_model(self, complexity: TaskComplexity) -> str:
        """
        根据复杂度选择模型。
        当前统一使用 DeepSeek V4 Flash (deepseek-chat)。
        """
        return self.cfg.model_flash

    def _resolve_model(
        self,
        model: Optional[str] = None,
        use_reasoner: Optional[bool] = None,
        complexity: Optional[TaskComplexity] = None,
    ) -> str:
        """解析最终使用的模型名称。优先级：显式model > 复杂度评估。统一使用 V4 Flash。"""
        if model:
            return model
        if complexity is not None:
            return self.select_model(complexity)
        return self.cfg.model_flash

    # ── API 调用方法 ──

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        use_reasoner: Optional[bool] = None,
        use_beta: bool = False,
        complexity: Optional[TaskComplexity] = None,
    ) -> Dict[str, Any]:
        """
        调用 LLM 并返回 JSON 结果，支持智能模型选择。

        Args:
            messages: 消息列表
            model: 显式指定模型（优先级最高）
            temperature: 温度参数
            max_tokens: 最大 tokens
            use_reasoner: 是否使用推理模型（已废弃，建议用 complexity）
            use_beta: 是否使用 beta 端点
            complexity: 任务复杂度（用于自动模型选择）
        """
        chosen_model = self._resolve_model(model, use_reasoner, complexity)
        client = self.beta_client if use_beta else self.client

        last_error = None
        for attempt in range(1, self.cfg.max_retries + 1):
            try:
                resp = client.chat.completions.create(
                    model=chosen_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                text = resp.choices[0].message.content
                return self._parse_json_response(text)
            except Exception as exc:
                last_error = exc
                if attempt == self.cfg.max_retries:
                    raise
                time.sleep(min(2 ** attempt, 8))
        raise RuntimeError(f"DeepSeek call failed: {last_error}")

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        fixed = self._fix_latex_escapes(text)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        for variant in [text, fixed]:
            repaired = self._try_repair_json(variant)
            if repaired is not None:
                return repaired

        raise json.JSONDecodeError("无法解析JSON响应", text, 0)

    def _try_repair_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text or not text.strip():
            return None

        text = self._fix_latex_escapes(text.strip())

        repair_points = []
        last_brace = text.rfind('}')
        if last_brace > 0:
            repair_points.append(last_brace + 1)
        last_bracket = text.rfind(']')
        if last_bracket > 0:
            repair_points.append(last_bracket + 1)
        repair_points.append(len(text))

        for cut_point in repair_points:
            truncated = text[:cut_point]
            open_braces = truncated.count('{') - truncated.count('}')
            open_brackets = truncated.count('[') - truncated.count(']')
            if open_braces >= 0 and open_brackets >= 0:
                candidate = truncated + ']' * open_brackets + '}' * open_braces
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict):
                        return result
                except (json.JSONDecodeError, ValueError):
                    continue

        return None

    def _fix_latex_escapes(self, text: str) -> str:
        result = []
        i = 0
        while i < len(text):
            if text[i] == '"':
                end = i + 1
                while end < len(text):
                    if text[end] == '\\':
                        end += 2
                    elif text[end] == '"':
                        break
                    else:
                        end += 1
                if end < len(text):
                    string_content = text[i:end + 1]
                    try:
                        json.loads(string_content)
                        result.append(string_content)
                    except json.JSONDecodeError:
                        fixed = self._fix_single_string(string_content)
                        result.append(fixed)
                    i = end + 1
                else:
                    result.append(text[i:])
                    break
            else:
                result.append(text[i])
                i += 1
        return ''.join(result)

    @staticmethod
    def _fix_single_string(s: str) -> str:
        inner = s[1:-1]
        inner = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', inner)
        fixed = '"' + inner + '"'
        try:
            json.loads(fixed)
            return fixed
        except json.JSONDecodeError:
            pass

        inner2 = s[1:-1]
        inner2 = inner2.replace('\\', '\\\\')
        inner2 = re.sub(r'\\\\{2,}', r'\\\\', inner2)
        safed = '"' + inner2 + '"'
        try:
            json.loads(safed)
            return safed
        except json.JSONDecodeError:
            return '"INVALID_ESCAPED"'

    def tool_call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        *,
        use_reasoner: Optional[bool] = None,
        strict: bool = False,
        complexity: Optional[TaskComplexity] = None,
    ) -> Any:
        chosen_model = self._resolve_model(use_reasoner=use_reasoner, complexity=complexity)
        client = self.beta_client if strict else self.client
        if strict:
            for t in tools:
                if t.get("type") == "function":
                    t["function"]["strict"] = True
        return client.chat.completions.create(
            model=chosen_model,
            messages=messages,
            tools=tools,
            temperature=0.0,
        )


_client: Optional[DeepSeekClient] = None


def get_deepseek_client() -> DeepSeekClient:
    global _client
    if _client is None:
        _client = DeepSeekClient.from_env()
    return _client
