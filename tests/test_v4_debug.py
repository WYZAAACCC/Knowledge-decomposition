import sys, os, base64, json, re
sys.path.insert(0, '../src')
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-test')

from src.agents.renderer_agent import RendererAgent
from src.models import Node, Edge, KnowledgeGraph, GraphStats, ValidationSummary, NodeType, Domain, TheoryContext, EdgeType

renderer = RendererAgent(output_dir="artifacts/test_v4")
nodes = [
    Node(id='equation.bernoulli', type=NodeType.EQUATION, title='伯努利方程', statement='p+1/2rv2+rgh=C', formula_latex='p+\\\\frac{1}{2}\\\\rho v^2+\\\\rho g h=C', domain=Domain.MECHANICS, abstraction_level=3, pedagogical_level=3, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='law.conservation_energy', type=NodeType.LAW, title='能量守恒定律', statement='能量守恒', formula_latex='E=const', domain=Domain.MECHANICS, abstraction_level=2, pedagogical_level=2, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='concept.pressure', type=NodeType.CONCEPT, title='压强', statement='单位面积上的力', formula_latex='p=F/A', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='concept.velocity', type=NodeType.CONCEPT, title='速度', statement='位移随时间的变化率', formula_latex='v=dx/dt', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='assumption.incompressible', type=NodeType.ASSUMPTION, title='不可压缩假设', statement='流体密度不变', formula_latex='N/A', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='equation.euler_fluid', type=NodeType.EQUATION, title='欧拉流体方程', statement='理想流体的运动方程', formula_latex='Euler', domain=Domain.MECHANICS, abstraction_level=4, pedagogical_level=3, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='concept.density', type=NodeType.CONCEPT, title='密度', statement='单位体积的质量', formula_latex='rho=m/V', domain=Domain.MECHANICS, abstraction_level=2, pedagogical_level=2, theory_context=TheoryContext.CLASSICAL, sources=['test']),
]
edges = [
    Edge(id='edge.law_conservation_energy.derives_from.equation_bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='law.conservation_energy', assumptions=['理想流体','不可压缩'], derivation_steps=['从能量守恒出发'], math_used=[], path_id='path.1'),
    Edge(id='edge.concept_pressure.derives_from.equation_bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='concept.pressure', assumptions=['压强定义'], derivation_steps=['压强项'], math_used=[], path_id='path.1'),
    Edge(id='edge.concept_velocity.derives_from.equation_bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='concept.velocity', assumptions=['速度定义'], derivation_steps=['速度项'], math_used=[], path_id='path.1'),
    Edge(id='edge.equation_bernoulli.derives_from.equation_euler_fluid', type=EdgeType.DERIVES_FROM, from_='equation.euler_fluid', to='equation.bernoulli', assumptions=['定常流动'], derivation_steps=['沿流线积分'], math_used=['微积分'], path_id='path.2'),
    Edge(id='edge.concept_density.derives_from.law_conservation_energy', type=EdgeType.DERIVES_FROM, from_='law.conservation_energy', to='concept.density', assumptions=['密度定义'], derivation_steps=['密度相关'], math_used=[], path_id='path.1'),
    Edge(id='edge.equation_bernoulli.assumes.assumption_incompressible', type=EdgeType.ASSUMES, from_='equation.bernoulli', to='assumption.incompressible', assumptions=[], derivation_steps=[], math_used=[], path_id='path.1'),
]
graph = KnowledgeGraph(
    topic='equation.bernoulli', build_version='1.0.0', nodes=nodes, edges=edges,
    canonical_path='path.1', alternate_paths=[],
    stats=GraphStats(node_count=len(nodes), edge_count=len(edges), derivation_edge_count=5, assumption_count=2, math_tool_count=0),
    validation_summary=ValidationSummary(schema_valid=True, dag_valid=True, assumptions_complete=True, dimensions_valid=True, canonical_path_exists=True, errors=[], warnings=[])
)
renderer._generate_graph_html(graph, renderer.output_dir / "test_v4.html")

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(f"file:///{os.path.abspath('artifacts/test_v4/test_v4.html').replace(os.sep, '/')}")
    page.wait_for_timeout(6000)

    nodes_data = page.evaluate("network.body.data.nodes.get()")
    edges_data = page.evaluate("network.body.data.edges.get()")
    raw_edges = page.evaluate("rawEdges")

    print("=== Debug Info ===")
    
    # Count targets from raw derives_from edges
    target_ids = set()
    for e in raw_edges:
        if e.get('type') == 'derives_from':
            target_ids.add(e.get('from'))
    print(f"Targets from raw derives_from edges: {target_ids}")
    
    # Count merge nodes
    merge_nodes = [n for n in nodes_data if n.get('id', '').startswith('merge_')]
    print(f"Merge nodes: {[n['id'] for n in merge_nodes]}")
    print(f"Merge count: {len(merge_nodes)}, Target count: {len(target_ids)}")
    
    # Check which targets have merge nodes
    for tid in target_ids:
        has_merge = any(tid.replace('.', '_') in n['id'] for n in merge_nodes)
        print(f"  Target '{tid}' has merge node: {has_merge}")
    
    # Check level info
    for n in nodes_data:
        if not n.get('id', '').startswith('merge_'):
            print(f"  Node: {n['id']}, level={n.get('level')}, label={repr(n.get('label', '')[:30])}")

    browser.close()
