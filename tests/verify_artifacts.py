from pathlib import Path
import json

artifacts_dir = Path('artifacts/latest')
print('=== 工件文件检查 ===')
for name in ['graph.json', 'report.md', 'debug.json', 'eval_report.json', 'graph.html']:
    p = artifacts_dir / name
    if p.exists():
        size = p.stat().st_size
        print(f'  {name}: OK ({size} bytes)')
    else:
        print(f'  {name}: MISSING')

html_path = artifacts_dir / 'graph.html'
if html_path.exists():
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    checks = {
        'D3.js': 'd3' in html.lower(),
        'SVG': '<svg' in html.lower() or 'svg' in html.lower(),
        'Node': 'node' in html.lower(),
        'Edge': 'edge' in html.lower() or 'link' in html.lower(),
        'Force': 'force' in html.lower(),
        'Zoom': 'zoom' in html.lower(),
    }
    print('\n=== HTML可视化检查 ===')
    for check_name, result in checks.items():
        status = 'OK' if result else 'MISSING'
        print(f'  {check_name}: {status}')

report_path = artifacts_dir / 'report.md'
if report_path.exists():
    with open(report_path, 'r', encoding='utf-8') as f:
        report = f.read()
    checks = {
        'Title': report.startswith('#'),
        'NodeCount': 'node' in report.lower() or '节点' in report,
        'EdgeCount': 'edge' in report.lower() or '边' in report,
    }
    print('\n=== 报告检查 ===')
    for check_name, result in checks.items():
        status = 'OK' if result else 'MISSING'
        print(f'  {check_name}: {status}')

eval_path = artifacts_dir / 'eval_report.json'
if eval_path.exists():
    with open(eval_path, 'r', encoding='utf-8') as f:
        eval_data = json.load(f)
    print('\n=== 评估报告检查 ===')
    for key in ['topic', 'build_status', 'validation_score', 'node_count', 'edge_count']:
        val = eval_data.get(key, 'MISSING')
        print(f'  {key}: {val}')

ontology_dir = artifacts_dir / 'ontology'
if ontology_dir.exists():
    print('\n=== 本体论文件检查 ===')
    for p in ontology_dir.iterdir():
        if p.is_file():
            print(f'  {p.name}: OK ({p.stat().st_size} bytes)')
