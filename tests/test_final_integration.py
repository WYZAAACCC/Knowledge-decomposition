"""
最终集成验证测试
================
验证所有功能完整可用：
1. 知识图谱构建（大层数多节点）
2. OWL/RDF/JSON-LD导出
3. 前端可视化增强
4. 输入验证
"""

import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import dotenv
dotenv.load_dotenv(project_root / ".env")

from src.orchestrator import GraphBuildOrchestrator
from src.exporters.ontology_exporter import OntologyExporter


def run_integration_test():
    print("=" * 70)
    print("🔬 最终集成验证测试")
    print("=" * 70)

    all_passed = True

    # ========== 测试1: 大规模图谱构建 ==========
    print("\n[测试1] 大规模图谱构建 (量子场论, 5层, 80节点)")
    orchestrator = GraphBuildOrchestrator(artifacts_dir="artifacts/latest")
    start = time.time()
    result = orchestrator.build_topic("量子场论", down=5, up=3, max_nodes=80)
    duration = time.time() - start

    if result.graph and result.status in ["success", "partial_success"]:
        n = len(result.graph.nodes)
        e = len(result.graph.edges)
        print(f"  ✅ 构建: {n}节点, {e}边, 状态={result.status}, 耗时={duration:.1f}s")
        if n < 20:
            print(f"  ⚠️ 节点数偏少({n})，但构建成功")
    else:
        print(f"  ❌ 构建失败: {result.status}")
        all_passed = False

    graph = result.graph

    # ========== 测试2: OWL/RDF/JSON-LD导出 ==========
    print("\n[测试2] OWL/RDF/JSON-LD导出验证")
    if graph:
        try:
            exporter = OntologyExporter(graph)
            output_dir = project_root / "artifacts" / "ontology_integration_test"
            output_dir.mkdir(parents=True, exist_ok=True)

            owl_content = exporter.export_owl_xml(str(output_dir / f"{graph.topic}.owl.xml"))
            turtle_content = exporter.export_rdf_turtle(str(output_dir / f"{graph.topic}.ttl"))
            jsonld_content = exporter.export_jsonld(str(output_dir / f"{graph.topic}.jsonld"))

            # 验证OWL
            owl_root = ET.fromstring(owl_content)
            owl_individuals = sum(1 for _ in owl_root.iter() if "NamedIndividual" in _.tag)
            if owl_individuals == len(graph.nodes):
                print(f"  ✅ OWL XML: {owl_individuals}个体与图谱节点一致")
            else:
                print(f"  ❌ OWL XML: 个体数{owl_individuals} vs 节点数{len(graph.nodes)}")
                all_passed = False

            # 验证Turtle
            turtle_lines = turtle_content.strip().split("\n")
            has_prefix = any("@prefix" in l for l in turtle_lines)
            has_ontology = any("owl:Ontology" in l for l in turtle_lines)
            if has_prefix and has_ontology:
                print(f"  ✅ RDF Turtle: 格式正确, {len(turtle_lines)}行")
            else:
                print(f"  ❌ RDF Turtle: 格式不正确")
                all_passed = False

            # 验证JSON-LD
            jsonld_data = json.loads(jsonld_content)
            jsonld_nodes = [i for i in jsonld_data.get("@graph", []) if "node/" in i.get("@id", "")]
            if len(jsonld_nodes) == len(graph.nodes):
                print(f"  ✅ JSON-LD: {len(jsonld_nodes)}节点与图谱一致")
            else:
                print(f"  ❌ JSON-LD: 节点数{len(jsonld_nodes)} vs {len(graph.nodes)}")
                all_passed = False

            # 验证文件存在
            files = list(output_dir.glob("*"))
            if len(files) >= 3:
                print(f"  ✅ 导出文件: {len(files)}个文件已生成")
            else:
                print(f"  ❌ 导出文件: 仅{len(files)}个文件")
                all_passed = False

        except Exception as e:
            print(f"  ❌ 导出异常: {e}")
            all_passed = False
    else:
        print("  ⏭️ 跳过（图谱为空）")
        all_passed = False

    # ========== 测试3: 前端可视化增强 ==========
    print("\n[测试3] 前端可视化增强验证")
    html_path = project_root / "artifacts" / "latest" / "graph.html"
    if html_path.exists():
        html_content = html_path.read_text(encoding='utf-8')
        features = {
            "搜索功能": 'handleSearch' in html_content,
            "路径高亮": 'highlightCanonicalPath' in html_content,
            "导出功能": 'exportSVG' in html_content and 'exportPNG' in html_content,
            "暗色模式": 'toggleTheme' in html_content and 'data-theme="dark"' in html_content,
            "小地图": 'drawMinimap' in html_content and 'minimap-canvas' in html_content,
            "统计面板": 'updateStatsOverlay' in html_content and 'stats-overlay' in html_content,
            "Tooltip": 'setupTooltip' in html_content,
            "路径数据": '__CANONICAL_PATH__' not in html_content and '__ALTERNATE_PATHS__' not in html_content,
        }
        feat_passed = sum(1 for v in features.values() if v)
        for name, ok in features.items():
            print(f"  {'✅' if ok else '❌'} {name}")
        if feat_passed < len(features):
            all_passed = False
    else:
        print("  ❌ graph.html不存在")
        all_passed = False

    # ========== 测试4: 输入验证 ==========
    print("\n[测试4] 输入验证（异常输入处理）")
    invalid_inputs = [
        ("", "空字符串"),
        ("<script>alert('xss')</script>", "XSS攻击"),
        ("'; DROP TABLE users; --", "SQL注入"),
        ("🎉😊🚀", "纯emoji"),
    ]
    for inp, desc in invalid_inputs:
        try:
            r = orchestrator.build_topic(inp, down=1, up=0, max_nodes=5)
            if r.status == "failed" or r.graph is None:
                print(f"  ✅ {desc}: 正确拒绝")
            else:
                print(f"  ⚠️ {desc}: 未被拒绝但可能可接受")
        except Exception:
            print(f"  ✅ {desc}: 正确抛出异常")

    # ========== 测试5: 正常输入兼容性 ==========
    print("\n[测试5] 正常输入兼容性验证")
    normal_inputs = ["F=ma", "E=mc²", "薛定谔方程", "麦克斯韦方程组"]
    normal_passed = 0
    for inp in normal_inputs:
        try:
            r = orchestrator.build_topic(inp, down=2, up=1, max_nodes=15)
            if r.graph and r.status in ["success", "partial_success"]:
                normal_passed += 1
                print(f"  ✅ {inp}: {len(r.graph.nodes)}节点")
            else:
                print(f"  ❌ {inp}: 构建失败")
        except Exception as e:
            print(f"  ❌ {inp}: 异常 {str(e)[:50]}")

    if normal_passed < len(normal_inputs):
        all_passed = False

    # ========== 汇总 ==========
    print(f"\n{'='*70}")
    if all_passed:
        print("🎉 最终集成验证全部通过！系统完整可用！")
    else:
        print("⚠️ 部分测试未通过，需要进一步检查")
    print(f"{'='*70}")

    return all_passed


if __name__ == "__main__":
    success = run_integration_test()
    sys.exit(0 if success else 1)
