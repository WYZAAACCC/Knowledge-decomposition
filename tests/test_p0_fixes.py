"""
P0 修复验证测试

覆盖 Fix 0, 1, 2, 5, 11, 12 的核心验收标准。
"""
import json
import sys
from pathlib import Path

import pytest

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from src.models import (
    Node, Edge, KnowledgeGraph, GraphStats, ValidationSummary,
    BuildMetadata, NodeType, EdgeType, Domain, NodeStatus, TheoryContext,
    TrustLevel, SourceRef, ProofStep,
)
from src.validators.placeholder_validator import (
    PlaceholderValidator, contains_placeholder, PLACEHOLDER_PATTERNS,
)
from src.agents.verifier_agent import VerifierAgent, VerificationOutput


def _make_test_graph():
    """创建测试用的小型知识图谱"""
    nodes = [
        Node(id="concept.force", type=NodeType.CONCEPT, title="力", domain=Domain.MECHANICS, abstraction_level=0, pedagogical_level=1, sources=["seed/test"], trust_level=TrustLevel.SEED),
        Node(id="concept.mass", type=NodeType.CONCEPT, title="质量", domain=Domain.MECHANICS, abstraction_level=0, pedagogical_level=1, sources=["seed/test"], trust_level=TrustLevel.SEED),
        Node(id="concept.acceleration", type=NodeType.CONCEPT, title="加速度", domain=Domain.MECHANICS, abstraction_level=0, pedagogical_level=1, sources=["seed/test"], trust_level=TrustLevel.SEED),
        Node(id="law.newton_second", type=NodeType.LAW, title="牛顿第二定律", domain=Domain.MECHANICS, abstraction_level=2, pedagogical_level=2, sources=["seed/test"], trust_level=TrustLevel.SEED),
        Node(id="equation.bernoulli", type=NodeType.EQUATION, title="伯努利方程", formula_latex="p + 1/2 \\rho v^2 + \\rho g h = C", domain=Domain.MECHANICS, abstraction_level=5, pedagogical_level=5, sources=["seed/test"], trust_level=TrustLevel.SEED),
    ]
    node_ids = {n.id for n in nodes}

    edges = [
        Edge(id="edge.law.derives.concept_force", type=EdgeType.DERIVES, from_="concept.force", to="law.newton_second", path_id="path.newton_1", derivation_steps=["力定义"], trust_level=TrustLevel.SEED),
        Edge(id="edge.law.derives.concept_mass", type=EdgeType.DERIVES, from_="concept.mass", to="law.newton_second", path_id="path.newton_1", derivation_steps=["质量定义"], trust_level=TrustLevel.SEED),
        Edge(id="edge.law.derives.acceleration", type=EdgeType.DERIVES, from_="concept.acceleration", to="law.newton_second", path_id="path.newton_1", derivation_steps=["加速度定义"], trust_level=TrustLevel.SEED),
    ]

    stats = GraphStats(
        node_count=len(nodes), edge_count=len(edges),
        derivation_edge_count=3, assumption_count=0, math_tool_count=0,
    )
    vs = ValidationSummary(schema_valid=True, dag_valid=True, assumptions_complete=False, dimensions_valid=True, canonical_path_exists=True)

    return KnowledgeGraph(
        topic="law.newton_second", build_version="0.1.0",
        nodes=nodes, edges=edges, canonical_path="path.newton_1",
        stats=stats, validation_summary=vs,
    )


# ===== Fix 0: Edge Direction Tests =====

class TestEdgeDirection:
    """Fix 0: 统一边方向"""

    def test_edge_from_is_prerequisite(self):
        """from = prerequisite/premise/lower-level"""
        graph = _make_test_graph()
        newton_edge = [e for e in graph.edges if e.to == "law.newton_second"][0]
        assert newton_edge.from_ in {"concept.force", "concept.mass", "concept.acceleration"}
        assert newton_edge.to == "law.newton_second"
        # from是基础概念（低层级），to是推导结论（高层级）
        from_node = [n for n in graph.nodes if n.id == newton_edge.from_][0]
        to_node = [n for n in graph.nodes if n.id == newton_edge.to][0]
        assert from_node.abstraction_level < to_node.abstraction_level

    def test_derives_type_exists(self):
        """derives类型已添加为推荐类型"""
        assert EdgeType.DERIVES.value == "derives"
        assert EdgeType.DERIVES in {EdgeType.DERIVES, EdgeType.DERIVES_FROM}


# ===== Fix 2: Trust Model Tests =====

class TestTrustModel:
    """Fix 2: 信任模型"""

    def test_trust_level_values(self):
        """TrustLevel包含所有定义的值"""
        values = {t.value for t in TrustLevel}
        assert "verified" in values
        assert "seed" in values
        assert "llm_proposal" in values
        assert "auto_generated" in values
        assert "unknown" in values

    def test_node_has_trust_level(self):
        """节点必须包含trust_level"""
        node = Node(id="concept.test", type=NodeType.CONCEPT, title="测试", domain=Domain.MECHANICS, abstraction_level=0, pedagogical_level=1, sources=["test"], trust_level=TrustLevel.SEED)
        assert node.trust_level == TrustLevel.SEED
        assert node.verified is False

    def test_source_ref_creation(self):
        """SourceRef模型"""
        sr = SourceRef(source_type="textbook", source_id="ISBN-xxx", title="大学物理", confidence=0.95)
        assert sr.source_type == "textbook"
        assert sr.confidence == 0.95

    def test_llm_proposal_marked_correctly(self):
        """LLM提议必须标记为llm_proposal"""
        node = Node(id="concept.llm_test", type=NodeType.CONCEPT, title="LLM生成", domain=Domain.MECHANICS, abstraction_level=0, pedagogical_level=1, sources=["llm"], trust_level=TrustLevel.LLM_PROPOSAL, verified=False)
        assert node.trust_level == TrustLevel.LLM_PROPOSAL
        assert not node.verified


# ===== Fix 5: PlaceholderValidator Tests =====

class TestPlaceholderValidator:
    """Fix 5: 占位内容验证"""

    def test_detect_todo_placeholder(self):
        assert contains_placeholder("待补充")
        assert contains_placeholder("TODO: implement")
        assert contains_placeholder("N/A")
        assert contains_placeholder("假设条件待补充")

    def test_valid_content_passes(self):
        assert not contains_placeholder("伯努利方程")
        assert not contains_placeholder("流体不可压缩")
        assert not contains_placeholder("p + 1/2 ρv² + ρgh = C")

    def test_placeholder_in_edge_fails(self):
        validator = PlaceholderValidator()
        graph = _make_test_graph()
        # 添加带占位的边
        bad_edge = Edge(
            id="edge.test.derives.test1", type=EdgeType.DERIVES,
            from_="concept.force", to="equation.bernoulli",
            path_id="path.test",
            assumptions=["待补充"], trust_level=TrustLevel.SEED,
        )
        graph.edges.append(bad_edge)
        result = validator.validate(graph)
        assert not result["passed"]
        assert len(result["errors"]) >= 1

    def test_clean_graph_passes(self):
        validator = PlaceholderValidator()
        graph = _make_test_graph()
        result = validator.validate(graph)
        assert result["passed"]
        assert len(result["errors"]) == 0

    def test_verifier_includes_placeholder(self):
        """PlaceholderValidator已集成到VerifierAgent"""
        verifier = VerifierAgent()
        assert hasattr(verifier, 'placeholder_validator')


# ===== Fix 12: BuildMetadata Tests =====

class TestBuildMetadata:
    """Fix 12: BuildMetadata类型"""

    def test_build_metadata_model(self):
        bm = BuildMetadata(
            schema_version="0.1.0",
            build_timestamp="2026-01-01T00:00:00Z",
            build_duration_seconds=1.5,
            pipeline_version="0.1.0",
            offline=True,
            strict=True,
            error_count=0,
            warning_count=0,
        )
        assert bm.strict is True
        assert bm.offline is True
        assert bm.error_count == 0

    def test_knowledge_graph_accepts_build_metadata(self):
        graph = _make_test_graph()
        bm = BuildMetadata(schema_version="0.1.0", build_timestamp="2026-01-01T00:00:00Z")
        graph.build_metadata = bm
        assert graph.build_metadata.strict is True


# ===== ProofStep Tests =====

class TestProofStep:
    """改进 1: 证明步骤"""

    def test_proof_step_creation(self):
        ps = ProofStep(
            id="proofstep.test.euler_to_bernoulli",
            title="积分欧拉方程得到伯努利方程",
            input_node_ids=["equation.euler_fluid"],
            output_node_id="equation.bernoulli",
            operation="integration",
            assumption_ids=["assumption.steady_flow", "assumption.incompressible_flow"],
            explanation_zh="沿流线积分欧拉方程",
        )
        assert ps.operation == "integration"
        assert len(ps.assumption_ids) == 2
        assert ps.trust_level == TrustLevel.SEED
        assert not ps.verified


# ===== Edge Model Tests =====

class TestEdgeModel:
    """Fix 6: Edge假设注册表"""

    def test_edge_has_assumption_ids(self):
        edge = Edge(
            id="edge.test.derives.test1", type=EdgeType.DERIVES,
            from_="concept.force", to="equation.bernoulli",
            path_id="path.test",
            assumption_ids=["assumption.steady_flow"],
            trust_level=TrustLevel.SEED,
        )
        assert len(edge.assumption_ids) == 1
        assert edge.assumption_ids[0] == "assumption.steady_flow"

    def test_edge_has_proof_step_ids(self):
        edge = Edge(
            id="edge.test.derives.test2", type=EdgeType.DERIVES,
            from_="concept.mass", to="equation.bernoulli",
            path_id="path.test2",
            proof_step_ids=["proofstep.test.1"],
            trust_level=TrustLevel.SEED,
        )
        assert len(edge.proof_step_ids) == 1

    def test_edge_has_trust_level(self):
        edge = Edge(
            id="edge.test.derives.test3", type=EdgeType.DERIVES,
            from_="concept.acceleration", to="equation.bernoulli",
            path_id="path.test3",
            trust_level=TrustLevel.LLM_PROPOSAL,
        )
        assert edge.trust_level == TrustLevel.LLM_PROPOSAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
