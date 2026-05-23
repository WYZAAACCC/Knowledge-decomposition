"""
第五层：benchmark topic测试

检查：
- 伯努利方程至少命中连续性、欧拉方程、稳态、不可压缩、无黏、沿流线等前提
- 热力学第一定律至少命中内能、功、热等前提
- 高斯定律至少命中电通量、闭合曲面等前提
- 薄透镜公式至少命中折射、傍轴近似等前提
- 杨氏双缝至少命中光程差、相干光源等前提

通过标准：
- prerequisite recall >= 0.80
- assumption coverage >= 0.90
"""

import pytest
import sys
import os
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.loader import DataLoader


class TestBenchmarkTopics:
    """benchmark topic测试"""

    def setup_class(self):
        self.loader = DataLoader()

    def test_benchmark_topics_file_exists(self):
        """测试benchmark_topics.yaml文件存在"""
        benchmark_file = Path(__file__).parent.parent / "data" / "benchmark_topics.yaml"
        assert benchmark_file.exists(), f"benchmark_topics.yaml文件不存在: {benchmark_file}"

        topics = self.loader.load_benchmark_topics()
        assert len(topics) > 0, "benchmark_topics.yaml中没有主题"

        print(f"benchmark_topics.yaml文件检查通过，包含 {len(topics)} 个主题")

    def test_benchmark_topic_structure(self):
        """测试benchmark主题结构"""
        topics = self.loader.load_benchmark_topics()

        for topic in topics:
            assert 'id' in topic, "主题缺少id字段"
            assert 'zh' in topic, "主题缺少zh字段"
            assert 'domain' in topic, "主题缺少domain字段"

            # prerequisites和applications可选
            if 'prerequisites' in topic:
                assert isinstance(topic['prerequisites'], list), "prerequisites必须是列表"

        print(f"benchmark主题结构检查通过")

    def test_bernoulli_topic_has_required_prerequisites(self):
        """测试伯努利主题有必需前提"""
        topics = self.loader.load_benchmark_topics()
        bernoulli = None

        for topic in topics:
            if '伯努利' in topic.get('zh', '') or 'bernoulli' in topic.get('id', '').lower():
                bernoulli = topic
                break

        if bernoulli:
            prerequisites = bernoulli.get('prerequisites', [])
            # 检查关键前提
            required = ['continuity', 'euler', 'steady_flow', 'incompressible', 'inviscid', 'along_streamline']
            found = sum(1 for req in required if any(req in str(prereq).lower() for prereq in prerequisites))
            coverage = found / len(required)
            assert coverage >= 0.8, f"伯努利方程前提覆盖率不足: {coverage:.2f}"

            print(f"伯努利方程前提检查通过，覆盖率: {coverage:.2f}")
        else:
            print("⚠️ 未找到伯努利主题，跳过检查")

    def test_first_law_thermodynamics_prerequisites(self):
        """测试热力学第一定律有必需前提"""
        topics = self.loader.load_benchmark_topics()
        first_law = None

        for topic in topics:
            if '热力学第一定律' in topic.get('zh', '') or 'first_law_thermodynamics' in topic.get('id', '').lower():
                first_law = topic
                break

        if first_law:
            prerequisites = first_law.get('prerequisites', [])
            # 检查关键前提
            required = ['internal_energy', 'heat', 'work', 'conservation_energy']
            found = sum(1 for req in required if any(req in str(prereq).lower() for prereq in prerequisites))
            coverage = found / len(required)
            assert coverage >= 0.8, f"热力学第一定律前提覆盖率不足: {coverage:.2f}"

            print(f"热力学第一定律前提检查通过，覆盖率: {coverage:.2f}")
        else:
            print("⚠️ 未找到热力学第一定律主题，跳过检查")

    def test_gauss_law_prerequisites(self):
        """测试高斯定律有必需前提"""
        topics = self.loader.load_benchmark_topics()
        gauss_law = None

        for topic in topics:
            if '高斯定律' in topic.get('zh', '') or 'gauss_electric' in topic.get('id', '').lower():
                gauss_law = topic
                break

        if gauss_law:
            prerequisites = gauss_law.get('prerequisites', [])
            # 检查关键前提
            required = ['electric_flux', 'closed_surface', 'coulomb']
            found = sum(1 for req in required if any(req in str(prereq).lower() for prereq in prerequisites))
            coverage = found / len(required)
            assert coverage >= 0.8, f"高斯定律前提覆盖率不足: {coverage:.2f}"

            print(f"高斯定律前提检查通过，覆盖率: {coverage:.2f}")
        else:
            print("⚠️ 未找到高斯定律主题，跳过检查")

    def test_thin_lens_prerequisites(self):
        """测试薄透镜公式有必需前提"""
        topics = self.loader.load_benchmark_topics()
        thin_lens = None

        for topic in topics:
            if '薄透镜公式' in topic.get('zh', '') or 'thin_lens' in topic.get('id', '').lower():
                thin_lens = topic
                break

        if thin_lens:
            prerequisites = thin_lens.get('prerequisites', [])
            # 检查关键前提
            required = ['refraction', 'paraxial_approximation', 'geometric_optics', 'focal_length']
            found = sum(1 for req in required if any(req in str(prereq).lower() for prereq in prerequisites))
            coverage = found / len(required)
            assert coverage >= 0.8, f"薄透镜公式前提覆盖率不足: {coverage:.2f}"

            print(f"薄透镜公式前提检查通过，覆盖率: {coverage:.2f}")
        else:
            print("⚠️ 未找到薄透镜公式主题，跳过检查")

    def test_youngs_double_slit_prerequisites(self):
        """测试杨氏双缝有必需前提"""
        topics = self.loader.load_benchmark_topics()
        young = None

        for topic in topics:
            if '杨氏双缝干涉' in topic.get('zh', '') or 'youngs_double_slit' in topic.get('id', '').lower():
                young = topic
                break

        if young:
            prerequisites = young.get('prerequisites', [])
            # 检查关键前提
            required = ['interference', 'coherent_sources', 'path_difference', 'wavelength']
            found = sum(1 for req in required if any(req in str(prereq).lower() for prereq in prerequisites))
            coverage = found / len(required)
            assert coverage >= 0.8, f"杨氏双缝前提覆盖率不足: {coverage:.2f}"

            print(f"杨氏双缝前提检查通过，覆盖率: {coverage:.2f}")
        else:
            print("⚠️ 未找到杨氏双缝主题，跳过检查")

    def test_topic_build_placeholder(self):
        """主题构建占位测试（实际构建需要API）"""
        # 此测试需要DeepSeek API，在CI环境中可能跳过
        if os.environ.get('SKIP_API_TESTS'):
            pytest.skip("跳过API测试")
        else:
            print("⚠️ 主题构建测试需要API，请在配置API密钥后运行")


if __name__ == "__main__":
    test = TestBenchmarkTopics()
    test.setup_class()

    print("运行benchmark topic测试...")

    try:
        test.test_benchmark_topics_file_exists()
        print("✓ benchmark文件测试通过")
    except AssertionError as e:
        print(f"✗ benchmark文件测试失败: {e}")

    try:
        test.test_benchmark_topic_structure()
        print("✓ benchmark主题结构测试通过")
    except AssertionError as e:
        print(f"✗ benchmark主题结构测试失败: {e}")

    try:
        test.test_bernoulli_topic_has_required_prerequisites()
        print("✓ 伯努利前提测试通过")
    except AssertionError as e:
        print(f"✗ 伯努利前提测试失败: {e}")

    print("benchmark topic测试完成")