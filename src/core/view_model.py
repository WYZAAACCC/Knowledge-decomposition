"""
Fix 10: GraphViewModel

将 KnowledgeGraph 转换为前端安全的 ViewModel。
所有数据通过 JSON script 标签注入，禁止 innerHTML。
"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from ..models import Node, Edge, KnowledgeGraph, TrustLevel


class ViewNode(BaseModel):
    """Fix 10: 前端节点视图"""
    id: str
    label: str
    title: str
    type: str
    level: int = 0
    group: str = "concept"
    trust_level: str = "seed"
    verified: bool = False
    formula: Optional[str] = None
    detail: dict = Field(default_factory=dict)


class ViewEdge(BaseModel):
    """Fix 10: 前端边视图"""
    model_config = {"populate_by_name": True}
    id: str
    from_: str = Field(alias="from")
    to: str
    label: str = ""
    type: str = "derives"
    arrows: str = "to"
    dashes: bool = False
    color_group: str = "derivation"
    assumption_ids: list[str] = Field(default_factory=list)
    proof_step_ids: list[str] = Field(default_factory=list)
    detail: dict = Field(default_factory=dict)


# Fix 10: 统一的节点样式注册表
NODE_STYLE_REGISTRY = {
    "concept": {"shape": "ellipse", "group": "concept", "color": "#4A90D9"},
    "quantity": {"shape": "dot", "group": "quantity", "color": "#50C878"},
    "definition": {"shape": "box", "group": "definition", "color": "#9370DB"},
    "law": {"shape": "hexagon", "group": "law", "color": "#FF6B6B"},
    "equation": {"shape": "box", "group": "equation", "color": "#FFA500"},
    "assumption": {"shape": "diamond", "group": "assumption", "color": "#87CEEB"},
    "application": {"shape": "database", "group": "application", "color": "#FFD700"},
    "warning": {"shape": "triangle", "group": "warning", "color": "#FF4500"},
    "math_tool": {"shape": "star", "group": "math_tool", "color": "#98FB98"},
    "model": {"shape": "circle", "group": "model", "color": "#DDA0DD"},
    "experiment": {"shape": "square", "group": "experiment", "color": "#F0E68C"},
    "intuition_card": {"shape": "text", "group": "intuition", "color": "#E6E6FA"},
}

EDGE_COLOR_REGISTRY = {
    "derives": "derivation",
    "derives_from": "derivation",
    "requires": "dependency",
    "uses_math": "math",
    "assumes": "assumption",
    "applies_to": "application",
    "equivalent_to": "equivalence",
    "special_case_of": "hierarchy",
    "approximation_of": "approximation",
    "motivated_by": "motivation",
    "related_to": "relation",
}


class GraphViewModel:
    """Fix 10: 将 KnowledgeGraph 转换为前端安全的 ViewModel"""

    @staticmethod
    def from_graph(graph: KnowledgeGraph) -> Dict[str, Any]:
        nodes = []
        for n in graph.nodes:
            style = NODE_STYLE_REGISTRY.get(
                n.type.value if hasattr(n.type, 'value') else str(n.type),
                {"shape": "ellipse", "group": "default"},
            )
            nodes.append(ViewNode(
                id=n.id,
                label=n.title,
                title=n.title,
                type=n.type.value if hasattr(n.type, 'value') else str(n.type),
                level=n.abstraction_level,
                group=style["group"],
                trust_level=n.trust_level.value if hasattr(n.trust_level, 'value') else str(n.trust_level),
                verified=n.verified,
                formula=n.formula_latex,
                detail={"statement": n.statement or "", "sources": n.sources},
            ).model_dump(by_alias=True))

        edges = []
        for e in graph.edges:
            color_group = EDGE_COLOR_REGISTRY.get(
                e.type.value if hasattr(e.type, 'value') else str(e.type),
                "relation",
            )
            is_llm = hasattr(e, 'trust_level') and e.trust_level in {
                TrustLevel.LLM_PROPOSAL, TrustLevel.AUTO_GENERATED, TrustLevel.UNKNOWN
            }
            edges.append(ViewEdge(
                id=e.id,
                from_=e.from_,
                to=e.to,
                label=e.type.value if hasattr(e.type, 'value') else str(e.type),
                type=e.type.value if hasattr(e.type, 'value') else str(e.type),
                arrows="to",
                dashes=is_llm,
                color_group=color_group,
                assumption_ids=getattr(e, 'assumption_ids', []) or [],
                proof_step_ids=getattr(e, 'proof_step_ids', []) or [],
                detail={"assumptions": e.assumptions, "confidence": e.confidence},
            ).model_dump(by_alias=True))

        return {
            "nodes": nodes,
            "edges": edges,
            "topic": graph.topic,
            "canonical_path": graph.canonical_path,
            "alternate_paths": graph.alternate_paths,
            "stats": graph.stats.model_dump(),
            "validation_summary": graph.validation_summary.model_dump(),
            "metadata": graph.build_metadata.model_dump() if graph.build_metadata else {},
        }

    @staticmethod
    def to_json_script(graph: KnowledgeGraph) -> str:
        """Fix 10: 安全JSON注入，使用 script[type=application/json]"""
        import json
        data = GraphViewModel.from_graph(graph)
        json_str = json.dumps(data, ensure_ascii=False)

        # 转义 </script> 防止提前闭合
        json_str = json_str.replace("</", "<\\/")
        return json_str
