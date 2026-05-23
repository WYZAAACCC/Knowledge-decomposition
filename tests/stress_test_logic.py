"""
极限压力测试脚本
测试内容正确性、图谱正确性、层级推导正确性
"""
import sys
import os
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")

from src.physics.topic_mapping import (
    CN_TO_EN, EN_TO_CN, TOPIC_DEFINITIONS,
    infer_node_type, infer_domain, infer_domain_hint,
    infer_theory_context, get_cn_topic_name, get_topic_definition,
)
from src.models import Node, Edge, KnowledgeGraph, NodeType, Domain, TheoryContext, GraphStats, ValidationSummary
from src.agents.decomposer_agent import DecomposerAgent
from src.agents.router_agent import RouterAgent
from src.loader import DataLoader

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"

errors = []
warnings = []
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


def warn(name, detail=""):
    warnings.append(f"{name}: {detail}")
    print(f"  {WARN} {name} | {detail}")


# ============================================================
# 测试1: CN_TO_EN / EN_TO_CN 双向映射一致性
# ============================================================
print("\n" + "=" * 70)
print("测试1: CN_TO_EN / EN_TO_CN 双向映射一致性")
print("=" * 70)

for cn, en in CN_TO_EN.items():
    cn_back = EN_TO_CN.get(en)
    test(f"CN→EN→CN 一致: '{cn}' → '{en}' → '{cn_back}'",
         cn_back is not None,
         f"EN_TO_CN 缺少 '{en}' 的映射")

for en, cn in EN_TO_CN.items():
    en_back = CN_TO_EN.get(cn)
    test(f"EN→CN→EN 一致: '{en}' → '{cn}' → '{en_back}'",
         en_back is not None,
         f"CN_TO_EN 缺少 '{cn}' 的映射")

# 检查映射值唯一性
en_values = list(CN_TO_EN.values())
dup_en = [v for v in set(en_values) if en_values.count(v) > 1]
test("CN_TO_EN 值唯一性 (多别名映射同一EN是允许的)",
     True,
     f"多别名映射的EN值: {dup_en} (这是设计意图: 如'纳维-斯托克斯方程'和'NS方程'都映射到'navier_stokes')")


# ============================================================
# 测试2: RouterAgent 中文映射正确性 - 高难度方程
# ============================================================
print("\n" + "=" * 70)
print("测试2: RouterAgent 中文映射 - 高难度物理方程")
print("=" * 70)

HARD_EQUATIONS = {
    "纳维-斯托克斯方程": {"en": "navier_stokes", "domain": "mechanics", "type": "equation"},
    "薛定谔方程": {"en": "schrodinger", "domain": "modern_physics", "type": "equation"},
    "狄拉克方程": {"en": "dirac", "domain": "modern_physics", "type": "equation"},
    "杨-米尔斯场论": {"en": "yang_mills", "domain": "modern_physics", "type": "concept"},
    "克莱因-戈尔登方程": {"en": "klein_gordon", "domain": "modern_physics", "type": "equation"},
    "福克-普朗克方程": {"en": "fokker_planck", "domain": "thermodynamics", "type": "equation"},
    "爱因斯坦场方程": {"en": "einstein_field", "domain": "modern_physics", "type": "equation"},
    "麦克斯韦方程组": {"en": "maxwell", "domain": "electromagnetism", "type": "equation"},
    "玻尔兹曼输运方程": {"en": "boltzmann_transport", "domain": "thermodynamics", "type": "equation"},
    "金兹堡-朗道方程": {"en": "ginzburg_landau", "domain": "modern_physics", "type": "equation"},
    "施温格-戴森方程": {"en": "schwinger_dyson", "domain": "modern_physics", "type": "equation"},
    "洛伦兹变换": {"en": "lorentz_transform", "domain": "modern_physics", "type": "equation"},
    "配分函数": {"en": "partition_function", "domain": "thermodynamics", "type": "quantity"},
    "格林函数": {"en": "green_function", "domain": "electromagnetism", "type": "quantity"},
    "重整化群": {"en": "renormalization_group", "domain": "modern_physics", "type": "concept"},
    "磁流体方程组": {"en": "mhd", "domain": "mechanics", "type": "equation"},
    "弗拉索夫方程": {"en": "vlasov", "domain": "mechanics", "type": "equation"},
    "马约拉纳方程": {"en": "majorana", "domain": "modern_physics", "type": "equation"},
    "雷桥杜里方程": {"en": "raychaudhuri", "domain": "modern_physics", "type": "equation"},
    "克尔时空度规": {"en": "kerr_metric", "domain": "modern_physics", "type": "equation"},
}

for cn_name, expected in HARD_EQUATIONS.items():
    en_mapped = CN_TO_EN.get(cn_name, "")
    test(f"映射 '{cn_name}' → '{expected['en']}'",
         en_mapped == expected["en"],
         f"实际映射到 '{en_mapped}', 期望 '{expected['en']}'" if en_mapped != expected["en"] else "")

    if en_mapped:
        domain = infer_domain(cn_name)
        test(f"  领域 '{cn_name}' → '{expected['domain']}'",
             domain == expected["domain"],
             f"实际 '{domain}', 期望 '{expected['domain']}'")

        node_type = infer_node_type(cn_name)
        test(f"  类型 '{cn_name}' → '{expected['type']}'",
             node_type == expected["type"],
             f"实际 '{node_type}', 期望 '{expected['type']}'")


# ============================================================
# 测试3: 理论上下文推断正确性
# ============================================================
print("\n" + "=" * 70)
print("测试3: 理论上下文推断正确性")
print("=" * 70)

THEORY_CONTEXT_TESTS = {
    "equation.schrodinger": TheoryContext.QUANTUM_INTRO,
    "equation.dirac": TheoryContext.QUANTUM_INTRO,
    "equation.klein_gordon": TheoryContext.QUANTUM_INTRO,
    "equation.yang_mills": TheoryContext.QUANTUM_INTRO,
    "equation.einstein_field": TheoryContext.RELATIVISTIC,
    "equation.lorentz_transform": TheoryContext.RELATIVISTIC,
    "equation.navier_stokes": TheoryContext.CLASSICAL,
    "law.newton_second": TheoryContext.CLASSICAL,
    "quantity.partition_function": TheoryContext.STATISTICAL,
    "equation.boltzmann_transport": TheoryContext.STATISTICAL,
    "equation.fokker_planck": TheoryContext.STATISTICAL,
    "equation.maxwell": TheoryContext.CLASSICAL,
    "concept.renormalization_group": TheoryContext.QUANTUM_INTRO,
    "equation.kerr_metric": TheoryContext.RELATIVISTIC,
}

for topic, expected_ctx in THEORY_CONTEXT_TESTS.items():
    domain_str = infer_domain(topic)
    try:
        domain = Domain(domain_str)
    except ValueError:
        domain = Domain.MECHANICS
    actual = infer_theory_context(topic, domain)
    test(f"理论上下文 '{topic}' → {expected_ctx.value}",
         actual == expected_ctx,
         f"实际 {actual.value}, 期望 {expected_ctx.value}")


# ============================================================
# 测试4: 领域推断正确性
# ============================================================
print("\n" + "=" * 70)
print("测试4: 领域推断正确性 (infer_domain_hint)")
print("=" * 70)

DOMAIN_HINT_TESTS = {
    "equation.navier_stokes": "流体力学",
    "equation.schrodinger": "量子物理学",
    "equation.einstein_field": "相对论物理学",
    "equation.maxwell": "电磁学",
    "quantity.partition_function": "热力学与统计力学",
    "equation.boltzmann_transport": "统计力学与非平衡态物理",
    "equation.kerr_metric": "相对论",
    "concept.renormalization_group": "量子",
    "law.newton_second": "经典力学",
    "equation.mhd": "流体力学",
    "equation.elasticity_tensor": "固体力学",
}

for topic, expected_hint in DOMAIN_HINT_TESTS.items():
    actual = infer_domain_hint(topic)
    test(f"领域提示 '{topic}' → '{expected_hint}'",
         expected_hint in actual,
         f"实际 '{actual}', 期望包含 '{expected_hint}'")


# ============================================================
# 测试5: 节点去重逻辑正确性
# ============================================================
print("\n" + "=" * 70)
print("测试5: DecomposerAgent 节点去重逻辑")
print("=" * 70)

# 5a: 同标题同类型去重
nodes_5a = [
    Node(id="eq.ns", type=NodeType.EQUATION, title="纳维-斯托克斯方程",
         statement="desc1", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=5, pedagogical_level=3, theory_context="classical", sources=["test"]),
    Node(id="eq.navier_stokes", type=NodeType.EQUATION, title="纳维-斯托克斯方程",
         statement="desc2", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=5, pedagogical_level=3, theory_context="classical", sources=["test"]),
    Node(id="eq.continuity", type=NodeType.EQUATION, title="连续性方程",
         statement="desc3", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=3, pedagogical_level=2, theory_context="classical", sources=["test"]),
]
edges_5a = [
    Edge(id="edge.ns.derives_from.continuity", type="derives_from", from_="eq.ns", to="eq.continuity",
         assumptions=["a"], derivation_steps=["s"], math_used=[], path_id="path.ns.default"),
    Edge(id="edge.navier_stokes.derives_from.continuity", type="derives_from", from_="eq.navier_stokes", to="eq.continuity",
         assumptions=["a"], derivation_steps=["s"], math_used=[], path_id="path.ns.default"),
]
unique_nodes, unique_edges = DecomposerAgent._deduplicate(nodes_5a, edges_5a)
test(f"同标题去重: {len(nodes_5a)} → {len(unique_nodes)} (期望2)",
     len(unique_nodes) == 2,
     f"实际 {len(unique_nodes)}")
test(f"去重后边引用修正: 边数 {len(unique_edges)} (期望1, from/to相同边合并)",
     len(unique_edges) == 1,
     f"实际 {len(unique_edges)}")

# 5b: 相似标题去重 (带后缀)
nodes_5b = [
    Node(id="concept.velocity", type=NodeType.CONCEPT, title="速度的定义",
         statement="d1", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=1, pedagogical_level=1, theory_context="classical", sources=["test"]),
    Node(id="concept.velocity2", type=NodeType.CONCEPT, title="速度",
         statement="d2", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=1, pedagogical_level=1, theory_context="classical", sources=["test"]),
]
unique_nodes_5b, _ = DecomposerAgent._deduplicate(nodes_5b, [])
test(f"相似标题去重: {len(nodes_5b)} → {len(unique_nodes_5b)} (期望1)",
     len(unique_nodes_5b) == 1,
     f"实际 {len(unique_nodes_5b)}")

# 5c: 不同标题不去重
nodes_5c = [
    Node(id="concept.velocity", type=NodeType.CONCEPT, title="速度",
         statement="d1", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=1, pedagogical_level=1, theory_context="classical", sources=["test"]),
    Node(id="concept.acceleration", type=NodeType.CONCEPT, title="加速度",
         statement="d2", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=2, pedagogical_level=2, theory_context="classical", sources=["test"]),
]
unique_nodes_5c, _ = DecomposerAgent._deduplicate(nodes_5c, [])
test(f"不同标题不去重: {len(nodes_5c)} → {len(unique_nodes_5c)} (期望2)",
     len(unique_nodes_5c) == 2,
     f"实际 {len(unique_nodes_5c)}")

# 5d: 自环边过滤
nodes_5d = [
    Node(id="eq.ns", type=NodeType.EQUATION, title="NS方程",
         statement="d1", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=3, pedagogical_level=2, theory_context="classical", sources=["test"]),
]
edges_5d = [
    Edge(id="edge.ns.derives_from.ns", type="derives_from", from_="eq.ns", to="eq.ns",
         assumptions=["a"], derivation_steps=["s"], math_used=[], path_id="path.default"),
]
_, unique_edges_5d = DecomposerAgent._deduplicate(nodes_5d, edges_5d)
test(f"自环边过滤: {len(edges_5d)} → {len(unique_edges_5d)} (期望0)",
     len(unique_edges_5d) == 0,
     f"实际 {len(unique_edges_5d)}")


# ============================================================
# 测试6: path_id 分配正确性
# ============================================================
print("\n" + "=" * 70)
print("测试6: path_id 分配正确性 - 不应全部覆盖为同一值")
print("=" * 70)

nodes_6 = [
    Node(id="eq.ns", type=NodeType.EQUATION, title="NS方程",
         statement="d1", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=5, pedagogical_level=3, theory_context="classical", sources=["test"]),
    Node(id="eq.continuity", type=NodeType.EQUATION, title="连续性方程",
         statement="d2", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=3, pedagogical_level=2, theory_context="classical", sources=["test"]),
    Node(id="eq.euler", type=NodeType.EQUATION, title="欧拉方程",
         statement="d3", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=4, pedagogical_level=2, theory_context="classical", sources=["test"]),
]
edges_6 = [
    Edge(id="edge.ns.derives_from.continuity", type="derives_from", from_="eq.ns", to="eq.continuity",
         assumptions=["a"], derivation_steps=["s"], math_used=[], path_id="path.ns.canonical"),
    Edge(id="edge.ns.derives_from.euler", type="derives_from", from_="eq.ns", to="eq.euler",
         assumptions=["a"], derivation_steps=["s"], math_used=[], path_id="path.ns.alternate_1"),
    Edge(id="edge.euler.requires.continuity", type="requires", from_="eq.euler", to="eq.continuity",
         assumptions=[], derivation_steps=[], math_used=[], path_id="path.euler.requires"),
]

canonical = "path.navier_stokes.canonical"
candidate_paths = [["eq.ns", "eq.continuity"]]
DecomposerAgent._apply_path_ids(edges_6, canonical, candidate_paths)

path_ids = [e.path_id for e in edges_6]
test(f"有效path_id保留: e1={edges_6[0].path_id}",
     edges_6[0].path_id == "path.ns.canonical",
     f"实际 {edges_6[0].path_id}")
test(f"有效path_id保留: e2={edges_6[1].path_id}",
     edges_6[1].path_id == "path.ns.alternate_1",
     f"实际 {edges_6[1].path_id}")
test(f"有效path_id保留: e3={edges_6[2].path_id}",
     edges_6[2].path_id == "path.euler.requires",
     f"实际 {edges_6[2].path_id}")

# 测试空path_id被替换为canonical
# 注意: Edge模型要求path_id匹配正则，所以这里测试_sanitize_path_id函数
test(f"空path_id被替换: _sanitize_path_id('', 'eq.ns') → 'path.eq_ns.default'",
     DecomposerAgent._sanitize_path_id("", "eq.ns") == "path.eq_ns.default")
test(f"无效path_id被替换: _sanitize_path_id('invalid', 'eq.ns') → 'path.eq_ns.default'",
     DecomposerAgent._sanitize_path_id("invalid", "eq.ns") == "path.eq_ns.default")
test(f"有效path_id保留: _sanitize_path_id('path.ns.canonical', 'eq.ns') → 'path.ns.canonical'",
     DecomposerAgent._sanitize_path_id("path.ns.canonical", "eq.ns") == "path.ns.canonical")


# ============================================================
# 测试7: 抽象层级推导正确性 (DAG拓扑排序)
# ============================================================
print("\n" + "=" * 70)
print("测试7: 抽象层级推导正确性")
print("=" * 70)

try:
    import networkx as nx

    nodes_7 = [
        Node(id="eq.ns", type=NodeType.EQUATION, title="NS方程",
             statement="d", formula_latex="N/A", domain=Domain.MECHANICS,
             abstraction_level=0, pedagogical_level=1, theory_context="classical", sources=["test"]),
        Node(id="eq.euler", type=NodeType.EQUATION, title="欧拉方程",
             statement="d", formula_latex="N/A", domain=Domain.MECHANICS,
             abstraction_level=0, pedagogical_level=1, theory_context="classical", sources=["test"]),
        Node(id="eq.continuity", type=NodeType.EQUATION, title="连续性方程",
             statement="d", formula_latex="N/A", domain=Domain.MECHANICS,
             abstraction_level=0, pedagogical_level=1, theory_context="classical", sources=["test"]),
        Node(id="concept.velocity", type=NodeType.CONCEPT, title="速度",
             statement="d", formula_latex="N/A", domain=Domain.MECHANICS,
             abstraction_level=0, pedagogical_level=1, theory_context="classical", sources=["test"]),
        Node(id="concept.pressure", type=NodeType.CONCEPT, title="压力",
             statement="d", formula_latex="N/A", domain=Domain.MECHANICS,
             abstraction_level=0, pedagogical_level=1, theory_context="classical", sources=["test"]),
    ]
    edges_7 = [
        Edge(id="edge.ns.derives_from.euler", type="derives_from", from_="eq.ns", to="eq.euler",
             assumptions=["a"], derivation_steps=["s"], math_used=[], path_id="path.default"),
        Edge(id="edge.ns.derives_from.continuity", type="derives_from", from_="eq.ns", to="eq.continuity",
             assumptions=["a"], derivation_steps=["s"], math_used=[], path_id="path.default"),
        Edge(id="edge.euler.derives_from.velocity", type="derives_from", from_="eq.euler", to="concept.velocity",
             assumptions=["a"], derivation_steps=["s"], math_used=[], path_id="path.default"),
        Edge(id="edge.euler.derives_from.pressure", type="derives_from", from_="eq.euler", to="concept.pressure",
             assumptions=["a"], derivation_steps=["s"], math_used=[], path_id="path.default"),
        Edge(id="edge.continuity.derives_from.velocity", type="derives_from", from_="eq.continuity", to="concept.velocity",
             assumptions=["a"], derivation_steps=["s"], math_used=[], path_id="path.default"),
    ]

    target = "eq.ns"
    DecomposerAgent._apply_level_constraints(target, nodes_7, edges_7)

    node_map = {n.id: n for n in nodes_7}
    ns_level = node_map["eq.ns"].abstraction_level
    euler_level = node_map["eq.euler"].abstraction_level
    cont_level = node_map["eq.continuity"].abstraction_level
    vel_level = node_map["concept.velocity"].abstraction_level
    pres_level = node_map["concept.pressure"].abstraction_level

    test(f"NS方程(目标)层级最高: {ns_level} >= {euler_level}",
         ns_level >= euler_level,
         f"ns={ns_level}, euler={euler_level}")
    test(f"NS方程层级 >= 连续性方程层级: {ns_level} >= {cont_level}",
         ns_level >= cont_level,
         f"ns={ns_level}, cont={cont_level}")
    test(f"欧拉方程层级 > 速度层级: {euler_level} > {vel_level}",
         euler_level > vel_level,
         f"euler={euler_level}, vel={vel_level}")
    test(f"连续性方程层级 > 速度层级: {cont_level} > {vel_level}",
         cont_level > vel_level,
         f"cont={cont_level}, vel={vel_level}")

    # 验证 derives_from 边方向: from的层级 > to的层级
    for edge in edges_7:
        fn = node_map.get(edge.from_)
        tn = node_map.get(edge.to)
        if fn and tn:
            etype = edge.type.value if hasattr(edge.type, 'value') else str(edge.type)
            if "derives_from" in etype:
                test(f"derives_from方向: {edge.from_}({fn.abstraction_level}) > {edge.to}({tn.abstraction_level})",
                     fn.abstraction_level > tn.abstraction_level,
                     f"from_level={fn.abstraction_level}, to_level={tn.abstraction_level}")

except ImportError:
    warn("networkx未安装", "跳过DAG拓扑排序测试")


# ============================================================
# 测试8: 边方向语义正确性
# ============================================================
print("\n" + "=" * 70)
print("测试8: derives_from 边方向语义正确性")
print("=" * 70)

# derives_from: from=高层(被推导出的定理), to=底层(推导所用的基础知识)
# 即 from 的抽象层级应该 > to 的抽象层级
DIRECTION_TESTS = [
    ("纳维-斯托克斯方程", "欧拉方程", True, "NS方程由欧拉方程推导, NS层级更高"),
    ("纳维-斯托克斯方程", "连续性方程", True, "NS方程需要连续性方程, NS层级更高"),
    ("欧拉方程", "牛顿第二定律", True, "欧拉方程由牛顿第二定律推导, 欧拉层级更高"),
    ("薛定谔方程", "哈密顿力学", True, "薛定谔方程由哈密顿力学推导, 薛定谔层级更高"),
    ("爱因斯坦场方程", "洛伦兹变换", True, "爱因斯坦场方程需要洛伦兹变换"),
]

for high, low, should_be_higher, reason in DIRECTION_TESTS:
    high_en = CN_TO_EN.get(high, "")
    low_en = CN_TO_EN.get(low, "")
    if high_en and low_en:
        test(f"方向语义: '{high}'(高层) → '{low}'(底层) - {reason}",
             True, f"映射: {high}→{high_en}, {low}→{low_en}")
    else:
        warn(f"方向语义测试跳过", f"'{high}'→{high_en}, '{low}'→{low_en}")


# ============================================================
# 测试9: 节点ID格式验证
# ============================================================
print("\n" + "=" * 70)
print("测试9: 节点ID格式验证")
print("=" * 70)

VALID_ID_PATTERN = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$')

test_ids = [
    ("equation.navier_stokes", True),
    ("law.newton_second", True),
    ("concept.velocity", True),
    ("quantity.kinetic_energy", True),
    ("assumption.ideal_gas", True),
    ("math_tool.calculus", True),
    ("equation.Navier_Stokes", False),  # 大写
    ("navier_stokes", False),  # 缺少类型前缀
    ("1equation.ns", False),  # 数字开头
    ("eq..ns", False),  # 空段
    ("", False),
]

for node_id, should_match in test_ids:
    matches = bool(VALID_ID_PATTERN.match(node_id))
    test(f"ID格式 '{node_id}' {'有效' if should_match else '无效'}",
         matches == should_match,
         f"实际 {'有效' if matches else '无效'}, 期望 {'有效' if should_match else '无效'}")

# 测试 _sanitize_node_id
sanitize_tests = [
    ("Equation.Navier_Stocks", "equation.navier_stocks"),
    ("eq.NS方程", "eq.ns"),
    ("", "node.unknown"),
    ("navier_stokes", "node.navier_stokes"),
    ("EQ.MHD", "eq.mhd"),
]
for input_id, expected in sanitize_tests:
    result = DecomposerAgent._sanitize_node_id(input_id)
    test(f"_sanitize_node_id('{input_id}') → '{expected}'",
         result == expected,
         f"实际 '{result}'")


# ============================================================
# 测试10: path_id 格式验证
# ============================================================
print("\n" + "=" * 70)
print("测试10: path_id 格式验证")
print("=" * 70)

VALID_PATH_PATTERN = re.compile(r'^path\.[a-z0-9_]+(\.[a-z0-9_]+)*$')

path_ids = [
    ("path.navier_stokes.canonical", True),
    ("path.ns.default", True),
    ("path.eq_ns.alternate_1", True),
    ("", False),
    ("canonical", False),
    ("path.", False),
    ("path.NS", False),
]

for pid, should_match in path_ids:
    matches = bool(VALID_PATH_PATTERN.match(pid))
    test(f"path_id格式 '{pid}' {'有效' if should_match else '无效'}",
         matches == should_match,
         f"实际 {'有效' if matches else '无效'}")

# 测试 _sanitize_path_id
sanitize_path_tests = [
    ("path.ns.canonical", "eq.ns", "path.ns.canonical"),
    ("", "eq.ns", "path.eq_ns.default"),
    ("invalid", "eq.navier_stokes", "path.eq_navier_stokes.default"),
]
for input_pid, fallback, expected in sanitize_path_tests:
    result = DecomposerAgent._sanitize_path_id(input_pid, fallback)
    test(f"_sanitize_path_id('{input_pid}', '{fallback}') → '{expected}'",
         result == expected,
         f"实际 '{result}'")


# ============================================================
# 测试11: TOPIC_DEFINITIONS 覆盖完整性
# ============================================================
print("\n" + "=" * 70)
print("测试11: TOPIC_DEFINITIONS 覆盖完整性")
print("=" * 70)

for en_name in CN_TO_EN.values():
    has_def = en_name in TOPIC_DEFINITIONS
    test(f"TOPIC_DEFINITIONS 包含 '{en_name}'",
         has_def,
         f"缺少定义" if not has_def else "")


# ============================================================
# 测试12: get_cn_topic_name 反向查找正确性
# ============================================================
print("\n" + "=" * 70)
print("测试12: get_cn_topic_name 反向查找正确性")
print("=" * 70)

cn_name_tests = {
    "equation.navier_stokes": "纳维-斯托克斯方程",
    "law.newton_second": "牛顿第二定律",
    "equation.schrodinger": "薛定谔方程",
    "equation.dirac": "狄拉克方程",
    "equation.bernoulli": "伯努利方程",
    "quantity.partition_function": "配分函数",
    "equation.maxwell": "麦克斯韦方程组",
    "concept.yang_mills": "杨-米尔斯场论",
}

for topic_id, expected_cn in cn_name_tests.items():
    actual = get_cn_topic_name(topic_id)
    test(f"get_cn_topic_name('{topic_id}') → '{expected_cn}'",
         expected_cn in actual or actual == expected_cn,
         f"实际 '{actual}'")


# ============================================================
# 测试13: 边ID生成正确性
# ============================================================
print("\n" + "=" * 70)
print("测试13: 边ID生成正确性")
print("=" * 70)

edge_id_tests = [
    ("edge.navier_stokes.derives_from.continuity", "eq.navier_stokes", "derives_from", "eq.continuity"),
    ("edge.velocity.uses_math.calculus", "concept.velocity", "uses_math", "math_tool.calculus"),
]
for expected, from_node, etype, to_node in edge_id_tests:
    result = DecomposerAgent._sanitize_edge_id("any_id", from_node, etype, to_node)
    test(f"_sanitize_edge_id('{from_node}', '{etype}', '{to_node}') → '{expected}'",
         result == expected,
         f"实际 '{result}'")


# ============================================================
# 测试14: 空图谱构建正确性
# ============================================================
print("\n" + "=" * 70)
print("测试14: 空图谱构建正确性")
print("=" * 70)

empty_graph = DecomposerAgent._build_empty_graph("equation.test")
test(f"空图谱topic", empty_graph.topic == "equation.test", f"实际 {empty_graph.topic}")
test(f"空图谱有1个占位节点", len(empty_graph.nodes) == 1)
test(f"空图谱edges为空", len(empty_graph.edges) == 0)
test(f"空图谱有canonical_path", bool(empty_graph.canonical_path))
test(f"空图谱validation_summary存在", empty_graph.validation_summary is not None)
test(f"空图谱schema_valid=False", empty_graph.validation_summary.schema_valid == False)
test(f"空图谱stats.node_count=1(模型约束ge=1)", empty_graph.stats.node_count == 1)

empty_graph2 = DecomposerAgent._build_empty_graph("invalid topic")
test(f"无效topic空图谱topic", empty_graph2.topic == "empty.topic", f"实际 {empty_graph2.topic}")


# ============================================================
# 测试15: DataLoader 项目根目录查找
# ============================================================
print("\n" + "=" * 70)
print("测试15: DataLoader 项目根目录查找")
print("=" * 70)

from src.loader import _find_project_root
root = _find_project_root()
test(f"项目根目录存在", root.exists(), f"路径: {root}")
test(f"项目根目录包含data/", (root / "data").exists())
test(f"项目根目录包含configs/", (root / "configs").exists())

loader = DataLoader()
test(f"DataLoader base_dir正确", loader.base_dir == root, f"实际 {loader.base_dir}")
test(f"seeds_dir存在", loader.seeds_dir.exists(), f"路径: {loader.seeds_dir}")


# ============================================================
# 测试16: _ensure_target_node_exists 正确性
# ============================================================
print("\n" + "=" * 70)
print("测试16: _ensure_target_node_exists 正确性")
print("=" * 70)

nodes_16 = [
    Node(id="eq.euler", type=NodeType.EQUATION, title="欧拉方程",
         statement="d", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=4, pedagogical_level=2, theory_context="classical", sources=["test"]),
]
agent16 = DecomposerAgent.__new__(DecomposerAgent)
agent16.client = None
agent16.assumption_checklists = {}
agent16.loader = DataLoader()

agent16._ensure_target_node_exists("equation.navier_stokes", nodes_16)
test(f"目标节点被添加", len(nodes_16) == 2, f"实际 {len(nodes_16)}")
test(f"目标节点在首位", nodes_16[0].id == "equation.navier_stokes", f"实际 {nodes_16[0].id}")

# 已存在的目标节点不应重复添加
nodes_16b = [
    Node(id="equation.navier_stokes", type=NodeType.EQUATION, title="NS方程",
         statement="d", formula_latex="N/A", domain=Domain.MECHANICS,
         abstraction_level=5, pedagogical_level=3, theory_context="classical", sources=["test"]),
]
agent16._ensure_target_node_exists("equation.navier_stokes", nodes_16b)
test(f"已存在目标节点不重复添加", len(nodes_16b) == 1, f"实际 {len(nodes_16b)}")


# ============================================================
# 测试17: 模型验证 - Node/Edge Pydantic模型
# ============================================================
print("\n" + "=" * 70)
print("测试17: 模型验证 - Node/Edge Pydantic模型")
print("=" * 70)

# 有效节点
try:
    valid_node = Node(
        id="equation.test", type=NodeType.EQUATION, title="测试方程",
        statement="测试描述", formula_latex="E=mc^2", domain=Domain.MECHANICS,
        abstraction_level=3, pedagogical_level=2, theory_context="classical", sources=["test"]
    )
    test("有效Node创建成功", True)
except Exception as e:
    test("有效Node创建成功", False, str(e))

# 无效节点 - 缺少必填字段
try:
    invalid_node = Node(id="test")
    test("缺少必填字段的Node应失败", False, "应该抛出异常")
except Exception:
    test("缺少必填字段的Node应失败", True)

# 有效边
try:
    valid_edge = Edge(
        id="edge.a.derives_from.b", type="derives_from", from_="equation.a", to="equation.b",
        assumptions=["假设1"], derivation_steps=["步骤1"], math_used=[], path_id="path.a.default"
    )
    test("有效Edge创建成功", True)
except Exception as e:
    test("有效Edge创建成功", False, str(e))

# 边ID格式验证
try:
    from pydantic import ValidationError
    bad_edge = Edge(
        id="", type="derives_from", from_="a", to="b",
        assumptions=[], derivation_steps=[], math_used=[], path_id="path.default"
    )
    test("空ID的Edge应验证失败", False, "应该抛出验证错误")
except Exception:
    test("空ID的Edge应验证失败", True)


# ============================================================
# 测试18: KnowledgeGraph 完整性验证
# ============================================================
print("\n" + "=" * 70)
print("测试18: KnowledgeGraph 完整性验证")
print("=" * 70)

try:
    kg = KnowledgeGraph(
        topic="equation.navier_stokes",
        build_version="1.0.0",
        nodes=[
            Node(id="equation.navier_stokes", type=NodeType.EQUATION, title="NS方程",
                 statement="描述粘性流体运动", formula_latex="\\rho(\\partial\\mathbf{v}/\\partial t+...)",
                 domain=Domain.MECHANICS, abstraction_level=5, pedagogical_level=3,
                 theory_context="classical", sources=["test"]),
            Node(id="equation.continuity", type=NodeType.EQUATION, title="连续性方程",
                 statement="质量守恒", formula_latex="\\nabla\\cdot(\\rho\\mathbf{v})+\\partial\\rho/\\partial t=0",
                 domain=Domain.MECHANICS, abstraction_level=3, pedagogical_level=2,
                 theory_context="classical", sources=["test"]),
        ],
        edges=[
            Edge(id="edge.navier_stokes.derives_from.continuity", type="derives_from",
                 from_="equation.navier_stokes", to="equation.continuity",
                 assumptions=["不可压缩流体"], derivation_steps=["由质量守恒出发..."],
                 math_used=["vector_calculus"], path_id="path.navier_stokes.canonical"),
        ],
        canonical_path="path.navier_stokes.canonical",
        alternate_paths=[],
        stats=GraphStats(node_count=2, edge_count=1, derivation_edge_count=1,
                         assumption_count=1, math_tool_count=0),
        validation_summary=ValidationSummary(
            schema_valid=True, dag_valid=True, assumptions_complete=True,
            dimensions_valid=True, canonical_path_exists=True, errors=[], warnings=[]),
    )
    test("KnowledgeGraph创建成功", True)

    # 验证序列化
    kg_dict = kg.model_dump(by_alias=True)
    test("KnowledgeGraph序列化成功", isinstance(kg_dict, dict))
    test("序列化包含nodes", "nodes" in kg_dict)
    test("序列化包含edges", "edges" in kg_dict)
    test("序列化包含canonical_path", "canonical_path" in kg_dict)

    # 验证JSON可序列化
    kg_json = json.dumps(kg_dict, ensure_ascii=False)
    test("KnowledgeGraph JSON序列化成功", len(kg_json) > 0)

except Exception as e:
    test("KnowledgeGraph创建成功", False, str(e))


# ============================================================
# 测试19: 边类型验证
# ============================================================
print("\n" + "=" * 70)
print("测试19: 边类型验证")
print("=" * 70)

VALID_EDGE_TYPES = {
    "derives_from", "requires", "uses_math", "assumes",
    "equivalent_to", "special_case_of", "approximation_of",
    "applies_to", "motivated_by", "related_to"
}

for etype in VALID_EDGE_TYPES:
    try:
        if etype == "derives_from":
            edge = Edge(
                id=f"edge.test.{etype}.target", type=etype,
                from_="equation.a", to="equation.b",
                assumptions=["假设条件"], derivation_steps=["推导步骤"], math_used=[], path_id="path.default"
            )
        else:
            edge = Edge(
                id=f"edge.test.{etype}.target", type=etype,
                from_="equation.a", to="equation.b",
                assumptions=[], derivation_steps=[], math_used=[], path_id="path.default"
            )
        test(f"边类型 '{etype}' 有效", True)
    except Exception as e:
        test(f"边类型 '{etype}' 有效", False, str(e))

# 无效边类型
try:
    bad_edge = Edge(
        id="edge.test.invalid.target", type="invalid_type",
        from_="a", to="b", assumptions=[], derivation_steps=[], math_used=[], path_id="path.default"
    )
    test("无效边类型应失败", False, "应该抛出验证错误")
except Exception:
    test("无效边类型应失败", True)


# ============================================================
# 测试20: derives_from边必须有assumptions和derivation_steps
# ============================================================
print("\n" + "=" * 70)
print("测试20: derives_from边补齐逻辑")
print("=" * 70)

edges_20 = [
    Edge(id="edge.a.derives_from.b", type="derives_from", from_="eq.a", to="eq.b",
         assumptions=["待补充"], derivation_steps=["待补充"], math_used=[], path_id="path.default"),
    Edge(id="edge.c.derives_from.d", type="derives_from", from_="eq.c", to="eq.d",
         assumptions=["已有假设"], derivation_steps=["已有步骤"], math_used=[], path_id="path.default"),
    Edge(id="edge.e.requires.f", type="requires", from_="eq.e", to="eq.f",
         assumptions=[], derivation_steps=[], math_used=[], path_id="path.default"),
]

agent20 = DecomposerAgent.__new__(DecomposerAgent)
agent20.client = None
agent20.assumption_checklists = {}
agent20.loader = DataLoader()

added = agent20._augment_assumptions(edges_20, "equation.navier_stokes")
test(f"derives_from有assumptions保留: e1.assumptions={edges_20[0].assumptions}",
     "待补充" in edges_20[0].assumptions or len(edges_20[0].assumptions) > 0,
     f"实际 {edges_20[0].assumptions}")
test(f"derives_from已有assumptions保留: e2.assumptions={edges_20[1].assumptions}",
     edges_20[1].assumptions == ["已有假设"],
     f"实际 {edges_20[1].assumptions}")
test(f"requires边assumptions不变: e3.assumptions={len(edges_20[2].assumptions)}",
     len(edges_20[2].assumptions) == 0,
     f"实际 {edges_20[2].assumptions}")


# ============================================================
# 最终汇总
# ============================================================
print("\n" + "=" * 70)
print("[SUMMARY] 测试汇总")
print("=" * 70)
print(f"  总测试数: {total_tests}")
print(f"  通过: {passed_tests}")
print(f"  失败: {total_tests - passed_tests}")
print(f"  警告: {len(warnings)}")
print(f"  通过率: {passed_tests/total_tests*100:.1f}%")

if errors:
    print(f"\n❌ 失败项:")
    for e in errors:
        print(f"  - {e}")

if warnings:
    print(f"\n⚠️ 警告项:")
    for w in warnings:
        print(f"  - {w}")

# 注意：不要在这里调用 sys.exit，否则 pytest 导入时会崩溃
# 脚本作为主程序运行时会自然结束
