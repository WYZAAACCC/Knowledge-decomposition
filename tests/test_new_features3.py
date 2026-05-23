from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto("http://localhost:8765/graph.html", timeout=30000)
    page.wait_for_timeout(12000)

    print("=== 1. 验证箭头存在 ===")
    arrows = page.evaluate("""
        () => {
            var total = visEdges.length;
            var withArrows = visEdges.filter(function(e) {
                return e.arrows && e.arrows.to && e.arrows.to.enabled !== false;
            }).length;
            var noArrows = visEdges.filter(function(e) {
                return !e.arrows || !e.arrows.to || e.arrows.to.enabled === false;
            }).length;
            return {total: total, withArrows: withArrows, noArrows: noArrows}
        }
    """)
    print(f"  边箭头: {arrows}")

    print("\n=== 2. 验证物理模拟状态 ===")
    physics = page.evaluate("""
        () => {
            return {
                physicsEnabled: typeof physicsEnabled !== 'undefined' ? physicsEnabled : 'undefined'
            }
        }
    """)
    print(f"  物理模拟: {physics}")

    print("\n=== 3. 验证悬停高亮 ===")
    hover = page.evaluate("""
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
                if (e.opacity !== 0.08) edgeHighlighted++;
            });
            clearHoverHighlight();
            return {testNode: testNodeId, highlightedNodes: highlighted, dimmedNodes: dimmed, highlightedEdges: edgeHighlighted}
        }
    """)
    print(f"  悬停高亮: {hover}")

    print("\n=== 4. 验证层高间距 ===")
    level_sep = page.evaluate("""
        () => {
            var positions = network.getPositions();
            var levels = {};
            for (var id in positions) {
                var node = rawNodes.find(function(n) {return n.id === id});
                if (node) {
                    if (!levels[node.level]) levels[node.level] = [];
                    levels[node.level].push(positions[id].y);
                }
            }
            var result = {};
            for (var l in levels) {
                var avgY = levels[l].reduce(function(a,b){return a+b},0) / levels[l].length;
                result['level_'+l] = {avgY: Math.round(avgY), count: levels[l].length};
            }
            return result;
        }
    """)
    print(f"  层级位置: {level_sep}")

    print("\n=== 5. 验证孤立节点 ===")
    isolated = page.evaluate("""
        () => {
            var connectedNodes = new Set();
            rawEdges.forEach(function(e) {
                connectedNodes.add(e.from);
                connectedNodes.add(e.to);
            });
            var isolated = rawNodes.filter(function(n) {return !connectedNodes.has(n.id)});
            return {total: rawNodes.length, connected: connectedNodes.size, isolated: isolated.length}
        }
    """)
    print(f"  连通性: {isolated}")

    print("\n=== 6. 验证节点躲避鼠标问题 ===")
    mouse_test = page.evaluate("""
        () => {
            var positions1 = network.getPositions();
            var ids = Object.keys(positions1);
            var node = ids[0];
            var pos1 = {x: positions1[node].x, y: positions1[node].y};
            return {initialPositions: pos1, physicsEnabled: physicsEnabled, nodeCount: ids.length}
        }
    """)
    print(f"  初始状态: {mouse_test}")

    # 模拟鼠标移动到节点上
    canvas = page.query_selector("#network-container canvas")
    if canvas:
        box = canvas.bounding_box()
        if box:
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            page.mouse.move(cx, cy)
            page.wait_for_timeout(500)
            page.mouse.move(cx + 10, cy + 10)
            page.wait_for_timeout(500)

    mouse_test2 = page.evaluate("""
        () => {
            var positions2 = network.getPositions();
            var ids = Object.keys(positions2);
            var node = ids[0];
            var pos2 = {x: positions2[node].x, y: positions2[node].y};
            return {afterMousePositions: pos2}
        }
    """)
    print(f"  鼠标移动后: {mouse_test2}")

    browser.close()
