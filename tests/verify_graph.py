import json

with open('artifacts/latest/graph.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('=== 图谱基本信息 ===')
print(f'Topic: {data.get("topic")}')
print(f'节点数: {len(data.get("nodes", []))}')
print(f'边数: {len(data.get("edges", []))}')
print(f'规范路径: {data.get("canonical_path")}')

print('\n=== 节点列表 ===')
for n in data.get('nodes', []):
    print(f'  [{n.get("type")}] {n.get("id")}: {n.get("title")} (层级{n.get("abstraction_level")})')

print('\n=== 边列表 ===')
for e in data.get('edges', []):
    print(f'  [{e.get("type")}] {e.get("from")} -> {e.get("to")} (path_id={e.get("path_id")})')
    if e.get('assumptions'):
        print(f'    assumptions: {e["assumptions"][:2]}')
    if e.get('derivation_steps'):
        steps = e['derivation_steps']
        print(f'    derivation_steps: {len(steps)}步')

print('\n=== 验证摘要 ===')
vs = data.get('validation_summary', {})
print(f'schema_valid: {vs.get("schema_valid")}')
print(f'dag_valid: {vs.get("dag_valid")}')
print(f'assumptions_complete: {vs.get("assumptions_complete")}')
print(f'canonical_path_exists: {vs.get("canonical_path_exists")}')

print('\n=== 层级验证 ===')
nodes = data.get('nodes', [])
edges = data.get('edges', [])
node_map = {n['id']: n for n in nodes}
all_ok = True
for e in edges:
    if e.get('type') == 'derives_from':
        fn = node_map.get(e.get('from'))
        tn = node_map.get(e.get('to'))
        if fn and tn:
            ok = fn['abstraction_level'] > tn['abstraction_level']
            if not ok:
                all_ok = False
            status = 'OK' if ok else 'FAIL'
            print(f'  {status}: {fn["title"]}({fn["abstraction_level"]}) > {tn["title"]}({tn["abstraction_level"]})')

print(f'\n层级验证结果: {"全部通过" if all_ok else "存在错误"}')

# 检查工件文件
from pathlib import Path
artifacts_dir = Path('artifacts/latest')
print('\n=== 工件文件检查 ===')
for name in ['graph.json', 'report.md', 'debug.json', 'eval_report.json', 'graph.html']:
    p = artifacts_dir / name
    exists = p.exists()
    size = p.stat().st_size if exists else 0
    print(f'  {name}: {"存在" if exists else "缺失"} ({size} bytes)')
