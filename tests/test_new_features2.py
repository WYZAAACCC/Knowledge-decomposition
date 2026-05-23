from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    page.goto("http://localhost:8765/graph.html", timeout=30000)
    page.wait_for_timeout(12000)

    print("=== 1. 验证双语标签 ===")
    labels = page.evaluate("""
        () => {
            return rawNodes.slice(0, 5).map(n => ({
                id: n.id,
                cn: n.cn_title,
                en: n.en_name,
                label: n.label,
                hasNewline: n.label.indexOf('\\n') >= 0
            }))
        }
    """)
    for n in labels:
        print(f"  {n['id']}: cn={n['cn']}, en={n['en']}, hasNewline={n['hasNewline']}")

    print("\n=== 2. 验证所有节点都是box形状 ===")
    shapes = page.evaluate("""
        () => {
            var shapeCounts = {};
            visNodes.forEach(function(n) {
                shapeCounts[n.shape] = (shapeCounts[n.shape] || 0) + 1;
            });
            return shapeCounts;
        }
    """)
    print(f"  节点形状分布: {shapes}")

    print("\n=== 3. 验证主节点高光 ===")
    main_node = page.evaluate("""
        () => {
            var main = visNodes.find(n => n.id === rawNodes.find(r => r.is_main).id);
            return main ? {
                id: main.id,
                color: main.color,
                borderWidth: main.borderWidth,
                fontSize: main.font.size,
                margin: main.margin
            } : null
        }
    """)
    print(f"  主节点: {main_node}")

    print("\n=== 4. 验证层高滑块 ===")
    slider_exists = page.evaluate("""
        () => {
            var slider = document.getElementById('level-sep-slider');
            return slider ? {exists: true, value: slider.value, min: slider.min, max: slider.max} : {exists: false}
        }
    """)
    print(f"  层高滑块: {slider_exists}")

    spac_slider = page.evaluate("""
        () => {
            var slider = document.getElementById('node-spac-slider');
            return slider ? {exists: true, value: slider.value, min: slider.min, max: slider.max} : {exists: false}
        }
    """)
    print(f"  间距滑块: {spac_slider}")

    print("\n=== 5. 验证updateLayout函数 ===")
    update_exists = page.evaluate("typeof updateLayout === 'function'")
    print(f"  updateLayout函数: {'✅' if update_exists else '❌'}")

    print("\n=== 6. 验证物理模拟已禁用 ===")
    physics_status = page.evaluate("""
        () => {
            return {
                physicsEnabled: typeof physicsEnabled !== 'undefined' ? physicsEnabled : 'undefined',
                networkPhysics: network ? network.options.physics.enabled : 'no network'
            }
        }
    """)
    print(f"  物理状态: {physics_status}")

    print("\n=== 7. 验证箭头存在 ===")
    arrows = page.evaluate("""
        () => {
            var edgeCount = visEdges.length;
            var edgesWithArrows = visEdges.filter(e => e.arrows && e.arrows.to && e.arrows.to.enabled).length;
            return {total: edgeCount, withArrows: edgesWithArrows}
        }
    """)
    print(f"  边箭头: {arrows}")

    print("\n=== 8. 验证悬停高亮推导链 ===")
    hover_result = page.evaluate("""
        () => {
            var testNodeId = rawNodes[0].id;
            applyHoverHighlight(testNodeId);
            var highlighted = 0;
            var dimmed = 0;
            visNodes.forEach(function(n) {
                if (n.opacity === 0.2) dimmed++;
                else highlighted++;
            });
            var edgeHighlighted = 0;
            visEdges.forEach(function(e) {
                if (e.opacity === 0.08) ; else edgeHighlighted++;
            });
            clearHoverHighlight();
            return {
                testNode: testNodeId,
                highlightedNodes: highlighted,
                dimmedNodes: dimmed,
                highlightedEdges: edgeHighlighted
            }
        }
    """)
    print(f"  悬停高亮: {hover_result}")

    print("\n=== 9. 验证层级间距 ===")
    level_sep = page.evaluate("""
        () => {
            return network ? network.options.layout.hierarchical.levelSeparation : 'no network'
        }
    """)
    print(f"  当前层高: {level_sep}")

    print("\n=== 10. 验证孤立节点 ===")
    isolated = page.evaluate("""
        () => {
            var connectedNodes = new Set();
            rawEdges.forEach(function(e) {
                connectedNodes.add(e.from);
                connectedNodes.add(e.to);
            });
            var isolated = rawNodes.filter(n => !connectedNodes.has(n.id));
            return {total: rawNodes.length, connected: connectedNodes.size, isolated: isolated.length}
        }
    """)
    print(f"  连通性: {isolated}")

    browser.close()
