import sys, os, base64, json, re, time
sys.path.insert(0, '../src')
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-test')

from src.agents.renderer_agent import RendererAgent
from src.models import Node, Edge, KnowledgeGraph, GraphStats, ValidationSummary, NodeType, Domain, TheoryContext, EdgeType

renderer = RendererAgent(output_dir="artifacts/test_browser")
nodes = [
    Node(id='equation.bernoulli', type=NodeType.EQUATION, title='伯努利方程', statement='p+1/2ρv²+ρgh=常数', formula_latex='p+\\\\frac{1}{2}\\\\rho v^2+\\\\rho g h=C', domain=Domain.MECHANICS, abstraction_level=3, pedagogical_level=3, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='law.conservation_energy', type=NodeType.LAW, title='能量守恒定律', statement='能量守恒', formula_latex='E=const', domain=Domain.MECHANICS, abstraction_level=2, pedagogical_level=2, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='concept.pressure', type=NodeType.CONCEPT, title='压强', statement='单位面积上的力', formula_latex='p=F/A', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='concept.velocity', type=NodeType.CONCEPT, title='速度', statement='位移随时间的变化率', formula_latex='v=dx/dt', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='assumption.incompressible', type=NodeType.ASSUMPTION, title='不可压缩假设', statement='流体密度不变', formula_latex='N/A', domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test']),
    Node(id='equation.euler_fluid', type=NodeType.EQUATION, title='欧拉流体方程', statement='理想流体的运动方程', formula_latex='Euler', domain=Domain.MECHANICS, abstraction_level=4, pedagogical_level=3, theory_context=TheoryContext.CLASSICAL, sources=['test']),
]
edges = [
    Edge(id='edge.conservation_energy.derives_from.equation_bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='law.conservation_energy', assumptions=['理想流体','不可压缩'], derivation_steps=['从能量守恒出发'], math_used=[], path_id='path.1'),
    Edge(id='edge.pressure.derives_from.equation_bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='concept.pressure', assumptions=['压强定义'], derivation_steps=['压强项'], math_used=[], path_id='path.1'),
    Edge(id='edge.velocity.derives_from.equation_bernoulli', type=EdgeType.DERIVES_FROM, from_='equation.bernoulli', to='concept.velocity', assumptions=['速度定义'], derivation_steps=['速度项'], math_used=[], path_id='path.1'),
    Edge(id='edge.equation_bernoulli.derives_from.equation_euler_fluid', type=EdgeType.DERIVES_FROM, from_='equation.euler_fluid', to='equation.bernoulli', assumptions=['定常流动'], derivation_steps=['沿流线积分'], math_used=['微积分'], path_id='path.2'),
    Edge(id='edge.equation_bernoulli.assumes.assumption_incompressible', type=EdgeType.ASSUMES, from_='equation.bernoulli', to='assumption.incompressible', assumptions=[], derivation_steps=[], math_used=[], path_id='path.1'),
]
graph = KnowledgeGraph(
    topic='equation.bernoulli', build_version='1.0.0', nodes=nodes, edges=edges,
    canonical_path='path.1', alternate_paths=[], 
    stats=GraphStats(node_count=len(nodes), edge_count=len(edges), derivation_edge_count=4, assumption_count=2, math_tool_count=0),
    validation_summary=ValidationSummary(schema_valid=True, dag_valid=True, assumptions_complete=True, dimensions_valid=True, canonical_path_exists=True, errors=[], warnings=[])
)
renderer._generate_graph_html(graph, renderer.output_dir / "test_browser.html")

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(f"file:///{os.path.abspath('artifacts/test_browser/test_browser.html').replace(os.sep, '/')}")
    page.wait_for_timeout(5000)
    
    results = {}
    
    # Test 1: Bilingual labels
    page.evaluate("var nodes=network.body.data.nodes.get(); window._testNodes=nodes")
    nodes_data = page.evaluate("window._testNodes")
    has_bilingual = False
    for n in nodes_data:
        if n.get('label') and '\n' in str(n.get('label', '')):
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
        results['main_node_font_size'] = main_node.get('font', {}).get('size', 0) >= 22
    else:
        results['main_node_color'] = False
        results['main_node_font_size'] = False
    
    # Test 3: Merge nodes exist
    merge_nodes = [n for n in nodes_data if n.get('id', '').startswith('merge_')]
    results['merge_nodes_exist'] = len(merge_nodes) > 0
    results['merge_node_shape'] = all(n.get('shape') == 'diamond' for n in merge_nodes) if merge_nodes else False
    
    # Test 4: No yellow on hover
    test_node_id = None
    for n in nodes_data:
        if not n.get('id', '').startswith('merge_'):
            test_node_id = n['id']
            break
    if test_node_id:
        before_color = page.evaluate(f"network.body.data.nodes.get('{test_node_id}').color.background")
        node_pos = page.evaluate(f"network.getPositions(['{test_node_id}'])")
        canvas_pos = page.evaluate(f"network.DOMtoCanvas({{x:500,y:400}})")
        page.evaluate(f"""
            network.emit('hoverNode', {{
                node: '{test_node_id}',
                pointer: {{
                    DOM: {{x: 500, y: 400}},
                    canvas: {{x: {canvas_pos['x'] if canvas_pos else 0}, y: {canvas_pos['y'] if canvas_pos else 0}}}
                }}
            }})
        """)
        page.wait_for_timeout(300)
        after_color = page.evaluate(f"network.body.data.nodes.get('{test_node_id}').color.background")
        results['no_yellow_hover'] = before_color == after_color
        page.evaluate("network.emit('blurNode')")
    
    # Test 5: Physics disabled
    physics_enabled = page.evaluate("typeof physicsEnabled !== 'undefined' ? physicsEnabled : true")
    results['physics_disabled'] = not physics_enabled
    
    # Test 6: No setData calls
    html_content = page.content()
    results['no_setData'] = 'setData' not in html_content
    
    # Test 7: Level separation
    level_sep = page.evaluate("typeof levelSep !== 'undefined' ? levelSep : 0")
    results['level_separation'] = level_sep >= 400
    
    # Test 8: Edges from merge nodes to targets
    edges_data = page.evaluate("network.body.data.edges.get()")
    merge_to_target = [e for e in edges_data if e.get('from', '').startswith('merge_')]
    results['merge_to_target_edges'] = len(merge_to_target) > 0
    
    # Test 9: Assumption edges to merge nodes
    assumption_to_merge = [e for e in edges_data if 'assumption' in e.get('id', '') and e.get('to', '').startswith('merge_')]
    results['assumption_to_merge'] = len(assumption_to_merge) > 0
    
    # Test 10: All derives_from edges go through merge nodes (no direct derives_from edges between regular nodes)
    direct_derives = [e for e in edges_data if not e.get('from', '').startswith('merge_') and not e.get('to', '').startswith('merge_')]
    results['all_derives_through_merge'] = len(direct_derives) == 0 or all('assumption' in e.get('id', '') for e in direct_derives)
    
    browser.close()

print("=== Browser-Level Verification ===")
all_pass = True
for name, result in results.items():
    status = 'PASS' if result else 'FAIL'
    if not result:
        all_pass = False
    print(f"  [{status}] {name}")

print(f"\n=== {'ALL PASSED' if all_pass else 'SOME FAILED'} ===")
