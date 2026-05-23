"""
数据模型定义

基于工程文档第7章的数据模型规范，使用Pydantic实现。
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict


def make_edge_id(edge_type: str, from_id: str, to_id: str) -> str:
    """Fix 16: 稳定Edge ID生成"""
    digest = hashlib.sha1(f"{edge_type}|{from_id}|{to_id}".encode()).hexdigest()[:10]
    return f"edge.{edge_type}.{digest}"


def make_proof_step_id(operation: str, output_id: str) -> str:
    """Fix 16: 稳定ProofStep ID生成"""
    digest = hashlib.sha1(f"{operation}|{output_id}".encode()).hexdigest()[:10]
    return f"proofstep.{operation}.{digest}"


# ===== 枚举类型 =====

class NodeType(str, Enum):
    """节点类型枚举"""
    CONCEPT = "concept"
    QUANTITY = "quantity"
    DEFINITION = "definition"
    LAW = "law"
    EQUATION = "equation"
    MODEL = "model"
    ASSUMPTION = "assumption"
    MATH_TOOL = "math_tool"
    APPLICATION = "application"
    EXPERIMENT = "experiment"
    WARNING = "warning"
    INTUITION_CARD = "intuition_card"


class EdgeType(str, Enum):
    """边类型枚举

    Fix 0: 统一边方向 — from = prerequisite/premise/lower-level, to = conclusion/higher-level
    """
    DERIVES = "derives"              # 推荐：从前提推导到结论
    DERIVES_FROM = "derives_from"    # 兼容旧格式
    REQUIRES = "requires"
    USES_MATH = "uses_math"
    ASSUMES = "assumes"
    EQUIVALENT_TO = "equivalent_to"
    SPECIAL_CASE_OF = "special_case_of"
    APPROXIMATION_OF = "approximation_of"
    APPLIES_TO = "applies_to"
    MOTIVATED_BY = "motivated_by"
    RELATED_TO = "related_to"

# Fix 7: 只对推导类边检查 DAG
DERIVATION_EDGE_TYPES = {EdgeType.DERIVES, EdgeType.DERIVES_FROM, EdgeType.REQUIRES, EdgeType.USES_MATH}


class TrustLevel(str, Enum):
    """Fix 2: 知识来源可信度等级"""
    VERIFIED = "verified"          # 已通过所有验证
    SEED = "seed"                  # 来自 seed 知识库
    MANUAL = "manual"              # 人工审核
    TEXTBOOK = "textbook"          # 教材确认
    LLM_PROPOSAL = "llm_proposal"  # LLM 提议，需人工审核
    AUTO_GENERATED = "auto_generated"  # 自动生成，未验证
    UNKNOWN = "unknown"


class RetrievalStatus(str, Enum):
    """Fix 3: 检索状态"""
    OK = "ok"
    TOPIC_NOT_FOUND = "topic_not_found"
    NO_CONNECTED_SUBGRAPH = "no_connected_subgraph"
    EMPTY_SEED = "empty_seed"


class Domain(str, Enum):
    """学科域枚举"""
    MECHANICS = "mechanics"
    THERMODYNAMICS = "thermodynamics"
    ELECTROMAGNETISM = "electromagnetism"
    OPTICS = "optics"
    MODERN_PHYSICS = "modern_physics"
    MATH_TOOLS = "math_tools"


class TheoryContext(str, Enum):
    """理论上下文枚举"""
    CLASSICAL = "classical"
    RELATIVISTIC = "relativistic"
    QUANTUM_INTRO = "quantum_intro"
    QUANTUM_ADVANCED = "quantum_advanced"
    STATISTICAL = "statistical"
    PHENOMENOLOGICAL = "phenomenological"


class NodeStatus(str, Enum):
    """节点状态枚举"""
    CANONICAL = "canonical"
    ALTERNATE = "alternate"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class BuildStatus(str, Enum):
    """构建状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"


# ===== 基础模型 =====

class ValidityInfo(BaseModel):
    """有效性条件"""
    frame: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class DimensionInfo(BaseModel):
    """量纲信息"""
    symbol: str
    base_dimensions: str = Field(..., pattern=r"^((M|L|T|I|Θ|N|J)\^?[+-]?\d*\s*)*$")
    unit: str


class SourceRef(BaseModel):
    """Fix 2: 知识来源引用"""
    source_type: str = Field(default="unknown", pattern=r"^(seed|textbook|manual|llm|script|unknown)$")
    source_id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    page: Optional[str] = None
    confidence: float = Field(ge=0, le=1, default=1.0)


class DimensionVector(BaseModel):
    """Fix 8: 量纲向量 (M, L, T, I, Θ, N, J)"""
    M: int = 0
    L: int = 0
    T: int = 0
    I: int = 0
    Theta: int = 0
    N: int = 0
    J: int = 0


class DimensionCheck(BaseModel):
    """Fix 8: 量纲检查结果"""
    expression: str
    expected: Optional[DimensionVector] = None
    actual: Optional[DimensionVector] = None
    passed: bool
    details: list[str] = Field(default_factory=list)


class ProofStep(BaseModel):
    """改进 1: 可验证推导步骤"""
    id: str = Field(..., pattern=r"^proofstep\.[a-z0-9_]+(\.[a-z0-9_]+)*$")
    title: str = Field(..., min_length=1)
    input_node_ids: list[str] = Field(default_factory=list)
    output_node_id: str
    input_expressions: list[str] = Field(default_factory=list)
    output_expression: Optional[str] = None
    operation: str = Field(
        default="algebraic_transform",
        pattern=r"^(definition_expansion|substitution|algebraic_transform|differentiation|integration|projection|approximation|limit|conservation_law|empirical_law|boundary_condition)$"
    )
    assumption_ids: list[str] = Field(default_factory=list)
    dimension_check: Optional[DimensionCheck] = None
    explanation_zh: str = Field(min_length=1)
    explanation_en: Optional[str] = None
    source: list[SourceRef] = Field(default_factory=list)
    trust_level: TrustLevel = TrustLevel.SEED
    verified: bool = False


class TopicCandidate(BaseModel):
    """Fix 3: 候选主题"""
    node_id: str
    title: str
    alias_match_score: float = Field(ge=0, le=1)
    graph_distance_hint: Optional[int] = None


class VerifiedInfo(BaseModel):
    """验证状态"""
    schema_: bool = Field(alias="schema", default=False)
    unit: bool = False
    symbolic: bool = False


# ===== 节点模型 =====

class Node(BaseModel):
    """知识图谱节点

    Fix 2: 增加 trust_level, provenance, verified 字段
    Fix 0: from = prerequisite, to = conclusion
    """
    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
    type: NodeType
    title: str = Field(..., min_length=1, max_length=100)
    statement: Optional[str] = Field(None, min_length=1, max_length=2000)
    formula_latex: Optional[str] = Field(None, max_length=1000)
    domain: Domain
    abstraction_level: int = Field(..., ge=0, le=10)
    pedagogical_level: int = Field(..., ge=1, le=10)
    theory_context: Optional[TheoryContext] = None
    status: NodeStatus = NodeStatus.CANONICAL
    validity: Optional[ValidityInfo] = None
    aliases: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    dimension: Optional[DimensionInfo] = None
    # Fix 2: 信任与溯源
    trust_level: TrustLevel = TrustLevel.SEED
    provenance: list[SourceRef] = Field(default_factory=list)
    verified: bool = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("dimension")
    @classmethod
    def validate_dimension_for_types(cls, v: Optional[DimensionInfo], info):
        """允许quantity、equation、concept和law类型有dimension"""
        if v is not None:
            node_type = info.data.get("type")
            allowed_types = [NodeType.QUANTITY, NodeType.EQUATION, NodeType.CONCEPT, NodeType.LAW]
            if node_type not in allowed_types:
                raise ValueError(f"dimension only allowed for {allowed_types}, got {node_type}")
        return v


# ===== 边模型 =====

class Edge(BaseModel):
    """知识图谱边

    Fix 0: from = prerequisite, to = conclusion
    Fix 6: assumption_ids 替代自由文本 assumptions
    """
    id: str = Field(
        ...,
        pattern=r"^edge\.[a-z0-9_]+\.(derives|derives_from|requires|uses_math|assumes|equivalent_to|special_case_of|approximation_of|applies_to|motivated_by|related_to)\.[a-z0-9_]+$"
    )
    type: EdgeType
    from_: str = Field(alias="from", pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
    to: str = Field(..., pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
    path_id: Optional[str] = Field(None, pattern=r"^path\.[a-z0-9_]+(\.[a-z0-9_]+)*$")
    assumptions: List[str] = Field(default_factory=list)
    # Fix 6: 注册表假设 ID
    assumption_ids: List[str] = Field(default_factory=list)
    derivation_steps: List[str] = Field(default_factory=list)
    # 改进 1: 证明步骤 ID
    proof_step_ids: List[str] = Field(default_factory=list)
    math_used: List[str] = Field(default_factory=list)
    approximation_tags: List[str] = Field(default_factory=list)
    verified: Optional[VerifiedInfo] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    failure_conditions: List[str] = Field(default_factory=list)
    # Fix 2: 信任与溯源
    trust_level: TrustLevel = TrustLevel.SEED
    provenance: list[SourceRef] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("assumptions", "derivation_steps")
    @classmethod
    def validate_derivation_fields(cls, v: List[str], info):
        """derives/derives_from边应包含assumptions或derivation_steps"""
        edge_type = info.data.get("type")
        if edge_type in (EdgeType.DERIVES, EdgeType.DERIVES_FROM):
            if not v and not info.data.get("assumption_ids") and not info.data.get("proof_step_ids"):
                raise ValueError(f"{edge_type.value} edges must have assumptions, assumption_ids, or proof_step_ids")
        return v


# ===== 图统计模型 =====

class GraphStats(BaseModel):
    """图谱统计信息"""
    node_count: int = Field(..., ge=1)
    edge_count: int = Field(..., ge=0)
    derivation_edge_count: int = Field(..., ge=0)
    assumption_count: int = Field(..., ge=0)
    math_tool_count: int = Field(..., ge=0)
    prerequisite_coverage: Optional[float] = Field(None, ge=0.0, le=1.0)
    assumption_coverage: Optional[float] = Field(None, ge=0.0, le=1.0)


class ValidationSummary(BaseModel):
    """验证摘要"""
    schema_valid: bool
    dag_valid: bool
    assumptions_complete: bool
    dimensions_valid: bool
    canonical_path_exists: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class BuildMetadata(BaseModel):
    """Fix 12: 构建元数据"""
    schema_version: str = "0.1.0"
    build_timestamp: Optional[str] = None  # ISO格式
    build_duration_seconds: Optional[float] = Field(None, ge=0)
    pipeline_version: str = "0.1.0"
    seed_hash: Optional[str] = None
    llm_calls: int = 0
    offline: bool = False
    strict: bool = True
    error_count: int = 0
    warning_count: int = 0
    agent_versions: Optional[Dict[str, str]] = None
    seed_sources: Optional[List[str]] = None


# ===== 图谱模型 =====

class KnowledgeGraph(BaseModel):
    """知识图谱"""
    topic: str = Field(..., pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
    build_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    nodes: List[Node] = Field(..., min_length=1)
    edges: List[Edge] = Field(default_factory=list)
    canonical_path: str = Field(..., pattern=r"^path\.[a-z0-9_]+(\.[a-z0-9_]+)*$")
    alternate_paths: List[str] = Field(default_factory=list)
    # 改进 1: 证明步骤
    proof_steps: list[ProofStep] = Field(default_factory=list)
    stats: GraphStats
    validation_summary: ValidationSummary
    build_metadata: Optional[BuildMetadata] = None

    model_config = ConfigDict(extra="forbid")


# ===== 构建报告模型 =====

class ErrorInfo(BaseModel):
    """错误信息"""
    code: str = Field(..., pattern=r"^[A-Z_]+$")
    target: str
    message: str
    stage: Optional[str] = None


class WarningInfo(BaseModel):
    """警告信息"""
    code: str
    message: str
    target: Optional[str] = None


class StageTimings(BaseModel):
    """阶段计时"""
    router: Optional[float] = Field(None, ge=0)
    planner: Optional[float] = Field(None, ge=0)
    retriever: Optional[float] = Field(None, ge=0)
    decomposer: Optional[float] = Field(None, ge=0)
    verifier: Optional[float] = Field(None, ge=0)
    ranker: Optional[float] = Field(None, ge=0)
    renderer: Optional[float] = Field(None, ge=0)


class TimingInfo(BaseModel):
    """计时信息"""
    total_seconds: float = Field(..., ge=0)
    stage_timings: StageTimings


class ValidatorResult(BaseModel):
    """验证器结果"""
    passed: bool
    details: List[str] = Field(default_factory=list)


class ValidatorResults(BaseModel):
    """所有验证器结果"""
    schema_validation: Optional[ValidatorResult] = Field(default=None, alias="schema")
    graph: Optional[ValidatorResult] = None
    assumptions: Optional[ValidatorResult] = None
    dimensions: Optional[ValidatorResult] = None
    duplicates: Optional[ValidatorResult] = None


class BuildReport(BaseModel):
    """构建报告"""
    topic: str = Field(..., pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
    status: BuildStatus
    failed_stage: Optional[str] = Field(
        None,
        pattern="^(router|planner|retriever|decomposer|verifier|ranker|renderer|unknown)$"
    )
    errors: List[ErrorInfo] = Field(default_factory=list)
    warnings: List[WarningInfo] = Field(default_factory=list)
    graph_hash: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    timing: TimingInfo
    validator_results: ValidatorResults
    suggested_actions: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")