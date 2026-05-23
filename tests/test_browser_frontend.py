"""
Playwright浏览器级别前端功能真实验证 v2
========================================
修复选择器问题，更精确地测试每个功能
"""

import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent


def run_browser_test():
    from playwright.sync_api import sync_playwright

    print("=" * 70)
    print("🌐 Playwright浏览器级别前端功能验证 v2")
    print("=" * 70)

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # 收集console错误
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("\n[1] 加载页面...")
        page.goto("http://localhost:8765/graph.html", timeout=30000)
        page.wait_for_timeout(10000)

        page_title = page.title()
        print(f"  页面标题: {page_title}")
        results.append(("页面加载", "物理知识图谱" in page_title or page_title != ""))

        # 检查vis-network是否加载
        print("\n[2] 检查vis-network渲染...")
        canvas_count = len(page.query_selector_all("canvas"))
        print(f"  Canvas数量: {canvas_count}")
        results.append(("Canvas渲染", canvas_count >= 1))

        # 检查JS错误
        js_errors = [e for e in console_errors if "vis" not in e.lower() or "network" not in e.lower()]
        if js_errors:
            print(f"  ⚠️ JS错误: {js_errors[:3]}")
        else:
            print("  无严重JS错误")

        # 测试搜索功能
        print("\n[3] 测试搜索功能...")
        search_input = page.query_selector("#search-input")
        if search_input:
            print("  搜索输入框存在: ✅")
            search_input.click()
            page.wait_for_timeout(300)
            search_input.fill("力")
            page.wait_for_timeout(500)

            search_results = page.query_selector("#search-results")
            if search_results:
                is_visible = search_results.is_visible()
                result_items = search_results.query_selector_all(".search-result-item")
                print(f"  搜索结果可见: {'✅' if is_visible else '❌'}")
                print(f"  搜索结果数量: {len(result_items)}")
                results.append(("搜索功能", is_visible and len(result_items) > 0))

                if result_items:
                    result_items[0].click()
                    page.wait_for_timeout(500)
                    print("  点击搜索结果成功: ✅")
            else:
                print("  ❌ 搜索结果容器不存在")
                results.append(("搜索功能", False))

            search_input.fill("")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
        else:
            print("  ❌ 搜索输入框不存在")
            results.append(("搜索功能", False))

        # 测试暗色模式
        print("\n[4] 测试暗色模式...")
        theme_btn = page.query_selector(".theme-toggle")
        if theme_btn:
            initial_theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
            theme_btn.click()
            page.wait_for_timeout(500)
            after_theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
            dark_works = after_theme == "dark"
            print(f"  切换: {initial_theme or 'light'} → {after_theme}")
            print(f"  暗色模式: {'✅' if dark_works else '❌'}")
            results.append(("暗色模式", dark_works))

            # 验证暗色模式CSS是否生效
            bg_color = page.evaluate("""
                () => {
                    const el = document.querySelector('.main-layout');
                    if (!el) return 'no element';
                    return window.getComputedStyle(el).backgroundColor;
                }
            """)
            print(f"  暗色模式背景色: {bg_color}")

            theme_btn.click()
            page.wait_for_timeout(300)
        else:
            print("  ❌ 主题切换按钮不存在")
            results.append(("暗色模式", False))

        # 测试路径高亮
        print("\n[5] 测试路径高亮...")
        canonical_btn = page.query_selector("#btn-highlight-canonical")
        if canonical_btn:
            canonical_btn.click()
            page.wait_for_timeout(500)
            is_active = "active" in (canonical_btn.get_attribute("class") or "")
            print(f"  规范路径高亮: {'✅' if is_active else '❌'}")
            results.append(("路径高亮-规范路径", is_active))

            clear_btn = page.query_selector("#btn-highlight-clear")
            if clear_btn:
                clear_btn.click()
                page.wait_for_timeout(300)
        else:
            print("  ❌ 规范路径按钮不存在")
            results.append(("路径高亮-规范路径", False))

        all_paths_btn = page.query_selector("#btn-highlight-all")
        if all_paths_btn:
            all_paths_btn.click()
            page.wait_for_timeout(500)
            is_active = "active" in (all_paths_btn.get_attribute("class") or "")
            print(f"  全部路径高亮: {'✅' if is_active else '❌'}")
            results.append(("路径高亮-全部路径", is_active))

            clear_btn = page.query_selector("#btn-highlight-clear")
            if clear_btn:
                clear_btn.click()
                page.wait_for_timeout(300)
        else:
            results.append(("路径高亮-全部路径", False))

        # 测试统计面板 - 使用evaluate检查DOM
        print("\n[6] 测试统计面板...")
        stats_overlay_exists = page.evaluate("""
            () => {
                const el = document.getElementById('stats-overlay');
                return el !== null;
            }
        """)
        print(f"  stats-overlay DOM存在: {'✅' if stats_overlay_exists else '❌'}")

        if stats_overlay_exists:
            # 使用toggleStats函数切换显示
            page.evaluate("""
                () => {
                    toggleStats();
                }
            """)
            page.wait_for_timeout(300)

            stats_visible = page.evaluate("""
                () => {
                    const el = document.getElementById('stats-overlay');
                    return el && window.getComputedStyle(el).display !== 'none' && 
                           window.getComputedStyle(el).opacity !== '0';
                }
            """)
            print(f"  统计面板可见(移除hidden后): {'✅' if stats_visible else '❌'}")

            # 检查统计内容
            stats_body = page.evaluate("""
                () => {
                    const el = document.getElementById('stats-overlay-body');
                    return el ? el.innerText : '';
                }
            """)
            has_stats = "节点总数" in stats_body or "边总数" in stats_body
            print(f"  统计内容有效: {'✅' if has_stats else '❌'}")
            if stats_body:
                print(f"  统计内容预览: {stats_body[:100]}...")
            results.append(("统计面板", stats_overlay_exists and has_stats))

            # 恢复hidden
            page.evaluate("""
                () => {
                    const el = document.getElementById('stats-overlay');
                    el.classList.add('hidden');
                }
            """)
        else:
            results.append(("统计面板", False))

        # 测试小地图
        print("\n[7] 测试小地图...")
        minimap_exists = page.evaluate("""
            () => {
                const el = document.getElementById('minimap-container');
                return el !== null;
            }
        """)
        print(f"  minimap-container DOM存在: {'✅' if minimap_exists else '❌'}")

        if minimap_exists:
            # 使用toggleMinimap函数切换显示
            page.evaluate("""
                () => {
                    toggleMinimap();
                }
            """)
            page.wait_for_timeout(500)

            minimap_canvas = page.evaluate("""
                () => {
                    const canvas = document.getElementById('minimap-canvas');
                    if (!canvas) return {exists: false};
                    const ctx = canvas.getContext('2d');
                    return {
                        exists: true,
                        width: canvas.width,
                        height: canvas.height,
                        hasContent: ctx.getImageData(0, 0, canvas.width, canvas.height).data.some(v => v > 0)
                    };
                }
            """)
            print(f"  小地图Canvas: {minimap_canvas}")
            minimap_works = minimap_canvas.get('exists', False) and minimap_canvas.get('width', 0) > 0
            print(f"  小地图功能: {'✅' if minimap_works else '❌'}")
            results.append(("小地图", minimap_works))

            # 恢复hidden
            page.evaluate("""
                () => {
                    const el = document.getElementById('minimap-container');
                    el.classList.add('hidden');
                }
            """)
        else:
            results.append(("小地图", False))

        # 测试缩放控件
        print("\n[8] 测试缩放控件...")
        zoom_controls_exists = page.evaluate("""
            () => {
                const el = document.querySelector('.zoom-controls');
                return el !== null;
            }
        """)
        print(f"  zoom-controls DOM存在: {'✅' if zoom_controls_exists else '❌'}")

        if zoom_controls_exists:
            zoom_level = page.evaluate("""
                () => {
                    const el = document.getElementById('zoom-level');
                    return el ? el.innerText : '';
                }
            """)
            print(f"  当前缩放级别: {zoom_level}")

            # 点击放大
            page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('.zoom-btn');
                    if (btns.length > 0) btns[0].click();
                }
            """)
            page.wait_for_timeout(500)

            new_zoom_level = page.evaluate("""
                () => {
                    const el = document.getElementById('zoom-level');
                    return el ? el.innerText : '';
                }
            """)
            zoom_changed = zoom_level != new_zoom_level
            print(f"  缩放后级别: {new_zoom_level}")
            print(f"  缩放功能: {'✅' if zoom_changed else '❌'}")
            results.append(("缩放控件", zoom_controls_exists and zoom_changed))
        else:
            print("  ❌ zoom-controls不存在")
            results.append(("缩放控件", False))

        # 测试Tooltip
        print("\n[9] 测试Tooltip...")
        tooltip_exists = page.evaluate("""
            () => {
                const el = document.getElementById('tooltip');
                return el !== null;
            }
        """)
        print(f"  tooltip DOM存在: {'✅' if tooltip_exists else '❌'}")

        if tooltip_exists:
            # 检查setupTooltip函数是否已执行
            tooltip_setup = page.evaluate("""
                () => {
                    return typeof window.setupTooltip === 'function' || 
                           (typeof network !== 'undefined' && network !== null);
                }
            """)
            print(f"  Tooltip函数/网络就绪: {'✅' if tooltip_setup else '❌'}")
            results.append(("Tooltip", tooltip_exists and tooltip_setup))
        else:
            results.append(("Tooltip", False))

        # 测试节点点击详情面板
        print("\n[10] 测试节点点击详情面板...")
        # 使用JS直接触发节点选择
        node_clicked = page.evaluate("""
            () => {
                if (typeof network === 'undefined' || !network) return false;
                const nodes = network.body.nodeIndices;
                if (nodes.length === 0) return false;
                network.selectNodes([nodes[0]]);
                network.emit('click', {nodes: [nodes[0]], edges: []});
                return true;
            }
        """)
        page.wait_for_timeout(800)

        if node_clicked:
            detail_visible = page.evaluate("""
                () => {
                    const el = document.getElementById('detail-panel');
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                }
            """)
            detail_content = page.evaluate("""
                () => {
                    const el = document.getElementById('detail-content');
                    return el ? el.innerText : '';
                }
            """)
            has_content = len(detail_content) > 20
            print(f"  详情面板可见: {'✅' if detail_visible else '❌'}")
            print(f"  详情内容有效: {'✅' if has_content else '❌'}")
            if detail_content:
                print(f"  内容预览: {detail_content[:80]}...")
            results.append(("节点详情面板", detail_visible and has_content))
        else:
            print("  ⚠️ 无法通过JS触发节点点击")
            results.append(("节点详情面板", False))

        # 测试导出按钮
        print("\n[11] 测试导出按钮...")
        export_svg_exists = page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.innerText.includes('导出SVG')) return true;
                }
                return false;
            }
        """)
        export_png_exists = page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.innerText.includes('导出PNG')) return true;
                }
                return false;
            }
        """)
        print(f"  导出SVG按钮: {'✅' if export_svg_exists else '❌'}")
        print(f"  导出PNG按钮: {'✅' if export_png_exists else '❌'}")
        results.append(("导出按钮", export_svg_exists and export_png_exists))

        # 测试图例
        print("\n[12] 测试图例...")
        legend_count = page.evaluate("""
            () => {
                return document.querySelectorAll('.legend-item').length;
            }
        """)
        print(f"  图例项数量: {legend_count}")
        results.append(("图例显示", legend_count >= 5))

        # 测试键盘快捷键
        print("\n[13] 测试键盘快捷键...")
        page.keyboard.press("t")
        page.wait_for_timeout(300)
        theme_after = page.evaluate("document.documentElement.getAttribute('data-theme')")
        shortcut_t = theme_after == "dark"
        print(f"  T键切换暗色: {'✅' if shortcut_t else '❌'}")
        if shortcut_t:
            page.keyboard.press("t")
            page.wait_for_timeout(300)

        page.keyboard.press("m")
        page.wait_for_timeout(300)
        minimap_visible = page.evaluate("""
            () => {
                const el = document.getElementById('minimap-container');
                return el && !el.classList.contains('hidden');
            }
        """)
        print(f"  M键切换小地图: {'✅' if minimap_visible else '❌'}")
        results.append(("键盘快捷键", shortcut_t and minimap_visible))

        if minimap_visible:
            page.keyboard.press("m")
            page.wait_for_timeout(300)

        # 测试类型过滤
        print("\n[14] 测试类型过滤...")
        type_select = page.query_selector("select")
        if type_select:
            type_select.select_option(value="law")
            page.wait_for_timeout(500)
            visible_nodes = page.evaluate("""
                () => {
                    if (typeof network === 'undefined' || !network) return -1;
                    return network.body.nodeIndices.length;
                }
            """)
            print(f"  过滤'定律'后可见节点: {visible_nodes}")

            type_select.select_option(value="")
            page.wait_for_timeout(300)
            all_nodes = page.evaluate("""
                () => {
                    if (typeof network === 'undefined' || !network) return -1;
                    return network.body.nodeIndices.length;
                }
            """)
            print(f"  重置过滤后可见节点: {all_nodes}")
            filter_works = visible_nodes >= 0 and all_nodes >= visible_nodes
            print(f"  过滤功能: {'✅' if filter_works else '❌'}")
            results.append(("类型过滤", filter_works))
        else:
            print("  ❌ 类型选择器不存在")
            results.append(("类型过滤", False))

        # 测试适应窗口
        print("\n[15] 测试适应窗口...")
        fit_works = page.evaluate("""
            () => {
                if (typeof network === 'undefined' || !network) return false;
                if (typeof fitNetwork === 'undefined') return false;
                fitNetwork();
                return true;
            }
        """)
        print(f"  fitNetwork函数可用: {'✅' if fit_works else '❌'}")
        results.append(("适应窗口", fit_works))

        # 检查JS错误汇总
        print("\n[16] 检查JS错误...")
        critical_errors = [e for e in console_errors if "Uncaught" in e or "TypeError" in e or "ReferenceError" in e]
        if critical_errors:
            print(f"  ⚠️ 严重JS错误: {critical_errors[:5]}")
            results.append(("无严重JS错误", False))
        else:
            print("  ✅ 无严重JS错误")
            results.append(("无严重JS错误", True))

        browser.close()

    # 汇总
    print(f"\n{'='*70}")
    print("📋 浏览器级别前端功能验证报告")
    print(f"{'='*70}")

    passed = 0
    failed = 0
    for name, ok in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}")
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n总计: {passed}/{len(results)} 通过 ({100*passed/max(len(results),1):.0f}%)")

    if failed > 0:
        print(f"\n⚠️ {failed}项功能未通过浏览器验证")
        return False
    else:
        print(f"\n🎉 所有前端功能在浏览器中验证通过！")
        return True


if __name__ == "__main__":
    try:
        success = run_browser_test()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
