"""
RankerAgent

在多条路径中选择canonical path。
"""

import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from ..deepseek_client import get_deepseek_client, TaskComplexity
from ..models import KnowledgeGraph
from ..physics.canonical_paths import get_canonical_paths


@dataclass
class RankerOutput:
    """RankerAgent输出"""
    selected_canonical_path: str
    ranking_scores: Dict[str, float]
    ranking_rationale: str
    alternate_paths: List[str]
    warnings: List[str]


class RankerAgent:
    """RankerAgent"""

    def __init__(self):
        """初始化"""
        self.client = get_deepseek_client()
        self.canonical_paths = get_canonical_paths()

    def run(self, decomposer_output: Dict[str, Any],
            verification_output: Optional[Dict[str, Any]] = None) -> RankerOutput:
        """
        运行RankerAgent

        Args:
            decomposer_output: DecomposerAgent的输出
            verification_output: VerifierAgent的输出（可选）

        Returns:
            RankerOutput对象
        """
        subgraph = decomposer_output.get("subgraph")
        if not isinstance(subgraph, KnowledgeGraph):
            # 尝试从字典转换
            subgraph = KnowledgeGraph(**subgraph)

        # 提取图中的路径
        paths = self._extract_paths_from_graph(subgraph)

        if not paths:
            # 没有路径，使用默认
            return RankerOutput(
                selected_canonical_path=subgraph.canonical_path or "",
                ranking_scores={},
                ranking_rationale="没有可排名的路径",
                alternate_paths=subgraph.alternate_paths or [],
                warnings=["图中没有找到有效路径"]
            )

        # 如果有验证结果，使用验证信息
        validation_scores = {}
        if verification_output:
            validation_scores = self._extract_validation_scores(verification_output)

        # 评分路径
        ranked_paths = self._rank_paths(paths, subgraph, validation_scores)

        # 选择最佳路径作为canonical path
        if ranked_paths:
            best_path_id, best_score, best_rationale = ranked_paths[0]
        else:
            best_path_id = subgraph.canonical_path or ""
            best_score = 0.0
            best_rationale = "没有路径可排名"

        # 生成警告
        warnings = []
        if best_score < 0.6:
            warnings.append(f"最佳路径评分较低: {best_score:.2f}")

        # 检查与本地规范路径建议的一致性
        canonical_suggestion = self.canonical_paths.get_canonical_path(subgraph.topic)
        if canonical_suggestion:
            suggested_path = canonical_suggestion.get("path", [])
            best_path_nodes = self._get_path_nodes(best_path_id, subgraph)
            best_path_node_ids = {n.id for n in best_path_nodes}
            missing_nodes = set(suggested_path) - best_path_node_ids
            if missing_nodes:
                warnings.append(f"最佳路径缺少规范路径建议的关键节点: {missing_nodes}")

        # 构建排名分数映射
        ranking_scores = {path_id: score for path_id, score, _ in ranked_paths}

        # 备用路径（除最佳路径外的其他路径）
        alternate_paths = [path_id for path_id, _, _ in ranked_paths[1:4]]  # 最多3个备用路径

        return RankerOutput(
            selected_canonical_path=best_path_id,
            ranking_scores=ranking_scores,
            ranking_rationale=best_rationale,
            alternate_paths=alternate_paths,
            warnings=warnings
        )

    def _extract_paths_from_graph(self, graph: KnowledgeGraph) -> List[str]:
        """
        从图中提取路径ID

        Args:
            graph: 知识图谱

        Returns:
            路径ID列表
        """
        # 收集所有有path_id的边
        path_ids = set()
        for edge in graph.edges:
            if edge.path_id:
                path_ids.add(edge.path_id)

        return list(path_ids)

    def _extract_validation_scores(self, verification_output: Dict[str, Any]) -> Dict[str, float]:
        """
        从验证结果中提取分数

        Args:
            verification_output: 验证输出

        Returns:
            验证分数字典
        """
        scores = {}

        # 提取各个验证器的通过率
        for validator_name, result in verification_output.items():
            if isinstance(result, dict) and "passed" in result:
                scores[validator_name] = 1.0 if result["passed"] else 0.0
                if "score" in result:
                    scores[f"{validator_name}_score"] = float(result["score"])

        return scores

    def _rank_paths(self, path_ids: List[str], graph: KnowledgeGraph,
                   validation_scores: Dict[str, float]) -> List[Tuple[str, float, str]]:
        """
        对路径进行排名

        Args:
            path_ids: 路径ID列表
            graph: 知识图谱
            validation_scores: 验证分数

        Returns:
            (路径ID, 分数, 理由) 列表
        """
        if len(path_ids) <= 1:
            # 只有一个路径，无需复杂排名
            if path_ids:
                return [(path_ids[0], 1.0, "唯一路径")]
            else:
                return []

        # 对于少量路径，使用本地规则
        if len(path_ids) <= 3:
            return self._rank_paths_locally(path_ids, graph, validation_scores)
        else:
            # 对于多个路径，使用LLM
            return self._rank_paths_with_llm(path_ids, graph, validation_scores)

    def _rank_paths_locally(self, path_ids: List[str], graph: KnowledgeGraph,
                           validation_scores: Dict[str, float]) -> List[Tuple[str, float, str]]:
        """
        使用本地规则对路径进行排名

        Args:
            path_ids: 路径ID列表
            graph: 知识图谱
            validation_scores: 验证分数

        Returns:
            (路径ID, 分数, 理由) 列表
        """
        ranked = []

        for path_id in path_ids:
            # 计算路径分数
            pedagogy_score = self._calculate_pedagogy_score(path_id, graph)
            validation_score = self._calculate_validation_score(path_id, graph, validation_scores)
            simplicity_score = self._calculate_simplicity_score(path_id, graph)
            source_confidence = self._calculate_source_confidence(path_id, graph)

            # 综合分数（使用文档中的权重）
            total_score = (
                0.35 * pedagogy_score +
                0.25 * validation_score +
                0.20 * simplicity_score +
                0.20 * source_confidence
            )

            # 生成理由
            rationale = f"教学性: {pedagogy_score:.2f}, 验证: {validation_score:.2f}, "
            rationale += f"简洁性: {simplicity_score:.2f}, 来源可信度: {source_confidence:.2f}"

            ranked.append((path_id, total_score, rationale))

        # 按分数降序排序
        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked

    def _rank_paths_with_llm(self, path_ids: List[str], graph: KnowledgeGraph,
                            validation_scores: Dict[str, float]) -> List[Tuple[str, float, str]]:
        """
        使用LLM对路径进行排名

        Args:
            path_ids: 路径ID列表
            graph: 知识图谱
            validation_scores: 验证分数

        Returns:
            (路径ID, 分数, 理由) 列表
        """
        system_prompt = """你是一个专业的物理知识图谱排名器，负责从多条推导路径中选出最优的规范路径(canonical path)。

你的核心能力：
1. 评估推导路径的教学价值
2. 判断推导的逻辑严谨性
3. 评估路径的完整性和可靠性

排名标准（按优先级排序）：

1. 逻辑严谨性（权重最高）：
   - 推导步骤是否完整，无跳步
   - 假设条件是否充分且必要
   - 数学推导是否正确
   - 量纲是否一致

2. 教学价值（权重高）：
   - 路径是否从基础概念出发，循序渐进
   - 推导过程是否清晰易懂
   - 是否符合物理学的教学逻辑（从简单到复杂、从特殊到一般）
   - 每一步的物理意义是否明确

3. 完整性（权重中）：
   - 路径是否覆盖了关键的知识节点
   - 假设条件是否完整列出
   - 数学工具是否充分说明

4. 简洁性（权重低）：
   - 路径是否简洁，无冗余步骤
   - 是否存在更直接的推导方式

评分规则：
- 0.9-1.0: 路径逻辑严谨、教学价值极高、假设完备
- 0.7-0.9: 路径基本正确，但有小瑕疵
- 0.5-0.7: 路径可用，但存在明显不足
- 0.3-0.5: 路径有较大问题
- 0.0-0.3: 路径不可用

输出必须是严格的JSON格式：
{
  "rankings": [
    {
      "path_id": "路径ID",
      "score": 0.0到1.0的分数,
      "rationale": "详细排名理由，包括优势和不足"
    }
  ],
  "overall_rationale": "整体排名逻辑的解释"
}
"""

        # 准备路径信息
        paths_info = []
        for path_id in path_ids:
            path_edges = [e for e in graph.edges if e.path_id == path_id]
            path_nodes = self._get_path_nodes(path_id, graph)

            path_info = {
                "path_id": path_id,
                "node_count": len(path_nodes),
                "edge_count": len(path_edges),
                "nodes": [
                    {
                        "id": n.id,
                        "title": getattr(n, 'title', ''),
                        "type": n.type,
                        "level": getattr(n, 'abstraction_level', 2),
                    }
                    for n in path_nodes[:15]
                ],
                "derivation_edges": [
                    {
                        "from": e.from_,
                        "to": e.to,
                        "assumptions_count": len(e.assumptions) if e.assumptions else 0,
                        "derivation_steps_count": len(e.derivation_steps) if e.derivation_steps else 0,
                        "math_used": e.math_used if e.math_used else [],
                    }
                    for e in path_edges if e.type == "derives_from"
                ],
                "assumptions_coverage": self._calculate_assumptions_coverage(path_edges),
                "has_validation_issues": self._check_validation_issues(path_id, validation_scores)
            }
            paths_info.append(path_info)

        user_prompt = f"""对以下推导路径进行排名：

目标主题：{graph.topic}
路径信息：
{json.dumps(paths_info, ensure_ascii=False, indent=2)}

请根据逻辑严谨性、教学价值、完整性和简洁性进行排名，给出详细的评分理由。"""

        try:
            response = self.client.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                complexity=TaskComplexity.MODERATE,  # 排名是中等任务
                max_tokens=2048
            )

            rankings = response.get("rankings", [])
            ranked_result = []

            for rank in rankings:
                path_id = rank.get("path_id")
                score = float(rank.get("score", 0.0))
                rationale = rank.get("rationale", "")
                ranked_result.append((path_id, score, rationale))

            # 确保所有路径都在结果中
            existing_paths = {r[0] for r in ranked_result}
            for path_id in path_ids:
                if path_id not in existing_paths:
                    ranked_result.append((path_id, 0.5, "未在LLM排名中，分配默认分数"))

            # 按分数排序
            ranked_result.sort(key=lambda x: x[1], reverse=True)

            return ranked_result

        except Exception as e:
            error_msg = f"RankerAgent LLM调用失败，使用本地规则: {e}"
            print(f"[ERROR] {error_msg}")
            return self._rank_paths_locally(path_ids, graph, validation_scores)

    def _calculate_pedagogy_score(self, path_id: str, graph: KnowledgeGraph) -> float:
        """计算教学性分数"""
        path_edges = [e for e in graph.edges if e.path_id == path_id]
        if not path_edges:
            return 0.0

        # 检查是否有推导步骤
        has_derivation_steps = all(e.derivation_steps for e in path_edges)
        # 检查假设是否完整
        has_assumptions = all(e.assumptions for e in path_edges if e.type == "derives_from")
        # 检查路径长度（适中为好）
        path_length = len(path_edges)
        length_score = 1.0 - abs(path_length - 5) / 10  # 理想长度5

        score = 0.0
        if has_derivation_steps:
            score += 0.4
        if has_assumptions:
            score += 0.3
        score += length_score * 0.3

        return min(1.0, score)

    def _calculate_validation_score(self, path_id: str, graph: KnowledgeGraph,
                                   validation_scores: Dict[str, float]) -> float:
        """计算验证分数"""
        # 如果没有验证信息，返回默认值
        if not validation_scores:
            return 0.7

        # 简单实现：使用平均验证分数
        if validation_scores:
            return sum(validation_scores.values()) / len(validation_scores)
        else:
            return 0.5

    def _calculate_simplicity_score(self, path_id: str, graph: KnowledgeGraph) -> float:
        """计算简洁性分数"""
        path_edges = [e for e in graph.edges if e.path_id == path_id]
        if not path_edges:
            return 0.0

        # 路径长度（越短越简洁）
        length = len(path_edges)
        # 分支数量（越少越简洁）
        from_nodes = [e.from_ for e in path_edges]
        to_nodes = [e.to for e in path_edges]
        branch_penalty = max(0, len(set(from_nodes)) - 1) + max(0, len(set(to_nodes)) - 1)

        # 计算分数
        length_score = max(0, 1.0 - length / 10)  # 长度超过10会降低分数
        branch_score = max(0, 1.0 - branch_penalty / 5)  # 分支超过5会降低分数

        return (length_score + branch_score) / 2

    def _calculate_source_confidence(self, path_id: str, graph: KnowledgeGraph) -> float:
        """计算来源可信度"""
        path_edges = [e for e in graph.edges if e.path_id == path_id]
        if not path_edges:
            return 0.5

        # 检查边是否有来源信息
        edges_with_sources = 0
        for edge in path_edges:
            if hasattr(edge, 'sources') and edge.sources:
                edges_with_sources += 1

        return edges_with_sources / len(path_edges)

    def _calculate_assumptions_coverage(self, edges: List) -> float:
        """计算假设覆盖率"""
        if not edges:
            return 0.0

        edges_with_assumptions = sum(1 for e in edges if e.assumptions)
        return edges_with_assumptions / len(edges)

    def _check_validation_issues(self, path_id: str, validation_scores: Dict[str, float]) -> bool:
        """检查验证问题"""
        # 如果有任何验证分数低于0.5，认为有问题
        for score in validation_scores.values():
            if score < 0.5:
                return True
        return False

    def _get_path_nodes(self, path_id: str, graph: KnowledgeGraph) -> list:
        path_edges = [e for e in graph.edges if e.path_id == path_id]
        node_ids = set()
        for edge in path_edges:
            node_ids.add(edge.from_)
            node_ids.add(edge.to)
        node_map = {n.id: n for n in graph.nodes}
        return [node_map[nid] for nid in node_ids if nid in node_map]