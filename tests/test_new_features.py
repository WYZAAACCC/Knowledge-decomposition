from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})

    page.goto("http://localhost:8765/graph.html", timeout=30000)
    page.wait_for_timeout(12000)

    print("=== 验证中英双语标签 ===")
    labels = page.evaluate("""
        () => {
            return rawNodes.map(n => ({
                id: n.id,
                cn_title: n.cn_title,
                en_name: n.en_name,
                label: n.label,
                is_main: n.is_main
            }))
        }
    """)
    for n in labels[:5]:
        print(f"  {n['id']}: cn={n['cn_title']}, en={n['en_name']}, is_main={n['is_main']}")

    print("\n=== 验证主节点高光 ===")
    main_node = page.evaluate("""
        () => {
            var main = rawNodes.find(n => n.is_main);
            if (!main) return null;
            var visNode = visNodes.find(v => v.id === main.id);
            return {
                id: main.id,
                size: visNode ? visNode.size : 'N/A',
                fontSize: visNode ? visNode.font.size : 'N/A',
                borderWidth: visNode ? visNode.borderWidth : 'N/A',
                color: visNode ? visNode.color : 'N/A'
            }
        }
    """)
    print(f"  主节点: {main_node}")

    print("\n=== 验证悬停高亮推导链 ===")
    hover_result = page.evaluate("""
        () => {
            if (!network) return 'network not loaded';
            var testNodeId = rawNodes[0].id;
            applyHoverHighlight(testNodeId);
            var highlightedCount = 0;
            var dimmedCount = 0;
            visNodes.forEach(function(n) {
                if (n.opacity === 1.0 || n.opacity === undefined) highlightedCount++;
                else if (n.opacity === 0.2) dimmedCount++;
            });
            clearHoverHighlight();
            return {
                testNode: testNodeId,
                highlighted: highlightedCount,
                dimmed: dimmedCount,
                total: visNodes.length
            }
        }
    """)
    print(f"  悬停高亮结果: {hover_result}")

    print("\n=== 验证层级间距 ===")
    layout_info = page.evaluate("""
        () => {
            if (!network) return 'network not loaded';
            var positions = network.getPositions();
            var levels = {};
            for (var id in positions) {
                var node = rawNodes.find(n => n.id === id);
                if (node) {
                    var level = node.level;
                    if (!levels[level]) levels[level] = [];
                    levels[level].push(positions[id].y);
                }
            }
            var result = {};
            for (var l in levels) {
                var avgY = levels[l].reduce((a,b) => a+b, 0) / levels[l].length;
                result['level_'+l] = {avgY: Math.round(avgY), count: levels[l].length};
            }
            return result;
        }
    """)
    print(f"  层级位置: {layout_info}")

    print("\n=== 验证孤立节点 ===")
    isolated = page.evaluate("""
        () => {
            var connectedNodes = new Set();
            rawEdges.forEach(function(e) {
                connectedNodes.add(e.from);
                connectedNodes.add(e.to);
            });
            var isolated = rawNodes.filter(n => !connectedNodes.has(n.id));
            return {
                total: rawNodes.length,
                connected: connectedNodes.size,
                isolated: isolated.length,
                isolatedIds: isolated.map(n => n.id)
            }
        }
    """)
    print(f"  连通性: {isolated}")

    browser.close()
