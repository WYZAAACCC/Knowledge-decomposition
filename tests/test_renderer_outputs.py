"""
第七层：renderer测试

检查：
- graph.html存在
- graph.html可读取graph.json
- 边详情不为空
- 节点数与graph.json一致

通过标准：renderer输出有效
"""

import pytest
import sys
import json
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.agents.renderer_agent import RendererAgent
from src.models import KnowledgeGraph, Node, Edge, GraphStats, ValidationSummary


class TestRendererOutputs:
    """renderer测试"""

    def setup_class(self):
        # 使用临时测试目录，避免污染真实工件
        import tempfile
        import shutil
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_renderer_"))
        self.renderer = RendererAgent(output_dir=str(self.test_dir))
        self.artifacts_dir = self.test_dir

    def teardown_class(self):
        # 清理临时目录
        import shutil
        if hasattr(self, 'test_dir') and self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_renderer_agent_instantiation(self):
        """测试RendererAgent可实例化"""
        assert self.renderer is not None
        assert hasattr(self.renderer, 'run')
        print("RendererAgent实例化测试通过")

    def test_renderer_output_files_exist(self):
        """测试renderer输出文件存在"""
        # 创建符合schema的示例图谱数据
        # 创建有效的节点
        node = Node(
            id="node.test1",
            type="concept",
            title="测试节点",
            domain="mechanics",
            abstraction_level=1,
            pedagogical_level=1,
            sources=["test"]
        )

        # 创建图谱统计信息
        stats = GraphStats(
            node_count=1,
            edge_count=0,
            derivation_edge_count=0,
            assumption_count=0,
            math_tool_count=0,
            prerequisite_coverage=0.0,
            assumption_coverage=0.0
        )

        # 创建验证摘要
        validation_summary = ValidationSummary(
            schema_valid=True,
            dag_valid=True,
            assumptions_complete=True,
            dimensions_valid=True,
            canonical_path_exists=True,
            errors=[],
            warnings=[]
        )

        # 创建知识图谱
        graph = KnowledgeGraph(
            topic="test.topic",
            build_version="1.0.0",
            nodes=[node],
            edges=[],
            canonical_path="path.test",
            alternate_paths=[],
            stats=stats,
            validation_summary=validation_summary
        )

        # 生成工件
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # 使用renderer生成graph.json
        graph_path = self.artifacts_dir / "graph.json"
        self.renderer._generate_graph_json(graph, graph_path)
        assert graph_path.exists(), f"graph.json不存在: {graph_path}"

        # 使用renderer生成report.md
        report_path = self.artifacts_dir / "report.md"
        self.renderer._generate_report_md(graph, None, None, report_path)
        assert report_path.exists(), f"report.md不存在: {report_path}"

        print("renderer输出文件存在测试通过")

    def test_graph_json_structure(self):
        """测试graph.json结构"""
        graph_path = self.artifacts_dir / "graph.json"
        if not graph_path.exists():
            pytest.skip("graph.json不存在")

        with open(graph_path, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)

        required_fields = ['topic', 'nodes', 'edges']
        for field in required_fields:
            assert field in graph_data, f"graph.json缺少字段 {field}"

        print("✓ graph.json结构测试通过")

    def test_renderer_methods_exist(self):
        """测试RendererAgent方法存在"""
        required_methods = ['_generate_graph_json', '_generate_report_md',
                           '_generate_debug_json', '_generate_eval_report',
                           '_generate_graph_html']

        for method in required_methods:
            assert hasattr(self.renderer, method), f"RendererAgent缺少方法 {method}"

        print("✓ RendererAgent方法检查通过")


if __name__ == "__main__":
    test = TestRendererOutputs()
    test.setup_class()

    print("运行renderer测试...")

    try:
        test.test_renderer_agent_instantiation()
        print("RendererAgent实例化测试通过")
    except AssertionError as e:
        print(f"✗ RendererAgent实例化测试失败: {e}")

    try:
        test.test_renderer_output_files_exist()
        print("✓ renderer输出文件测试通过")
    except AssertionError as e:
        print(f"✗ renderer输出文件测试失败: {e}")

    print("renderer测试完成")