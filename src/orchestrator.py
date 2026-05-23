"""
编排器

协调各个Agent的执行流程。
"""

import json
import re
import time
import sys
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

from .agents.router_agent import RouterAgent, RouterOutput
from .agents.planner_agent import PlannerAgent, PlannerOutput
from .agents.retriever_agent import RetrieverAgent, RetrievalOutput
from .agents.decomposer_agent import DecomposerAgent, DecomposerOutput
from .agents.verifier_agent import VerifierAgent, VerificationOutput
from .agents.ranker_agent import RankerAgent, RankerOutput
from .agents.renderer_agent import RendererAgent, RendererOutput
from .loader import DataLoader
from .models import KnowledgeGraph, ValidationSummary, BuildMetadata, TrustLevel
from .utils.logging import get_default_logger


class BuildStage(str, Enum):
    START = "start"
    ROUTER = "router"
    PLANNER = "planner"
    RETRIEVAL = "retrieval"
    DECOMPOSER = "decomposer"
    VERIFICATION = "verification"
    RANKER = "ranker"
    RENDERER = "renderer"
    FINALIZE = "finalize"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ProgressUpdate:
    stage: BuildStage
    status: str
    message: str
    details: Dict[str, Any]
    timestamp: float


@dataclass
class BuildResult:
    status: str
    topic: str
    graph: Optional[KnowledgeGraph]
    artifacts: Dict[str, Any]
    timing: Dict[str, float]
    errors: list
    warnings: list
    debug_info: Dict[str, Any]
    progress_updates: list


_STAGE_CN = {
    "start": "开始", "router": "路由", "planner": "规划",
    "retrieval": "检索", "decomposer": "分解", "verification": "验证",
    "ranker": "排名", "renderer": "渲染", "finalize": "最终化",
    "complete": "完成", "error": "错误",
}

_MSG_SIMPLIFY = [
    ("开始构建主题", "开始构建"), ("RouterAgent完成", "路由完成"),
    ("PlannerAgent完成", "规划完成"), ("RetrieverAgent完成", "检索完成"),
    ("DecomposerAgent完成", "分解完成"), ("VerifierAgent完成", "验证完成"),
    ("RankerAgent完成", "排名完成"), ("RendererAgent完成", "渲染完成"),
    ("最终图谱构建完成", "图谱构建完成"), ("主题构建完成", "构建完成"),
    ("构建失败", "构建失败"),
]


class _LLMCallCounter:
    """Fix 12: LLM调用计数器"""
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1


class ProgressTracker:

    def __init__(self, progress_callback: Optional[Callable[[ProgressUpdate], None]] = None):
        self.progress_callback = progress_callback
        self.updates = []

    def update(self, stage: BuildStage, status: str, message: str, details: Dict[str, Any] = None):
        if details is None:
            details = {}

        update = ProgressUpdate(
            stage=stage, status=status, message=message,
            details=details, timestamp=time.time()
        )
        self.updates.append(update)

        if self.progress_callback:
            try:
                self.progress_callback(update)
            except Exception:
                pass

        stage_cn = _STAGE_CN.get(stage.value, stage.value)
        simple_message = message[:20] + "..." if len(message) > 20 else message
        for pattern, replacement in _MSG_SIMPLIFY:
            if pattern in message:
                simple_message = replacement
                break

        print(f"[PROGRESS] {stage.value}: {status} - {simple_message}", file=sys.stderr)
        if details:
            for key in ["duration", "node_count", "edge_count", "candidate_nodes", "score", "passed"]:
                if key in details:
                    print(f"  {key}: {details[key]}", file=sys.stderr)


class GraphBuildOrchestrator:

    def __init__(self, artifacts_dir: str = "artifacts/latest",
                 progress_callback: Optional[Callable[[ProgressUpdate], None]] = None,
                 offline: bool = False,
                 strict: bool = False,
                 no_llm: bool = False,
                 allow_proposals: bool = False):
        self.logger = get_default_logger()
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Fix 14: 新增模式
        self.offline = offline
        self.strict = strict
        self.no_llm = no_llm
        self.allow_proposals = allow_proposals

        self.progress_tracker = ProgressTracker(progress_callback)

        self.loader = DataLoader()
        self.router = RouterAgent(self.loader, offline=self.offline)
        self.planner = PlannerAgent(self.loader)
        self.retriever = RetrieverAgent(self.loader)
        self.decomposer = DecomposerAgent(self.loader)
        self.verifier = VerifierAgent()
        self.ranker = RankerAgent()
        self.renderer = RendererAgent(artifacts_dir)

        self.timing = {}
        self.errors = []
        self.warnings = []
        self.llm_call_counter = _LLMCallCounter()
        self._down = None
        self._up = None
        self._max_nodes = None

    def build_topic(self, topic_text: str, max_retries: int = 1,
                    down: int = None, up: int = None, max_nodes: int = None) -> BuildResult:
        self.logger.info(f"开始构建主题: {topic_text}")
        self.timing = {}
        self.errors = []
        self.warnings = []
        self._down = down
        self._up = up
        self._max_nodes = max_nodes

        start_time = time.time()

        self.progress_tracker.update(
            BuildStage.START, "started",
            f"开始构建主题: {topic_text}",
            {"topic": topic_text, "down": down, "up": up, "max_nodes": max_nodes}
        )

        try:
            validated_topic = self._validate_input(topic_text)
            if validated_topic is None:
                raise ValueError(f"输入无效: '{topic_text[:50]}' 不是有效的物理主题")
            topic_text = validated_topic

            router_output = self._run_stage(
                BuildStage.ROUTER, "运行RouterAgent进行主题标准化",
                lambda: self.router.run(topic_text),
                lambda out: f"RouterAgent完成: {out.normalized_topic if out else '失败'}",
                lambda out: {"normalized_topic": out.normalized_topic if out else None}
            )
            if not router_output or not router_output.normalized_topic:
                raise RuntimeError(f"路由失败: 无法标准化主题 '{topic_text}'")

            planner_output = self._run_stage(
                BuildStage.PLANNER, "运行PlannerAgent制定展开计划",
                lambda: self.planner.run(self._build_planner_input(router_output)),
                lambda out: f"PlannerAgent完成: {out.target if out else '失败'}",
                lambda out: {"target": out.target if out else None}
            )

            retrieval_output = self._run_stage(
                BuildStage.RETRIEVAL, "运行RetrieverAgent检索候选知识",
                lambda: self.retriever.run(self._to_dict(planner_output)),
                lambda out: f"RetrieverAgent完成: 找到{len(out.candidate_nodes) if out else 0}个候选节点",
                lambda out: {"candidate_nodes": len(out.candidate_nodes) if out else 0}
            )
            if not retrieval_output.candidate_nodes:
                self.warnings.append("检索阶段未找到候选节点，图谱可能为空")

            decomposer_output = self._run_stage(
                BuildStage.DECOMPOSER, "运行DecomposerAgent组装子图",
                lambda: self.decomposer.run(self._to_dict(retrieval_output)),
                lambda out: (f"DecomposerAgent完成: 组装{len(out.subgraph.nodes) if out and out.subgraph else 0}个节点, "
                             f"{len(out.subgraph.edges) if out and out.subgraph else 0}条边"),
                lambda out: {
                    "node_count": len(out.subgraph.nodes) if out and out.subgraph else 0,
                    "edge_count": len(out.subgraph.edges) if out and out.subgraph else 0
                }
            )

            verification_output = self._run_stage(
                BuildStage.VERIFICATION, "运行VerifierAgent验证图谱",
                lambda: self.verifier.run(self._to_dict(decomposer_output)),
                lambda out: f"VerifierAgent完成: {'通过' if out and out.passed else '未通过'}, "
                            f"分数{out.overall_score if out else 0:.2f}",
                lambda out: {"passed": out.passed if out else False, "score": out.overall_score if out else 0}
            )

            ranker_output = self._run_stage(
                BuildStage.RANKER, "运行RankerAgent选择规范路径",
                lambda: self.ranker.run(self._to_dict(decomposer_output),
                                        self._to_dict(verification_output) if verification_output else None),
                lambda out: f"RankerAgent完成: 选择规范路径 '{out.selected_canonical_path if out else '无'}'",
                lambda out: {"canonical_path": out.selected_canonical_path if out else None}
            )

            # Fix 1: Build final_graph BEFORE running renderer
            self.progress_tracker.update(BuildStage.FINALIZE, "started", "构建最终图谱")
            final_graph = self._build_final_graph(
                decomposer_output.subgraph, ranker_output, verification_output
            )
            self.progress_tracker.update(
                BuildStage.FINALIZE, "completed",
                f"最终图谱构建完成: {len(final_graph.nodes)}个节点, {len(final_graph.edges)}条边",
                {"node_count": len(final_graph.nodes), "edge_count": len(final_graph.edges)}
            )

            renderer_output = self._run_stage(
                BuildStage.RENDERER, "运行RendererAgent生成输出工件",
                lambda: self._run_renderer(final_graph, ranker_output, verification_output),
                lambda out: "RendererAgent完成",
                lambda out: {}
            )

            artifacts = self._collect_artifacts(
                final_graph, router_output, planner_output, retrieval_output,
                decomposer_output, verification_output, ranker_output, renderer_output
            )

            self.timing["total"] = time.time() - start_time

            status = self._determine_status(final_graph, verification_output)

            self.progress_tracker.update(
                BuildStage.COMPLETE, "completed",
                f"主题构建完成: {status}",
                {"status": status, "total_duration": self.timing["total"]}
            )

            result = BuildResult(
                status=status, topic=topic_text, graph=final_graph,
                artifacts=artifacts, timing=self.timing,
                errors=self.errors, warnings=self.warnings,
                debug_info=self._build_debug_info(
                    router_output, planner_output, retrieval_output,
                    decomposer_output, verification_output, ranker_output
                ),
                progress_updates=self.progress_tracker.updates
            )

            self.logger.info(f"主题构建完成: {topic_text}, 状态: {status}, 耗时: {self.timing['total']:.2f}s")
            return result

        except Exception as e:
            self.timing["total"] = time.time() - start_time
            self.errors.append(f"构建过程中发生异常: {str(e)}")
            self.logger.error(f"构建主题失败: {topic_text}, 错误: {e}")

            self.progress_tracker.update(
                BuildStage.ERROR, "failed", f"构建失败: {str(e)}", {"exception": str(e)}
            )

            return BuildResult(
                status="failed", topic=topic_text, graph=None,
                artifacts={}, timing=self.timing,
                errors=self.errors, warnings=self.warnings,
                debug_info={"exception": str(e)},
                progress_updates=self.progress_tracker.updates
            )

    def _run_stage(self, stage: BuildStage, start_msg: str,
                   run_fn: Callable, complete_msg_fn: Callable,
                   details_fn: Callable):
        self.progress_tracker.update(stage, "started", start_msg)
        stage_start = time.time()
        result = run_fn()
        self.timing[stage.value] = time.time() - stage_start
        self.progress_tracker.update(
            stage, "completed", complete_msg_fn(result),
            {**details_fn(result), "duration": self.timing[stage.value]}
        )
        return result

    def _build_planner_input(self, router_output: RouterOutput) -> Dict[str, Any]:
        d = self._to_dict(router_output)
        if self._down is not None:
            d['down'] = self._down
        if self._up is not None:
            d['up'] = self._up
        if self._max_nodes is not None:
            d['max_nodes'] = self._max_nodes
        return d

    def _run_renderer(self, final_graph: KnowledgeGraph,
                      ranker_output: RankerOutput,
                      verification_output: VerificationOutput) -> Optional[RendererOutput]:
        # Fix 1: Renderer receives the final graph with canonical_path and validation_summary
        renderer_input = {
            "graph": final_graph,
            "canonical_path": getattr(ranker_output, "selected_canonical_path", None) if ranker_output else None,
            "alternate_paths": getattr(ranker_output, "alternate_paths", []) if ranker_output else [],
            "validation": self._to_dict(verification_output) if verification_output else None,
        }
        return self.renderer.run(
            renderer_input,
            self._to_dict(verification_output) if verification_output else None
        )

    @staticmethod
    def _to_dict(obj) -> Dict[str, Any]:
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        return obj.__dict__

    def _validate_input(self, topic_text: str) -> Optional[str]:
        if not topic_text or not topic_text.strip():
            return None
        topic_text = topic_text.strip()
        if len(topic_text) > 100:
            topic_text = topic_text[:100]

        xss_patterns = [r'<script', r'javascript:', r'on\w+\s*=', r'<iframe', r'<img\s+on']
        for pattern in xss_patterns:
            if re.search(pattern, topic_text, re.IGNORECASE):
                return None

        sql_patterns = [r"'\s*;\s*drop\s", r"'\s*;\s*delete\s", r"'\s*;\s*insert\s",
                        r"'\s*or\s+'1'\s*=\s*'1", r"union\s+select", r"--\s*$"]
        for pattern in sql_patterns:
            if re.search(pattern, topic_text, re.IGNORECASE):
                return None

        if re.match(r'^[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\s]+$', topic_text):
            return None

        if re.match(r'^[a\s]+$', topic_text, re.IGNORECASE) and len(topic_text) > 50:
            return None

        return topic_text

    def _build_final_graph(self, subgraph: KnowledgeGraph,
                           ranker_output: RankerOutput,
                           verification_output: VerificationOutput) -> KnowledgeGraph:
        if ranker_output and ranker_output.selected_canonical_path:
            subgraph.canonical_path = ranker_output.selected_canonical_path
        if ranker_output and ranker_output.alternate_paths:
            subgraph.alternate_paths = ranker_output.alternate_paths

        if verification_output:
            try:
                subgraph.validation_summary = ValidationSummary(
                    schema_valid=getattr(verification_output, 'passed', False),
                    dag_valid=getattr(verification_output, 'passed', False),
                    assumptions_complete=getattr(verification_output, 'overall_score', 0) >= 0.7,
                    dimensions_valid=getattr(verification_output, 'overall_score', 0) >= 0.7,
                    canonical_path_exists=bool(subgraph.canonical_path),
                    errors=getattr(verification_output, 'critical_errors', []),
                    warnings=getattr(verification_output, 'warnings', [])[:10]
                )
            except Exception:
                pass

        # Fix 12: Use proper BuildMetadata Pydantic model
        import datetime
        subgraph.build_metadata = BuildMetadata(
            build_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            build_duration_seconds=self.timing.get("total", 0),
            seed_sources=list(self.loader.load_all_seeds().keys()),
        )
        return subgraph

    def _determine_status(self, graph: KnowledgeGraph,
                          verification_output: VerificationOutput) -> str:
        if not graph.nodes:
            self.errors.append("图谱为空")
            return "failed"
        if verification_output and not verification_output.passed:
            if verification_output.overall_score >= 0.3:
                self.warnings.append("验证未完全通过，但分数达到阈值")
                return "partial_success"
            self.errors.append("验证失败")
            return "failed"
        return "success"

    def _collect_artifacts(self, graph: KnowledgeGraph,
                           router_output: RouterOutput,
                           planner_output: PlannerOutput,
                           retrieval_output: RetrievalOutput,
                           decomposer_output: DecomposerOutput,
                           verification_output: VerificationOutput,
                           ranker_output: RankerOutput,
                           renderer_output: Optional[RendererOutput]) -> Dict[str, Any]:
        artifacts = {}

        # Fix 11: NEVER replace final_graph with decomposer subgraph
        # The graph passed here is the authoritative final graph

        if renderer_output and hasattr(renderer_output, 'artifacts'):
            artifacts.update(renderer_output.artifacts)

        if "graph_json" not in artifacts:
            graph_file = self.artifacts_dir / "graph.json"
            with open(graph_file, 'w', encoding='utf-8') as f:
                json.dump(graph.model_dump(by_alias=True), f, ensure_ascii=False, indent=2)
            artifacts["graph_json"] = str(graph_file)

        if "debug_json" not in artifacts:
            debug_info = self._build_debug_info(
                router_output, planner_output, retrieval_output,
                decomposer_output, verification_output, ranker_output
            )
            debug_file = self.artifacts_dir / "debug.json"
            with open(debug_file, 'w', encoding='utf-8') as f:
                json.dump(debug_info, f, ensure_ascii=False, indent=2)
            artifacts["debug_json"] = str(debug_file)

        if "report_md" not in artifacts:
            report_file = self.artifacts_dir / "report.md"
            report_content = self._generate_report(graph, verification_output, ranker_output)
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            artifacts["report_md"] = str(report_file)

        if "eval_report_json" not in artifacts:
            eval_info = {
                "topic": graph.topic,
                "build_status": "success" if graph else "failed",
                "validation_score": verification_output.overall_score if verification_output else 0.0,
                "node_count": len(graph.nodes) if graph else 0,
                "edge_count": len(graph.edges) if graph else 0,
                "assumption_coverage": (
                    verification_output.validation_results.get("assumptions", {}).get("score", 0.0)
                    if verification_output else 0.0
                ),
                "dimension_pass_rate": (
                    1.0 if verification_output and verification_output.validation_results.get("dimensions", {}).get("passed", False) else 0.0
                ),
                "canonical_path_exists": bool(graph.canonical_path) if graph else False
            }
            eval_file = self.artifacts_dir / "eval_report.json"
            with open(eval_file, 'w', encoding='utf-8') as f:
                json.dump(eval_info, f, ensure_ascii=False, indent=2)
            artifacts["eval_report_json"] = str(eval_file)

        return artifacts

    def _build_debug_info(self, router_output, planner_output, retrieval_output,
                          decomposer_output, verification_output, ranker_output) -> Dict[str, Any]:
        return {
            "router_output": self._to_dict(router_output),
            "planner_output": self._to_dict(planner_output),
            "retrieval_evidence": retrieval_output.retrieval_evidence if retrieval_output else {},
            "assembly_evidence": decomposer_output.assembly_evidence if decomposer_output else {},
            "validation_results": verification_output.validation_results if verification_output else {},
            "ranking_scores": ranker_output.ranking_scores if ranker_output else {}
        }

    def _generate_report(self, graph: KnowledgeGraph,
                         verification_output: VerificationOutput,
                         ranker_output: RankerOutput) -> str:
        """改进 10: 升级为结构化知识分解报告"""
        lines = [
            f"# {graph.topic} 知识分解报告", "",
            "## 1. 目标知识点",
            f"- **主题ID**: `{graph.topic}`",
            f"- **类型**: {self._get_topic_node_type(graph)}",
            f"- **公式**: {self._get_topic_formula(graph)}",
            f"- **构建状态**: {'成功' if graph else '失败'}",
            ""
        ]

        # 分层依赖图
        if graph.nodes:
            levels = {}
            for node in graph.nodes:
                lvl = node.abstraction_level
                levels.setdefault(lvl, []).append(node)

            lines.extend(["## 2. 分层依赖图", ""])
            for lvl in sorted(levels.keys()):
                type_map = {
                    "concept": "基础概念", "definition": "定义",
                    "quantity": "物理量", "math_tool": "数学工具",
                    "law": "基本定律", "equation": "方程",
                    "assumption": "假设", "application": "应用",
                }
                label = type_map.get("concept", "")
                nodes_str = ", ".join(
                    f"`{n.id}`({n.title})" for n in levels[lvl][:8]
                )
                lines.append(f"- **Level {lvl}**: {nodes_str}")
            lines.append("")

        # 推导路径
        if graph.canonical_path:
            lines.extend([
                "## 3. 规范推导路径",
                f"**路径ID**: `{graph.canonical_path}`", "",
            ])
            path_edges = [e for e in graph.edges if e.path_id == graph.canonical_path]
            for i, edge in enumerate(path_edges, 1):
                from_node = self._find_node(graph, edge.from_)
                to_node = self._find_node(graph, edge.to)
                lines.append(
                    f"{i}. `{edge.from_}` ({from_node.title if from_node else '?'}) "
                    f"→ `{edge.to}` ({to_node.title if to_node else '?'})"
                    f"  [{edge.type.value}]"
                )
            if graph.proof_steps:
                lines.append("")
                lines.append("### 证明步骤")
                for ps in graph.proof_steps:
                    lines.append(f"- **{ps.id}**: {ps.explanation_zh}")
            lines.append("")

        # 假设
        lines.extend(["## 4. 显式假设", ""])
        all_assumptions = set()
        for edge in graph.edges:
            for aid in getattr(edge, 'assumption_ids', []) or []:
                all_assumptions.add(aid)
            for a in getattr(edge, 'assumptions', []) or []:
                all_assumptions.add(a)
        if all_assumptions:
            lines.append("| ID | 简述 |")
            lines.append("|----|------|")
            for aid in sorted(all_assumptions):
                lines.append(f"| `{aid}` | - |")
        else:
            lines.append("*无注册假设*")
        lines.append("")

        # 量纲验证
        if verification_output and verification_output.validation_results:
            dim_result = verification_output.validation_results.get("dimensions", {})
            lines.extend([
                "## 5. 量纲验证",
                f"- **通过**: {'是' if dim_result.get('passed', False) else '否'}",
                f"- **分数**: {dim_result.get('score', 0):.2f}",
                ""
            ])

        # 验证结果
        if verification_output:
            lines.extend([
                "## 6. 验证结果",
                f"- **总体分数**: {verification_output.overall_score:.2f}",
                f"- **Schema**: {'PASS' if verification_output.validation_results.get('schema', {}).get('passed') else 'FAIL'}",
                f"- **图结构**: {'PASS' if verification_output.validation_results.get('graph_structure', {}).get('passed') else 'FAIL'}",
                f"- **假设**: {'PASS' if verification_output.validation_results.get('assumptions', {}).get('passed') else 'FAIL'}",
                f"- **占位检查**: {'PASS' if verification_output.validation_results.get('placeholder', {}).get('passed') else 'FAIL'}",
                ""
            ])
            if verification_output.critical_errors:
                lines.append("### 关键错误")
                lines.extend(f"- {e}" for e in verification_output.critical_errors[:10])
                lines.append("")

        # 来源
        lines.extend([
            "## 7. 来源与可信度", "",
            "| 源类型 | 节点数 |",
            "|--------|--------|",
        ])
        trust_counts = {}
        for node in graph.nodes:
            tl = getattr(node, 'trust_level', TrustLevel.SEED)
            trust_counts[tl.value if hasattr(tl, 'value') else str(tl)] = \
                trust_counts.get(tl.value if hasattr(tl, 'value') else str(tl), 0) + 1
        for tl, count in sorted(trust_counts.items()):
            lines.append(f"| {tl} | {count} |")
        lines.append("")

        # 建议
        if verification_output and verification_output.suggested_actions:
            lines.append("## 8. 建议操作")
            lines.extend(f"- {a}" for a in verification_output.suggested_actions)
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _get_topic_node_type(graph) -> str:
        for node in graph.nodes:
            if node.id == graph.topic:
                return node.type.value
        return "unknown"

    @staticmethod
    def _get_topic_formula(graph) -> str:
        for node in graph.nodes:
            if node.id == graph.topic and node.formula_latex:
                return f"${node.formula_latex}$"
        return "N/A"

    @staticmethod
    def _find_node(graph, node_id):
        for node in graph.nodes:
            if node.id == node_id:
                return node
        return None
