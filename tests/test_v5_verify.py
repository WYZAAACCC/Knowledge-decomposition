import sys, os
sys.path.insert(0, '../src')
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-test')

from src.agents.renderer_agent import RendererAgent
from src.models import Node, Edge, KnowledgeGraph, GraphStats, ValidationSummary, NodeType, Domain, TheoryContext, EdgeType

renderer = RendererAgent(output_dir="artifacts/test_v5")
nodes = [
    Node(id='equation.bernoulli', type=NodeType.EQUATION, title='伯努利方程', statement='p+1/2rv2+rgh=C', formula_latex='p+\\\\frac{1}{2}\\\\rho v^2+\\\\rho g h=C', domain=Domain.MECHANICS, abstraction_level=3, pedagogical_level=3, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='law.conservation_energy', type=NodeType.LAW, title='能量守恒定律', statement='能量守恒', formula_latex='E=const', domain=Domain.MECHANICS, abstraction_level=2, pedagogical_level=2, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='concept.pressure', type=NodeType.CONCEPT, title='压强', statement='单位面积上的力', formula_latex='p=F/A', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='concept.velocity', type=NodeType.CONCEPT, title='速度', statement='位移随时间的变化率', formula_latex='v=dx/dt', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='assumption.incompressible', type=NodeType.ASSUMPTION, title='不可压缩假设', statement='流体密度不变', formula_latex='N/A', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='equation.euler_fluid', type=NodeType.EQUATION, title='欧拉流体方程', statement='理想流体的运动方程', formula_latex='Euler', domain=Domain.MECHANICS, abstraction_level=4, pedagogical_level=3, theory_context=TheoryContext.CLASSICAL, sources=['test']),
]
edges = [
    Edge(id='edge.law_conservation_energy.derives_from.equation_bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='law.conservation_energy', assumptions=['理想流体','不可压缩'], derivation_steps=['从能量守恒出发'], math_used=[], path_id='path.1'),
    Edge(id='edge.concept_pressure.derives_from.equation_bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='concept.pressure', assumptions=['压强定义'], derivation_steps=['压强项'], math_used=[], path_id='path.1'),
    Edge(id='edge.concept_velocity.derives_from.equation_bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='concept.velocity', assumptions=['速度定义'], derivation_steps=['速度项'], math_used=[], path_id='path.1'),
    Edge(id='edge.equation_bernoulli.derives_from.equation_euler_fluid', type=EdgeType.DERIVES_FROM, from_='equation.euler_fluid', to='equation.bernoulli', assumptions=['定常流动'], derivation_steps=['沿流线积分'], math_used=['微积分'], path_id='path.2'),
    Edge(id='edge.equation_bernoulli.assumes.assumption_incompressible', type=EdgeType.ASSUMES, from_='equation.bernoulli', to='assumption.incompressible', assumptions=[], derivation_steps=[], math_used=[], path_id='path.1'),
]
graph = KnowledgeGraph(
    topic='equation.bernoulli', build_version='1.0.0', nodes=nodes, edges=edges,
    canonical_path='path.1', alternate_paths=[],
    stats=GraphStats(node_count=len(nodes), edge_count=len(edges), derivation_edge_count=4, assumption_count=2, math_tool_count=0),
    validation_summary=ValidationSummary(schema_valid=True, dag_valid=True, assumptions_complete=True, dimensions_valid=True, canonical_path_exists=True, errors=[], warnings=[])
)
renderer._generate_graph_html(graph, renderer.output_dir / "test_v5.html")

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(f"file:///{os.path.abspath('artifacts/test_v5/test_v5.html').replace(os.sep, '/')}")
    page.wait_for_timeout(6000)

    results = {}
    nodes_data = page.evaluate("network.body.data.nodes.get()")
    edges_data = page.evaluate("network.body.data.edges.get()")

    # Test 1: Chinese-only labels (no English)
    has_english_in_label = False
    for n in nodes_data:
        if not n.get('id', '').startswith('merge_'):
            label = str(n.get('label', ''))
            lines = label.split('\n')
            for line in lines:
                if line.strip() and all(ord(c) < 128 for c in line.strip()):
                    has_english_in_label = True
                    break
    results['chinese_only_labels'] = not has_english_in_label

    # Test 2: Merge nodes are visible diamonds
    merge_nodes = [n for n in nodes_data if n.get('id', '').startswith('merge_')]
    results['merge_nodes_exist'] = len(merge_nodes) > 0
    results['merge_node_shape_diamond'] = all(n.get('shape') == 'diamond' for n in merge_nodes) if merge_nodes else False
    results['merge_node_visible_size'] = all(n.get('size', 0) >= 10 for n in merge_nodes) if merge_nodes else False
    results['merge_node_has_label'] = all(n.get('label', '') != '' for n in merge_nodes) if merge_nodes else False

    # Test 3: Main node highlight
    main_node = None
    for n in nodes_data:
        if 'bernoulli' in n.get('id', '') and 'euler' not in n.get('id', ''):
            main_node = n
            break
    if main_node:
        results['main_node_color'] = main_node.get('color', {}).get('background', '') == '#e74c3c'
        results['main_node_font_size'] = main_node.get('font', {}).get('size', 0) >= 24
    else:
        results['main_node_color'] = False
        results['main_node_font_size'] = False

    # Test 4: Merge at half-levels
    if merge_nodes:
        half_levels = [n.get('level', 0) for n in merge_nodes]
        results['merge_at_half_levels'] = any(l != int(l) for l in half_levels)
    else:
        results['merge_at_half_levels'] = False

    # Test 5: No same-level derivation
    regular_edges = [e for e in edges_data if not e.get('from', '').startswith('merge_') and not e.get('to', '').startswith('merge_')]
    same_level = 0
    for e in regular_edges:
        fn = next((n for n in nodes_data if n['id'] == e.get('from')), None)
        tn = next((n for n in nodes_data if n['id'] == e.get('to')), None)
        if fn and tn and fn.get('level') == tn.get('level'):
            same_level += 1
    results['no_same_level_derivation'] = same_level == 0

    # Test 6: Physics disabled
    results['physics_disabled'] = page.evaluate("typeof physicsEnabled !== 'undefined' ? !physicsEnabled : false")

    # Test 7: Click merge shows derivation
    if merge_nodes:
        merge_id = merge_nodes[0]['id']
        page.evaluate(f"network.selectNodes(['{merge_id}'])")
        page.evaluate(f"network.emit('click', {{nodes: ['{merge_id}'], edges: []}})")
        page.wait_for_timeout(300)
        detail = page.evaluate("document.getElementById('detail-content').textContent")
        results['click_merge_shows_derivation'] = '推导' in detail or '来源' in detail
    else:
        results['click_merge_shows_derivation'] = False

    # Test 8: Hover no color change
    test_node_id = None
    for n in nodes_data:
        if not n.get('id', '').startswith('merge_'):
            test_node_id = n['id']
            break
    if test_node_id:
        before = page.evaluate(f"network.body.data.nodes.get('{test_node_id}').color.background")
        page.evaluate("""var canvas = document.getElementById('network-container').querySelector('canvas'); canvas.dispatchEvent(new MouseEvent('mousemove', {clientX: 500, clientY: 400, bubbles: true}));""")
        page.wait_for_timeout(200)
        after = page.evaluate(f"network.body.data.nodes.get('{test_node_id}').color.background")
        results['hover_no_color_change'] = before == after
    else:
        results['hover_no_color_change'] = False

    browser.close()

print("=== Verification ===")
all_pass = True
for name, result in results.items():
    status = 'PASS' if result else 'FAIL'
    if not result: all_pass = False
    print(f'  [{status}] {name}')

print(f"\n=== {'ALL PASSED' if all_pass else 'SOME FAILED'} ===")
