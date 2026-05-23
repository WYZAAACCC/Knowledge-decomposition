"""
重复验证器

去重别名表达，检测formula_latex等价重复，检测同义节点合并机会。
"""

import re
from typing import Dict, List, Tuple, Set, Optional, Any
from collections import defaultdict
from difflib import SequenceMatcher

from ..models import Node, Edge, KnowledgeGraph


class DuplicateValidator:
    """重复验证器"""

    def __init__(self, similarity_threshold: float = 0.9):
        """
        初始化

        Args:
            similarity_threshold: 相似度阈值（0-1）
        """
        self.similarity_threshold = similarity_threshold

    def find_duplicate_nodes_by_alias(self, nodes: List[Node]) -> List[List[Node]]:
        """
        通过别名查找重复节点

        Args:
            nodes: 节点列表

        Returns:
            重复节点组列表
        """
        # 构建别名到节点的映射
        alias_to_nodes = defaultdict(list)

        for node in nodes:
            # 节点ID本身
            alias_to_nodes[node.id].append(node)

            # 显式别名
            if hasattr(node, 'aliases') and node.aliases:
                for alias in node.aliases:
                    alias_to_nodes[alias].append(node)

            # 标题也可能作为别名
            if hasattr(node, 'title') and node.title:
                alias_to_nodes[node.title].append(node)

        # 找出有多个节点的别名
        duplicate_groups = []
        processed_nodes = set()

        for alias, node_list in alias_to_nodes.items():
            if len(node_list) > 1:
                # 过滤已处理的节点
                new_group = [node for node in node_list if node.id not in processed_nodes]
                if len(new_group) > 1:
                    duplicate_groups.append(new_group)
                    for node in new_group:
                        processed_nodes.add(node.id)

        return duplicate_groups

    def find_similar_formulas(self, nodes: List[Node]) -> List[Tuple[Node, Node, float]]:
        """
        查找相似公式

        Args:
            nodes: 节点列表

        Returns:
            (节点1, 节点2, 相似度) 列表
        """
        similar_pairs = []

        # 只检查equation节点
        equation_nodes = [node for node in nodes if node.type == "equation"]
        formula_nodes = [node for node in equation_nodes
                         if hasattr(node, 'formula_latex') and node.formula_latex]

        for i, node1 in enumerate(formula_nodes):
            for j, node2 in enumerate(formula_nodes[i+1:], i+1):
                similarity = self._calculate_formula_similarity(
                    node1.formula_latex, node2.formula_latex
                )

                if similarity >= self.similarity_threshold:
                    similar_pairs.append((node1, node2, similarity))

        return similar_pairs

    def find_semantically_similar_nodes(self, nodes: List[Node]) -> List[Tuple[Node, Node, float]]:
        """
        查找语义相似的节点（基于标题和陈述）

        Args:
            nodes: 节点列表

        Returns:
            (节点1, 节点2, 相似度) 列表
        """
        similar_pairs = []

        # 提取文本特征
        node_texts = {}
        for node in nodes:
            text_parts = []

            if hasattr(node, 'title') and node.title:
                text_parts.append(node.title)

            if hasattr(node, 'statement') and node.statement:
                text_parts.append(node.statement)

            if text_parts:
                node_texts[node.id] = ' '.join(text_parts)

        # 计算文本相似度
        node_ids = list(node_texts.keys())

        for i, id1 in enumerate(node_ids):
            for j, id2 in enumerate(node_ids[i+1:], i+1):
                if id1 == id2:
                    continue

                similarity = self._calculate_text_similarity(
                    node_texts[id1], node_texts[id2]
                )

                if similarity >= self.similarity_threshold:
                    node1 = next(n for n in nodes if n.id == id1)
                    node2 = next(n for n in nodes if n.id == id2)
                    similar_pairs.append((node1, node2, similarity))

        return similar_pairs

    def find_potential_merges(self, graph: KnowledgeGraph) -> Dict[str, Any]:
        """
        查找潜在的合并机会

        Args:
            graph: 知识图谱

        Returns:
            合并建议详情
        """
        suggestions = {
            "duplicate_alias_groups": [],
            "similar_formula_pairs": [],
            "semantically_similar_pairs": [],
            "merge_recommendations": []
        }

        # 1. 别名重复
        alias_duplicates = self.find_duplicate_nodes_by_alias(graph.nodes)
        suggestions["duplicate_alias_groups"] = [
            {"nodes": [node.id for node in group], "reason": "共享别名"}
            for group in alias_duplicates
        ]

        # 2. 公式相似
        formula_similarities = self.find_similar_formulas(graph.nodes)
        suggestions["similar_formula_pairs"] = [
            {"node1": pair[0].id, "node2": pair[1].id, "similarity": pair[2]}
            for pair in formula_similarities
        ]

        # 3. 语义相似
        semantic_similarities = self.find_semantically_similar_nodes(graph.nodes)
        suggestions["semantically_similar_pairs"] = [
            {"node1": pair[0].id, "node2": pair[1].id, "similarity": pair[2]}
            for pair in semantic_similarities
        ]

        # 4. 生成合并建议
        all_suggestions = set()

        # 从别名重复生成建议
        for group in alias_duplicates:
            if len(group) > 1:
                node_ids = [node.id for node in group]
                # 建议保留第一个，合并其他
                keep = node_ids[0]
                merge = node_ids[1:]
                all_suggestions.add((tuple(sorted(node_ids)), "别名重复"))

        # 从公式相似生成建议
        for node1, node2, similarity in formula_similarities:
            if similarity > 0.95:  # 高相似度
                node_ids = tuple(sorted([node1.id, node2.id]))
                all_suggestions.add((node_ids, f"公式相似度 {similarity:.2f}"))

        # 从语义相似生成建议
        for node1, node2, similarity in semantic_similarities:
            if similarity > 0.9:  # 高相似度
                node_ids = tuple(sorted([node1.id, node2.id]))
                all_suggestions.add((node_ids, f"语义相似度 {similarity:.2f}"))

        # 转换为建议列表
        for node_ids, reason in all_suggestions:
            suggestions["merge_recommendations"].append({
                "nodes": list(node_ids),
                "reason": reason,
                "action": "考虑合并这些节点"
            })

        return suggestions

    def validate_graph_uniqueness(self, graph: KnowledgeGraph) -> Tuple[bool, List[str], Dict]:
        """
        验证图的唯一性

        Args:
            graph: 知识图谱

        Returns:
            (是否唯一, 警告信息列表, 验证详情)
        """
        warnings = []
        details = self.find_potential_merges(graph)

        # 生成警告
        if details["duplicate_alias_groups"]:
            for group in details["duplicate_alias_groups"]:
                warnings.append(f"别名重复: {group['nodes']}")

        if details["similar_formula_pairs"]:
            for pair in details["similar_formula_pairs"]:
                if pair["similarity"] > 0.95:
                    warnings.append(
                        f"高度相似公式: {pair['node1']} 和 {pair['node2']} "
                        f"(相似度: {pair['similarity']:.2f})"
                    )

        if details["semantically_similar_pairs"]:
            for pair in details["semantically_similar_pairs"]:
                if pair["similarity"] > 0.9:
                    warnings.append(
                        f"语义相似节点: {pair['node1']} 和 {pair['node2']} "
                        f"(相似度: {pair['similarity']:.2f})"
                    )

        # 检查节点ID唯一性
        node_ids = [node.id for node in graph.nodes]
        duplicate_ids = self._find_duplicate_ids(node_ids)
        if duplicate_ids:
            for node_id in duplicate_ids:
                warnings.append(f"重复节点ID: {node_id}")

        # 检查边ID唯一性
        edge_ids = [edge.id for edge in graph.edges]
        duplicate_edge_ids = self._find_duplicate_ids(edge_ids)
        if duplicate_edge_ids:
            for edge_id in duplicate_edge_ids:
                warnings.append(f"重复边ID: {edge_id}")

        # 汇总
        passed = (len(details["merge_recommendations"]) == 0 and
                  len(duplicate_ids) == 0 and
                  len(duplicate_edge_ids) == 0)
        details["passed"] = passed
        details["warning_count"] = len(warnings)
        details["duplicate_node_ids"] = duplicate_ids
        details["duplicate_edge_ids"] = duplicate_edge_ids

        return passed, warnings, details

    def _calculate_formula_similarity(self, formula1: str, formula2: str) -> float:
        """
        计算公式相似度

        简化实现：基于字符串编辑距离
        实际实现可能需要标准化LaTeX格式
        """
        if not formula1 or not formula2:
            return 0.0

        # 标准化公式
        norm1 = self._normalize_formula(formula1)
        norm2 = self._normalize_formula(formula2)

        # 计算相似度
        matcher = SequenceMatcher(None, norm1, norm2)
        return matcher.ratio()

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        计算文本相似度

        基于编辑距离
        """
        if not text1 or not text2:
            return 0.0

        matcher = SequenceMatcher(None, text1.lower(), text2.lower())
        return matcher.ratio()

    def _normalize_formula(self, formula: str) -> str:
        """
        标准化公式字符串

        移除空格、标准化符号等
        """
        if not formula:
            return ""

        # 移除LaTeX命令
        result = re.sub(r'\\[a-zA-Z]+', '', formula)

        # 移除大括号
        result = re.sub(r'[{}]', '', result)

        # 移除空格
        result = re.sub(r'\s+', '', result)

        # 标准化等号
        result = result.replace('≡', '=').replace('≈', '=').replace('≅', '=')

        return result

    def _find_duplicate_ids(self, ids: List[str]) -> List[str]:
        """查找重复ID"""
        seen = set()
        duplicates = set()

        for item_id in ids:
            if item_id in seen:
                duplicates.add(item_id)
            else:
                seen.add(item_id)

        return list(duplicates)