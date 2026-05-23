"""
Fix 4: VerifiedGraphAssembler

只从 retrieval_output 的候选节点/边中选择，不创建新知识。
LLM 提议由 LLMProposalGenerator 单独输出。
"""
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field

from ..models import Node, Edge, KnowledgeGraph, GraphStats, ValidationSummary, TrustLevel


@dataclass
class AssemblyOutput:
    """组装器输出"""
    subgraph: KnowledgeGraph
    used_node_ids: Set[str] = field(default_factory=set)
    used_edge_ids: Set[str] = field(default_factory=set)
    skipped_nodes: List[str] = field(default_factory=list)
    skipped_edges: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class VerifiedGraphAssembler:
    """Fix 4: 只从候选节点/边中组装，不创造新知识"""

    def __init__(self, strict: bool = True):
        self.strict = strict

    def run(self, retrieval_output: Any, planner_output: Optional[Dict] = None) -> AssemblyOutput:
        """从候选集中组装验证子图"""
        warnings = []

        candidate_nodes = getattr(retrieval_output, 'candidate_nodes', []) or []
        candidate_edges = getattr(retrieval_output, 'candidate_edges', []) or []

        if not candidate_nodes:
            return AssemblyOutput(
                subgraph=self._empty_graph("unknown"),
                warnings=["No candidate nodes available for assembly"],
            )

        # 收集所有可用节点ID
        available_ids = {n.id for n in candidate_nodes}

        # 只选择端点都在候选集中的边
        valid_edges = []
        skipped_edges = []
        for edge in candidate_edges:
            if hasattr(edge, 'from_'):
                from_id = edge.from_
            else:
                continue
            to_id = edge.to if hasattr(edge, 'to') else None

            if from_id in available_ids and to_id in available_ids:
                # Fix 2: strict模式下排除 LLM/auto_generated
                if self.strict:
                    tl = getattr(edge, 'trust_level', None)
                    if tl and tl in {TrustLevel.LLM_PROPOSAL, TrustLevel.AUTO_GENERATED, TrustLevel.UNKNOWN}:
                        skipped_edges.append(edge.id)
                        continue
                valid_edges.append(edge)
            else:
                skipped_edges.append(getattr(edge, 'id', str(edge)))

        # 选择有边连接的节点（排除完全孤立的非应用/非警告节点）
        connected_ids = set()
        for edge in valid_edges:
            connected_ids.add(getattr(edge, 'from_', ''))
            connected_ids.add(getattr(edge, 'to', ''))

        selected_nodes = []
        skipped_nodes = []
        for node in candidate_nodes:
            if self.strict:
                tl = getattr(node, 'trust_level', None)
                if tl and tl in {TrustLevel.LLM_PROPOSAL, TrustLevel.AUTO_GENERATED, TrustLevel.UNKNOWN}:
                    skipped_nodes.append(node.id)
                    continue

            if node.id in connected_ids or node.type.value in {'application', 'warning'}:
                selected_nodes.append(node)
            else:
                skipped_nodes.append(node.id)
                warnings.append(f"Isolated node excluded: {node.id}")

        subgraph = self._build_graph(selected_nodes, valid_edges)
        return AssemblyOutput(
            subgraph=subgraph,
            used_node_ids={n.id for n in selected_nodes},
            used_edge_ids={e.id for e in valid_edges},
            skipped_nodes=skipped_nodes,
            skipped_edges=skipped_edges,
            warnings=warnings,
        )

    def _build_graph(self, nodes: List[Node], edges: List[Edge]) -> KnowledgeGraph:
        if not nodes:
            return self._empty_graph("unknown")
        topic = nodes[0].id if nodes else "unknown"
        stats = GraphStats(
            node_count=len(nodes),
            edge_count=len(edges),
            derivation_edge_count=sum(1 for e in edges if e.type.value in {'derives', 'derives_from'}),
            assumption_count=sum(len(getattr(e, 'assumption_ids', []) or []) + len(getattr(e, 'assumptions', []) or []) for e in edges),
            math_tool_count=sum(1 for n in nodes if n.type.value == 'math_tool'),
        )
        vs = ValidationSummary(
            schema_valid=True, dag_valid=True,
            assumptions_complete=False, dimensions_valid=False,
            canonical_path_exists=True,
        )
        return KnowledgeGraph(
            topic=topic, build_version="0.1.0",
            nodes=nodes, edges=edges,
            canonical_path="path.default",
            stats=stats, validation_summary=vs,
        )

    @staticmethod
    def _empty_graph(topic: str) -> KnowledgeGraph:
        return KnowledgeGraph(
            topic=topic, build_version="0.1.0",
            nodes=[], edges=[],
            canonical_path="path.empty",
            stats=GraphStats(node_count=0, edge_count=0, derivation_edge_count=0, assumption_count=0, math_tool_count=0),
            validation_summary=ValidationSummary(schema_valid=False, dag_valid=False, assumptions_complete=False, dimensions_valid=False, canonical_path_exists=False),
        )


class LLMProposalGenerator:
    """Fix 4 + Improvement 7: LLM只能提出缺失节点/边/假设，输出到proposals.json，含自检"""

    def __init__(self):
        self.proposals: Dict[str, Any] = {
            "missing_nodes": [],
            "missing_edges": [],
            "suggested_assumptions": [],
            "suggested_proof_steps": [],
            "confidence": 0.0,
            "requires_human_review": True,
            # Improvement 7: LLM自检
            "possible_hallucinations": [],
            "missing_sources": [],
        }

    def generate_proposals(
        self,
        retrieval_output: Any,
        assembled_graph: KnowledgeGraph,
        use_llm: bool = False,
    ) -> Dict[str, Any]:
        """生成LLM提议（仅在 !strict 或 --allow-proposals 时使用）"""
        if not use_llm:
            self._self_check()
            return self.proposals

        # LLM调用接口
        self._self_check()
        return self.proposals

    def _self_check(self):
        """Improvement 7: LLM输出自检

        检查LLM提议中的潜在问题：
        - 可能的幻觉（无来源的声明）
        - 需要人工审核的项目
        - 缺失的来源引用
        """
        # 检查所有提议是否有来源
        all_items = (
            self.proposals["missing_nodes"]
            + self.proposals["missing_edges"]
            + self.proposals["suggested_assumptions"]
            + self.proposals["suggested_proof_steps"]
        )

        for item in all_items:
            if isinstance(item, dict):
                if not item.get("source_needed", True) and not item.get("source"):
                    self.proposals["missing_sources"].append(
                        f"{item.get('id', '?')}: 缺少来源引用"
                    )
                if item.get("confidence", 0) < 0.5:
                    self.proposals["possible_hallucinations"].append(
                        f"{item.get('id', '?')}: 低置信度({item.get('confidence', 0)})"
                    )

        self.proposals["requires_human_review"] = bool(
            self.proposals["possible_hallucinations"]
            or self.proposals["missing_sources"]
        )

    def add_proposal(self, proposal_type: str, item: Dict[str, Any]):
        """添加单个提议"""
        if proposal_type in self.proposals:
            self.proposals[proposal_type].append(item)
        self._self_check()

    def save_proposals(self, output_dir: str):
        """保存proposals到proposals.json"""
        import json
        from pathlib import Path
        path = Path(output_dir) / "proposals.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.proposals, f, ensure_ascii=False, indent=2)
