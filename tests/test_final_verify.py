import sys, os, base64, json, re
sys.path.insert(0, '../src')
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-test')

from src.agents.renderer_agent import RendererAgent
from src.models import Node, Edge, KnowledgeGraph, GraphStats, ValidationSummary, NodeType, Domain, TheoryContext, EdgeType

renderer = RendererAgent(output_dir="artifacts/test_final")

nodes = [
    Node(id='equation.bernoulli', type=NodeType.EQUATION, title='伯努利方程', statement='p+1/2ρv²+ρgh=常数', formula_latex='p+\\\\frac{1}{2}\\\\rho v^2+\\\\rho g h=C', domain=Domain.MECHANICS, abstraction_level=3, pedagogical_level=3, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='law.conservation_energy', type=NodeType.LAW, title='能量守恒定律', statement='能量既不会凭空产生', formula_latex='E_{total}=const', domain=Domain.MECHANICS, abstraction_level=2, pedagogical_level=2, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='concept.pressure', type=NodeType.CONCEPT, title='压强', statement='单位面积上的力', formula_latex='p=F/A', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='concept.velocity', type=NodeType.CONCEPT, title='速度', statement='位移随时间的变化率', formula_latex='v=dx/dt', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='concept.density', type=NodeType.CONCEPT, title='密度', statement='单位体积的质量', formula_latex='\\\\rho=m/V', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='assumption.incompressible', type=NodeType.ASSUMPTION, title='不可压缩假设', statement='流体密度不变', formula_latex='N/A', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='concept.kinetic_energy', type=NodeType.CONCEPT, title='动能', statement='物体因运动而具有的能量', formula_latex='E_k=\\\\frac{1}{2}mv^2', domain=Domain.MECHANICS, abstraction_level=2, pedagogical_level=2, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='equation.euler_fluid', type=NodeType.EQUATION, title='欧拉流体方程', statement='理想流体的运动方程', formula_latex='\\\\rho(\\\\frac{\\\\partial v}{\\\\partial t}+v\\\\cdot\\\\nabla v)=-\\\\nabla p+\\\\rho g', domain=Domain.MECHANICS, abstraction_level=4, pedagogical_level=3, theory_context=TheoryContext.CLASSICAL, sources=['test']),
]

edges = [
    Edge(id='edge.conservation_energy.derives_from.bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='law.conservation_energy', assumptions=['理想流体','定常流动','不可压缩'], derivation_steps=['从能量守恒出发...'], math_used=[], path_id='path.bernoulli.default'),
    Edge(id='edge.kinetic_energy.derives_from.bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='concept.kinetic_energy', assumptions=['动能定义'], derivation_steps=['动能项...'], math_used=[], path_id='path.bernoulli.default'),
    Edge(id='edge.pressure.derives_from.bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='concept.pressure', assumptions=['压强定义'], derivation_steps=['压强项...'], math_used=[], path_id='path.bernoulli.default'),
    Edge(id='edge.velocity.derives_from.bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='concept.velocity', assumptions=['速度定义'], derivation_steps=['速度项...'], math_used=[], path_id='path.bernoulli.default'),
    Edge(id='edge.density.derives_from.bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='concept.density', assumptions=['密度定义'], derivation_steps=['密度项...'], math_used=[], path_id='path.bernoulli.default'),
    Edge(id='edge.bernoulli.derives_from.euler', type=EdgeType.DERIVES_FROM, from_='equation.euler_fluid', to='equation.bernoulli', assumptions=['定常流动','沿流线积分'], derivation_steps=['沿流线积分欧拉方程...'], math_used=['微积分'], path_id='path.bernoulli.default'),
    Edge(id='edge.bernoulli.assumes.incompressible', type=EdgeType.ASSUMES, from_='equation.bernoulli', to='assumption.incompressible', assumptions=[], derivation_steps=[], math_used=[], path_id='path.bernoulli.default'),
]

graph = KnowledgeGraph(
    topic='equation.bernoulli',
    build_version='1.0.0',
    nodes=nodes,
    edges=edges,
    canonical_path='path.bernoulli.canonical',
    alternate_paths=[],
    stats=GraphStats(node_count=len(nodes), edge_count=len(edges), derivation_edge_count=5, assumption_count=3, math_tool_count=0),
    validation_summary=ValidationSummary(schema_valid=True, dag_valid=True, assumptions_complete=True, dimensions_valid=True, canonical_path_exists=True, errors=[], warnings=[])
)

renderer._generate_graph_html(graph, renderer.output_dir / "test_final.html")

with open(renderer.output_dir / "test_final.html", 'r', encoding='utf-8') as f:
    html = f.read()

print("=== Final Comprehensive Verification ===")
print()

# 1. Decode base64 data to check bilingual labels
match = re.search(r'b64DecodeUnicode\("([^"]+)"\)', html)
if match:
    b64_data = match.group(1)
    decoded = base64.b64decode(b64_data).decode('utf-8')
    nodes_data = json.loads(decoded)
    print(f"[1] Bilingual labels in data:")
    for n in nodes_data:
        label = n.get('label', '')
        cn = n.get('cn_title', '')
        en = n.get('en_name', '')
        has_newline = '\\n' in label
        print(f"  {n['id']}: label='{label[:40]}...' cn='{cn}' en='{en}' has_newline={has_newline}")
    print()

# 2. Check chosen:false
chosen_count = html.count('chosen:false')
print(f"[2] chosen:false count: {chosen_count} (expected >= 3)")
print()

# 3. Check no setData calls
setdata_count = html.count('setData')
print(f"[3] setData calls: {setdata_count} (expected 0)")
print()

# 4. Check physics disabled after stabilization
physics_disabled = 'physics.enabled=false' in html or "physics:{enabled:false}" in html
print(f"[4] Physics disabled after stabilization: {physics_disabled}")
print()

# 5. Check levelSeparation default
level_sep_match = re.search(r"levelSep=parseInt\(localStorage.*?\)\|\|(\d+)", html)
if level_sep_match:
    print(f"[5] Default levelSeparation: {level_sep_match.group(1)} (expected 450)")
print()

# 6. Check main node styling
main_font_size = 'font.size=24' in html
main_color = '#e74c3c' in html
main_size = 'vn.size=50' in html
print(f"[6] Main node: font.size=24={main_font_size}, #e74c3c={main_color}, size=50={main_size}")
print()

# 7. Check merge nodes
diamond_count = html.count("'diamond'")
merge_symbol = '\\u2295' in html or '⊕' in html
print(f"[7] Merge nodes: diamond_shape_count={diamond_count}, ⊕_symbol={merge_symbol}")
print()

# 8. Check assumption edges point to merge nodes
assumption_to_merge = 'edge_assumption_' in html
print(f"[8] Assumption edges to merge nodes: {assumption_to_merge}")
print()

# 9. Check hoverConnectedEdges
hover_connected = 'hoverConnectedEdges:false' in html
print(f"[9] hoverConnectedEdges:false: {hover_connected}")
print()

# 10. Check 推导 and 假设 labels
has_derivation_label = '\\u63A8\\u5BFC' in html or '推导' in html
has_assumption_label = '\\u5047\\u8BBE' in html or '假设' in html
print(f"[10] 推导 label: {has_derivation_label}, 假设 label: {has_assumption_label}")
print()

all_pass = (
    chosen_count >= 3 and
    setdata_count == 0 and
    physics_disabled and
    level_sep_match and level_sep_match.group(1) == '450' and
    main_font_size and main_color and main_size and
    diamond_count > 0 and merge_symbol and
    assumption_to_merge and
    hover_connected and
    has_derivation_label and has_assumption_label
)

print(f"=== Overall: {'ALL PASSED' if all_pass else 'SOME FAILED'} ===")
print(f"HTML file: {renderer.output_dir / 'test_final.html'}")
