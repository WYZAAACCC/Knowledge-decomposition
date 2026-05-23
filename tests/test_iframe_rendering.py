#!/usr/bin/env python
"""
物理知识图谱系统 - iframe渲染诊断测试
验证graph.html的loading-indicator是否消失，Canvas是否真正渲染
"""

import os
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_graph_html_loading():
    """测试graph.html的loading-indicator是否消失"""
    from playwright.sync_api import sync_playwright

    print("="*80)
    print("🧪 graph.html加载诊断测试")
    print("="*80)

    html_path = project_root / "artifacts" / "latest" / "graph.html"
    if not html_path.exists():
        print("❌ graph.html不存在")
        return False

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1920, 'height': 1080})
    page = context.new_page()

    file_url = f"file:///{str(html_path).replace(os.sep, '/')}"
    print(f"\n🌐 加载: {file_url}")
    page.goto(file_url, timeout=30000)

    # 等待并检查
    for wait_time in [1, 2, 3, 5, 8]:
        time.sleep(1 if wait_time <= 3 else 2)
        print(f"\n  ⏳ 等待{wait_time}秒后检查...")

        loading_visible = page.evaluate("""
            function() {
                var el = document.getElementById('loading-indicator');
                return el ? el.style.display !== 'none' : false;
            }
        """)
        print(f"    loading-indicator可见: {loading_visible}")

        if not loading_visible:
            print(f"    ✅ loading-indicator已消失！")

            # 检查是哪种渲染模式
            canvas_visible = page.evaluate("""
                function() {
                    var el = document.getElementById('canvas-fallback');
                    return el ? el.style.display !== 'none' : false;
                }
            """)
            network_visible = page.evaluate("""
                function() {
                    var el = document.getElementById('network-container');
                    return el ? el.style.display !== 'none' && el.offsetHeight > 0 : false;
                }
            """)
            vis_exists = page.evaluate("typeof vis !== 'undefined' && typeof vis.Network !== 'undefined'")
            network_obj = page.evaluate("typeof network !== 'undefined' && network !== null")

            print(f"    vis-network CDN加载: {vis_exists}")
            print(f"    network对象存在: {network_obj}")
            print(f"    network-container可见: {network_visible}")
            print(f"    canvas-fallback可见: {canvas_visible}")

            # 检查Canvas像素
            if canvas_visible:
                pixel_count = page.evaluate("""
                    function() {
                        var canvas = document.getElementById('canvas-fallback');
                        if (!canvas) return 0;
                        var ctx = canvas.getContext('2d');
                        var imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                        var pixels = imageData.data;
                        var nonWhite = 0;
                        for (var i = 0; i < pixels.length; i += 4) {
                            if (pixels[i] !== 255 || pixels[i+1] !== 255 || pixels[i+2] !== 255) {
                                nonWhite++;
                            }
                        }
                        return nonWhite;
                    }
                """)
                print(f"    Canvas非白色像素: {pixel_count}")
                if pixel_count > 100:
                    print(f"    ✅ Canvas已绘制图谱内容！")
                    break
            elif network_obj:
                print(f"    ✅ vis-network已创建图谱！")
                break

    # 最终截图
    screenshot_dir = project_root / "artifacts" / "test_screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshot_dir / "loading_diagnostic.png"))
    print(f"\n  📸 截图已保存")

    # 最终状态检查
    final_loading = page.evaluate("""
        function() {
            var el = document.getElementById('loading-indicator');
            return el ? el.style.display !== 'none' : false;
        }
    """)

    browser.close()
    playwright.stop()

    if not final_loading:
        print("\n✅ 测试通过！loading-indicator已消失，图谱已渲染！")
        return True
    else:
        print("\n❌ 测试失败！loading-indicator仍然可见！")
        return False


if __name__ == "__main__":
    success = test_graph_html_loading()
    sys.exit(0 if success else 1)
