"""
DecomposerAgent

把候选知识组装成局部子图。
生成局部DAG，补齐边上的assumptions，生成derivation_steps，
连接数学工具节点，标记应用节点。
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from ..deepseek_client import get_deepseek_client, TaskComplexity
from ..models import Node, Edge, KnowledgeGraph, GraphStats, ValidationSummary, NodeType, Domain
from ..physics.assumption_checklists import get_assumption_checklists
from ..physics.topic_mapping import (
    get_cn_topic_name, infer_domain_hint, get_topic_definition, infer_theory_context
)
from ..loader import DataLoader


@dataclass
class DecomposerOutput:
    subgraph: KnowledgeGraph
    assembly_evidence: Dict[str, Any]
    assumptions_added: List[str]
    derivation_steps_added: int


_VALID_EDGE_TYPES = {
    "derives_from", "requires", "uses_math", "assumes",
    "equivalent_to", "special_case_of", "approximation_of",
    "applies_to", "motivated_by", "related_to"
}

_DEFAULT_ASSUMPTIONS = [
    "idealized_system:忽略次要因素的理想化模型",
    "classical_physics:经典物理框架下成立",
    "negligible_friction:摩擦力等耗散力可忽略"
]


class DecomposerAgent:

    def __init__(self, loader: Optional[DataLoader] = None):
        self.client = get_deepseek_client()
        self.assumption_checklists = get_assumption_checklists()
        self.loader = loader or DataLoader()

    def run(self, retrieval_output: Dict[str, Any]) -> DecomposerOutput:
        candidate_nodes = retrieval_output.get("candidate_nodes", [])
        candidate_edges = retrieval_output.get("candidate_edges", [])
        candidate_paths = retrieval_output.get("candidate_paths", [])
        max_nodes = retrieval_output.get("max_nodes", 40)
        retrieval_evidence = retrieval_output.get("retrieval_evidence", {})
        target = retrieval_evidence.get("target_node", "")

        if not candidate_nodes:
            return DecomposerOutput(
                subgraph=self._build_empty_graph(target),
                assembly_evidence={"error": "没有候选节点"},
                assumptions_added=[],
                derivation_steps_added=0
            )

        assembled_nodes, assembled_edges = self._assemble_with_llm(
            target, candidate_nodes, candidate_edges, candidate_paths, max_nodes
        )

        assumptions_added = self._augment_assumptions(assembled_edges, target)
        derivation_steps_added = self._augment_derivation_steps(assembled_edges)
        assembled_nodes, assembled_edges = self._deduplicate(assembled_nodes, assembled_edges)
        self._connect_math_tools(assembled_nodes, assembled_edges)
        assembled_nodes, assembled_edges = self._connect_or_remove_isolated(
            target, assembled_nodes, assembled_edges
        )

        subgraph = self._build_knowledge_graph(
            target, assembled_nodes, assembled_edges, candidate_paths
        )

        assembly_evidence = {
            "target": target,
            "input_nodes_count": len(candidate_nodes),
            "input_edges_count": len(candidate_edges),
            "output_nodes_count": len(assembled_nodes),
            "output_edges_count": len(assembled_edges),
            "assumptions_added_count": len(assumptions_added),
            "derivation_steps_added": derivation_steps_added,
            "llm_used": True,
            "assembly_strategy": "LLM-based assembly with augmentation"
        }

        return DecomposerOutput(
            subgraph=subgraph,
            assembly_evidence=assembly_evidence,
            assumptions_added=assumptions_added,
            derivation_steps_added=derivation_steps_added
        )

    @staticmethod
    def _build_empty_graph(target: str) -> KnowledgeGraph:
        topic = target if re.match(r'^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$', target or '') else "empty.topic"
        placeholder = Node(
            id="node.empty_placeholder", type=NodeType.CONCEPT, title="空图谱占位节点",
            statement="构建失败，无有效节点", formula_latex="N/A",
            domain=Domain.MECHANICS, abstraction_level=1, pedagogical_level=1,
            theory_context="classical", sources=["placeholder"]
        )
        return KnowledgeGraph(
            topic=topic, build_version="1.0.0",
            nodes=[placeholder], edges=[], canonical_path="path.empty.default",
            alternate_paths=[],
            stats=GraphStats(node_count=1, edge_count=0, derivation_edge_count=0,
                             assumption_count=0, math_tool_count=0),
            validation_summary=ValidationSummary(
                schema_valid=False, dag_valid=False, assumptions_complete=False,
                dimensions_valid=False, canonical_path_exists=False, errors=[], warnings=[])
        )

    def _assemble_with_llm(self, target: str, nodes: List[Node], edges: List[Edge],
                           candidate_paths: List[List[str]], max_nodes: int = 40) -> Tuple[List[Node], List[Edge]]:
        cn_topic = get_cn_topic_name(target)
        domain_hint = infer_domain_hint(target)
        topic_definition = get_topic_definition(target)

        system_prompt = self._build_system_prompt(target, cn_topic, domain_hint, topic_definition)
        user_prompt = self._build_user_prompt(target, cn_topic, domain_hint, nodes, edges,
                                              candidate_paths, max_nodes)

        try:
            response = self._call_llm_with_fallback(system_prompt, user_prompt, target,
                                                     cn_topic, domain_hint, max_nodes)

            if "error" in response:
                print(f"[ERROR] DecomposerAgent LLM返回错误: {response['error']}")
                return self._fallback_from_seeds(target, nodes, edges)

            assembled_nodes = self._parse_nodes_from_response(response, nodes)
            assembled_edges = self._parse_edges_from_response(response, edges, assembled_nodes)

            if not assembled_edges and assembled_nodes:
                assembled_nodes, assembled_edges = self._handle_no_edges(
                    target, assembled_nodes, assembled_edges
                )

            self._ensure_target_node_exists(target, assembled_nodes)

            if max_nodes > 30 and len(assembled_nodes) < max_nodes:
                assembled_nodes, assembled_edges = self._multi_stage_expand(
                    target, assembled_nodes, assembled_edges, max_nodes, cn_topic, domain_hint
                )

            return assembled_nodes, assembled_edges

        except Exception as e:
            print(f"[ERROR] DecomposerAgent LLM调用失败: {e}")
            return self._fallback_from_seeds(target, nodes, edges)

    def _call_llm_with_fallback(self, system_prompt: str, user_prompt: str,
                                 target: str, cn_topic: str, domain_hint: str,
                                 max_nodes: int) -> Dict:
        # 智能模型选择：根据节点数决定复杂度
        main_complexity = self.client.estimate_complexity(
            task_type="assembly", max_nodes=max_nodes, requires_derivation=True
        )
        try:
            return self.client.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0, complexity=main_complexity, max_tokens=8192
            )
        except Exception as llm_err:
            print(f"[WARN] DecomposerAgent 主LLM调用失败: {llm_err}")
            try:
                fallback_prompt = self._build_fallback_prompt(target, cn_topic, domain_hint, max_nodes)
                # 回退使用 Flash 节省成本
                return self.client.chat_json(
                    messages=[
                        {"role": "system", "content": f"你是一个物理知识图谱构建器，输出严格JSON。当前主题：{cn_topic}（{domain_hint}）。"},
                        {"role": "user", "content": fallback_prompt}
                    ],
                    temperature=0.1, complexity=TaskComplexity.SIMPLE, max_tokens=8192
                )
            except Exception as fallback_err:
                print(f"[WARN] 回退LLM调用也失败: {fallback_err}")
                return {"error": f"LLM调用失败: {llm_err}"}

    def _parse_nodes_from_response(self, response: Dict, existing_nodes: List[Node]) -> List[Node]:
        node_id_map = {n.id: n for n in existing_nodes}
        assembled = []

        for item in response.get("nodes", []):
            if isinstance(item, str):
                if item in node_id_map:
                    assembled.append(node_id_map[item])
            elif isinstance(item, dict):
                new_id = self._sanitize_node_id(item.get("id", ""))
                if new_id in node_id_map:
                    assembled.append(node_id_map[new_id])
                else:
                    node = self._create_node_from_dict(item, new_id)
                    if node:
                        assembled.append(node)
                        node_id_map[new_id] = node
        return assembled

    def _parse_edges_from_response(self, response: Dict, existing_edges: List[Edge],
                                    assembled_nodes: List[Node]) -> List[Edge]:
        node_ids = {n.id for n in assembled_nodes}
        assembled = []

        for edge_dict in response.get("edges", []):
            if not isinstance(edge_dict, dict):
                continue

            existing = next((e for e in existing_edges if e.id == edge_dict.get("id")), None)
            if existing:
                for field in ["assumptions", "derivation_steps", "math_used"]:
                    if field in edge_dict:
                        setattr(existing, field, edge_dict[field])
                assembled.append(existing)
                continue

            edge = self._create_edge_from_dict(edge_dict, node_ids)
            if edge:
                assembled.append(edge)

        return assembled

    def _create_node_from_dict(self, item: Dict, new_id: str) -> Optional[Node]:
        try:
            node_type_str = item.get("type", "concept")
            try:
                node_type = NodeType(node_type_str)
            except ValueError:
                node_type = NodeType.CONCEPT

            domain_str = item.get("domain", "mechanics")
            try:
                domain = Domain(domain_str)
            except ValueError:
                domain = Domain.MECHANICS

            abs_level = max(0, min(5, item.get("abstraction_level", 2) or 2))
            ped_level = max(1, min(5, item.get("pedagogical_level", abs_level) or abs_level))
            formula = item.get("formula_latex", "") or "N/A"
            theory_ctx = infer_theory_context(new_id, domain)

            return Node(
                id=new_id, type=node_type,
                title=item.get("title", new_id),
                statement=item.get("statement", "") or new_id,
                formula_latex=formula, domain=domain,
                abstraction_level=abs_level, pedagogical_level=ped_level,
                theory_context=theory_ctx, sources=["LLM_generated"]
            )
        except Exception as e:
            print(f"警告: 创建新节点失败 {new_id}: {e}")
            return None

    _EDGE_TYPE_MAPPING = {
        "derives_to": "derives_from",
        "implies": "derives_from",
        "defines": "requires",
        "addresses": "related_to",
        "includes": "requires",
        "depends_on": "requires",
        "uses": "uses_math",
        "based_on": "motivated_by",
        "leads_to": "derives_from",
        "results_in": "derives_from",
        "entails": "derives_from",
        "necessitates": "requires",
        "presupposes": "assumes",
        "constitutes": "equivalent_to",
        "represents": "equivalent_to",
        "generalizes": "special_case_of",
        "specializes": "special_case_of",
        "approximates": "approximation_of",
        "simplifies_to": "approximation_of",
        "applicable_to": "applies_to",
        "motivates": "motivated_by",
        "relates_to": "related_to",
        "connected_to": "related_to",
    }

    def _create_edge_from_dict(self, edge_dict: Dict, valid_node_ids: set) -> Optional[Edge]:
        edge_type = edge_dict.get("type", "derives_from")
        from_node = edge_dict.get("from") or edge_dict.get("from_")
        to_node = edge_dict.get("to")

        if from_node is None or to_node is None:
            return None

        if edge_type == "derives_to":
            edge_type = "derives_from"
            from_node, to_node = to_node, from_node

        # 将非法边类型映射为合法类型
        edge_type = self._EDGE_TYPE_MAPPING.get(edge_type, edge_type)
        if edge_type not in _VALID_EDGE_TYPES:
            print(f"[WARN] 忽略非法边类型 '{edge_dict.get('type')}'，映射为 'related_to'")
            edge_type = "related_to"

        from_node = self._sanitize_node_id(from_node)
        to_node = self._sanitize_node_id(to_node)

        if from_node not in valid_node_ids or to_node not in valid_node_ids:
            return None

        edge_id = self._sanitize_edge_id(
            edge_dict.get("id", f"edge.{from_node}.{edge_type}.{to_node}"),
            from_node, edge_type, to_node
        )
        path_id = self._sanitize_path_id(edge_dict.get("path_id", ""), from_node)

        assumptions = edge_dict.get("assumptions", []) or []
        derivation_steps = edge_dict.get("derivation_steps", []) or []
        math_used = edge_dict.get("math_used", []) or []

        if edge_type == "derives_from":
            if not assumptions:
                assumptions = ["假设条件待补充"]
            if not derivation_steps:
                derivation_steps = ["推导步骤待补充"]

        try:
            return Edge(
                id=edge_id, type=edge_type, from_=from_node, to=to_node,
                assumptions=assumptions, derivation_steps=derivation_steps,
                math_used=math_used, path_id=path_id
            )
        except Exception as e:
            print(f"警告: 创建边失败 {edge_id}: {e}")
            return None

    def _ensure_target_node_exists(self, target: str, assembled_nodes: List[Node]):
        existing_ids = {n.id for n in assembled_nodes}
        target_sanitized = self._sanitize_node_id(target)
        if target_sanitized in existing_ids:
            return

        cn_topic = get_cn_topic_name(target)
        topic_definition = get_topic_definition(target)
        domain_hint = infer_domain_hint(target)
        domain_str = self._infer_domain_from_hint(domain_hint)
        try:
            domain = Domain(domain_str)
        except ValueError:
            domain = Domain.MECHANICS

        theory_ctx = infer_theory_context(target, domain)
        node_type = NodeType.EQUATION if "equation" in target or "eq" in target else \
                    NodeType.LAW if "law" in target else \
                    NodeType.QUANTITY if "quantity" in target else NodeType.CONCEPT

        target_node = Node(
            id=target_sanitized, type=node_type, title=cn_topic,
            statement=topic_definition, formula_latex="N/A",
            domain=domain, abstraction_level=5, pedagogical_level=3,
            theory_context=theory_ctx, sources=["forced_target"]
        )
        assembled_nodes.insert(0, target_node)
        print(f"[INFO] 强制添加目标节点: {target_sanitized} ({cn_topic})")

    def _handle_no_edges(self, target: str, nodes: List[Node],
                         edges: List[Edge]) -> Tuple[List[Node], List[Edge]]:
        seed_edges = self._get_edges_from_seeds(target)
        if seed_edges:
            print(f"LLM未组装出边，从种子数据找到 {len(seed_edges)} 条相关边")
            seed_node_ids = set()
            for edge in seed_edges:
                seed_node_ids.add(edge.from_)
                seed_node_ids.add(edge.to)
            existing_ids = {n.id for n in nodes}
            for node_id in seed_node_ids - existing_ids:
                node = self.loader.get_node_by_id(node_id)
                if node:
                    nodes.append(node)
            edges.extend(seed_edges)
        else:
            print("种子数据也没有边，自动生成derives_from边")
            for i in range(len(nodes) - 1):
                from_node = nodes[i]
                to_node = nodes[i + 1]
                try:
                    auto_edge = Edge(
                        id=self._sanitize_edge_id(
                            f"edge.{from_node.id}.derives_from.{to_node.id}",
                            from_node.id, "derives_from", to_node.id
                        ),
                        type="derives_from", from_=from_node.id, to=to_node.id,
                        assumptions=["假设条件待补充"],
                        derivation_steps=["推导步骤待补充"],
                        math_used=[],
                        path_id=self._sanitize_path_id("", from_node.id)
                    )
                    edges.append(auto_edge)
                except Exception as e:
                    print(f"自动创建边失败: {e}")
        return nodes, edges

    def _fallback_from_seeds(self, target: str, nodes: List[Node],
                              edges: List[Edge]) -> Tuple[List[Node], List[Edge]]:
        seed_edges = self._get_edges_from_seeds(target)
        if seed_edges:
            seed_node_ids = set()
            for edge in seed_edges:
                seed_node_ids.add(edge.from_)
                seed_node_ids.add(edge.to)
            existing_ids = {n.id for n in nodes}
            for node_id in seed_node_ids - existing_ids:
                node = self.loader.get_node_by_id(node_id)
                if node:
                    nodes.append(node)
            return nodes, edges + seed_edges
        return nodes[:20], edges[:30]

    @staticmethod
    def _build_system_prompt(target: str, cn_topic: str, domain_hint: str,
                             topic_definition: str) -> str:
        return f"""你是一个严谨的物理知识图谱构建器，擅长数学与物理推导。
你的任务是根据候选节点和候选边组装一个局部子图，并生成完整的推导过程。

【当前构建目标】
- 主题ID: {target}
- 中文名称: {cn_topic}
- 所属领域: {domain_hint}
- 主题定义: {topic_definition}

⚠️ 极其重要：你必须围绕"{cn_topic}"（{domain_hint}）来构建知识图谱，绝不能将主题误解为其他含义！
例如："partition_function"指的是统计力学中的配分函数Z=Σe^(-βEᵢ)，而不是数学中的通用函数概念。
例如："green_function"指的是物理学中的格林函数G(x,x')，而不是数学中的任意绿色函数。

核心规则：
1. 优先使用提供的候选节点来构建子图
2. 如果候选节点不足以构建完整的推导链，你可以创建新的节点来填补空白
3. 新创建的节点必须包含完整的物理信息（id, type, title, statement, formula_latex, domain, abstraction_level）
4. 新节点的ID格式必须为: {{类型前缀}}.{{英文简称}}，如 eq.navier_stokes, concept.viscosity
5. 对于推导边(derives_from)，必须包含assumptions和derivation_steps
6. derivation_steps必须包含完整的数学推导过程，每一步都要有公式和物理解释
7. 尽量保持图的结构清晰，避免过度复杂
8. 输出必须是严格的JSON格式
9. 所有节点和边必须与{cn_topic}（{domain_hint}）直接相关，禁止生成无关的通用数学概念
10. 目标节点 {target}（{cn_topic}）必须是图中的核心节点

推导步骤格式要求（极其重要）：
- 每一步必须包含数学公式（使用LaTeX语法，用$...$包裹行内公式，$$...$$包裹独立公式）
- 每一步必须有物理意义的解释
- 步骤之间要有逻辑连贯性，从前提逐步推导到结论
- 示例格式："由牛顿第二定律 $\\vec{{F}}=m\\vec{{a}}$，将加速度表示为 $a=\\frac{{dv}}{{dt}}$，代入得 $F=m\\frac{{dv}}{{dt}}$"

节点描述要求：
- statement字段必须包含完整的物理描述，包括物理意义、适用条件、物理量含义
- formula_latex字段必须包含完整的数学公式（LaTeX格式）

输出格式：
{{
  "nodes": [
    "已有节点ID",
    {{"id": "新节点ID", "type": "节点类型", "title": "标题", "statement": "描述", "formula_latex": "LaTeX公式", "domain": "学科域", "abstraction_level": 层级数字}}
  ],
  "edges": [
    {{
      "id": "边ID",
      "type": "边类型(derives_from/requires/uses_math等)",
      "from": "起始节点ID（被推导出的高层定理）",
      "to": "目标节点ID（推导所用的底层知识）",
      "assumptions": ["假设列表，每个假设要有清晰描述"],
      "derivation_steps": [
        "步骤1：从X出发，根据Y定律，$公式$，物理意义是...",
        "步骤2：对上式进行Z操作，$公式$，这表示...",
        "步骤3：整理得到最终结果 $公式$，即所求"
      ],
      "math_used": ["使用的数学工具"],
      "path_id": "路径ID"
    }}
  ],
  "rationale": "组装理由"
}}

如果信息不足，返回{{"error": "信息不足"}}。"""

    @staticmethod
    def _build_user_prompt(target: str, cn_topic: str, domain_hint: str,
                           nodes: List[Node], edges: List[Edge],
                           candidate_paths: List[List[str]], max_nodes: int) -> str:
        candidate_data = {
            "target": target,
            "candidate_nodes": [
                {
                    "id": n.id, "type": n.type,
                    "title": getattr(n, 'title', ''),
                    "statement": getattr(n, 'statement', '') or '',
                    "formula_latex": getattr(n, 'formula_latex', '') or '',
                    "abstraction_level": getattr(n, 'abstraction_level', 2),
                }
                for n in nodes[:50]
            ],
            "candidate_edges": [
                {
                    "id": e.id, "type": e.type,
                    "from": e.from_, "to": e.to,
                    "assumptions": getattr(e, 'assumptions', []) or [],
                    "derivation_steps": getattr(e, 'derivation_steps', []) or [],
                    "math_used": getattr(e, 'math_used', []) or [],
                }
                for e in edges[:100]
            ],
            "candidate_paths": candidate_paths[:15]
        }

        if max_nodes > 60:
            initial_target = min(max_nodes // 2, 45)
            min_nodes = max(initial_target - 10, 15)
        else:
            min_nodes = max(max_nodes // 2, 15)
        min_edges = max(min_nodes - 5, 10)

        return f"""请为"{cn_topic}"（{domain_hint}）组装局部子图。

⚠️ 再次强调：主题是"{cn_topic}"，属于{domain_hint}，不是通用数学概念！

候选数据：
{json.dumps(candidate_data, ensure_ascii=False, indent=2)}

请组装一个合理的子图，确保：
1. 图是连通的有向无环图(DAG)
2. 每条derives_from边必须包含完整的推导步骤，每步要有数学公式（LaTeX）和物理解释
3. 假设条件必须清晰描述，说明为什么需要这些假设
4. 如果可能，包含一条从基础到目标的清晰推导路径
5. 节点数量控制在{min_nodes}-{max_nodes}个之间，确保推导链完整
6. derivation_steps中的公式使用LaTeX语法，行内公式用$...$，独立公式用$$...$$
7. 如果候选节点不足以构建完整的推导链，请创建新节点（以对象形式提供，包含id/type/title/statement/formula_latex/domain/abstraction_level）
8. 新节点的ID格式必须为: 类型前缀.英文简称，如 eq.schrodinger, concept.wave_function
9. 目标节点 '{target}'（{cn_topic}）必须是图中的核心节点，且其内容必须与{domain_hint}直接相关
10. 所有节点和边必须与{cn_topic}（{domain_hint}）直接相关，禁止生成无关的通用数学概念
11. 推导链必须有清晰的层次结构：从底层基础概念→中层理论工具→高层核心结论
"""

    @staticmethod
    def _build_fallback_prompt(target: str, cn_topic: str, domain_hint: str,
                               max_nodes: int) -> str:
        if max_nodes > 60:
            initial_target = min(max_nodes // 2, 45)
            min_nodes = max(initial_target - 10, 15)
        else:
            min_nodes = max(max_nodes // 2, 15)
        min_edges = max(min_nodes - 5, 10)
        return f"""请为物理主题 '{target}'（{cn_topic}，{domain_hint}）生成一个知识图谱子图。

⚠️ 重要：这是{domain_hint}中的{cn_topic}，不是通用数学概念！

要求：
1. 生成{min_nodes}-{max_nodes}个节点，包含定律、方程、概念、物理量、假设、数学工具等类型
2. 生成{min_edges}-{max_nodes}条边，主要是derives_from类型
3. 每条derives_from边必须有derivation_steps（含LaTeX公式）
4. 节点ID格式: 类型.英文简称（如eq.navier_stokes）
5. 边ID格式: edge.from_id.derives_from.to_id
6. 所有节点必须与{cn_topic}（{domain_hint}）直接相关
7. 推导链必须有清晰的层次结构：底层基础概念→中层理论工具→高层核心结论

输出JSON格式：
{{"nodes": [{{"id":"eq.xxx","type":"equation","title":"中文名","statement":"描述","formula_latex":"LaTeX","domain":"mechanics","abstraction_level":2}}],"edges":[{{"id":"edge.xxx.derives_from.yyy","type":"derives_from","from":"高层","to":"底层","assumptions":[],"derivation_steps":["步骤1"],"math_used":[],"path_id":"path.xxx.default"}}]}}"""

    def _multi_stage_expand(self, target: str, nodes: List[Node], edges: List[Edge],
                            max_nodes: int, cn_topic: str, domain_hint: str) -> Tuple[List[Node], List[Edge]]:
        existing_ids = {n.id for n in nodes}
        current_count = len(nodes)
        max_stages = 5 if max_nodes > 60 else 3

        print(f"[INFO] 开始多阶段扩展: 当前{current_count}节点, 目标{max_nodes}节点")

        for stage in range(1, max_stages + 1):
            if current_count >= max_nodes * 0.8:
                break

            needed = max_nodes - current_count
            stage_target = min(needed, 25)
            expand_candidates = self._find_expand_candidates(nodes, edges)

            if not expand_candidates:
                break

            print(f"[INFO] 阶段{stage}: 扩展{len(expand_candidates)}个分支，目标新增{stage_target}节点")

            new_nodes, new_edges = self._call_llm_for_expansion(
                target, expand_candidates, nodes, edges,
                stage_target, cn_topic, domain_hint, stage
            )

            if not new_nodes:
                break

            for nn in new_nodes:
                if nn.id not in existing_ids:
                    existing_ids.add(nn.id)
                    nodes.append(nn)
                    current_count += 1

            for ne in new_edges:
                if not any(e.id == ne.id or (e.from_ == ne.from_ and e.to == ne.to) for e in edges):
                    edges.append(ne)

            self._connect_isolated_nodes(new_nodes, existing_ids, edges, expand_candidates)

            print(f"[INFO] 阶段{stage}完成: 新增{len(new_nodes)}节点/{len(new_edges)}边, 总计{current_count}节点")

        print(f"[INFO] 多阶段扩展结束: 最终{current_count}节点/{len(edges)}边")
        return nodes, edges

    @staticmethod
    def _connect_isolated_nodes(new_nodes: List[Node], existing_ids: set,
                                 edges: List[Edge], expand_candidates: List[Dict]):
        new_node_ids = {nn.id for nn in new_nodes if nn.id in existing_ids}
        nodes_with_edges = {e.from_ for e in edges} | {e.to for e in edges}
        isolated = [nid for nid in new_node_ids if nid not in nodes_with_edges]

        if not isolated or not expand_candidates:
            return

        best_parent = expand_candidates[0]["id"]
        for cand in expand_candidates:
            if cand.get("abstraction_level", 0) >= 2:
                best_parent = cand["id"]
                break

        for isolated_id in isolated:
            try:
                edge_id = f"edge.{isolated_id}.derives_from.{best_parent}"
                edge_id = re.sub(r'[^a-z0-9_.]', '_', edge_id)
                auto_edge = Edge(
                    id=edge_id, type="derives_from",
                    from_=isolated_id, to=best_parent,
                    assumptions=["假设条件待补充"],
                    derivation_steps=["推导步骤待补充"],
                    math_used=[],
                    path_id=self._sanitize_path_id("", isolated_id)
                )
                edges.append(auto_edge)
            except Exception:
                pass

    @staticmethod
    def _find_expand_candidates(nodes: List[Node], edges: List[Edge]) -> List[Dict]:
        from_node_ids = {e.from_ for e in edges}
        to_node_ids = {e.to for e in edges}

        candidates = []
        for node in nodes:
            out_degree = sum(1 for e in edges if e.from_ == node.id)
            in_degree = sum(1 for e in edges if e.to == node.id)
            is_leaf = (node.id in to_node_ids) and (node.id not in from_node_ids)
            has_few_children = out_degree <= 2

            if (is_leaf or has_few_children) and node.type != NodeType.ASSUMPTION:
                candidates.append({
                    "id": node.id,
                    "type": str(node.type.value),
                    "title": getattr(node, 'title', ''),
                    "statement": getattr(node, 'statement', '')[:200],
                    "abstraction_level": getattr(node, 'abstraction_level', 2),
                    "reason": "leaf" if is_leaf else "few_children"
                })

        candidates.sort(key=lambda x: x.get("abstraction_level", 2), reverse=True)
        return candidates[:12]

    def _call_llm_for_expansion(self, target: str, candidates: List[Dict],
                                existing_nodes: List[Node], existing_edges: List[Edge],
                                target_new_count: int, cn_topic: str,
                                domain_hint: str, stage: int) -> Tuple[List[Node], List[Edge]]:
        candidates_json = json.dumps(candidates, ensure_ascii=False, indent=2)
        existing_ids_json = json.dumps(list({n.id for n in existing_nodes}), ensure_ascii=False)

        per_candidate = target_new_count // max(len(candidates), 1) + 2
        expansion_prompt = (
            f"你是{domain_hint}专家，正在为{cn_topic}构建深层知识图谱。\n\n"
            f"当前任务：第{stage}阶段扩展，为{cn_topic}（{domain_hint}）添加更详细的推导支撑。\n\n"
            f"核心约束：所有新节点必须与{cn_topic}（{domain_hint}）直接相关！\n"
            f"禁止生成与{cn_topic}无关的通用数学或物理概念！\n\n"
            "待扩展分支（需要更详细的底层支撑或上层推论）：\n"
            + candidates_json + "\n\n"
            "已有节点ID（不要重复创建）：\n"
            + existing_ids_json + "\n\n"
            "极其重要的要求：\n"
            f"1. 为每个待扩展分支生成约{per_candidate}个新的支撑/推论节点\n"
            "2. **每个新节点必须至少有一条边连接到已有节点或其他新节点**，孤立节点将被删除！\n"
            "3. **edges数组中的边数量必须至少等于nodes数组中节点数量的80%**\n"
            f"4. 每个新节点的statement必须明确说明它与{cn_topic}的关系\n"
            "5. 新节点必须是该领域的专业概念、方程、数学工具或物理量\n"
            "6. 每条derives_from边必须包含derivation_steps（含LaTeX公式）和assumptions\n"
            "7. 边的from字段必须是高层节点ID，to字段必须是底层节点ID\n"
            "8. 边的from/to必须引用nodes数组中的节点ID或已有节点ID\n"
            "9. 输出严格JSON格式，包含nodes数组和edges数组\n"
            f"10. 节点的domain字段应设为与{domain_hint}对应的英文域名\n\n"
            "边类型说明：\n"
            "- derives_from: 从底层知识推导出高层知识（from=高层, to=底层）\n"
            "- requires: 高层知识需要底层知识作为前提（from=高层, to=底层）\n"
            "- uses_math: 使用数学工具（from=使用方, to=数学工具）\n"
            "- assumes: 依赖假设条件（from=依赖方, to=假设）\n"
        )

        # 智能模型选择：扩展阶段越高，越复杂
        expand_complexity = self.client.estimate_complexity(
            task_type="expansion", max_nodes=target_new_count + len(existing_nodes),
            expansion_stage=stage, requires_derivation=True
        )
        try:
            response = self.client.chat_json(
                messages=[
                    {"role": "system", "content": f"你是{domain_hint}知识图谱扩展器。主题：{cn_topic}。"},
                    {"role": "user", "content": expansion_prompt}
                ],
                temperature=0.0, complexity=expand_complexity, max_tokens=8192
            )

            if "error" in response or "nodes" not in response:
                return [], []

            return self._parse_expansion_response(response, stage)

        except Exception as e:
            print(f"[ERROR] 阶段{stage} LLM调用失败: {e}")
            return [], []

    def _parse_expansion_response(self, response: Dict, stage: int) -> Tuple[List[Node], List[Edge]]:
        new_nodes = []
        new_edges = []

        for item in response.get("nodes", []):
            if isinstance(item, str):
                continue
            try:
                node_id = self._sanitize_node_id(item.get("id", ""))
                if not node_id:
                    continue
                abs_level = max(0, min(5, item.get("abstraction_level", 2) or 2))
                ped_level = max(1, min(5, item.get("pedagogical_level", abs_level) or abs_level))
                domain_str = item.get("domain", "mechanics") or "mechanics"
                try:
                    domain = Domain(domain_str)
                except ValueError:
                    domain = Domain.MECHANICS
                theory_ctx = infer_theory_context(item.get("id", ""), domain)
                node_type_str = item.get("type", "concept") or "concept"
                try:
                    node_type = NodeType(node_type_str)
                except ValueError:
                    node_type = NodeType.CONCEPT
                new_node = Node(
                    id=node_id, type=node_type,
                    title=item.get("title", ""),
                    statement=item.get("statement", "") or item.get("title", "") or "待补充",
                    formula_latex=item.get("formula_latex", "") or "N/A",
                    domain=domain, abstraction_level=abs_level,
                    pedagogical_level=ped_level, theory_context=theory_ctx,
                    sources=[f"llm_stage{stage}"]
                )
                new_nodes.append(new_node)
            except Exception as e:
                print(f"[WARN] 阶段{stage} 解析节点失败: {e}")

        for item in response.get("edges", []):
            if isinstance(item, str):
                continue
            try:
                edge_type = item.get("type", "derives_from") or "derives_from"
                assumptions = item.get("assumptions", []) or []
                derivation_steps = item.get("derivation_steps", []) or []

                if isinstance(derivation_steps, str):
                    derivation_steps = [derivation_steps]
                if isinstance(assumptions, str):
                    assumptions = [assumptions]

                if edge_type == "derives_from":
                    if not assumptions:
                        assumptions = ["假设条件待补充"]
                    if not derivation_steps:
                        derivation_steps = ["推导步骤待补充"]

                from_id = (item.get("from") or item.get("from_node") or
                           item.get("source") or item.get("src") or "")
                to_id = (item.get("to") or item.get("to_node") or
                         item.get("target") or item.get("dst") or "")
                if not from_id or not to_id:
                    continue
                from_id = self._sanitize_node_id(str(from_id))
                to_id = self._sanitize_node_id(str(to_id))
                new_edge = Edge(
                    id=self._sanitize_edge_id(
                        item.get("id", f"edge.{from_id}.{edge_type}.{to_id}"),
                        from_id, edge_type, to_id
                    ),
                    type=edge_type, from_=from_id, to=to_id,
                    assumptions=assumptions, derivation_steps=derivation_steps,
                    math_used=item.get("math_used", []) or [],
                    path_id=f"path.{from_id.replace('.', '_')}.default"
                )
                new_edges.append(new_edge)
            except Exception as e:
                print(f"[WARN] 阶段{stage} 解析边失败: {e}")

        return new_nodes, new_edges

    @staticmethod
    def _sanitize_node_id(node_id: str) -> str:
        if not node_id:
            return "node.unknown"
        node_id = str(node_id).strip().lower()
        node_id = re.sub(r'[^a-z0-9_.]', '_', node_id)
        node_id = re.sub(r'_+', '_', node_id).strip('_')
        if not node_id:
            return "node.unknown"
        if '.' not in node_id:
            node_id = f"node.{node_id}"
        if not re.match(r'^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$', node_id):
            node_id = f"node.{node_id.replace('.', '_')}"
            if not re.match(r'^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$', node_id):
                node_id = "node.unknown"
        return node_id

    @staticmethod
    def _sanitize_edge_id(edge_id: str, from_node: str, edge_type: str, to_node: str) -> str:
        if edge_type not in _VALID_EDGE_TYPES:
            edge_type = "derives_from"
        from_part = from_node.split('.')[-1] if '.' in from_node else from_node
        to_part = to_node.split('.')[-1] if '.' in to_node else to_node
        from_part = re.sub(r'[^a-z0-9_]', '_', from_part)
        to_part = re.sub(r'[^a-z0-9_]', '_', to_part)
        return f"edge.{from_part}.{edge_type}.{to_part}"

    @staticmethod
    def _sanitize_path_id(path_id: str, fallback_key: str = "") -> str:
        if path_id:
            path_id = str(path_id).strip().lower()
            path_id = re.sub(r'[^a-z0-9_.]', '_', path_id)
            path_id = re.sub(r'_+', '_', path_id)
            if re.match(r'^path\.[a-z0-9_]+(\.[a-z0-9_]+)*$', path_id):
                return path_id
        key = re.sub(r'[^a-z0-9_]', '_', (fallback_key or "default").lower())
        return f"path.{key}.default"

    @staticmethod
    def _deduplicate(nodes: List[Node], edges: List[Edge]) -> Tuple[List[Node], List[Edge]]:
        seen_node_ids = set()
        unique_nodes = []
        title_to_id = {}

        for node in nodes:
            if node.id in seen_node_ids:
                continue
            title_lower = (getattr(node, 'title', '') or '').strip().lower()
            is_dup = False

            if title_lower and title_lower in title_to_id:
                is_dup = True
                keep_id = title_to_id[title_lower]
                for edge in edges:
                    if edge.from_ == node.id:
                        edge.from_ = keep_id
                    if edge.to == node.id:
                        edge.to = keep_id
            else:
                if title_lower:
                    title_to_id[title_lower] = node.id
                node_title = getattr(node, 'title', '')
                for existing_title, existing_id in title_to_id.items():
                    if existing_id == node.id:
                        continue
                    if DecomposerAgent._titles_are_similar(node_title, existing_title):
                        is_dup = True
                        for edge in edges:
                            if edge.from_ == node.id:
                                edge.from_ = existing_id
                            if edge.to == node.id:
                                edge.to = existing_id
                        break
                if not is_dup and title_lower:
                    title_to_id[title_lower] = node.id

            if not is_dup:
                seen_node_ids.add(node.id)
                unique_nodes.append(node)

        valid_node_ids = {n.id for n in unique_nodes}
        seen_edge_ids = set()
        seen_edge_keys = set()
        unique_edges = []
        for edge in edges:
            if edge.from_ not in valid_node_ids or edge.to not in valid_node_ids:
                continue
            if edge.from_ == edge.to:
                continue
            edge_key = (edge.from_, edge.to, str(edge.type.value if hasattr(edge.type, 'value') else edge.type))
            if edge.id in seen_edge_ids or edge_key in seen_edge_keys:
                continue
            seen_edge_ids.add(edge.id)
            seen_edge_keys.add(edge_key)
            unique_edges.append(edge)

        return unique_nodes, unique_edges

    @staticmethod
    def _titles_are_similar(title1: str, title2: str) -> bool:
        if not title1 or not title2:
            return False
        t1 = title1.strip().lower()
        t2 = title2.strip().lower()
        if t1 == t2:
            return True
        t1_core = re.sub(r'(的定义|定义|概念|定律|方程|定理|原理|法则)$', '', t1)
        t2_core = re.sub(r'(的定义|定义|概念|定律|方程|定理|原理|法则)$', '', t2)
        return bool(t1_core and t2_core and t1_core == t2_core)

    def _augment_assumptions(self, edges: List[Edge], target: str) -> List[str]:
        added = []
        for edge in edges:
            etype = edge.type.value if hasattr(edge.type, 'value') else str(edge.type)
            if "derives_from" in etype and not edge.assumptions:
                checklist = self.assumption_checklists.get_topic_checklist(target)
                if checklist:
                    edge.assumptions = checklist[:3]
                else:
                    edge.assumptions = list(_DEFAULT_ASSUMPTIONS)
                added.extend(edge.assumptions)
        return added

    def _augment_derivation_steps(self, edges: List[Edge]) -> int:
        derives_edges = [
            e for e in edges
            if "derives_from" in (e.type.value if hasattr(e.type, 'value') else str(e.type))
        ]
        needs_steps = [
            e for e in derives_edges
            if not e.derivation_steps or all(len(s) < 30 for s in e.derivation_steps)
        ]

        if not needs_steps:
            return 0

        steps_added = 0
        if len(needs_steps) <= 5:
            detailed = self._generate_detailed_derivation_batch(needs_steps)
            if detailed:
                for edge_id, steps in detailed.items():
                    for e in needs_steps:
                        if e.id == edge_id and steps:
                            e.derivation_steps = steps
                            steps_added += len(steps)
                if steps_added > 0:
                    return steps_added

        for edge in needs_steps:
            if not edge.derivation_steps:
                edge.derivation_steps = [
                    f"从 {edge.to} 出发，应用相关物理定律和数学工具",
                    "经过数学推导和物理分析",
                    f"得到 {edge.from_} 的结论"
                ]
                steps_added += len(edge.derivation_steps)

        return steps_added

    def _generate_detailed_derivation_batch(self, edges: List[Edge]) -> Dict[str, List[str]]:
        if not edges:
            return {}

        system_prompt = """你是一位严谨的物理学教授，擅长数学推导和物理解释。
你需要为给定的物理推导边生成完整的推导步骤。

要求：
1. 每一步必须包含数学公式（使用LaTeX语法，$...$行内，$$...$$独立）
2. 每一步必须有清晰的物理意义解释
3. 步骤之间逻辑连贯，从前提逐步推导到结论
4. 推导过程要完整，不能跳步
5. 注明每步使用的物理定律或数学方法

输出严格的JSON格式：
{
  "derivations": {
    "边ID": [
      "步骤1：从X定律出发，$公式$，这表示...",
      "步骤2：对上式进行Y变换，$公式$，物理意义是...",
      "步骤3：最终得到 $公式$，即所求结论"
    ]
  }
}"""

        edge_descs = []
        for e in edges:
            assumptions_str = "、".join(e.assumptions) if e.assumptions else "无特殊假设"
            math_str = "、".join(e.math_used) if e.math_used else "基础数学"
            edge_descs.append(
                f"边ID: {e.id}\n从 {e.to} 推导出 {e.from_}\n"
                f"假设条件: {assumptions_str}\n数学工具: {math_str}"
            )

        user_prompt = f"请为以下{len(edges)}条推导边生成完整的推导步骤：\n\n{chr(10).join(edge_descs)}\n\n请确保每一步都有数学公式和物理解释。"

        try:
            response = self.client.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                complexity=TaskComplexity.COMPLEX,  # 推导步骤生成需要强推理
                max_tokens=4096
            )
            return response.get("derivations", {})
        except Exception as e:
            print(f"[WARN] 生成详细推导步骤失败: {e}")
            return {}

    @staticmethod
    def _connect_math_tools(nodes: List[Node], edges: List[Edge]):
        math_tool_nodes = [n for n in nodes if "math_tool" in (n.type.value if hasattr(n.type, 'value') else str(n.type))]
        equation_nodes = [n for n in nodes if "equation" in (n.type.value if hasattr(n.type, 'value') else str(n.type))]

        if not math_tool_nodes or not equation_nodes:
            return

        keyword_map = {
            "calculus": ["derivative", "differentiation", "integral", "integration"],
            "vector": ["vector", "gradient", "divergence"],
        }

        for eq_node in equation_nodes:
            eq_title = getattr(eq_node, 'title', '').lower()
            for math_node in math_tool_nodes:
                math_name = math_node.id.lower()
                for math_key, eq_keywords in keyword_map.items():
                    if math_key in math_name and any(kw in eq_title for kw in eq_keywords):
                        DecomposerAgent._add_math_edge(math_node.id, eq_node.id, edges)

    @staticmethod
    def _add_math_edge(math_tool_id: str, target_id: str, edges: List[Edge]):
        from_part = math_tool_id.split('.')[-1] if '.' in math_tool_id else math_tool_id
        to_part = target_id.split('.')[-1] if '.' in target_id else target_id
        edge_id = f"edge.{from_part}.uses_math.{to_part}"
        if not any(e.id == edge_id for e in edges):
            edge = Edge(
                id=edge_id, type="uses_math",
                from_=target_id, to=math_tool_id,
                assumptions=[], derivation_steps=[],
                math_used=[math_tool_id],
                path_id=f"path.{from_part}.math_connection"
            )
            edges.append(edge)

    @staticmethod
    def _connect_or_remove_isolated(target: str, nodes: List[Node],
                                     edges: List[Edge]) -> Tuple[List[Node], List[Edge]]:
        if not nodes or not edges:
            return nodes, edges

        node_ids_with_edges = set()
        for edge in edges:
            node_ids_with_edges.add(edge.from_)
            node_ids_with_edges.add(edge.to)

        connected_nodes = [n for n in nodes if n.id in node_ids_with_edges]
        isolated_nodes = [n for n in nodes if n.id not in node_ids_with_edges]

        if not isolated_nodes:
            return nodes, edges

        target_sanitized = DecomposerAgent._sanitize_node_id(target)
        node_map = {n.id: n for n in connected_nodes}

        max_connect_attempts = min(len(isolated_nodes) * 2, 200)
        new_edges = []
        connected_isolated_ids = set()

        for iso_node in isolated_nodes:
            if len(connected_nodes) + len(connected_isolated_ids) >= len(nodes):
                break

            best_parent = None
            best_score = -1

            for cn in connected_nodes:
                score = 0
                if cn.domain == iso_node.domain:
                    score += 10
                if cn.type == iso_node.type:
                    score += 5
                if abs(cn.abstraction_level - iso_node.abstraction_level) <= 2:
                    score += 3
                if cn.abstraction_level > iso_node.abstraction_level:
                    score += 2
                score -= abs(cn.abstraction_level - iso_node.abstraction_level)
                if score > best_score:
                    best_score = score
                    best_parent = cn

            if best_parent is None and connected_nodes:
                best_parent = connected_nodes[0]

            if best_parent:
                if best_parent.abstraction_level >= iso_node.abstraction_level:
                    from_id, to_id = best_parent.id, iso_node.id
                    etype = "derives_from"
                else:
                    from_id, to_id = iso_node.id, best_parent.id
                    etype = "derives_from"

                from_part = from_id.split('.')[-1] if '.' in from_id else from_id
                to_part = to_id.split('.')[-1] if '.' in to_id else to_id
                edge_id = f"edge.{from_part}.{etype}.{to_part}"

                if not any(e.from_ == from_id and e.to == to_id for e in edges + new_edges):
                    try:
                        new_edge = Edge(
                            id=edge_id, type=etype,
                            from_=from_id, to=to_id,
                            assumptions=["假设条件待补充"],
                            derivation_steps=["推导步骤待补充"],
                            math_used=[],
                            path_id=f"path.{from_part.replace('.', '_')}.auto_connect"
                        )
                        new_edges.append(new_edge)
                        connected_isolated_ids.add(iso_node.id)
                    except Exception:
                        pass

        edges.extend(new_edges)
        still_isolated = [n for n in isolated_nodes if n.id not in connected_isolated_ids]
        if still_isolated:
            still_ids = {n.id for n in still_isolated}
            final_nodes = [n for n in nodes if n.id not in still_ids]
            print(f"[INFO] 移除{len(still_isolated)}个无法连接的孤立节点")
            return final_nodes, edges

        return nodes, edges

    @staticmethod
    def _infer_domain_from_hint(domain_hint: str) -> str:
        hint_lower = domain_hint.lower()
        if "相对论" in hint_lower:
            return "modern_physics"
        if "量子" in hint_lower:
            return "modern_physics"
        if "电磁" in hint_lower:
            return "electromagnetism"
        if "热力学" in hint_lower or "统计" in hint_lower:
            return "thermodynamics"
        if "流体" in hint_lower or "经典力学" in hint_lower:
            return "mechanics"
        return "mechanics"

    def _build_knowledge_graph(self, target: str, nodes: List[Node], edges: List[Edge],
                               candidate_paths: List[List[str]]) -> KnowledgeGraph:
        canonical_path = self._compute_canonical_path(target, candidate_paths, edges)
        self._apply_path_ids(edges, canonical_path, candidate_paths)
        self._apply_level_constraints(target, nodes, edges)

        derives_count = sum(1 for e in edges if "derives_from" in (e.type.value if hasattr(e.type, 'value') else str(e.type)))
        math_tool_count = sum(1 for n in nodes if "math_tool" in (n.type.value if hasattr(n.type, 'value') else str(n.type)))
        assumption_count = sum(len(e.assumptions) for e in edges)

        alternate_paths = []
        if len(candidate_paths) > 1:
            clean_t = re.sub(r'[^a-z0-9_]', '', target.lower().replace('.', '_')) or "topic_default"
            for i in range(1, min(len(candidate_paths), 4)):
                alternate_paths.append(f"path.{clean_t}.alternate_{i}")

        return KnowledgeGraph(
            topic=target, build_version="1.0.0",
            nodes=nodes, edges=edges,
            canonical_path=canonical_path,
            alternate_paths=alternate_paths,
            stats=GraphStats(
                node_count=len(nodes), edge_count=len(edges),
                derivation_edge_count=derives_count,
                assumption_count=assumption_count,
                math_tool_count=math_tool_count
            ),
            validation_summary=ValidationSummary(
                schema_valid=False, dag_valid=False,
                assumptions_complete=False, dimensions_valid=False,
                canonical_path_exists=bool(canonical_path),
                errors=[], warnings=[]
            ),
            build_metadata=None
        )

    @staticmethod
    def _compute_canonical_path(target: str, candidate_paths: List[List[str]],
                                 edges: List[Edge]) -> str:
        clean_t = re.sub(r'[^a-z0-9_]', '', target.lower().replace('.', '_')) or "topic_default"

        if candidate_paths:
            shortest = min(candidate_paths, key=len)
            canonical = f"path.{clean_t}.canonical"
            for i in range(len(shortest) - 1):
                for edge in edges:
                    if edge.from_ == shortest[i] and edge.to == shortest[i + 1]:
                        edge.path_id = canonical
                        break
            return canonical

        return f"path.{clean_t}.default"

    @staticmethod
    def _apply_path_ids(edges: List[Edge], canonical_path: str,
                         candidate_paths: List[List[str]]):
        path_id_pattern = re.compile(r'^path\.[a-z0-9_]+(\.[a-z0-9_]+)*$')
        for edge in edges:
            if not edge.path_id or not path_id_pattern.match(edge.path_id):
                edge.path_id = canonical_path

    @staticmethod
    def _apply_level_constraints(target: str, nodes: List[Node], edges: List[Edge]):
        """
        Compute correct hierarchical abstraction levels from the graph structure.

        Core principle: derives_from(from=A, to=B) means "A is derived from B."
        So A is more derived (higher level), B is more foundational (lower level).

        Level computation:
        1. Build a DAG where edges go foundational→derived (edge.to → edge.from_)
        2. Roots (most foundational, no incoming derives_from) = level 0
        3. Longest-path distance from roots = abstraction_level
           This correctly handles merge points: when node C is derived from both
           A and B, it gets max(level(A), level(B)) + 1.

        Validation:
        - Every derives_from edge must satisfy from.level > to.level
        - If violations exist, try to fix levels before removing edges
        - Cycles are broken by removing the edge with fewest assumptions
        """
        try:
            import networkx as nx

            node_map = {n.id: n for n in nodes}
            target_in_nodes = target in node_map

            if len(nodes) <= 1:
                return

            # ── Phase 1: Build level-computation DAG ──
            # DAG direction: foundational → derived (reversed from derives_from)
            G = nx.DiGraph()
            G.add_nodes_from(node_map.keys())

            for edge in edges:
                etype = str(edge.type.value) if hasattr(edge.type, 'value') else str(edge.type)
                if etype == "derives_from":
                    if edge.to in node_map and edge.from_ in node_map:
                        G.add_edge(edge.to, edge.from_)  # foundational → derived

            # ── Phase 2: Handle cycles ──
            if G.nodes() and not nx.is_directed_acyclic_graph(G):
                DecomposerAgent._break_cycles(G, edges)

            if not G.nodes() or not nx.is_directed_acyclic_graph(G):
                # Still cyclic or empty — assign default levels
                for i, node in enumerate(nodes):
                    node.abstraction_level = i % 6
                return

            # ── Phase 3: Longest-path distance from roots ──
            levels = {}
            topo = list(nx.topological_sort(G))

            for nid in topo:
                preds = list(G.predecessors(nid))
                if not preds:
                    levels[nid] = 0
                else:
                    # Merge point: maximum distance among all incoming derivation paths
                    levels[nid] = max(levels[p] for p in preds) + 1

            for nid, lvl in levels.items():
                if nid in node_map:
                    node_map[nid].abstraction_level = lvl

            # ── Phase 4: Handle nodes not in derives_from DAG ──
            unassigned = [n for n in nodes if n.id not in levels]
            if unassigned:
                max_lvl = max(levels.values()) if levels else 5
                for node in unassigned:
                    # Infer level from adjacent edges or related nodes
                    related_lvls = []
                    for edge in edges:
                        if edge.from_ == node.id and edge.to in levels:
                            related_lvls.append(levels[edge.to] + 1)
                        elif edge.to == node.id and edge.from_ in levels:
                            related_lvls.append(levels[edge.from_] - 1)
                    if related_lvls:
                        node.abstraction_level = max(0, sum(related_lvls) // len(related_lvls))
                    else:
                        node.abstraction_level = max_lvl // 2

            # ── Phase 5: Fix assumption nodes ──
            for node in nodes:
                ntype = node.type.value if hasattr(node.type, 'value') else str(node.type)
                if ntype == "assumption":
                    in_levels, out_levels = [], []
                    for edge in edges:
                        if edge.to == node.id:
                            src = node_map.get(edge.from_)
                            if src:
                                in_levels.append(src.abstraction_level)
                        if edge.from_ == node.id:
                            tgt = node_map.get(edge.to)
                            if tgt:
                                out_levels.append(tgt.abstraction_level)
                    if in_levels and out_levels:
                        node.abstraction_level = (max(in_levels) + min(out_levels) + 1) // 2
                    elif in_levels:
                        node.abstraction_level = max(in_levels)
                    elif out_levels:
                        node.abstraction_level = max(0, min(out_levels) - 1)

            # ── Phase 6: Validate and fix derives_from direction ──
            # derives_from: from.level MUST be > to.level
            # Fix approach: adjust levels upward (propagate) rather than deleting edges
            DecomposerAgent._fix_level_direction_violations(node_map, edges, target)

            # ── Phase 7: Ensure target node is at the top ──
            if target_in_nodes:
                max_lvl = max((n.abstraction_level for n in nodes), default=0)
                if node_map[target].abstraction_level < max_lvl:
                    node_map[target].abstraction_level = max_lvl

            # ── Phase 8: Bridge weakly-connected components ──
            DecomposerAgent._bridge_components(node_map, nodes, edges)

            # ── Phase 9: Re-assign levels via topological depth ──
            # LLM-assigned levels are often unreliable (most nodes at level 0).
            # Use reverse topological sort: compute longest path from each node
            # to the target node. This gives meaningful "distance from target".
            try:
                import networkx as nx
                G_lvl = nx.DiGraph()
                for node in nodes:
                    G_lvl.add_node(node.id)
                for edge in edges:
                    etype = edge.type.value if hasattr(edge.type, 'value') else str(edge.type)
                    if etype == "derives_from":
                        G_lvl.add_edge(edge.to, edge.from_)
                    else:
                        G_lvl.add_edge(edge.from_, edge.to)

                if nx.is_directed_acyclic_graph(G_lvl) and target in G_lvl:
                    level_map = {}
                    for nid in nx.topological_sort(G_lvl):
                        preds = list(G_lvl.predecessors(nid))
                        if not preds:
                            level_map[nid] = 0
                        else:
                            level_map[nid] = max(level_map.get(p, 0) for p in preds) + 1

                    max_depth = max(level_map.values()) if level_map else 1
                    target_depth = level_map.get(target, max_depth)

                    if target_depth > 0 and max_depth > 0:
                        for nid in level_map:
                            level_map[nid] = round(level_map[nid] * 10 / max_depth)
                        level_map[target] = 10

                    for node in nodes:
                        if node.id in level_map:
                            node.abstraction_level = level_map[node.id]
            except Exception as e:
                print(f"[WARN] 拓扑层级重算失败: {e}")

            # ── Phase 9b: Quantize to [0..10] if needed ──
            actual_levels = sorted(set(n.abstraction_level for n in nodes))
            if len(actual_levels) > 11:
                step = len(actual_levels) / 11.0
                level_remap = {}
                for i, old in enumerate(actual_levels):
                    level_remap[old] = min(10, int(i / step))
            else:
                level_remap = {old: new for new, old in enumerate(actual_levels)}
            for node in nodes:
                node.abstraction_level = level_remap.get(node.abstraction_level, 0)

            # ── Phase 9c: Re-fix direction violations after quantization ──
            DecomposerAgent._fix_level_direction_violations(node_map, edges, target)

            # ── Phase 9d: Final quantize to [0..10] ──
            actual_levels = sorted(set(n.abstraction_level for n in nodes))
            if len(actual_levels) > 11:
                step = len(actual_levels) / 11.0
                level_remap = {}
                for i, old in enumerate(actual_levels):
                    level_remap[old] = min(10, int(i / step))
            else:
                level_remap = {old: new for new, old in enumerate(actual_levels)}
            for node in nodes:
                node.abstraction_level = level_remap.get(node.abstraction_level, 0)

            # Final: ensure target is at the highest level
            if target_in_nodes:
                max_lvl = max((n.abstraction_level for n in nodes), default=0)
                if node_map[target].abstraction_level < max_lvl:
                    node_map[target].abstraction_level = max_lvl

        except ImportError:
            pass
        except Exception as e:
            print(f"[WARN] _apply_level_constraints 执行失败: {e}")

    @staticmethod
    def _break_cycles(G, edges):
        """Break cycles in the level-computation DAG by removing the weakest edge in each cycle."""
        import networkx as nx
        try:
            cycles = list(nx.simple_cycles(G))
        except Exception:
            return
        for cycle in cycles:
            if len(cycle) <= 1:
                continue
            weakest = None
            weakest_score = 999
            for i in range(len(cycle)):
                u, v = cycle[i], cycle[(i + 1) % len(cycle)]
                if G.has_edge(u, v):
                    # Prefer to break edges with fewer assumptions (weaker derivation)
                    corr_edge = next((e for e in edges if e.from_ == v and e.to == u), None)
                    score = len(corr_edge.assumptions) if corr_edge and corr_edge.assumptions else 0
                    if score < weakest_score:
                        weakest_score = score
                        weakest = (u, v)
            if weakest:
                G.remove_edge(*weakest)

    @staticmethod
    def _fix_level_direction_violations(node_map, edges, target):
        """
        Fix derives_from direction violations by adjusting levels.
        A derives_from B  →  A.level must be > B.level.
        When violated, increase A.level and propagate upward.
        """
        changed = True
        max_iterations = 50
        iteration = 0

        while changed and iteration < max_iterations:
            changed = False
            iteration += 1
            for edge in edges:
                etype = str(edge.type.value) if hasattr(edge.type, 'value') else str(edge.type)
                if etype != "derives_from":
                    continue
                fn = node_map.get(edge.from_)
                tn = node_map.get(edge.to)
                if not fn or not tn:
                    continue
                if fn.abstraction_level <= tn.abstraction_level:
                    fn.abstraction_level = tn.abstraction_level + 1
                    changed = True

        # Remove any remaining violations that couldn't be fixed
        edges_to_remove = set()
        for edge in edges:
            etype = str(edge.type.value) if hasattr(edge.type, 'value') else str(edge.type)
            if etype != "derives_from":
                continue
            fn = node_map.get(edge.from_)
            tn = node_map.get(edge.to)
            if fn and tn and fn.abstraction_level <= tn.abstraction_level:
                edges_to_remove.add(edge.id)

        if edges_to_remove:
            # edges list is modified in place by the caller's list reference
            edges[:] = [e for e in edges if e.id not in edges_to_remove]

    @staticmethod
    def _bridge_components(node_map, nodes, edges):
        """Connect weakly-connected components with bridge edges."""
        import networkx as nx

        if len(nodes) <= 1:
            return

        G_conn = nx.DiGraph()
        for node in nodes:
            G_conn.add_node(node.id)
        for edge in edges:
            G_conn.add_edge(edge.from_, edge.to)

        components = list(nx.weakly_connected_components(G_conn))
        if len(components) <= 1:
            return

        largest = max(components, key=len)
        for small_comp in components:
            if small_comp == largest:
                continue

            best_small = None
            best_large = None
            best_score = -999

            for nid in small_comp:
                sn = node_map.get(nid)
                if not sn:
                    continue
                for lid in largest:
                    ln = node_map.get(lid)
                    if not ln:
                        continue
                    score = 0
                    if sn.domain == ln.domain:
                        score += 10
                    if abs(sn.abstraction_level - ln.abstraction_level) <= 2:
                        score += 5
                    if ln.abstraction_level > sn.abstraction_level:
                        score += 3
                    if score > best_score:
                        best_score = score
                        best_small = sn
                        best_large = ln

            if best_small and best_large:
                if best_large.abstraction_level >= best_small.abstraction_level:
                    from_id, to_id = best_large.id, best_small.id
                else:
                    from_id, to_id = best_small.id, best_large.id

                from_part = from_id.split('.')[-1] if '.' in from_id else from_id
                to_part = to_id.split('.')[-1] if '.' in to_id else to_id
                try:
                    bridge = Edge(
                        id=f"edge.{from_part}.derives_from.{to_part}",
                        type="derives_from", from_=from_id, to=to_id,
                        assumptions=["假设条件待补充"],
                        derivation_steps=["推导步骤待补充"],
                        math_used=[],
                        path_id=f"path.{from_part.replace('.', '_')}.bridge"
                    )
                    edges.append(bridge)
                except Exception:
                    pass

        # Remove nodes that remain completely isolated after bridging
        G_conn2 = nx.DiGraph()
        for node in nodes:
            G_conn2.add_node(node.id)
        for edge in edges:
            G_conn2.add_edge(edge.from_, edge.to)

        final_components = list(nx.weakly_connected_components(G_conn2))
        if final_components:
            final_largest = max(final_components, key=len)
            if len(final_largest) < len(nodes):
                nodes[:] = [n for n in nodes if n.id in final_largest]
                edges[:] = [e for e in edges if e.from_ in final_largest and e.to in final_largest]

    def _get_edges_from_seeds(self, target_node_id: str) -> List[Edge]:
        try:
            all_seeds = self.loader.load_all_seeds()
            related = []
            for domain, seed_data in all_seeds.items():
                for edge_data in seed_data.get("edges", []):
                    if edge_data.get("from") == target_node_id or edge_data.get("to") == target_node_id:
                        try:
                            related.append(Edge(**edge_data))
                        except Exception as e:
                            print(f"警告: 解析边失败 {edge_data.get('id', 'unknown')}: {e}")
            return related
        except Exception as e:
            print(f"警告: 从种子数据获取边失败: {e}")
            return []
