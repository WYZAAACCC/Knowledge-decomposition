"""
前端可视化增强验证测试
验证新增功能：搜索、路径高亮、导出、暗色模式、小地图、统计面板、tooltip
"""

import json
import sys
import re
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import dotenv
dotenv.load_dotenv(project_root / ".env")

from src.orchestrator import GraphBuildOrchestrator


def test_html_features():
    print("=" * 70)
    print("🧪 前端可视化增强验证测试")
    print("=" * 70)

    print("\n[1/3] 构建知识图谱...")
    orchestrator = GraphBuildOrchestrator(artifacts_dir="artifacts/latest")
    build_result = orchestrator.build_topic("欧姆定律", down=2, up=1, max_nodes=15)

    if not build_result.graph:
        print("❌ 图谱构建失败")
        return False

    graph = build_result.graph
    print(f"  图谱构建成功: {len(graph.nodes)}节点, {len(graph.edges)}边")

    print("\n[2/3] 读取生成的HTML文件...")
    html_path = project_root / "artifacts" / "latest" / "graph.html"
    if not html_path.exists():
        print("❌ graph.html不存在")
        return False

    html_content = html_path.read_text(encoding='utf-8')
    print(f"  HTML文件大小: {len(html_content)}字符")

    print("\n[3/3] 验证新增功能...")

    checks = {
        "搜索栏": 'id="search-input"' in html_content,
        "搜索结果容器": 'id="search-results"' in html_content,
        "路径高亮-规范路径": 'highlightCanonicalPath' in html_content,
        "路径高亮-全部路径": 'highlightAllPaths' in html_content,
        "路径高亮-清除": 'clearHighlight' in html_content,
        "导出SVG": 'exportSVG' in html_content,
        "导出PNG": 'exportPNG' in html_content,
        "暗色模式": 'toggleTheme' in html_content,
        "暗色模式CSS": 'data-theme="dark"' in html_content,
        "小地图": 'minimap-canvas' in html_content,
        "小地图绘制": 'drawMinimap' in html_content,
        "统计面板": 'stats-overlay' in html_content,
        "统计计算": 'updateStatsOverlay' in html_content,
        "Tooltip": 'setupTooltip' in html_content,
        "规范路径数据": '__CANONICAL_PATH__' not in html_content,
        "备用路径数据": '__ALTERNATE_PATHS__' not in html_content,
        "搜索功能JS": 'handleSearch' in html_content,
        "键盘快捷键-S搜索": "search-input" in html_content and "focus()" in html_content,
        "键盘快捷键-T主题": "toggleTheme" in html_content,
        "键盘快捷键-M小地图": "toggleMinimap" in html_content,
        "暗色模式CSS变量": "--bg:#1a1b2e" in html_content,
        "导出按钮-SVG": '导出SVG' in html_content,
        "导出按钮-PNG": '导出PNG' in html_content,
        "统计按钮": 'toggleStats' in html_content,
        "小地图按钮": 'toggleMinimap' in html_content,
    }

    passed = 0
    failed = 0
    for name, result in checks.items():
        icon = "✅" if result else "❌"
        print(f"  {icon} {name}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*70}")
    print(f"总计: {passed}/{len(checks)} 通过 ({100*passed/len(checks):.0f}%)")

    if failed > 0:
        print(f"\n❌ {failed}项检查未通过")
        return False
    else:
        print(f"\n🎉 所有前端增强功能验证通过！")
        return True


if __name__ == "__main__":
    success = test_html_features()
    sys.exit(0 if success else 1)
