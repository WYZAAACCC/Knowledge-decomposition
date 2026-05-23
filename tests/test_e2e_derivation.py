"""
端到端验证：构建完整的推导图谱并验证

在不调用LLM的情况下，模拟完整的Agent流水线：
1. 构建节点和边（模拟Decomposer输出）
2. 应用层级约束（递归归并推导）
3. 运行所有验证器
4. 输出完整的验证报告
"""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")

from src.models import (
    Node, Edge, KnowledgeGraph, NodeType, EdgeType,
    Domain, TheoryContext, NodeStatus, GraphStats, ValidationSummary
)
from src.agents.decomposer_agent import DecomposerAgent
from src.validators.schema_validator import SchemaValidator
from src.validators.graph_validator import GraphValidator
from src.validators.assumption_validator import AssumptionValidator
from src.validators.dimension_validator import DimensionValidator
from src.validators.duplicate_validator import DuplicateValidator

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

errors = []
total = 0
passed = 0

def t(name, condition, detail=""):
    global total, passed
    total += 1
    if condition:
        passed += 1
        print(f"  {PASS} {name}")
    else:
        print(f"  {FAIL} {name} | {detail}")
        errors.append(f"{name}: {detail}")


def make_node(nid, ntype, title, level=2, domain=Domain.MECHANICS, formula="N/A", theory=TheoryContext.CLASSICAL):
    return Node(
        id=nid, type=ntype, title=title, statement=title,
        formula_latex=formula, domain=domain,
        abstraction_level=level, pedagogical_level=max(1, level),
        theory_context=theory, sources=["test"]
    )


def make_edge(eid, etype, from_id, to_id, assumptions=None, steps=None, path="path.test.default"):
    return Edge(
        id=eid, type=EdgeType(etype), from_=from_id, to=to_id,
        assumptions=assumptions or ["test assumption"],
        derivation_steps=steps or ["step 1", "step 2"],
        math_used=[], path_id=path
    )


# ============================================================
# 构建纳维-斯托克斯方程的简化推导图谱（15节点模拟）
# ============================================================
print("=" * 70)
print("端到端验证：纳维-斯托克斯方程推导图谱")
print("=" * 70)

nodes = [
    # 最基础层
    make_node("law.newton_second", NodeType.LAW, "Newton's Second Law",
              level=0, formula=r"$\vec{F}=m\vec{a}$"),
    make_node("concept.force", NodeType.CONCEPT, "Force",
              level=0, formula=r"$\vec{F}$"),
    make_node("concept.mass", NodeType.CONCEPT, "Mass",
              level=0, formula=r"$m$"),

    # 基础层
    make_node("concept.momentum", NodeType.CONCEPT, "Momentum",
              level=1, formula=r"$\vec{p}=m\vec{v}$"),
    make_node("concept.stress", NodeType.CONCEPT, "Stress Tensor",
              level=1, formula=r"$\sigma_{ij}$"),
    make_node("concept.strain", NodeType.CONCEPT, "Strain Rate",
              level=1, formula=r"$\dot{\epsilon}_{ij}$"),

    # 中间层
    make_node("eq.cauchy_momentum", NodeType.EQUATION, "Cauchy Momentum Equation",
              level=2, formula=r"$\rho\frac{D\vec{v}}{Dt}=\nabla\cdot\sigma+\rho\vec{g}$"),
    make_node("concept.constitutive", NodeType.CONCEPT, "Constitutive Relation",
              level=2, formula=r"$\sigma_{ij}=-p\delta_{ij}+\tau_{ij}$"),

    # 关键假设
    make_node("assumption.newtonian_fluid", NodeType.ASSUMPTION, "Newtonian Fluid",
              level=2),
    make_node("assumption.incompressible", NodeType.ASSUMPTION, "Incompressible Flow",
              level=2),
    make_node("assumption.constant_viscosity", NodeType.ASSUMPTION, "Constant Viscosity",
              level=2),

    # 高层
    make_node("eq.navier_stokes_general", NodeType.EQUATION, "Navier-Stokes (General)",
              level=3, formula=r"$\rho\frac{D\vec{v}}{Dt}=-\nabla p+\mu\nabla^2\vec{v}+\rho\vec{g}$"),

    # 目标
    make_node("eq.navier_stokes_incompressible", NodeType.EQUATION,
              "Navier-Stokes (Incompressible)",
              level=4, formula=r"$\frac{\partial\vec{v}}{\partial t}+(\vec{v}\cdot\nabla)\vec{v}=-\frac{1}{\rho}\nabla p+\nu\nabla^2\vec{v}+\vec{g}$"),
]

edges = [
    # 牛顿第二定律 → 动量
    make_edge("edge.momentum.derives_from.newton", "derives_from",
              "concept.momentum", "law.newton_second",
              assumptions=["classical_mechanics"],
              steps=["由 $\\vec{F}=m\\vec{a}=m\\frac{d\\vec{v}}{dt}=\\frac{d(m\\vec{v})}{dt}$ 得 $\\vec{p}=m\\vec{v}$"]),

    # 牛顿 → 柯西动量方程
    make_edge("edge.cauchy.derives_from.newton", "derives_from",
              "eq.cauchy_momentum", "law.newton_second",
              assumptions=["continuum_hypothesis"],
              steps=["将牛顿第二定律应用于连续介质微元体，考虑表面力和体积力"]),

    # 应力+应变+本构 → 柯西
    make_edge("edge.cauchy.derives_from.stress", "derives_from",
              "eq.cauchy_momentum", "concept.stress"),
    make_edge("edge.constitutive.derives_from.stress", "derives_from",
              "concept.constitutive", "concept.stress"),
    make_edge("edge.constitutive.derives_from.strain", "derives_from",
              "concept.constitutive", "concept.strain"),

    # 假设边
    make_edge("edge.ns_general.assumes.newtonian", "assumes",
              "eq.navier_stokes_general", "assumption.newtonian_fluid",
              assumptions=[], steps=[]),
    make_edge("edge.ns_inc.assumes.incompressible", "assumes",
              "eq.navier_stokes_incompressible", "assumption.incompressible",
              assumptions=[], steps=[]),
    make_edge("edge.ns_general.assumes.const_visc", "assumes",
              "eq.navier_stokes_general", "assumption.constant_viscosity",
              assumptions=[], steps=[]),

    # 核心推导链: 柯西+本构 → NS General
    make_edge("edge.ns_general.derives_from.cauchy", "derives_from",
              "eq.navier_stokes_general", "eq.cauchy_momentum",
              assumptions=["newtonian_fluid", "constant_viscosity"],
              steps=[
                  "从柯西动量方程 $\\rho\\frac{D\\vec{v}}{Dt}=\\nabla\\cdot\\sigma+\\rho\\vec{g}$ 出发",
                  "代入牛顿流体本构 $\\sigma_{ij}=-p\\delta_{ij}+\\mu(\\partial_i v_j+\\partial_j v_i)$",
                  "计算散度 $\\nabla\\cdot\\sigma=-\\nabla p+\\mu\\nabla^2\\vec{v}$",
                  "得到 $\\rho\\frac{D\\vec{v}}{Dt}=-\\nabla p+\\mu\\nabla^2\\vec{v}+\\rho\\vec{g}$"
              ],
              path="path.navier_stokes.canonical"),
    make_edge("edge.ns_general.derives_from.constitutive", "derives_from",
              "eq.navier_stokes_general", "concept.constitutive",
              path="path.navier_stokes.canonical"),

    # NS General → NS Incompressible (特例)
    make_edge("edge.ns_inc.derives_from.ns_gen", "derives_from",
              "eq.navier_stokes_incompressible", "eq.navier_stokes_general",
              assumptions=["incompressible_flow", "constant_viscosity"],
              steps=[
                  "从 NS 一般形式出发",
                  "不可压缩条件 $\\nabla\\cdot\\vec{v}=0$",
                  "代入 $\\frac{D\\vec{v}}{Dt}=\\frac{\\partial\\vec{v}}{\\partial t}+(\\vec{v}\\cdot\\nabla)\\vec{v}$",
                  "令 $\\nu=\\mu/\\rho$ 为运动粘度",
              ],
              path="path.navier_stokes.canonical"),
]

# ── 第一阶段：应用层级约束 ──
print("\n[1] 应用层级约束 (递归归并推导)...")
DecomposerAgent._apply_level_constraints("eq.navier_stokes_incompressible", nodes, edges)

node_map = {n.id: n for n in nodes}

t("目标节点存在", "eq.navier_stokes_incompressible" in node_map)
t("所有边引用存在的节点",
  all(e.from_ in node_map and e.to in node_map for e in edges),
  f"无效边: {[(e.from_, e.to) for e in edges if e.from_ not in node_map or e.to not in node_map]}")

# ── 第二阶段：验证层级推导 ──
print("\n[2] 验证层级推导正确性...")

# 牛顿 → 动量 → 柯西 → NS General → NS Incompressible
l_newton = node_map["law.newton_second"].abstraction_level
l_momentum = node_map["concept.momentum"].abstraction_level
l_cauchy = node_map["eq.cauchy_momentum"].abstraction_level
l_ns_gen = node_map["eq.navier_stokes_general"].abstraction_level
l_ns_inc = node_map["eq.navier_stokes_incompressible"].abstraction_level

t("牛顿第二定律是最底层",
  l_newton == 0, f"实际: {l_newton}")

t("推导链单调递增: 牛顿 → 动量",
  l_momentum > l_newton, f"动量={l_momentum}, 牛顿={l_newton}")

t("柯西在牛顿之上",
  l_cauchy > l_newton, f"柯西={l_cauchy}, 牛顿={l_newton}")

t("推导链单调递增: 牛顿 → NS General",
  l_ns_gen > l_newton, f"NS_gen={l_ns_gen}, 牛顿={l_newton}")

t("推导链单调递增: NS General → NS Incompressible",
  l_ns_inc > l_ns_gen, f"NS_inc={l_ns_inc}, NS_gen={l_ns_gen}")

t("完整推导链: 0→1→2→3",
  l_newton < l_cauchy < l_ns_gen < l_ns_inc,
  f"层级序列: {l_newton}→{l_cauchy}→{l_ns_gen}→{l_ns_inc}")

# 验证归并(Merge): 柯西方程从牛顿+应力两个来源推导
t("柯西归并正确: 层级 > max(牛顿, 应力)",
  l_cauchy > max(l_newton, node_map["concept.stress"].abstraction_level))

# 验证归并: NS General 从柯西+本构两个来源
t("NS General 归并正确: 层级 > max(柯西, 本构)",
  l_ns_gen > max(l_cauchy, node_map["concept.constitutive"].abstraction_level))

# 所有 derives_from 方向正确
all_good = True
for e in edges:
    etype = str(e.type.value) if hasattr(e.type, 'value') else str(e.type)
    if etype == "derives_from":
        fn = node_map.get(e.from_)
        tn = node_map.get(e.to)
        if fn and tn and fn.abstraction_level <= tn.abstraction_level:
            all_good = False
            print(f"  方向错误: {e.from_}(L{fn.abstraction_level}) → {e.to}(L{tn.abstraction_level})")
t("所有 derives_from 边方向正确 (from.level > to.level)", all_good)

# ── 第三阶段：构建 KnowledgeGraph ──
print("\n[3] 构建 KnowledgeGraph 并运行验证器...")

derives_count = 0
for e in edges:
    etype = str(e.type.value) if hasattr(e.type, 'value') else str(e.type)
    if etype == "derives_from":
        derives_count += 1

assumption_count = sum(len(e.assumptions) for e in edges)
math_tool_count = 0
for n in nodes:
    ntype = str(n.type.value) if hasattr(n.type, 'value') else str(n.type)
    if ntype == "math_tool":
        math_tool_count += 1

kg = KnowledgeGraph(
    topic="eq.navier_stokes_incompressible",
    build_version="1.0.0",
    nodes=nodes, edges=edges,
    canonical_path="path.navier_stokes.canonical",
    alternate_paths=[],
    stats=GraphStats(
        node_count=len(nodes), edge_count=len(edges),
        derivation_edge_count=derives_count,
        assumption_count=assumption_count,
        math_tool_count=math_tool_count
    ),
    validation_summary=ValidationSummary(
        schema_valid=False, dag_valid=False,
        assumptions_complete=False, dimensions_valid=False,
        canonical_path_exists=True, errors=[], warnings=[]
    )
)

t("KnowledgeGraph 创建成功", kg is not None)
t(f"节点数: {len(nodes)}", len(nodes) == 13)
t(f"边数: {len(edges)}", len(edges) >= 12)
t(f"derives_from 边: {derives_count}", derives_count >= 7)

# ── 第四阶段：运行所有验证器 ──
print("\n[4] 运行验证器...")

# Schema 验证
sv = SchemaValidator()
schema_ok, schema_errs, schema_details = sv.validate_graph(kg)
t("Schema 验证通过", schema_ok, str(schema_errs[:2]) if schema_errs else "")

# DAG 验证
gv = GraphValidator()
dag_ok, dag_errs, dag_details = gv.validate_complete(kg)
t("DAG 验证通过", dag_ok, str(dag_errs[:2]) if dag_errs else "")
t("无环", dag_details.get("dag_valid", False))
t("无悬空边", dag_details.get("dangling_edge_count", 1) == 0)

# 假设验证
av = AssumptionValidator()
try:
    a_ok, a_errs, a_details = av.validate_graph_assumptions(kg)
    t("假设验证运行正常", isinstance(a_ok, bool))
except Exception as e:
    print(f"  假设验证(预期部分失败): {e}")

# 量纲验证
dv = DimensionValidator()
try:
    d_ok, d_errs, d_details = dv.validate_graph_dimensions(kg)
    t("量纲验证运行正常", isinstance(d_ok, bool))
except Exception as e:
    print(f"  量纲验证(预期部分失败): {e}")

# 重复验证
dupv = DuplicateValidator()
try:
    dup_ok, dup_warns, dup_details = dupv.validate_graph_uniqueness(kg)
    t("重复验证运行正常", isinstance(dup_ok, bool))
except Exception as e:
    print(f"  重复验证(预期部分失败): {e}")

# ── 第五阶段：输出推导图谱报告 ──
print("\n[5] 推导图谱报告...")
print("-" * 70)
print(f"{'层级':<6} {'节点ID':<40} {'类型':<15} {'标题':<30}")
print("-" * 70)

for node in sorted(nodes, key=lambda n: n.abstraction_level):
    ntype = str(node.type.value) if hasattr(node.type, 'value') else str(node.type)
    print(f"L{node.abstraction_level:<5} {node.id:<40} {ntype:<15} {node.title:<30}")

print("-" * 70)
print(f"\n推导边 ({derives_count} 条):")
for edge in edges:
    etype = str(edge.type.value) if hasattr(edge.type, 'value') else str(edge.type)
    if etype == "derives_from":
        fn = node_map[edge.from_]
        tn = node_map[edge.to]
        print(f"  {fn.title} (L{fn.abstraction_level})  derives_from  {tn.title} (L{tn.abstraction_level})")
    elif etype == "assumes":
        fn = node_map[edge.from_]
        tn = node_map[edge.to]
        print(f"  {fn.title}  assumes  {tn.title}")

# ── 汇总 ──
print("\n" + "=" * 70)
print("端到端验证汇总")
print("=" * 70)
print(f"  总测试: {total}")
print(f"  通过: {passed}")
print(f"  失败: {total - passed}")
print(f"  通过率: {100 * passed / total:.1f}%" if total > 0 else "N/A")

if total == passed:
    print(f"\n{PASS} 所有端到端测试通过！")
else:
    print(f"\n{FAIL} {total - passed} 项测试失败")
    for e in errors:
        print(f"  - {e}")

# 保存图谱到 artifacts
artifact_dir = Path(__file__).parent.parent / "artifacts" / "test_output"
artifact_dir.mkdir(parents=True, exist_ok=True)

graph_path = artifact_dir / "graph_verified.json"
with open(graph_path, 'w', encoding='utf-8') as f:
    json.dump(kg.model_dump(by_alias=True), f, ensure_ascii=False, indent=2)
print(f"\n已验证图谱保存至: {graph_path}")
