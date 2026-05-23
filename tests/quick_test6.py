import dotenv, sys, json
sys.path.insert(0, '../src')
dotenv.load_dotenv('../.env')
from strict_content_test import *

test_indices = [0, 1]  # 广义相对论, 薛定谔方程

for idx in test_indices:
    spec = TOPIC_SPECS[idx]
    r = run_single_test(spec)
    p = 'PASS' if r.get('passed') else 'FAIL'
    c = r.get('checks', {})
    nc = c.get('node_count', 0)
    ec = c.get('edge_count', 0)
    dep = c.get('max_depth', 0)
    rel = c.get('content_relevance', 0)
    form = c.get('formula_coverage', 0)
    assump = c.get('assumption_coverage', 0)
    print(f'\n{p} | {spec.name} | N={nc} E={ec} D={dep} rel={rel:.0%} form={form:.0%} assump={assump:.0%}')
    if r.get('errors'):
        for e in r['errors'][:3]:
            print(f'  ERR: {e}')
