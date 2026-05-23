#!/usr/bin/env python
"""
简化测试renderer_agent.py是否能正确生成graph.html
"""

from pathlib import Path
from src.agents.renderer_agent import RendererAgent

# 模拟一个简单的图谱对象
class MockGraph:
    def __init__(self):
        self.topic = "eq.bernoulli"
        self.nodes = [
            type('Node', (), {
                'id': 'eq.bernoulli',
                'type': 'equation',
                'title': '伯努利方程',
                'statement': '流体力学中的能量守恒定律',
                'formula_latex': 'p + \\frac{1}{2}\\rho v^2 + \\rho g h = \\text{常数}',
                'domain': 'mechanics'
            })(),
            type('Node', (), {
                'id': 'eq.continuity',
                'type': 'equation',
                'title': '连续性方程',
                'statement': '质量守恒在流体中的体现',
                'domain': 'mechanics'
            })(),
            type('Node', (), {
                'id': 'assumption.steady_flow',
                'type': 'assumption',
                'title': '稳态流动',
                'domain': 'mechanics'
            })(),
            type('Node', (), {
                'id': 'assumption.incompressible',
                'type': 'assumption',
                'title': '不可压缩流体',
                'domain': 'mechanics'
            })()
        ]
        self.edges = [
            type('Edge', (), {
                'id': 'edge.bernoulli.derives_from.continuity',
                'type': 'derives_from',
                'from_': 'eq.bernoulli',
                'to': 'eq.continuity',
                'path_id': 'path.eq.bernoulli.canonical',
                'assumptions': ['steady_flow', 'incompressible'],
                'derivation_steps': [
                    '从欧拉方程出发',
                    '沿流线方向投影',
                    '对路径积分',
                    '整理得到压强项、位能项和动能项之和守恒'
                ],
                'math_used': ['line_integral']
            })(),
            type('Edge', (), {
                'id': 'edge.bernoulli.requires.assumption_steady_flow',
                'type': 'requires',
                'from_': 'eq.bernoulli',
                'to': 'assumption.steady_flow',
                'path_id': 'path.eq.bernoulli.canonical'
            })(),
            type('Edge', (), {
                'id': 'edge.bernoulli.requires.assumption_incompressible',
                'type': 'requires',
                'from_': 'eq.bernoulli',
                'to': 'assumption.incompressible',
                'path_id': 'path.eq.bernoulli.canonical'
            })()
        ]
        self.canonical_path = 'path.eq.bernoulli.canonical'
        self.alternate_paths = []
    
    def model_dump(self, by_alias=True):
        return {
            'topic': self.topic,
            'nodes': [vars(node) for node in self.nodes],
            'edges': [vars(edge) for edge in self.edges],
            'canonical_path': self.canonical_path,
            'alternate_paths': self.alternate_paths
        }

if __name__ == "__main__":
    # 创建模拟图谱
    test_graph = MockGraph()
    
    # 初始化renderer
    renderer = RendererAgent(output_dir="artifacts/latest")
    
    # 直接测试_generate_graph_html方法
    print("开始测试renderer...")
    output_path = Path("artifacts/latest/graph.html")
    
    try:
        renderer._generate_graph_html(test_graph, output_path)
        print("\n✓ graph.html 生成成功!")
        print(f"  大小: {output_path.stat().st_size} 字节")
    except Exception as e:
        print(f"\n✗ 生成失败: {e}")
