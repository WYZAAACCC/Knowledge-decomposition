"""
严格复杂图谱测试框架

测试高级物理知识的深层推导，要求：
- 层数 >= 5
- 节点数 >= 50
- 边数 >= 40
- 内容与主题高度相关
- 推导链完整（底层→中层→高层）
"""

import json
import sys
import time
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
dotenv.load_dotenv(project_root / ".env")

from src.orchestrator import GraphBuildOrchestrator
from src.models import KnowledgeGraph, Node, Edge


@dataclass
class StrictTestResult:
    topic: str
    passed: bool
    node_count: int
    edge_count: int
    max_depth: int
    derivation_depth: int
    isolated_nodes: int
    dangling_edges: int
    schema_valid: bool
    graph_connected: bool
    content_relevance: float
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]


class StrictTestSuite:
    """严格测试套件"""

    # 最小要求
    MIN_NODES = 50
    MIN_EDGES = 40
    MIN_DEPTH = 4
    MIN_VALIDATION_SCORE = 0.85

    # 高级物理主题 - 需要深层推导的复杂主题
    ADVANCED_TOPICS = [
        {"name": "量子场论", "down": 5, "up": 3, "max_nodes": 80,
         "description": "量子力学+相对论+场的量子化，需要从基础物理→量子力学→相对论量子力学→量子场论的多层推导"},

        {"name": "规范场论", "down": 5, "up": 3, "max_nodes": 80,
         "description": "杨-米尔斯理论、纤维丛、联络、曲率，需要李代数、纤维丛的深层知识"},

        {"name": "统计力学", "down": 5, "up": 3, "max_nodes": 80,
         "description": "从经典力学→统计力学→平衡态统计→非平衡统计的完整推导链"},

        {"name": "广义相对论", "down": 5, "up": 3, "max_nodes": 80,
         "description": "从欧几里得几何→黎曼几何→爱因斯坦场方程的完整数学物理推导"},

        {"name": "量子电动力学", "down": 5, "up": 3, "max_nodes": 70,
         "description": "QED的完整推导：麦克斯韦方程→量子化→Feynman图→重整化"},

        {"name": "量子色动力学", "down": 5, "up": 2, "max_nodes": 70,
         "description": "强相互作用的规范理论，SU(3)规范对称性"},

        {"name": "重整化群", "down": 5, "up": 2, "max_nodes": 70,
         "description": "从微扰论→重整化→重整化群的深层理论"},

        {"name": "超弦理论", "down": 4, "up": 2, "max_nodes": 70,
         "description": "从点粒子→弦理论→超弦的扩展，需要大量数学工具"},
    ]

    def __init__(self):
        self.results: List[StrictTestResult] = []

    def run_strict_test(self, topic_info: Dict) -> StrictTestResult:
        """运行严格测试"""
        topic = topic_info["name"]
        down = topic_info["down"]
        up = topic_info["up"]
        max_nodes = topic_info["max_nodes"]

        print(f"\n{'='*80}")
        print(f"【严格测试】{topic}")
        print(f"参数: down={down}, up={up}, max_nodes={max_nodes}")
        print(f"要求: 节点>={self.MIN_NODES}, 边>={self.MIN_EDGES}, 层数>={self.MIN_DEPTH}")
        print(f"{'='*80}")

        errors = []
        warnings = []

        try:
            orchestrator = GraphBuildOrchestrator(artifacts_dir="artifacts/latest")
            start_time = time.time()
            result = orchestrator.build_topic(
                topic,
                down=down,
                up=up,
                max_nodes=max_nodes
            )
            build_time = time.time() - start_time

            if not result.graph:
                return StrictTestResult(
                    topic=topic,
                    passed=False,
                    node_count=0, edge_count=0,
                    max_depth=0, derivation_depth=0,
                    isolated_nodes=0, dangling_edges=0,
                    schema_valid=False, graph_connected=False,
                    content_relevance=0.0,
                    errors=["图谱构建失败"],
                    warnings=[], details={}
                )

            graph = result.graph

            # 1. 验证节点数和边数
            node_count = len(graph.nodes)
            edge_count = len(graph.edges)

            if node_count < self.MIN_NODES:
                errors.append(f"节点数不足: {node_count} < {self.MIN_NODES}")
            if edge_count < self.MIN_EDGES:
                errors.append(f"边数不足: {edge_count} < {self.MIN_EDGES}")

            # 2. 分析图深度
            max_depth, derivation_depth = self._analyze_graph_depth(graph)

            if max_depth < self.MIN_DEPTH:
                errors.append(f"图深度不足: {max_depth} < {self.MIN_DEPTH}")

            # 3. 检查孤立节点和悬空边
            isolated_nodes, dangling_edges = self._check_graph_connectivity(graph)

            if isolated_nodes > node_count * 0.2:
                warnings.append(f"孤立节点过多: {isolated_nodes}/{node_count} ({100*isolated_nodes/node_count:.1f}%)")

            # 4. 检查图连通性
            graph_connected = self._check_full_connectivity(graph)

            if not graph_connected:
                warnings.append("图不连通，可能缺少中间推导步骤")

            # 5. 验证内容相关性
            content_relevance = self._validate_content_relevance(graph, topic)

            if content_relevance < 0.7:
                errors.append(f"内容相关性不足: {content_relevance:.2f} < 0.70")

            # 6. 验证Schema
            schema_valid = self._validate_schema(graph)

            # 7. 检查验证分数
            validation_score = 0.0
            vr = result.debug_info.get('validation_results', {})
            if vr:
                schema_score = vr.get('schema', {}).get('score', 0) * 0.30
                graph_score = vr.get('graph_structure', {}).get('score', 0) * 0.30
                assumption_score = vr.get('assumptions', {}).get('score', 0) * 0.20
                dim_score = vr.get('dimensions', {}).get('score', 0) * 0.10
                dup_score = vr.get('duplicates', {}).get('score', 0) * 0.10
                validation_score = schema_score + graph_score + assumption_score + dim_score + dup_score

            if validation_score < self.MIN_VALIDATION_SCORE:
                errors.append(f"验证分数不足: {validation_score:.2f} < {self.MIN_VALIDATION_SCORE}")

            # 汇总
            passed = (
                len(errors) == 0 and
                node_count >= self.MIN_NODES and
                edge_count >= self.MIN_EDGES and
                max_depth >= self.MIN_DEPTH and
                validation_score >= self.MIN_VALIDATION_SCORE
            )

            print(f"\n📊 测试结果:")
            print(f"   节点数: {node_count} {'✅' if node_count >= self.MIN_NODES else '❌'}")
            print(f"   边数: {edge_count} {'✅' if edge_count >= self.MIN_EDGES else '❌'}")
            print(f"   图深度: {max_depth} {'✅' if max_depth >= self.MIN_DEPTH else '❌'}")
            print(f"   推导深度: {derivation_depth}")
            print(f"   孤立节点: {isolated_nodes}")
            print(f"   悬空边: {dangling_edges}")
            print(f"   连通性: {'✅' if graph_connected else '⚠️'}")
            print(f"   内容相关性: {content_relevance:.2%} {'✅' if content_relevance >= 0.7 else '❌'}")
            print(f"   Schema验证: {'✅' if schema_valid else '❌'}")
            print(f"   验证分数: {validation_score:.2f} {'✅' if validation_score >= self.MIN_VALIDATION_SCORE else '❌'}")
            print(f"   构建时间: {build_time:.1f}s")

            if errors:
                print(f"\n❌ 错误:")
                for e in errors:
                    print(f"   - {e}")

            if warnings:
                print(f"\n⚠️ 警告:")
                for w in warnings:
                    print(f"   - {w}")

            print(f"\n{'='*80}")
            print(f"【{topic}】{'✅ 通过' if passed else '❌ 失败'}")
            print(f"{'='*80}")

            return StrictTestResult(
                topic=topic,
                passed=passed,
                node_count=node_count,
                edge_count=edge_count,
                max_depth=max_depth,
                derivation_depth=derivation_depth,
                isolated_nodes=isolated_nodes,
                dangling_edges=dangling_edges,
                schema_valid=schema_valid,
                graph_connected=graph_connected,
                content_relevance=content_relevance,
                errors=errors,
                warnings=warnings,
                details={
                    "down": down, "up": up, "max_nodes": max_nodes,
                    "validation_score": validation_score,
                    "build_time": build_time,
                    "topic_description": topic_info.get("description", "")
                }
            )

        except Exception as e:
            print(f"\n💥 异常: {e}")
            import traceback
            traceback.print_exc()
            return StrictTestResult(
                topic=topic,
                passed=False,
                node_count=0, edge_count=0,
                max_depth=0, derivation_depth=0,
                isolated_nodes=0, dangling_edges=0,
                schema_valid=False, graph_connected=False,
                content_relevance=0.0,
                errors=[str(e)],
                warnings=[],
                details={}
            )

    def _analyze_graph_depth(self, graph: KnowledgeGraph) -> tuple[int, int]:
        """分析图深度"""
        import networkx as nx

        G = nx.DiGraph()
        for node in graph.nodes:
            G.add_node(node.id)
        for edge in graph.edges:
            G.add_edge(edge.from_, edge.to)

        if G.number_of_nodes() == 0:
            return 0, 0

        # 找最长路径（近似深度）
        try:
            longest_path = nx.dag_longest_path(G)
            max_depth = len(longest_path) - 1
        except nx.NetworkXError:
            max_depth = 0

        # 计算推导深度（从叶节点到根节点的最大距离）
        leaves = [n for n in G.nodes() if G.in_degree(n) == 0]
        roots = [n for n in G.nodes() if G.out_degree(n) == 0]

        derivation_depth = 0
        for leaf in leaves:
            for root in roots:
                try:
                    path_len = nx.shortest_path_length(G, leaf, root)
                    derivation_depth = max(derivation_depth, path_len)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue

        return max_depth, derivation_depth

    def _check_graph_connectivity(self, graph: KnowledgeGraph) -> tuple[int, int]:
        """检查图的连通性"""
        import networkx as nx

        G = nx.DiGraph()
        for node in graph.nodes:
            G.add_node(node.id)
        for edge in graph.edges:
            G.add_edge(edge.from_, edge.to)

        # 孤立节点
        isolated = sum(1 for n in G.nodes() if G.degree(n) == 0)

        # 悬空边（指向不存在节点的边）
        node_ids = set(n.id for n in graph.nodes)
        dangling = sum(1 for e in graph.edges if e.from_ not in node_ids or e.to not in node_ids)

        return isolated, dangling

    def _check_full_connectivity(self, graph: KnowledgeGraph) -> bool:
        """检查图是否完全连通"""
        import networkx as nx

        G = nx.DiGraph()
        for node in graph.nodes:
            G.add_node(node.id)
        for edge in graph.edges:
            G.add_edge(edge.from_, edge.to)

        if G.number_of_nodes() == 0:
            return False

        # 强连通分量
        sccs = list(nx.strongly_connected_components(G))

        # 检查最大连通分量是否包含大部分节点
        if not sccs:
            return False

        largest_scc = max(sccs, key=len)
        coverage = len(largest_scc) / G.number_of_nodes()

        return coverage >= 0.8

    def _validate_content_relevance(self, graph: KnowledgeGraph, topic: str) -> float:
        """验证内容与主题的相关性"""
        topic_keywords = self._extract_topic_keywords(topic)
        relevant_count = 0
        total_count = len(graph.nodes)

        for node in graph.nodes:
            node_text = (
                (node.id or "") + " " +
                (getattr(node, 'title', '') or "") + " " +
                (getattr(node, 'statement', '') or "") + " " +
                (getattr(node, 'formula_latex', '') or "")
            ).lower()

            # 检查是否有相关关键词
            for keyword in topic_keywords:
                if keyword.lower() in node_text:
                    relevant_count += 1
                    break

        return relevant_count / total_count if total_count > 0 else 0.0

    def _extract_topic_keywords(self, topic: str) -> List[str]:
        """提取主题关键词"""
        keywords_map = {
            "量子场论": ["量子", "场", "场论", "量子化", "费曼", "散射", "矩阵", "规范", "相互作用"],
            "规范场论": ["规范", "杨-米尔斯", "SU(2)", "SU(3)", "联络", "曲率", "纤维丛", "对称性"],
            "统计力学": ["统计", "配分函数", "玻尔兹曼", "熵", "系综", "微观", "宏观", "热力学"],
            "广义相对论": ["相对论", "时空", "度规", "黎曼", "曲率", "爱因斯坦", "引力", "黑洞"],
            "量子电动力学": ["QED", "量子电动力学", "电子", "光子", "费曼图", "重整化", "电磁"],
            "量子色动力学": ["QCD", "量子色动力学", "夸克", "胶子", "色荷", "SU(3)", "强相互作用"],
            "重整化群": ["重整化", "RG", "标度", "临界", "不动点", "量子场论"],
            "超弦理论": ["弦", "超弦", "维度", "紧化", "卡拉比-丘", "杂化弦"],
        }

        return keywords_map.get(topic, [topic])

    def _validate_schema(self, graph: KnowledgeGraph) -> bool:
        """验证Schema"""
        from src.validators.schema_validator import SchemaValidator
        try:
            sv = SchemaValidator()
            passed, _, _ = sv.validate_graph(graph)
            return passed
        except Exception:
            return False

    def run_all_tests(self) -> List[StrictTestResult]:
        """运行所有测试"""
        print("\n" + "="*80)
        print("🚀 开始严格测试套件")
        print(f"要求: 节点>={self.MIN_NODES}, 边>={self.MIN_EDGES}, 层数>={self.MIN_DEPTH}")
        print("="*80)

        for topic_info in self.ADVANCED_TOPICS:
            result = self.run_strict_test(topic_info)
            self.results.append(result)

            # 如果失败，记录但不停止，继续测试其他主题
            if not result.passed:
                print(f"\n⚠️ {topic_info['name']} 未通过严格测试，继续测试其他主题...")

        return self.results

    def print_summary(self):
        """打印汇总报告"""
        print("\n" + "="*80)
        print("📋 严格测试汇总报告")
        print("="*80)

        passed_count = sum(1 for r in self.results if r.passed)
        total_count = len(self.results)

        for r in self.results:
            status_icon = "✅" if r.passed else "❌"
            print(f"\n{status_icon} {r.topic}")
            print(f"   节点: {r.node_count}, 边: {r.edge_count}, 深度: {r.max_depth}")
            print(f"   推导深度: {r.derivation_depth}, 内容相关: {r.content_relevance:.1%}")
            if r.errors:
                print(f"   错误: {r.errors[:2]}")

        print(f"\n{'='*80}")
        print(f"通过: {passed_count}/{total_count}")

        if passed_count == total_count:
            print("🎉 所有严格测试通过！")
        else:
            print(f"⚠️ 还有 {total_count - passed_count} 个测试未通过，需要修复")

        print("="*80)

        # 保存详细报告
        report = {
            "passed_count": passed_count,
            "total_count": total_count,
            "all_passed": passed_count == total_count,
            "results": [
                {
                    "topic": r.topic,
                    "passed": r.passed,
                    "node_count": r.node_count,
                    "edge_count": r.edge_count,
                    "max_depth": r.max_depth,
                    "derivation_depth": r.derivation_depth,
                    "content_relevance": r.content_relevance,
                    "validation_score": r.details.get("validation_score", 0),
                    "errors": r.errors,
                    "warnings": r.warnings,
                    "topic_description": r.details.get("topic_description", ""),
                }
                for r in self.results
            ]
        }

        with open(project_root / "strict_test_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n详细报告已保存到 strict_test_report.json")

        return passed_count == total_count


def main():
    suite = StrictTestSuite()
    suite.run_all_tests()
    all_passed = suite.print_summary()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
