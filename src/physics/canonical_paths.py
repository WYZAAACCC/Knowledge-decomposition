"""
规范路径建议

存储默认主路径建议。若LLM排序与本地canonical path规则冲突，
优先参考本地规则并记录warning。
"""

from typing import Dict, List, Optional, Tuple
import yaml
from pathlib import Path


class CanonicalPaths:
    """规范路径管理器"""

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

        self._paths: Dict[str, Dict] = {}
        self._load_paths()

    def _load_paths(self):
        """从配置文件加载规范路径"""
        if not self.config_dir.exists():
            return

        for yaml_file in self.config_dir.glob("*.yaml"):
            domain = yaml_file.stem
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)

                # 提取规范路径
                if "canonical_paths" in data:
                    self._paths[domain] = data["canonical_paths"]

            except Exception as e:
                print(f"警告: 加载规范路径 {yaml_file} 失败: {e}")

    def get_canonical_path(self, topic_id: str, domain: str = None) -> Optional[Dict]:
        """
        获取主题的规范路径建议

        Args:
            topic_id: 主题ID
            domain: 学科域

        Returns:
            包含path和rationale的字典，或None
        """
        if domain is None:
            domain = self._infer_domain(topic_id)

        if domain not in self._paths:
            return None

        return self._paths[domain].get(topic_id)

    def _infer_domain(self, topic_id: str) -> str:
        """从主题ID推断学科域"""
        # 简单实现，可以根据需要扩展
        if "bernoulli" in topic_id or "newton" in topic_id:
            return "mechanics"
        elif "thermodynamics" in topic_id or "entropy" in topic_id:
            return "thermodynamics"
        elif "gauss" in topic_id or "ampere" in topic_id:
            return "electromagnetism"
        elif "lens" in topic_id or "refraction" in topic_id:
            return "optics"
        elif "relativity" in topic_id or "quantum" in topic_id:
            return "modern_physics"
        else:
            return "mechanics"  # 默认

    def compare_paths(self, topic_id: str, candidate_paths: List[List[str]],
                      domain: str = None) -> Tuple[Optional[str], List[str], Dict]:
        """
        比较候选路径与规范路径

        Args:
            topic_id: 主题ID
            candidate_paths: 候选路径列表（每个路径是节点ID列表）
            domain: 学科域

        Returns:
            (推荐的规范路径ID, 警告列表, 评分详情)
        """
        canonical_suggestion = self.get_canonical_path(topic_id, domain)
        warnings = []
        scores = {}

        if not canonical_suggestion:
            # 没有规范路径建议，返回第一个候选路径
            if candidate_paths:
                return candidate_paths[0], warnings, scores
            else:
                return None, warnings, scores

        suggested_path = canonical_suggestion.get("path", [])
        suggested_rationale = canonical_suggestion.get("rationale", "")

        # 计算每个候选路径与规范路径的相似度
        best_path = None
        best_score = -1

        for i, path in enumerate(candidate_paths):
            score = self._calculate_path_similarity(path, suggested_path)
            scores[f"path_{i}"] = {
                "score": score,
                "length": len(path),
                "matches_canonical": score > 0.7  # 阈值
            }

            if score > best_score:
                best_score = score
                best_path = path

        # 如果最佳路径与规范路径差异较大，生成警告
        if best_score < 0.5 and suggested_path:
            warnings.append(
                f"候选路径与规范路径差异较大。规范路径建议: {suggested_path}"
            )
            warnings.append(f"理由: {suggested_rationale}")

        return best_path, warnings, scores

    def _calculate_path_similarity(self, path1: List[str], path2: List[str]) -> float:
        """
        计算两个路径的相似度

        简单实现：基于共同节点的比例
        """
        if not path1 or not path2:
            return 0.0

        set1 = set(path1)
        set2 = set(path2)

        intersection = set1 & set2
        union = set1 | set2

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def validate_path_completeness(self, path: List[str], topic_id: str,
                                   domain: str = None) -> Tuple[bool, List[str]]:
        """
        验证路径的完整性

        Args:
            path: 路径节点ID列表
            topic_id: 主题ID
            domain: 学科域

        Returns:
            (是否完整, 缺失的关键节点)
        """
        canonical_suggestion = self.get_canonical_path(topic_id, domain)
        if not canonical_suggestion:
            return True, []  # 没有规范要求

        required_nodes = set(canonical_suggestion.get("path", []))
        path_nodes = set(path)

        missing = required_nodes - path_nodes

        if missing:
            return False, list(missing)
        else:
            return True, []

    def get_all_canonical_paths(self) -> Dict[str, Dict]:
        """获取所有规范路径"""
        return self._paths.copy()


# 全局规范路径实例
_canonical_paths: Optional[CanonicalPaths] = None

def get_canonical_paths() -> CanonicalPaths:
    """获取全局规范路径实例"""
    global _canonical_paths
    if _canonical_paths is None:
        _canonical_paths = CanonicalPaths()
    return _canonical_paths