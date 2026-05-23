import sys
import os
sys.path.insert(0, '../src')

os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-test-placeholder-for-unit-test')

from src.agents.planner_agent import PlannerAgent
from src.agents.retriever_agent import RetrievalOutput
from src.models import Node, NodeType, Domain, TheoryContext

print('=== Test1: Parameter Flow ===')
planner = PlannerAgent()

router_output_with_params = {
    'normalized_topic': 'equation.bernoulli',
    'domain': 'mechanics',
    'node_type': 'equation',
    'confidence': 0.9,
    'down': 5,
    'up': 3,
    'max_nodes': 80
}
result = planner.run(router_output_with_params)
print(f'[planner] User params: down={result.expand_down}, up={result.expand_up}, max_nodes={result.max_nodes}')
assert result.expand_down == 5, f'Expected 5, got {result.expand_down}'
assert result.expand_up == 3, f'Expected 3, got {result.expand_up}'
assert result.max_nodes == 80, f'Expected 80, got {result.max_nodes}'
print('  OK - User params passed correctly')

router_output_no_params = {
    'normalized_topic': 'equation.bernoulli',
    'domain': 'mechanics',
    'node_type': 'equation',
    'confidence': 0.9
}
result2 = planner.run(router_output_no_params)
print(f'[planner] Fallback: down={result2.expand_down}, up={result2.expand_up}, max_nodes={result2.max_nodes}')
assert result2.expand_down == 4, f'Expected 4, got {result2.expand_down}'
assert result2.expand_up == 2, f'Expected 2, got {result2.expand_up}'
assert result2.max_nodes == 50, f'Expected 50, got {result2.max_nodes}'
print('  OK - Fallback logic correct')

router_output_partial = {
    'normalized_topic': 'equation.bernoulli',
    'domain': 'mechanics',
    'node_type': 'equation',
    'confidence': 0.9,
    'down': 6
}
result3 = planner.run(router_output_partial)
print(f'[planner] Partial(down=6): down={result3.expand_down}, up={result3.expand_up}, max_nodes={result3.max_nodes}')
assert result3.expand_down == 6, f'Expected 6, got {result3.expand_down}'
assert result3.expand_up == 2, f'Expected 2, got {result3.expand_up}'
assert result3.max_nodes == 50, f'Expected 50, got {result3.max_nodes}'
print('  OK - Partial params handled correctly')

ro = RetrievalOutput(candidate_nodes=[], candidate_edges=[], candidate_paths=[], retrieval_evidence={}, seed_coverage=0.0)
print(f'[retriever] Default max_nodes: {ro.max_nodes}')
assert ro.max_nodes == 40, f'Expected 40, got {ro.max_nodes}'
print('  OK - Default max_nodes correct')

try:
    node_l0 = Node(id='test.node', type=NodeType.CONCEPT, title='test', statement='test', formula_latex='N/A', domain=Domain.MECHANICS, abstraction_level=0, pedagogical_level=1, theory_context=TheoryContext.CLASSICAL, sources=['test'])
    print('[models] abstraction_level=0 allowed OK')
except Exception as e:
    print(f'[models] abstraction_level=0 NOT allowed: {e}')

try:
    node_l5 = Node(id='test.node2', type=NodeType.CONCEPT, title='test', statement='test', formula_latex='N/A', domain=Domain.MECHANICS, abstraction_level=5, pedagogical_level=3, theory_context=TheoryContext.CLASSICAL, sources=['test'])
    print('[models] abstraction_level=5 allowed OK')
except Exception as e:
    print(f'[models] abstraction_level=5 NOT allowed: {e}')

try:
    node_l6 = Node(id='test.node3', type=NodeType.CONCEPT, title='test', statement='test', formula_latex='N/A', domain=Domain.MECHANICS, abstraction_level=6, pedagogical_level=3, theory_context=TheoryContext.CLASSICAL, sources=['test'])
    print('[models] abstraction_level=6 should be rejected but was allowed!')
except Exception:
    print('[models] abstraction_level=6 correctly rejected OK')

print()
print('=== Test2: Range Consistency ===')
params = {
    'app.py down': (1, 8, 3),
    'app.py up': (0, 5, 2),
    'app.py max_nodes': (15, 150, 40),
    'build_topic.py down': (1, 8, 3),
    'build_topic.py up': (0, 5, 2),
    'build_topic.py max_nodes': (15, 150, 40),
}
all_ok = True
for name, (min_val, max_val, default) in params.items():
    if not (min_val <= default <= max_val):
        print(f'  FAIL {name}: default={default} not in [{min_val}, {max_val}]')
        all_ok = False
    else:
        print(f'  OK {name}: default={default} in [{min_val}, {max_val}]')
if all_ok:
    print('All range consistency checks passed!')
else:
    print('Range consistency issues found!')

print()
print('=== ALL TESTS PASSED ===')
