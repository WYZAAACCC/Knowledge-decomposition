"""
数据模型定义

基于工程文档第7章的数据模型规范，使用Pydantic实现。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict


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
    """边类型枚举"""
    DERIVES_FROM = "derives_from"
    REQUIRES = "requires"
    USES_MATH = "uses_math"
    ASSUMES = "assumes"
    EQUIVALENT_TO = "equivalent_to"
    SPECIAL_CASE_OF = "special_case_of"
    APPROXIMATION_OF = "approximation_of"
    APPLIES_TO = "applies_to"
    MOTIVATED_BY = "motivated_by"
    RELATED_TO = "related_to"


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


class VerifiedInfo(BaseModel):
    """验证状态"""
    schema_: bool = Field(alias="schema", default=False)
    unit: bool = False
    symbolic: bool = False


# ===== 节点模型 =====

class Node(BaseModel):
    """知识图谱节点"""
    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
    type: NodeType
    title: str = Field(..., min_length=1, max_length=100)
    statement: Optional[str] = Field(None, min_length=1, max_length=2000)
    formula_latex: Optional[str] = Field(None, min_length=1, max_length=1000)
    domain: Domain
    abstraction_level: int = Field(..., ge=0, le=10)
    pedagogical_level: int = Field(..., ge=1, le=10)
    theory_context: Optional[TheoryContext] = None
    status: NodeStatus = NodeStatus.CANONICAL
    validity: Optional[ValidityInfo] = None
    aliases: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    sources: List[str] = Field(..., min_length=1)
    dimension: Optional[DimensionInfo] = None

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
    """知识图谱边"""
    id: str = Field(
        ...,
        pattern=r"^edge\.[a-z0-9_]+\.(derives_from|requires|uses_math|assumes|equivalent_to|special_case_of|approximation_of|applies_to|motivated_by|related_to)\.[a-z0-9_]+$"
    )
    type: EdgeType
    from_: str = Field(alias="from", pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
    to: str = Field(..., pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
    path_id: str = Field(..., pattern=r"^path\.[a-z0-9_]+(\.[a-z0-9_]+)*$")
    assumptions: List[str] = Field(default_factory=list)
    derivation_steps: List[str] = Field(default_factory=list)
    math_used: List[str] = Field(default_factory=list)
    approximation_tags: List[str] = Field(default_factory=list)
    verified: Optional[VerifiedInfo] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    failure_conditions: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("assumptions", "derivation_steps")
    @classmethod
    def validate_derivation_fields(cls, v: List[str], info):
        """derives_from边必须包含assumptions和derivation_steps"""
        edge_type = info.data.get("type")
        if edge_type == EdgeType.DERIVES_FROM:
            if not v:
                raise ValueError("derives_from edges must have non-empty assumptions and derivation_steps")
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
    """构建元数据"""
    build_timestamp: Optional[str] = None  # ISO格式
    build_duration_seconds: Optional[float] = Field(None, ge=0)
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