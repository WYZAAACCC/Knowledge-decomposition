#!/usr/bin/env python
"""
测试RendererAgent生成HTML文件的功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.renderer_agent import RendererAgent
from src.models import KnowledgeGraph, Node, Edge, NodeType, EdgeType, Domain, GraphStats, ValidationSummary


def test_renderer_html():
    """测试RendererAgent生成HTML文件"""
    # 创建一个简单的测试图谱
    nodes = [
        Node(
            id="test.topic",
            type=NodeType.CONCEPT,
            title="测试主题",
            statement="这是一个测试主题",
            formula_latex="E=mc^2",
            domain=Domain.MECHANICS,
            abstraction_level=1,
            pedagogical_level=1,
            sources=["test_source"]
        ),
        Node(
            id="test.node1",
            type=NodeType.EQUATION,
            title="测试节点1",
            statement="这是测试节点1",
            formula_latex="F=ma",
            domain=Domain.MECHANICS,
            abstraction_level=1,
            pedagogical_level=1,
            sources=["test_source"]
        ),
        Node(
            id="test.node2",
            type=NodeType.LAW,
            title="测试节点2",
            statement="这是测试节点2",
            domain=Domain.MECHANICS,
            abstraction_level=1,
            pedagogical_level=1,
            sources=["test_source"]
        )
    ]
    
    edges = [
        Edge(
            id="edge.test.derives_from.node1",
            type=EdgeType.DERIVES_FROM,
            from_="test.topic",
            to="test.node1",
            path_id="path.test.1",
            assumptions=["假设1"],
            derivation_steps=["步骤1", "步骤2"]
        ),
        Edge(
            id="edge.test.requires.node2",
            type=EdgeType.REQUIRES,
            from_="test.node1",
            to="test.node2",
            path_id="path.test.1"
        )
    ]
    
    graph = KnowledgeGraph(
        topic="test.topic",
        build_version="1.0.0",
        nodes=nodes,
        edges=edges,
        canonical_path="path.test.1",
        alternate_paths=[],
        stats=GraphStats(
            node_count=3,
            edge_count=2,
            derivation_edge_count=1,
            assumption_count=1,
            math_tool_count=0
        ),
        validation_summary=ValidationSummary(
            schema_valid=True,
            dag_valid=True,
            assumptions_complete=True,
            dimensions_valid=True,
            canonical_path_exists=True
        )
    )
    
    # 创建RendererAgent
    renderer = RendererAgent(output_dir="artifacts/test")
    
    # 测试生成HTML文件
    html_path = Path("artifacts/test/graph.html")
    try:
        renderer._generate_graph_html(graph, html_path)
        print(f"[OK] 成功生成HTML文件: {html_path}")
        # 检查文件是否存在
        if html_path.exists():
            print(f"[OK] HTML文件存在，大小: {html_path.stat().st_size} 字节")
        else:
            print(f"[FAIL] HTML文件不存在")
    except Exception as e:
        print(f"[FAIL] 生成HTML文件时出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_renderer_html()
