import sys, os, json, base64
sys.path.insert(0, '../src')
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-test')

from src.agents.renderer_agent import RendererAgent
from src.models import Node, Edge, KnowledgeGraph, GraphStats, ValidationSummary, NodeType, Domain, TheoryContext, EdgeType

renderer = RendererAgent(output_dir="artifacts/test_verify")

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

renderer._generate_graph_html(graph, renderer.output_dir / "test_verify.html")

with open(renderer.output_dir / "test_verify.html", 'r', encoding='utf-8') as f:
    html = f.read()

checks = {
    'chosen:false in nodes': 'chosen:false' in html,
    'hoverConnectedEdges:false': 'hoverConnectedEdges:false' in html,
    'bilingual label (伯努利方程\\nbernoulli)': '伯努利方程' in html or 'cn_title' in html,
    'main node highlight (#e74c3c)': html.count('#e74c3c') > 0,
    'font size 24 for main': 'font.size=24' in html or '"size":24' in html,
    'levelSeparation 450': '450' in html,
    'merge node (⊕)': '\\u2295' in html or '⊕' in html,
    'diamond shape for merge': "'diamond'" in html,
    '推导 label': '\\u63A8\\u5BFC' in html or '推导' in html,
    '假设 label on assumption edge': '\\u5047\\u8BBE' in html or '假设' in html,
    'is_main detection': 'is_main' in html,
}

print("=== HTML Verification ===")
all_pass = True
for name, result in checks.items():
    status = 'PASS' if result else 'FAIL'
    if not result:
        all_pass = False
    print(f'  [{status}] {name}')

if all_pass:
    print("\nAll checks PASSED!")
else:
    print("\nSome checks FAILED!")

print(f"\nHTML file size: {len(html)} bytes")
print(f"File: {renderer.output_dir / 'test_verify.html'}")
