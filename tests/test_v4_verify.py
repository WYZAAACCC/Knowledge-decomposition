import sys, os, base64, json, re, time
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

with open(renderer.output_dir / "test_v4.html", 'r', encoding='utf-8') as f:
    html = f.read()

print("=== Code-Level Checks ===")
checks = {
    'hover:false': 'hover:false' in html,
    'no hover:true': 'hover:true' not in html,
    'shape:dot for merge': "shape:'dot'" in html,
    'mergeLevel=targetLevel-0.5': 'targetLevel-0.5' in html,
    'chosen:false': 'chosen:false' in html,
    'no setData': 'setData' not in html,
    'physics disabled after stab': 'physics.enabled=false' in html or 'physics:{enabled:false}' in html,
    'levelSep 450': '450' in html,
    'main font 26': 'font.size=26' in html,
    'main color #e74c3c': '#e74c3c' in html,
    'cn_title in tooltip': 'cn_title' in html,
    'en_name in tooltip': 'en_name' in html,
    'showMergeDetails': 'showMergeDetails' in html,
    'canvas mousemove': 'canvas.addEventListener' in html and 'mousemove' in html,
    'no hoverNode event': "network.on('hoverNode'" not in html,
    'nodeOrigColors': 'nodeOrigColors' in html,
    'selectNode color restore': 'selectNode' in html and 'origColor' in html,
    'deselectNode color restore': 'deselectNode' in html,
    'same-level filter (sLevel>=tLevel)': 'sLevel>=tLevel' in html,
}
all_pass = True
for name, result in checks.items():
    status = 'PASS' if result else 'FAIL'
    if not result: all_pass = False
    print(f'  [{status}] {name}')

print(f"\n=== Code-Level: {'ALL PASSED' if all_pass else 'SOME FAILED'} ===")

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(f"file:///{os.path.abspath('artifacts/test_v4/test_v4.html').replace(os.sep, '/')}")
    page.wait_for_timeout(6000)

    results = {}

    # Test 1: Bilingual labels
    nodes_data = page.evaluate("network.body.data.nodes.get()")
    has_bilingual = False
    for n in nodes_data:
        label = str(n.get('label', ''))
        if '\n' in label:
            parts = label.split('\n')
            if len(parts) >= 2 and any(ord(c) > 127 for c in parts[0]):
                has_bilingual = True
                break
    results['bilingual_labels'] = has_bilingual

    # Test 2: Main node highlight
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

    # Test 3: Merge nodes are small dots at half-levels
    merge_nodes = [n for n in nodes_data if n.get('id', '').startswith('merge_')]
    results['merge_nodes_exist'] = len(merge_nodes) > 0
    results['merge_node_shape_dot'] = all(n.get('shape') == 'dot' for n in merge_nodes) if merge_nodes else False
    results['merge_node_size_small'] = all(n.get('size', 99) <= 10 for n in merge_nodes) if merge_nodes else False
    if merge_nodes:
        half_levels = [n.get('level', 0) for n in merge_nodes]
        results['merge_at_half_levels'] = any(l != int(l) for l in half_levels)
    else:
        results['merge_at_half_levels'] = False

    # Test 4: No same-level derivation edges
    edges_data = page.evaluate("network.body.data.edges.get()")
    regular_edges = [e for e in edges_data if not e.get('from', '').startswith('merge_') and not e.get('to', '').startswith('merge_')]
    same_level_derives = 0
    for e in regular_edges:
        from_node = next((n for n in nodes_data if n['id'] == e.get('from')), None)
        to_node = next((n for n in nodes_data if n['id'] == e.get('to')), None)
        if from_node and to_node:
            if from_node.get('level') == to_node.get('level'):
                same_level_derives += 1
    results['no_same_level_derivation'] = same_level_derives == 0

    # Test 5: Each target with valid (lower-level) sources has exactly one merge node
    valid_targets = set()
    for e in page.evaluate("rawEdges"):
        if e.get('type') == 'derives_from':
            target_id = e.get('from')
            source_id = e.get('to')
            tn = next((n for n in nodes_data if n['id'] == target_id), None)
            sn = next((n for n in nodes_data if n['id'] == source_id), None)
            if tn and sn and sn.get('level', 0) < tn.get('level', 0):
                valid_targets.add(target_id)
    results['one_merge_per_valid_target'] = len(merge_nodes) == len(valid_targets)

    # Test 6: Merge nodes only connect to targets above them
    merge_to_target = [e for e in edges_data if e.get('from', '').startswith('merge_') and not e.get('to', '').startswith('merge_')]
    all_above = True
    for e in merge_to_target:
        from_node = next((n for n in nodes_data if n['id'] == e['from']), None)
        to_node = next((n for n in nodes_data if n['id'] == e['to']), None)
        if from_node and to_node:
            if from_node.get('level', 0) >= to_node.get('level', 0):
                all_above = False
    results['merge_points_upward'] = all_above and len(merge_to_target) > 0

    # Test 7: Physics disabled
    results['physics_disabled'] = page.evaluate("typeof physicsEnabled !== 'undefined' ? !physicsEnabled : false")

    # Test 8: Click merge node shows derivation
    if merge_nodes:
        merge_id = merge_nodes[0]['id']
        page.evaluate(f"network.selectNodes(['{merge_id}'])")
        page.evaluate(f"network.emit('click', {{nodes: ['{merge_id}'], edges: []}})")
        page.wait_for_timeout(300)
        detail_content = page.evaluate("document.getElementById('detail-content').textContent")
        results['click_merge_shows_derivation'] = '推导' in detail_content or '来源' in detail_content
    else:
        results['click_merge_shows_derivation'] = False

    # Test 9: Hover does not change node color
    test_node_id = None
    for n in nodes_data:
        if not n.get('id', '').startswith('merge_'):
            test_node_id = n['id']
            break
    if test_node_id:
        before_color = page.evaluate(f"network.body.data.nodes.get('{test_node_id}').color.background")
        page.evaluate(f"""
            var canvas = document.getElementById('network-container').querySelector('canvas');
            canvas.dispatchEvent(new MouseEvent('mousemove', {{clientX: 500, clientY: 400, bubbles: true}}));
        """)
        page.wait_for_timeout(200)
        after_color = page.evaluate(f"network.body.data.nodes.get('{test_node_id}').color.background")
        results['hover_no_color_change'] = before_color == after_color
    else:
        results['hover_no_color_change'] = False

    # Test 10: Assumption edges to merge nodes
    assumption_to_merge = [e for e in edges_data if 'assumption' in e.get('id', '') and e.get('to', '').startswith('merge_')]
    results['assumption_to_merge'] = len(assumption_to_merge) > 0

    browser.close()

print("\n=== Browser-Level Checks ===")
browser_all_pass = True
for name, result in results.items():
    status = 'PASS' if result else 'FAIL'
    if not result: browser_all_pass = False
    print(f'  [{status}] {name}')

print(f"\n=== Browser-Level: {'ALL PASSED' if browser_all_pass else 'SOME FAILED'} ===")
print(f"\n=== Overall: {'ALL PASSED' if all_pass and browser_all_pass else 'SOME FAILED'} ===")
