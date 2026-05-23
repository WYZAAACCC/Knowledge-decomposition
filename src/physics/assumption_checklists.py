"""
假设检查清单

按学科域和主题维护默认前提检查清单。
"""

from typing import Dict, List, Set, Tuple, Optional
import yaml
import os
from pathlib import Path


class AssumptionChecklists:
    """假设检查清单管理器"""

    def __init__(self, config_dir: str = None):
        """
        初始化

        Args:
            config_dir: 配置文件目录，默认为项目根目录下的configs/domain_rules
        """
        if config_dir is None:
            # 默认路径
            self.config_dir = Path(__file__).parent.parent.parent / "configs" / "domain_rules"
        else:
            self.config_dir = Path(config_dir)

        self._checklists: Dict[str, Dict[str, List[str]]] = {}
        self._domain_checklists: Dict[str, Set[str]] = {}
        self._load_checklists()

    def _load_checklists(self):
        """从配置文件加载检查清单"""
        if not self.config_dir.exists():
            return

        for yaml_file in self.config_dir.glob("*.yaml"):
            domain = yaml_file.stem
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)

                # 提取假设检查清单
                if "assumption_checklists" in data:
                    self._checklists[domain] = data["assumption_checklists"]

                # 提取该学科域的所有假设
                domain_assumptions = set()
                for topic_assumptions in data.get("assumption_checklists", {}).values():
                    domain_assumptions.update(topic_assumptions)
                self._domain_checklists[domain] = domain_assumptions

            except Exception as e:
                print(f"警告: 加载假设检查清单 {yaml_file} 失败: {e}")

    def get_topic_checklist(self, topic_id: str, domain: str = None) -> List[str]:
        """
        获取主题的假设检查清单

        Args:
            topic_id: 主题ID，如 "eq.bernoulli"
            domain: 学科域，如果为None则从topic_id推断

        Returns:
            假设ID列表
        """
        if domain is None:
            # 从topic_id推断学科域
            # 简单实现：检查topic_id是否包含学科域信息
            if "eq.bernoulli" in topic_id:
                domain = "mechanics"
            elif "law.first_law_thermodynamics" in topic_id:
                domain = "thermodynamics"
            elif "law.gauss_electric" in topic_id:
                domain = "electromagnetism"
            elif "eq.thin_lens" in topic_id:
                domain = "optics"
            else:
                domain = "mechanics"  # 默认

        if domain not in self._checklists:
            return []

        return self._checklists[domain].get(topic_id, [])

    def get_domain_assumptions(self, domain: str) -> Set[str]:
        """获取学科域的所有假设"""
        return self._domain_checklists.get(domain, set())

    def check_topic_assumptions(self, topic_id: str, provided_assumptions: List[str],
                                domain: str = None) -> Dict[str, List[str]]:
        """
        检查主题的假设覆盖率

        Args:
            topic_id: 主题ID
            provided_assumptions: 提供的假设列表
            domain: 学科域

        Returns:
            字典包含:
            - missing: 缺失的假设
            - extra: 多余的假设
            - coverage: 覆盖率 (0-1)
        """
        required = set(self.get_topic_checklist(topic_id, domain))
        provided = set(provided_assumptions)

        missing = required - provided
        extra = provided - required

        coverage = 0.0
        if required:
            coverage = len(provided & required) / len(required)

        return {
            "missing": list(missing),
            "extra": list(extra),
            "coverage": coverage,
            "required_count": len(required),
            "provided_count": len(provided),
            "matched_count": len(provided & required)
        }

    def validate_derivation_edge(self, edge_type: str, assumptions: List[str],
                                 topic_id: str = None) -> Tuple[bool, str]:
        """
        验证推导边的假设

        Args:
            edge_type: 边类型
            assumptions: 假设列表
            topic_id: 相关主题ID（用于检查清单）

        Returns:
            (是否有效, 错误信息)
        """
        if edge_type == "derives_from":
            if not assumptions:
                return False, "derives_from边必须包含至少一个假设"

            if topic_id:
                # 检查是否满足检查清单
                checklist = self.get_topic_checklist(topic_id)
                if checklist:
                    missing = set(checklist) - set(assumptions)
                    if missing:
                        return False, f"缺失关键假设: {missing}"

            # 检查假设格式（简单检查）
            for assumption in assumptions:
                if not isinstance(assumption, str) or not assumption.strip():
                    return False, f"无效假设: {assumption}"

        return True, "验证通过"

    def get_all_checklists(self) -> Dict[str, Dict[str, List[str]]]:
        """获取所有检查清单"""
        return self._checklists.copy()


# 全局检查清单实例
_checklists: Optional[AssumptionChecklists] = None

def get_assumption_checklists() -> AssumptionChecklists:
    """获取全局假设检查清单实例"""
    global _checklists
    if _checklists is None:
        _checklists = AssumptionChecklists()
    return _checklists