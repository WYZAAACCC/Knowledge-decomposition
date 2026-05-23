"""
Fix 15: 输入安全验证模块

集中处理用户输入校验，供前端、CLI、orchestrator 共用。
"""
import re
from typing import Optional


MAX_TOPIC_LENGTH = 100

_XSS_PATTERNS = [
    r'<script', r'javascript:', r'on\w+\s*=', r'<iframe', r'<img\s+on',
    r'<embed', r'<object', r'<applet',
]

_SQL_PATTERNS = [
    r"'\s*;\s*drop\s", r"'\s*;\s*delete\s", r"'\s*;\s*insert\s",
    r"'\s*or\s+'1'\s*=\s*'1", r"union\s+select", r"--\s*$",
]

_PLACEHOLDER_PATTERNS = [
    r"待补充", r"TODO", r"TBD", r"N/?A", r"placeholder",
]


def validate_topic_text(topic_text: str) -> Optional[str]:
    """验证并清洗主题文本"""
    if not topic_text or not topic_text.strip():
        return None

    topic_text = topic_text.strip()

    if len(topic_text) > MAX_TOPIC_LENGTH:
        topic_text = topic_text[:MAX_TOPIC_LENGTH]

    # XSS check
    for pattern in _XSS_PATTERNS:
        if re.search(pattern, topic_text, re.IGNORECASE):
            return None

    # SQL injection check
    for pattern in _SQL_PATTERNS:
        if re.search(pattern, topic_text, re.IGNORECASE):
            return None

    # Emoji-only check
    if re.match(
        r'^[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\s]+$',
        topic_text
    ):
        return None

    # Random spam check
    if re.match(r'^[a\s]+$', topic_text, re.IGNORECASE) and len(topic_text) > 50:
        return None

    return topic_text


def sanitize_html_text(text: str) -> str:
    """安全地清理HTML文本"""
    if not text:
        return ""
    # Remove common XSS vectors
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    return text


def is_placeholder(text: str) -> bool:
    """检查文本是否为占位内容"""
    if not text:
        return False
    return any(re.search(p, text, re.IGNORECASE) for p in _PLACEHOLDER_PATTERNS)
