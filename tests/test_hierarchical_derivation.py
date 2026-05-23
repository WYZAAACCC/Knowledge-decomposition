"""
综合测试：层级推导正确性、递归归并、智能模型选择

测试覆盖:
1. 基础层级计算 — 线性推导链
2. 归并(Merge)推导 — 多源汇聚
3. 递归层级 — 深层嵌套推导
4. 环检测与修复
5. 方向约束验证 (derives_from: from.level > to.level)
6. 孤立组件桥接
7. 边界情况 (空图、单节点、全孤立)
8. 智能模型选择逻辑
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")

from src.models import Node, Edge, KnowledgeGraph, NodeType, EdgeType, Domain, TheoryContext, GraphStats, ValidationSummary
from src.agents.decomposer_agent import DecomposerAgent
from src.deepseek_client import TaskComplexity, DeepSeekClient

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

errors = []
total_tests = 0
passed_tests = 0


def test(name, condition, detail=""):
    global total_tests, passed_tests
    total_tests += 1
    if condition:
        passed_tests += 1
        print(f"  {PASS} {name}")
    else:
        msg = f"  {FAIL} {name}"
        if detail:
            msg += f" | {detail}"
        print(msg)
        errors.append(f"{name}: {detail}")


def make_node(nid, ntype=NodeType.CONCEPT, title="", level=2, domain=Domain.MECHANICS):
    """Helper: create a Node for testing."""
    return Node(
        id=nid, type=ntype, title=title or nid,
        statement=title or nid, formula_latex="N/A",
        domain=domain, abstraction_level=level,
        pedagogical_level=max(1, level),
        theory_context=TheoryContext.CLASSICAL, sources=["test"]
    )


def make_edge(eid, etype, from_id, to_id, assumptions=None, steps=None):
    """Helper: create an Edge for testing."""
    return Edge(
        id=eid, type=EdgeType(etype), from_=from_id, to=to_id,
        assumptions=assumptions or ["test assumption"],
        derivation_steps=steps or ["step 1", "step 2"],
        math_used=[], path_id="path.test.default"
    )


# ============================================================
# 测试1: 基础线性推导链 — 层级计算
# ============================================================
print("\n" + "=" * 70)
print("测试1: 基础线性推导链层级计算")
print("=" * 70)

def test_linear_chain():
    # A → B → C → D (derives_from: D from C, C from B, B from A)
    # 所以 A 是基础(level 0), B 是 level 1, C 是 level 2, D 是 level 3
    nodes = [
        make_node("concept.a", NodeType.CONCEPT, "A", 0),
        make_node("concept.b", NodeType.CONCEPT, "B", 0),
        make_node("concept.c", NodeType.CONCEPT, "C", 0),
        make_node("equation.target", NodeType.EQUATION, "Target", 0),
    ]
    edges = [
        make_edge("edge.b.derives_from.a", "derives_from", "concept.b", "concept.a"),
        make_edge("edge.c.derives_from.b", "derives_from", "concept.c", "concept.b"),
        make_edge("edge.target.derives_from.c", "derives_from", "equation.target", "concept.c"),
    ]

    DecomposerAgent._apply_level_constraints("equation.target", nodes, edges)

    node_map = {n.id: n for n in nodes}
    test("A 是基础层 (level 0)", node_map["concept.a"].abstraction_level == 0,
         f"实际: {node_map['concept.a'].abstraction_level}")
    test("B 是 A 的推导 (B > A)", node_map["concept.b"].abstraction_level > node_map["concept.a"].abstraction_level,
         f"B={node_map['concept.b'].abstraction_level}, A={node_map['concept.a'].abstraction_level}")
    test("C 是 B 的推导 (C > B)", node_map["concept.c"].abstraction_level > node_map["concept.b"].abstraction_level,
         f"C={node_map['concept.c'].abstraction_level}, B={node_map['concept.b'].abstraction_level}")
    test("Target 是最顶层", node_map["equation.target"].abstraction_level >= node_map["concept.c"].abstraction_level,
         f"Target={node_map['equation.target'].abstraction_level}, C={node_map['concept.c'].abstraction_level}")
    test("层级严格单调递增", (
        node_map["concept.a"].abstraction_level <
        node_map["concept.b"].abstraction_level <
        node_map["concept.c"].abstraction_level <
        node_map["equation.target"].abstraction_level
    ))
    test("所有 derives_from 方向正确 (from.level > to.level)", all(
        node_map[e.from_].abstraction_level > node_map[e.to].abstraction_level
        for e in edges if str(e.type.value) == "derives_from"
    ))

test_linear_chain()


# ============================================================
# 测试2: 归并(Merge)推导 — 多源汇聚到同一节点
# ============================================================
print("\n" + "=" * 70)
print("测试2: 归并(Merge)推导 — 多源汇聚")
print("=" * 70)

def test_merge_derivation():
    # A(level 0), B(level 0) 都推导出 C
    # C = max(level(A), level(B)) + 1 = 1
    # C 推导出 D: D = level(C) + 1 = 2
    nodes = [
        make_node("concept.a", NodeType.CONCEPT, "基础A", 0),
        make_node("concept.b", NodeType.CONCEPT, "基础B", 0),
        make_node("equation.c", NodeType.EQUATION, "汇聚C", 0),
        make_node("equation.target", NodeType.EQUATION, "目标D", 0),
    ]
    edges = [
        make_edge("edge.c.derives_from.a", "derives_from", "equation.c", "concept.a"),
        make_edge("edge.c.derives_from.b", "derives_from", "equation.c", "concept.b"),
        make_edge("edge.target.derives_from.c", "derives_from", "equation.target", "equation.c"),
    ]

    DecomposerAgent._apply_level_constraints("equation.target", nodes, edges)

    node_map = {n.id: n for n in nodes}
    test("A 和 B 都是基础层 (同层级)", node_map["concept.a"].abstraction_level == node_map["concept.b"].abstraction_level,
         f"A={node_map['concept.a'].abstraction_level}, B={node_map['concept.b'].abstraction_level}")
    test("C 的层级 > A 的层级 (归并后正确)", node_map["equation.c"].abstraction_level > node_map["concept.a"].abstraction_level,
         f"C={node_map['equation.c'].abstraction_level}, A={node_map['concept.a'].abstraction_level}")
    test("C 的层级 > B 的层级", node_map["equation.c"].abstraction_level > node_map["concept.b"].abstraction_level,
         f"C={node_map['equation.c'].abstraction_level}, B={node_map['concept.b'].abstraction_level}")
    test("Target (D) > C", node_map["equation.target"].abstraction_level > node_map["equation.c"].abstraction_level)

test_merge_derivation()


# ============================================================
# 测试3: 深层递归推导 (5+ 层)
# ============================================================
print("\n" + "=" * 70)
print("测试3: 深层递归推导")
print("=" * 70)

def test_deep_recursion():
    # 构建一条 8 层的链
    nodes = []
    edges = []
    for i in range(8):
        nodes.append(make_node(f"concept.l{i}", NodeType.CONCEPT, f"层级{i}", 0))
    for i in range(7):
        edges.append(make_edge(
            f"edge.l{i+1}.derives_from.l{i}", "derives_from",
            f"concept.l{i+1}", f"concept.l{i}"
        ))

    DecomposerAgent._apply_level_constraints("concept.l7", nodes, edges)

    node_map = {n.id: n for n in nodes}
    for i in range(8):
        test(f"层级{i} 的 abstraction_level >= {i}",
             node_map[f"concept.l{i}"].abstraction_level >= i,
             f"实际: {node_map[f'concept.l{i}'].abstraction_level}")

    # 验证严格递增或至少非递减
    levels = [node_map[f"concept.l{i}"].abstraction_level for i in range(8)]
    test("层级非递减", all(levels[i] <= levels[i+1] for i in range(7)),
         f"层级序列: {levels}")

test_deep_recursion()


# ============================================================
# 测试4: 复杂归并 — 菱形依赖 (Diamond Dependency)
# ============================================================
print("\n" + "=" * 70)
print("测试4: 菱形依赖归并")
print("=" * 70)

def test_diamond_dependency():
    #   A(基础)
    #  / \
    # B   C  (中间层)
    #  \ /
    #   D     (汇聚, 应该取最长路径)
    #   |
    #   E     (目标)
    nodes = [
        make_node("concept.a", NodeType.CONCEPT, "A根", 0),
        make_node("concept.b", NodeType.CONCEPT, "B左", 0),
        make_node("concept.c", NodeType.CONCEPT, "C右", 0),
        make_node("equation.d", NodeType.EQUATION, "D汇", 0),
        make_node("equation.target", NodeType.EQUATION, "E目标", 0),
    ]
    edges = [
        make_edge("edge.b.derives_from.a", "derives_from", "concept.b", "concept.a"),
        make_edge("edge.c.derives_from.a", "derives_from", "concept.c", "concept.a"),
        make_edge("edge.d.derives_from.b", "derives_from", "equation.d", "concept.b"),
        make_edge("edge.d.derives_from.c", "derives_from", "equation.d", "concept.c"),
        make_edge("edge.target.derives_from.d", "derives_from", "equation.target", "equation.d"),
    ]

    DecomposerAgent._apply_level_constraints("equation.target", nodes, edges)

    node_map = {n.id: n for n in nodes}
    la = node_map["concept.a"].abstraction_level
    lb = node_map["concept.b"].abstraction_level
    lc = node_map["concept.c"].abstraction_level
    ld = node_map["equation.d"].abstraction_level
    le = node_map["equation.target"].abstraction_level

    test("A 是最底层", la == 0, f"实际: {la}")
    test("B 和 C 同层级 (都直接从 A 推导)", lb == lc, f"B={lb}, C={lc}")
    test("B > A", lb > la)
    test("D > B", ld > lb, f"D={ld}, B={lb}")
    test("D > C", ld > lc, f"D={ld}, C={lc}")
    test("D = max(B,C) + 1 (归并层级正确)", ld == max(lb, lc) + 1,
         f"D={ld}, max(B,C)+1={max(lb, lc)+1}")
    test("E (Target) 是最高层", le >= ld, f"E={le}, D={ld}")

test_diamond_dependency()


# ============================================================
# 测试5: 环检测与修复
# ============================================================
print("\n" + "=" * 70)
print("测试5: 环检测与修复")
print("=" * 70)

def test_cycle_detection():
    # A → B → C → A (环)
    nodes = [
        make_node("concept.a", NodeType.CONCEPT, "A", 0),
        make_node("concept.b", NodeType.CONCEPT, "B", 0),
        make_node("concept.c", NodeType.CONCEPT, "C", 0),
    ]
    edges = [
        make_edge("edge.b.derives_from.a", "derives_from", "concept.b", "concept.a"),
        make_edge("edge.c.derives_from.b", "derives_from", "concept.c", "concept.b"),
        make_edge("edge.a.derives_from.c", "derives_from", "concept.a", "concept.c"),  # 回环!
    ]

    DecomposerAgent._apply_level_constraints("concept.a", nodes, edges)

    # 环应该被打破 — 至少有一条边被移除
    import networkx as nx
    G = nx.DiGraph()
    for node in nodes:
        G.add_node(node.id)
    for edge in edges:
        G.add_edge(edge.from_, edge.to)

    is_dag = nx.is_directed_acyclic_graph(G)
    test("环已被打破 — 图变为 DAG", is_dag,
         f"剩余边数: {len(edges)}")

test_cycle_detection()


# ============================================================
# 测试6: 方向约束验证 (derives_from: from.level > to.level)
# ============================================================
print("\n" + "=" * 70)
print("测试6: derives_from 方向约束")
print("=" * 70)

def test_direction_constraint():
    # 故意创建违反方向约束的层级
    nodes = [
        make_node("concept.base", NodeType.CONCEPT, "基础", 5),   # 高层级(错误!)
        make_node("concept.derived", NodeType.CONCEPT, "推导", 1),  # 低层级(错误!)
        make_node("equation.target", NodeType.EQUATION, "目标", 3),
    ]
    edges = [
        make_edge("edge.derived.derives_from.base", "derives_from",
                  "concept.derived", "concept.base"),  # 方向: derived.from = base
        make_edge("edge.target.derives_from.derived", "derives_from",
                  "equation.target", "concept.derived"),
    ]

    DecomposerAgent._apply_level_constraints("equation.target", nodes, edges)

    node_map = {n.id: n for n in nodes}

    # 修复后: derived.level 应该 > base.level
    ld = node_map["concept.derived"].abstraction_level
    lb = node_map["concept.base"].abstraction_level

    test("推导节点层级 > 基础节点层级 (已自动修复)",
         ld > lb, f"derived={ld}, base={lb}")

    # 验证所有剩余的 derives_from 边都满足方向约束
    all_valid = True
    for edge in edges:
        etype = str(edge.type.value) if hasattr(edge.type, 'value') else str(edge.type)
        if etype == "derives_from":
            fn = node_map.get(edge.from_)
            tn = node_map.get(edge.to)
            if fn and tn and fn.abstraction_level <= tn.abstraction_level:
                all_valid = False
                break
    test("所有 derives_from 边方向正确", all_valid)

test_direction_constraint()


# ============================================================
# 测试7: 边界情况
# ============================================================
print("\n" + "=" * 70)
print("测试7: 边界情况")
print("=" * 70)

def test_edge_cases():
    # 空节点
    nodes_empty = []
    edges_empty = []
    DecomposerAgent._apply_level_constraints("no.target", nodes_empty, edges_empty)
    test("空节点列表不崩溃", len(nodes_empty) == 0)

    # 单节点
    nodes_single = [make_node("concept.solo", NodeType.CONCEPT, "Solo", 5)]
    DecomposerAgent._apply_level_constraints("concept.solo", nodes_single, [])
    test("单节点不崩溃", nodes_single[0].id == "concept.solo")

    # 无边节点 (全孤立)
    nodes_iso = [
        make_node("concept.a", NodeType.CONCEPT, "A", 0),
        make_node("concept.b", NodeType.CONCEPT, "B", 0),
        make_node("equation.target", NodeType.EQUATION, "T", 0),
    ]
    DecomposerAgent._apply_level_constraints("equation.target", nodes_iso, [])
    test("无边节点不崩溃", len(nodes_iso) >= 1)

    # 目标节点不在节点列表中
    nodes_no_target = [
        make_node("concept.x", NodeType.CONCEPT, "X", 2),
        make_node("concept.y", NodeType.CONCEPT, "Y", 3),
    ]
    edges_nt = [
        make_edge("edge.y.derives_from.x", "derives_from", "concept.y", "concept.x"),
    ]
    DecomposerAgent._apply_level_constraints("concept.missing", nodes_no_target, edges_nt)
    test("缺失目标节点不崩溃", len(nodes_no_target) == 2)

test_edge_cases()


# ============================================================
# 测试8: 混合边类型
# ============================================================
print("\n" + "=" * 70)
print("测试8: 混合边类型 (derives_from + requires + uses_math)")
print("=" * 70)

def test_mixed_edge_types():
    nodes = [
        make_node("concept.math", NodeType.MATH_TOOL, "微积分", 0),
        make_node("concept.base", NodeType.CONCEPT, "基础物理", 0),
        make_node("equation.mid", NodeType.EQUATION, "中间方程", 0),
        make_node("equation.target", NodeType.EQUATION, "最终目标", 0),
    ]
    edges = [
        make_edge("edge.mid.derives_from.base", "derives_from", "equation.mid", "concept.base"),
        make_edge("edge.mid.uses_math.math", "uses_math", "equation.mid", "concept.math"),
        make_edge("edge.target.derives_from.mid", "derives_from", "equation.target", "equation.mid"),
    ]

    DecomposerAgent._apply_level_constraints("equation.target", nodes, edges)

    node_map = {n.id: n for n in nodes}

    # derives_from 层级应该正确
    test("mid > base (使用 derives_from)", node_map["equation.mid"].abstraction_level > node_map["concept.base"].abstraction_level)
    test("target > mid", node_map["equation.target"].abstraction_level > node_map["equation.mid"].abstraction_level)

    # math_tool 节点不应该被删除
    math_node = node_map.get("concept.math")
    test("math_tool 节点存在", math_node is not None)

test_mixed_edge_types()


# ============================================================
# 测试9: 智能模型选择
# ============================================================
print("\n" + "=" * 70)
print("测试9: 智能模型选择 (性价比原则)")
print("=" * 70)

def test_model_selection():
    client = DeepSeekClient.from_env()

    # 简单路由任务 → Flash
    c = client.estimate_complexity(task_type="routing", max_nodes=10)
    test("路由任务 → SIMPLE", c == TaskComplexity.SIMPLE, f"实际: {c.value}")
    test("路由任务 → 选择 Flash", client.select_model(c) == client.cfg.model_flash)

    # 小规模组装 → MODERATE = Flash
    c = client.estimate_complexity(task_type="assembly", max_nodes=25)
    test("小规模组装(25节点) → MODERATE", c == TaskComplexity.MODERATE, f"实际: {c.value}")
    test("MODERATE复杂度 → 选择 Flash (性价比)", client.select_model(c) == client.cfg.model_flash)

    # 大规模组装 → COMPLEX = Pro
    c = client.estimate_complexity(task_type="assembly", max_nodes=80, requires_derivation=True)
    test("大规模组装(80节点+推导) → COMPLEX 或更高",
         c in (TaskComplexity.COMPLEX, TaskComplexity.VERY_COMPLEX),
         f"实际: {c.value}")
    test("COMPLEX复杂度 → 选择 Pro", client.select_model(c) == client.cfg.model_pro)

    # 扩展阶段3 → COMPLEX
    c = client.estimate_complexity(task_type="expansion", max_nodes=60, expansion_stage=3, requires_derivation=True)
    test("第3阶段扩展 → COMPLEX 或更高",
         c in (TaskComplexity.COMPLEX, TaskComplexity.VERY_COMPLEX),
         f"实际: {c.value}")
    test("COMPLEX阶段 → 选择 Pro", client.select_model(c) == client.cfg.model_pro)

    # 回退模式 → 总是 SIMPLE
    c = client.estimate_complexity(task_type="expansion", max_nodes=100, is_fallback=True)
    test("回退模式(即使100节点) → SIMPLE/MODERATE (节省成本)",
         c in (TaskComplexity.SIMPLE, TaskComplexity.MODERATE),
         f"实际: {c.value}")

    # 分类任务 → SIMPLE
    c = client.estimate_complexity(task_type="classification")
    test("分类任务 → SIMPLE", c == TaskComplexity.SIMPLE, f"实际: {c.value}")

test_model_selection()


# ============================================================
# 测试10: 实际物理知识图谱层级验证 (伯努利方程简化版)
# ============================================================
print("\n" + "=" * 70)
print("测试10: 物理知识图谱层级验证 (伯努利方程)")
print("=" * 70)

def test_physics_graph():
    nodes = [
        make_node("law.newton_second", NodeType.LAW, "Newton's Second Law", 0, Domain.MECHANICS),
        make_node("concept.force", NodeType.CONCEPT, "Force", 0, Domain.MECHANICS),
        make_node("concept.work", NodeType.CONCEPT, "Work", 0, Domain.MECHANICS),
        make_node("concept.kinetic_energy", NodeType.CONCEPT, "Kinetic Energy", 0, Domain.MECHANICS),
        make_node("concept.potential_energy", NodeType.CONCEPT, "Potential Energy", 0, Domain.MECHANICS),
        make_node("concept.conservation_energy", NodeType.CONCEPT, "Conservation of Energy", 0, Domain.MECHANICS),
        make_node("assumption.incompressible", NodeType.ASSUMPTION, "Incompressible Flow", 0, Domain.MECHANICS),
        make_node("assumption.steady_flow", NodeType.ASSUMPTION, "Steady Flow", 0, Domain.MECHANICS),
        make_node("concept.fluid_element", NodeType.CONCEPT, "Fluid Element", 0, Domain.MECHANICS),
        make_node("eq.energy_conservation_fluid", NodeType.EQUATION, "Energy Conservation in Fluid", 0, Domain.MECHANICS),
        make_node("equation.bernoulli", NodeType.EQUATION, "Bernoulli Equation", 0, Domain.MECHANICS),
    ]
    edges = [
        make_edge("edge.work.derives_from.force", "derives_from", "concept.work", "concept.force"),
        make_edge("edge.kinetic.derives_from.newton", "derives_from", "concept.kinetic_energy", "law.newton_second"),
        make_edge("edge.conservation.derives_from.work", "derives_from", "concept.conservation_energy", "concept.work"),
        make_edge("edge.conservation.derives_from.kinetic", "derives_from", "concept.conservation_energy", "concept.kinetic_energy"),
        make_edge("edge.conservation.derives_from.potential", "derives_from", "concept.conservation_energy", "concept.potential_energy"),
        make_edge("edge.fluid_energy.derives_from.conservation", "derives_from", "eq.energy_conservation_fluid", "concept.conservation_energy"),
        make_edge("edge.fluid_energy.derives_from.fluid", "derives_from", "eq.energy_conservation_fluid", "concept.fluid_element"),
        make_edge("edge.bernoulli.derives_from.fluid_energy", "derives_from", "equation.bernoulli", "eq.energy_conservation_fluid"),
        make_edge("edge.bernoulli.assumes.incompressible", "assumes", "equation.bernoulli", "assumption.incompressible"),
        make_edge("edge.bernoulli.assumes.steady", "assumes", "equation.bernoulli", "assumption.steady_flow"),
    ]

    DecomposerAgent._apply_level_constraints("equation.bernoulli", nodes, edges)

    node_map = {n.id: n for n in nodes}

    # 牛顿定律应该是基础层
    test("牛顿第二定律在最底层附近",
         node_map["law.newton_second"].abstraction_level <= 2,
         f"实际: {node_map['law.newton_second'].abstraction_level}")

    # 能量守恒中间层
    l_conservation = node_map["concept.conservation_energy"].abstraction_level
    test("能量守恒在牛顿定律之上",
         l_conservation > node_map["law.newton_second"].abstraction_level,
         f"守恒={l_conservation}, 牛顿={node_map['law.newton_second'].abstraction_level}")

    # 伯努利方程应该是顶层
    l_bernoulli = node_map["equation.bernoulli"].abstraction_level
    test("伯努利方程在最顶层",
         l_bernoulli >= l_conservation,
         f"伯努利={l_bernoulli}, 守恒={l_conservation}")

    # 假设节点应该有合理层级
    l_incomp = node_map["assumption.incompressible"].abstraction_level
    test("假设节点层级合理 (≤ 目标)",
         l_incomp <= l_bernoulli,
         f"假设={l_incomp}, 伯努利={l_bernoulli}")

    # 验证所有 derives_from 边方向
    all_valid = True
    for edge in edges:
        etype = str(edge.type.value) if hasattr(edge.type, 'value') else str(edge.type)
        if etype == "derives_from":
            fn = node_map.get(edge.from_)
            tn = node_map.get(edge.to)
            if fn and tn and fn.abstraction_level <= tn.abstraction_level:
                all_valid = False
                print(f"  方向错误: {edge.from_} (level={fn.abstraction_level}) → {edge.to} (level={tn.abstraction_level})")
    test("物理图谱所有 derives_from 方向正确", all_valid)

    # 验证推导链完整性: 牛顿→动能→守恒→流体能量→伯努利
    test("牛顿→动能→守恒→流体能量→伯努利 层级递增",
         (node_map["law.newton_second"].abstraction_level <
          node_map["concept.kinetic_energy"].abstraction_level <
          node_map["concept.conservation_energy"].abstraction_level <
          node_map["eq.energy_conservation_fluid"].abstraction_level <
          node_map["equation.bernoulli"].abstraction_level),
         f"实际层级: 牛顿={node_map['law.newton_second'].abstraction_level}, "
         f"动能={node_map['concept.kinetic_energy'].abstraction_level}, "
         f"守恒={node_map['concept.conservation_energy'].abstraction_level}, "
         f"流体能量={node_map['eq.energy_conservation_fluid'].abstraction_level}, "
         f"伯努利={node_map['equation.bernoulli'].abstraction_level}")

test_physics_graph()


# ============================================================
# 测试汇总
# ============================================================
print("\n" + "=" * 70)
print("测试汇总")
print("=" * 70)
print(f"  总测试数: {total_tests}")
print(f"  通过: {passed_tests}")
print(f"  失败: {len(errors)}")
print(f"  通过率: {100 * passed_tests / total_tests:.1f}%" if total_tests > 0 else "N/A")

if errors:
    print(f"\n失败项:")
    for e in errors:
        print(f"  - {e}")

print()
if passed_tests == total_tests:
    print("\033[92m所有测试通过!\033[0m")
else:
    print(f"\033[91m{len(errors)} 项测试失败\033[0m")
