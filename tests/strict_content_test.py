"""
严格内容验证测试框架
验证：节点内容正确性、边方向正确性、层级分类正确性、假设正确性、图谱连通性
"""
import json
import sys
import time
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple
import dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
dotenv.load_dotenv(project_root / ".env")

from src.orchestrator import GraphBuildOrchestrator
from src.models import KnowledgeGraph, Node, Edge, NodeType


@dataclass
class TopicSpec:
    name: str
    required_keywords: List[str]
    required_formulas: List[str]
    expected_domain: str
    min_nodes: int = 50
    min_edges: int = 40
    min_depth: int = 3
    forbidden_keywords: List[str] = field(default_factory=list)


TOPIC_SPECS = [
    TopicSpec(
        name="广义相对论",
        required_keywords=["时空", "度规", "曲率", "张量", "引力", "黎曼", "爱因斯坦", "测地线", "协变"],
        required_formulas=["G", "R", "g", "T", "einstein"],
        expected_domain="relativistic",
        forbidden_keywords=["函数映射", "集合论", "数列"]
    ),
    TopicSpec(
        name="薛定谔方程",
        required_keywords=["波函数", "哈密顿", "量子态", "本征", "概率", "算符", "薛定谔"],
        required_formulas=["iℏ", "ψ", "Ĥ", "E"],
        expected_domain="quantum",
        forbidden_keywords=["经典力学体系", "流体力学方程"]
    ),
    TopicSpec(
        name="狄拉克方程",
        required_keywords=["旋量", "费米子", "反物质", "狄拉克", "γ矩阵", "自旋", "相对论"],
        required_formulas=["γ^μ", "ψ", "iγ", "mψ"],
        expected_domain="quantum",
        forbidden_keywords=["经典力学", "流体力学"]
    ),
    TopicSpec(
        name="杨-米尔斯规范场论",
        required_keywords=["规范", "杨-米尔斯", "SU(2)", "SU(3)", "联络", "曲率", "非阿贝尔", "对称性"],
        required_formulas=["F_μν", "A_μ", "[D_μ", "规范场"],
        expected_domain="quantum",
        forbidden_keywords=["流体", "热力学第二定律"]
    ),
    TopicSpec(
        name="麦克斯韦方程组",
        required_keywords=["电场", "磁场", "电磁", "高斯", "法拉第", "安培", "位移电流"],
        required_formulas=["nabla", "E", "B", "curl"],
        expected_domain="electromagnetism",
        forbidden_keywords=["量子态", "波函数"]
    ),
    TopicSpec(
        name="纳维-斯托克斯方程",
        required_keywords=["粘性", "流体", "压力", "速度场", "雷诺数", "湍流", "纳维"],
        required_formulas=["ρ", "∇p", "μ∇²", "∂v/∂t"],
        expected_domain="mechanics",
        forbidden_keywords=["量子", "波函数"]
    ),
    TopicSpec(
        name="玻尔兹曼输运方程",
        required_keywords=["分布函数", "碰撞", "输运", "弛豫", "玻尔兹曼", "散射"],
        required_formulas=["∂f/∂t", "C[f]", "∇ᵥf", "碰撞积分"],
        expected_domain="statistical",
        forbidden_keywords=["量子态", "波函数"]
    ),
    TopicSpec(
        name="弹性力学四阶张量重构",
        required_keywords=["应力", "应变", "张量", "弹性", "胡克定律", "本构", "对称性"],
        required_formulas=["C_ijkl", "σ_ij", "ε_kl", "刚度"],
        expected_domain="mechanics",
        forbidden_keywords=["量子", "波函数"]
    ),
    TopicSpec(
        name="克尔时空度规",
        required_keywords=["克尔", "黑洞", "旋转", "度规", "视界", "奇点", "角动量"],
        required_formulas=["ds²", "Δ", "Σ", "a=J/M"],
        expected_domain="relativistic",
        forbidden_keywords=["量子态", "波函数"]
    ),
    TopicSpec(
        name="雷桥杜里方程",
        required_keywords=["测地线", "聚焦", "膨胀", "剪切", "旋度", "里奇曲率"],
        required_formulas=["dθ/dτ", "σ_μν", "ω_μν", "R_μν"],
        expected_domain="relativistic",
        forbidden_keywords=["量子态", "波函数"]
    ),
    TopicSpec(
        name="施温格-戴森方程",
        required_keywords=["格林函数", "自能", "费曼图", "传播子", "量子场论", "重整化"],
        required_formulas=["G⁻¹", "Σ[G]", "G₀⁻¹", "自能"],
        expected_domain="quantum",
        forbidden_keywords=["流体", "热力学第二定律"]
    ),
    TopicSpec(
        name="马约拉纳方程",
        required_keywords=["马约拉纳", "费米子", "反粒子", "自旋", "手征", "中微子"],
        required_formulas=["ψ=ψᶜ", "H_M", "马约拉纳质量"],
        expected_domain="quantum",
        forbidden_keywords=["流体", "热力学"]
    ),
    TopicSpec(
        name="金兹堡-朗道方程",
        required_keywords=["超导", "序参量", "金兹堡", "朗道", "相变", "库珀对", "穿透深度"],
        required_formulas=["ψ", "αψ+β|ψ|²", "A/c", "序参量"],
        expected_domain="quantum",
        forbidden_keywords=["流体力学", "纳维"]
    ),
    TopicSpec(
        name="刘维尔方程",
        required_keywords=["相空间", "概率密度", "泊松括号", "哈密顿", "刘维尔", "守恒"],
        required_formulas=["∂ρ/∂t", "{H,ρ}", "相空间"],
        expected_domain="statistical",
        forbidden_keywords=["量子态", "波函数"]
    ),
    TopicSpec(
        name="弗拉索夫方程",
        required_keywords=["等离子体", "分布函数", "自洽场", "弗拉索夫", "无碰撞", "电磁场"],
        required_formulas=["f", "E", "B", "vlasov"],
        expected_domain="statistical",
        forbidden_keywords=["量子态", "波函数"]
    ),
    TopicSpec(
        name="磁流体方程组",
        required_keywords=["磁流体", "等离子体", "磁场", "感应方程", "洛伦兹力", "MHD", "阿尔芬"],
        required_formulas=["B", "v", "plasma", "alfven"],
        expected_domain="mechanics",
        forbidden_keywords=["量子态", "波函数"]
    ),
]


class StrictContentValidator:
    """严格内容验证器"""

    def validate_graph(self, graph: KnowledgeGraph, spec: TopicSpec) -> Dict[str, Any]:
        results = {
            "topic": spec.name,
            "passed": True,
            "errors": [],
            "warnings": [],
            "checks": {}
        }

        # 1. 基本数量检查
        node_count = len(graph.nodes)
        edge_count = len(graph.edges)
        results["checks"]["node_count"] = node_count
        results["checks"]["edge_count"] = edge_count

        if node_count < spec.min_nodes:
            results["errors"].append(f"节点数不足: {node_count} < {spec.min_nodes}")
            results["passed"] = False
        if edge_count < spec.min_edges:
            results["errors"].append(f"边数不足: {edge_count} < {spec.min_edges}")
            results["passed"] = False

        # 2. 内容相关性检查
        content_check = self._check_content_relevance(graph, spec)
        results["checks"]["content_relevance"] = content_check["score"]
        if content_check["score"] < 0.4:
            results["errors"].append(f"内容相关性不足: {content_check['score']:.1%}")
            results["passed"] = False
        results["checks"]["irrelevant_nodes"] = content_check.get("irrelevant", [])

        # 3. 禁止关键词检查
        forbidden_check = self._check_forbidden_content(graph, spec)
        results["checks"]["forbidden_content"] = forbidden_check
        if forbidden_check:
            results["errors"].append(f"包含禁止内容: {forbidden_check[:3]}")
            results["passed"] = False

        # 4. 必需公式检查
        formula_check = self._check_required_formulas(graph, spec)
        results["checks"]["formula_coverage"] = formula_check["coverage"]
        if formula_check["coverage"] < 0.25:
            results["errors"].append(f"公式覆盖率不足: {formula_check['coverage']:.1%}")
            results["passed"] = False
        results["checks"]["missing_formulas"] = formula_check.get("missing", [])

        # 5. 边方向正确性检查
        edge_check = self._check_edge_directions(graph)
        results["checks"]["edge_direction_valid"] = edge_check["valid"]
        results["checks"]["edge_direction_errors"] = edge_check.get("errors", [])
        if not edge_check["valid"]:
            results["warnings"].append(f"边方向问题: {edge_check.get('errors', [])[:3]}")

        # 6. 层级分类检查
        level_check = self._check_abstraction_levels(graph)
        results["checks"]["level_distribution"] = level_check["distribution"]
        if level_check.get("all_same_level"):
            results["warnings"].append("所有节点层级相同，缺少层次结构")

        # 7. 假设正确性检查
        assumption_check = self._check_assumptions(graph)
        results["checks"]["assumption_coverage"] = assumption_check["coverage"]
        results["checks"]["empty_assumptions"] = assumption_check.get("empty_count", 0)
        if assumption_check["coverage"] < 0.7:
            results["warnings"].append(f"假设覆盖率低: {assumption_check['coverage']:.1%}")

        # 8. 图深度检查
        depth = self._compute_graph_depth(graph)
        results["checks"]["max_depth"] = depth
        if depth < spec.min_depth:
            results["errors"].append(f"图深度不足: {depth} < {spec.min_depth}")
            results["passed"] = False

        # 9. 连通性检查
        connectivity = self._check_connectivity(graph)
        results["checks"]["connected"] = connectivity["connected"]
        results["checks"]["isolated_nodes"] = connectivity["isolated_count"]
        if connectivity["isolated_count"] > node_count * 0.2:
            results["warnings"].append(f"孤立节点过多: {connectivity['isolated_count']}")

        return results

    def _check_content_relevance(self, graph: KnowledgeGraph, spec: TopicSpec) -> Dict:
        relevant = 0
        irrelevant = []
        for node in graph.nodes:
            text = f"{node.id} {getattr(node, 'title', '')} {getattr(node, 'statement', '') or ''} {getattr(node, 'formula_latex', '') or ''}".lower()
            is_relevant = any(kw.lower() in text for kw in spec.required_keywords)
            if is_relevant:
                relevant += 1
            else:
                irrelevant.append(node.id)
        total = len(graph.nodes)
        score = relevant / total if total > 0 else 0
        return {"score": score, "irrelevant": irrelevant[:10]}

    def _check_forbidden_content(self, graph: KnowledgeGraph, spec: TopicSpec) -> List[str]:
        found = []
        for node in graph.nodes:
            title = getattr(node, 'title', '').lower()
            for kw in spec.forbidden_keywords:
                if kw.lower() in title:
                    found.append(f"{node.id}: {kw}")
        return found

    def _check_required_formulas(self, graph: KnowledgeGraph, spec: TopicSpec) -> Dict:
        found = 0
        missing = []
        for formula in spec.required_formulas:
            formula_found = False
            formula_variants = self._generate_formula_variants(formula)
            for node in graph.nodes:
                fl = getattr(node, 'formula_latex', '') or ''
                st = getattr(node, 'statement', '') or ''
                combined = (fl + ' ' + st).lower()
                for variant in formula_variants:
                    if variant.lower() in combined:
                        formula_found = True
                        break
                if formula_found:
                    break
            if formula_found:
                found += 1
            else:
                missing.append(formula)
        coverage = found / len(spec.required_formulas) if spec.required_formulas else 1.0
        return {"coverage": coverage, "missing": missing}

    def _generate_formula_variants(self, formula: str) -> List[str]:
        variants = [formula]
        greek_map = {
            'μ': ['mu', '\\mu', '{\\mu}'],
            'ν': ['nu', '\\nu', '{\\nu}'],
            'α': ['alpha', '\\alpha'],
            'β': ['beta', '\\beta'],
            'γ': ['gamma', '\\gamma'],
            'θ': ['theta', '\\theta'],
            'ρ': ['rho', '\\rho'],
            'σ': ['sigma', '\\sigma'],
            'ψ': ['psi', '\\psi'],
            'φ': ['phi', '\\phi'],
            'ε': ['epsilon', '\\epsilon', '\\varepsilon'],
            'ω': ['omega', '\\omega'],
            'λ': ['lambda', '\\lambda'],
            '∂': ['partial', '\\partial'],
            '∇': ['nabla', '\\nabla'],
            'ℏ': ['hbar', '\\hbar'],
        }
        for greek, replacements in greek_map.items():
            if greek in formula:
                for rep in replacements:
                    variants.append(formula.replace(greek, rep))
        variants.append(formula.replace('_', ''))
        variants.append(formula.replace('_', '\\_'))
        if '_' in formula:
            parts = formula.split('_')
            if len(parts) == 2:
                variants.append(f"{parts[0]}_{{{parts[1]}}}")
                variants.append(f"{parts[0]}_{{\\{parts[1]}}}")
        return variants

    def _check_edge_directions(self, graph: KnowledgeGraph) -> Dict:
        node_ids = {n.id for n in graph.nodes}
        errors = []
        for edge in graph.edges:
            if edge.from_ not in node_ids:
                errors.append(f"边{edge.id}: from={edge.from_}不存在")
            if edge.to not in node_ids:
                errors.append(f"边{edge.id}: to={edge.to}不存在")
            if edge.type == "derives_from":
                from_node = next((n for n in graph.nodes if n.id == edge.from_), None)
                to_node = next((n for n in graph.nodes if n.id == edge.to), None)
                if from_node and to_node:
                    if hasattr(from_node, 'abstraction_level') and hasattr(to_node, 'abstraction_level'):
                        if from_node.abstraction_level < to_node.abstraction_level - 1:
                            errors.append(f"边{edge.id}: derives_from层级跳跃过大(from={from_node.abstraction_level}, to={to_node.abstraction_level})")
        return {"valid": len(errors) == 0, "errors": errors[:5]}

    def _check_abstraction_levels(self, graph: KnowledgeGraph) -> Dict:
        distribution = {}
        all_same = True
        first_level = None
        for node in graph.nodes:
            level = getattr(node, 'abstraction_level', 2)
            distribution[level] = distribution.get(level, 0) + 1
            if first_level is None:
                first_level = level
            elif level != first_level:
                all_same = False
        return {"distribution": distribution, "all_same_level": all_same}

    def _check_assumptions(self, graph: KnowledgeGraph) -> Dict:
        derives_edges = [e for e in graph.edges if e.type == "derives_from"]
        with_assumptions = sum(1 for e in derives_edges if e.assumptions and len(e.assumptions) > 0 and e.assumptions != ["假设条件待补充"])
        empty_count = sum(1 for e in derives_edges if not e.assumptions or e.assumptions == ["假设条件待补充"])
        coverage = with_assumptions / len(derives_edges) if derives_edges else 1.0
        return {"coverage": coverage, "empty_count": empty_count}

    def _compute_graph_depth(self, graph: KnowledgeGraph) -> int:
        try:
            import networkx as nx
            G = nx.DiGraph()
            for node in graph.nodes:
                G.add_node(node.id)
            for edge in graph.edges:
                G.add_edge(edge.from_, edge.to)
            if G.number_of_nodes() == 0:
                return 0
            try:
                path = nx.dag_longest_path(G)
                return len(path) - 1
            except nx.NetworkXUnfeasible:
                try:
                    sccs = list(nx.strongly_connected_components(G))
                    for scc in sccs:
                        if len(scc) > 1:
                            edges_to_remove = [(u, v) for u, v in G.edges() if u in scc and v in scc]
                            G.remove_edges_from(edges_to_remove)
                            break
                    path = nx.dag_longest_path(G)
                    return len(path) - 1
                except Exception:
                    try:
                        return nx.diameter(G.to_undirected())
                    except Exception:
                        return 0
            except nx.NetworkXError:
                return 0
        except ImportError:
            return 0

    def _check_connectivity(self, graph: KnowledgeGraph) -> Dict:
        try:
            import networkx as nx
            G = nx.DiGraph()
            for node in graph.nodes:
                G.add_node(node.id)
            for edge in graph.edges:
                G.add_edge(edge.from_, edge.to)
            isolated = sum(1 for n in G.nodes() if G.degree(n) == 0)
            if G.number_of_nodes() == 0:
                return {"connected": False, "isolated_count": 0}
            largest_cc = max(nx.weakly_connected_components(G), key=len)
            connected = len(largest_cc) / G.number_of_nodes() >= 0.8
            return {"connected": connected, "isolated_count": isolated}
        except ImportError:
            return {"connected": True, "isolated_count": 0}


def run_single_test(spec: TopicSpec) -> Dict:
    print(f"\n{'='*80}")
    print(f"【严格测试】{spec.name}")
    print(f"要求: 节点≥{spec.min_nodes}, 边≥{spec.min_edges}, 深度≥{spec.min_depth}")
    print(f"{'='*80}")

    try:
        orchestrator = GraphBuildOrchestrator(artifacts_dir="artifacts/latest")
        result = orchestrator.build_topic(
            spec.name, down=5, up=3, max_nodes=80
        )

        if not result.graph:
            return {"topic": spec.name, "passed": False, "errors": ["图谱构建失败"]}

        validator = StrictContentValidator()
        validation = validator.validate_graph(result.graph, spec)

        # 打印结果
        checks = validation["checks"]
        print(f"\n  节点数: {checks.get('node_count', 0)}")
        print(f"  边数: {checks.get('edge_count', 0)}")
        print(f"  图深度: {checks.get('max_depth', 0)}")
        print(f"  内容相关性: {checks.get('content_relevance', 0):.1%}")
        print(f"  公式覆盖率: {checks.get('formula_coverage', 0):.1%}")
        print(f"  假设覆盖率: {checks.get('assumption_coverage', 0):.1%}")
        print(f"  层级分布: {checks.get('level_distribution', {})}")
        print(f"  孤立节点: {checks.get('isolated_nodes', 0)}")
        print(f"  连通性: {'✅' if checks.get('connected') else '❌'}")
        print(f"  边方向: {'✅' if checks.get('edge_direction_valid') else '⚠️'}")

        if validation["errors"]:
            print(f"\n  ❌ 错误:")
            for e in validation["errors"][:5]:
                print(f"    - {e}")

        if validation["warnings"]:
            print(f"\n  ⚠️ 警告:")
            for w in validation["warnings"][:3]:
                print(f"    - {w}")

        status = "✅ 通过" if validation["passed"] else "❌ 失败"
        print(f"\n  【{spec.name}】{status}")

        return validation

    except Exception as e:
        print(f"\n  💥 异常: {e}")
        import traceback
        traceback.print_exc()
        return {"topic": spec.name, "passed": False, "errors": [str(e)]}


def main():
    all_results = []
    passed_count = 0
    failed_topics = []

    for spec in TOPIC_SPECS:
        result = run_single_test(spec)
        all_results.append(result)
        if result.get("passed"):
            passed_count += 1
        else:
            failed_topics.append(spec.name)

    print(f"\n\n{'='*80}")
    print(f"📋 严格测试汇总")
    print(f"{'='*80}")
    print(f"通过: {passed_count}/{len(TOPIC_SPECS)}")

    if failed_topics:
        print(f"\n❌ 未通过的主题:")
        for t in failed_topics:
            print(f"  - {t}")
    else:
        print(f"\n🎉 所有严格测试通过！")

    with open(project_root / "strict_content_report.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    return len(failed_topics) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
