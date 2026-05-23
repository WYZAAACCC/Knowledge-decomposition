"""
Schema验证器

验证节点、边、图和构建报告是否符合JSON schema。
"""

import json
import jsonschema
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

from ..models import Node, Edge, KnowledgeGraph, BuildReport
from ..loader import DataLoader


class SchemaValidator:
    """Schema验证器"""

    def __init__(self, loader: Optional[DataLoader] = None):
        """
        初始化

        Args:
            loader: 数据加载器，用于加载schema文件
        """
        self.loader = loader or DataLoader()
        self._schemas_cache: Dict[str, Dict] = {}

    def _load_schema(self, schema_name: str) -> Dict:
        """加载schema（带缓存）"""
        if schema_name not in self._schemas_cache:
            # 加载schema文件
            schema = self.loader.load_schema(schema_name)
            # 如果是graph schema，移除对外部文件的引用，使用内联定义
            if schema_name == "graph":
                # 移除对node.schema.json和edge.schema.json的引用
                if "properties" in schema:
                    if "nodes" in schema["properties"]:
                        if "items" in schema["properties"]["nodes"]:
                            if "$ref" in schema["properties"]["nodes"]["items"]:
                                schema["properties"]["nodes"]["items"]["$ref"] = "#/definitions/node"
                    if "edges" in schema["properties"]:
                        if "items" in schema["properties"]["edges"]:
                            if "$ref" in schema["properties"]["edges"]["items"]:
                                schema["properties"]["edges"]["items"]["$ref"] = "#/definitions/edge"
            self._schemas_cache[schema_name] = schema
        return self._schemas_cache[schema_name]

    def validate_node(self, node_data: Union[Dict, Node]) -> Tuple[bool, List[str]]:
        """
        验证节点schema

        Args:
            node_data: 节点数据（字典或Node对象）

        Returns:
            (是否通过, 错误信息列表)
        """
        try:
            # 转换为字典
            if isinstance(node_data, Node):
                data = node_data.model_dump(by_alias=True)
            else:
                data = node_data

            schema = self._load_schema("node")
            jsonschema.validate(data, schema)
            return True, []

        except jsonschema.ValidationError as e:
            error_msg = f"节点schema验证失败: {e.message}"
            if e.path:
                error_msg += f" (路径: {'/'.join(str(p) for p in e.path)})"
            return False, [error_msg]

        except Exception as e:
            return False, [f"节点schema验证异常: {str(e)}"]

    def validate_edge(self, edge_data: Union[Dict, Edge]) -> Tuple[bool, List[str]]:
        """
        验证边schema

        Args:
            edge_data: 边数据（字典或Edge对象）

        Returns:
            (是否通过, 错误信息列表)
        """
        try:
            # 转换为字典
            if isinstance(edge_data, Edge):
                data = edge_data.model_dump(by_alias=True)
            else:
                data = edge_data

            schema = self._load_schema("edge")
            jsonschema.validate(data, schema)
            return True, []

        except jsonschema.ValidationError as e:
            error_msg = f"边schema验证失败: {e.message}"
            if e.path:
                error_msg += f" (路径: {'/'.join(str(p) for p in e.path)})"
            return False, [error_msg]

        except Exception as e:
            return False, [f"边schema验证异常: {str(e)}"]

    def validate_graph(self, graph_data: Union[Dict, KnowledgeGraph]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        验证图谱schema

        Args:
            graph_data: 图谱数据（字典或KnowledgeGraph对象）

        Returns:
            (是否通过, 错误信息列表, 验证详情)
        """
        try:
            # 转换为字典
            if isinstance(graph_data, KnowledgeGraph):
                data = graph_data.model_dump(by_alias=True)
            else:
                data = graph_data

            # 直接使用包含内联定义的schema，避免外部引用
            graph_schema = {
                "$schema": "http://json-schema.org/draft-2020-12/schema",
                "title": "知识图谱",
                "description": "完整的物理知识图谱",
                "type": "object",
                "required": ["topic", "build_version", "nodes", "edges", "canonical_path", "alternate_paths", "stats", "validation_summary"],
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "主题ID",
                        "pattern": "^[a-z][a-z0-9_]*(\\.[a-z0-9_]+)+$"
                    },
                    "build_version": {
                        "type": "string",
                        "description": "构建版本",
                        "pattern": "^\\d+\\.\\d+\\.\\d+$",
                    },
                    "nodes": {
                        "type": "array",
                        "items": {
                            "$ref": "#/definitions/node"
                        },
                        "description": "节点列表",
                        "minItems": 1
                    },
                    "edges": {
                        "type": "array",
                        "items": {
                            "$ref": "#/definitions/edge"
                        },
                        "description": "边列表",
                        "minItems": 0
                    },
                    "canonical_path": {
                        "type": "string",
                        "description": "主路径ID",
                        "pattern": "^path\\.[a-z0-9_]+(\\.[a-z0-9_]+)*$"
                    },
                    "alternate_paths": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "备用路径ID列表",
                        "minItems": 0
                    },
                    "stats": {
                        "type": "object",
                        "description": "统计信息",
                        "required": ["node_count", "edge_count", "derivation_edge_count", "assumption_count", "math_tool_count"],
                        "properties": {
                            "node_count": {
                                "type": "integer",
                                "minimum": 1
                            },
                            "edge_count": {
                                "type": "integer",
                                "minimum": 0
                            },
                            "derivation_edge_count": {
                                "type": "integer",
                                "minimum": 0
                            },
                            "assumption_count": {
                                "type": "integer",
                                "minimum": 0
                            },
                            "math_tool_count": {
                                "type": "integer",
                                "minimum": 0
                            },
                            "prerequisite_coverage": {
                                "type": ["number", "null"],
                                "minimum": 0,
                                "maximum": 1
                            },
                            "assumption_coverage": {
                                "type": ["number", "null"],
                                "minimum": 0,
                                "maximum": 1
                            }
                        }
                    },
                    "validation_summary": {
                        "type": "object",
                        "description": "验证摘要",
                        "required": ["schema_valid", "dag_valid", "assumptions_complete", "dimensions_valid", "canonical_path_exists"],
                        "properties": {
                            "schema_valid": {
                                "type": "boolean"
                            },
                            "dag_valid": {
                                "type": "boolean"
                            },
                            "assumptions_complete": {
                                "type": "boolean"
                            },
                            "dimensions_valid": {
                                "type": "boolean"
                            },
                            "canonical_path_exists": {
                                "type": "boolean"
                            },
                            "errors": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "warnings": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            }
                        }
                    },
                    "build_metadata": {
                        "type": ["object", "null"],
                        "description": "构建元数据",
                        "properties": {
                            "build_timestamp": {
                                "type": ["string", "number", "null"]
                            },
                            "build_duration_seconds": {
                                "type": ["number", "null"],
                                "minimum": 0
                            },
                            "agent_versions": {
                                "type": ["object", "null"]
                            },
                            "seed_sources": {
                                "type": ["array", "null"],
                                "items": {
                                    "type": "string"
                                }
                            }
                        }
                    }
                },
                "additionalProperties": False,
                "definitions": {
                    "node": {
                        "type": "object",
                        "required": ["id", "type", "title", "domain", "abstraction_level", "pedagogical_level", "sources"],
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "节点唯一标识符",
                                "pattern": "^[a-z][a-z0-9_]*(\\.[a-z0-9_]+)+$"
                            },
                            "type": {
                                "type": "string",
                                "description": "节点类型",
                                "enum": ["concept", "quantity", "definition", "law", "equation", "model", "assumption", "math_tool", "application", "experiment", "warning", "intuition_card"]
                            },
                            "title": {
                                "type": "string",
                                "description": "节点标题",
                                "minLength": 1,
                                "maxLength": 100
                            },
                            "statement": {
                                "type": ["string", "null"],
                                "description": "陈述或定义",
                                "minLength": 1,
                                "maxLength": 2000
                            },
                            "formula_latex": {
                                "type": ["string", "null"],
                                "description": "LaTeX公式表示",
                                "minLength": 1,
                                "maxLength": 1000
                            },
                            "domain": {
                                "type": "string",
                                "description": "所属学科域",
                                "enum": ["mechanics", "thermodynamics", "electromagnetism", "optics", "modern_physics", "math_tools"]
                            },
                            "abstraction_level": {
                                "type": "integer",
                                "description": "抽象级别（0-10）",
                                "minimum": 0,
                                "maximum": 10
                            },
                            "pedagogical_level": {
                                "type": "integer",
                                "description": "教学级别（1-10）",
                                "minimum": 1,
                                "maximum": 10
                            },
                            "theory_context": {
                                "type": ["string", "null"],
                                "description": "理论上下文",
                                "enum": ["classical", "relativistic", "quantum_intro", "quantum_advanced", "statistical", "phenomenological"]
                            },
                            "status": {
                                "type": ["string", "null"],
                                "description": "节点状态",
                                "enum": ["canonical", "alternate", "deprecated", "experimental", None]
                            },
                            "validity": {
                                "type": ["object", "null"],
                                "description": "有效性条件",
                                "properties": {
                                    "frame": {
                                        "type": "string",
                                        "description": "参考系条件"
                                    },
                                    "notes": {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        },
                                        "description": "额外说明"
                                    }
                                }
                            },
                            "aliases": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "别名列表",
                                "minItems": 0
                            },
                            "tags": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "标签列表",
                                "minItems": 0
                            },
                            "sources": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "来源列表",
                                "minItems": 1
                            },
                            "dimension": {
                                "type": ["object", "null"],
                                "description": "量纲信息（仅适用于quantity/equation类型）",
                                "properties": {
                                    "symbol": {
                                        "type": "string",
                                        "description": "量纲符号"
                                    },
                                    "base_dimensions": {
                                        "type": "string",
                                        "description": "基本量纲表示",
                                        "pattern": "^((M|L|T|I|Θ|N|J)\\^?[+-]?\\d*\\s*)*$"
                                    },
                                    "unit": {
                                        "type": "string",
                                        "description": "标准单位"
                                    }
                                }
                            }
                        },
                        "additionalProperties": False
                    },
                    "edge": {
                        "type": "object",
                        "required": ["id", "type", "from", "to", "path_id"],
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "边唯一标识符",
                                "pattern": "^edge\\.[a-z0-9_]+\\.(derives_from|requires|uses_math|assumes|equivalent_to|special_case_of|approximation_of|applies_to|motivated_by|related_to)\\.[a-z0-9_]+$"
                            },
                            "type": {
                                "type": "string",
                                "description": "边类型",
                                "enum": ["derives_from", "requires", "uses_math", "assumes", "equivalent_to", "special_case_of", "approximation_of", "applies_to", "motivated_by", "related_to"]
                            },
                            "from": {
                                "type": "string",
                                "description": "源节点ID",
                                "pattern": "^[a-z][a-z0-9_]*(\\.[a-z0-9_]+)+$"
                            },
                            "to": {
                                "type": "string",
                                "description": "目标节点ID",
                                "pattern": "^[a-z][a-z0-9_]*(\\.[a-z0-9_]+)+$"
                            },
                            "path_id": {
                                "type": "string",
                                "description": "所属路径ID",
                                "pattern": "^path\\.[a-z0-9_]+(\\.[a-z0-9_]+)*$"
                            },
                            "assumptions": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "假设列表",
                                "minItems": 0
                            },
                            "derivation_steps": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "推导步骤",
                                "minItems": 0
                            },
                            "math_used": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "使用的数学工具",
                                "minItems": 0
                            },
                            "approximation_tags": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "近似标签",
                                "minItems": 0
                            },
                            "verified": {
                                "type": ["object", "null"],
                                "description": "验证状态",
                                "properties": {
                                    "schema": {
                                        "type": "boolean",
                                        "description": "schema验证通过"
                                    },
                                    "unit": {
                                        "type": "boolean",
                                        "description": "单位验证通过"
                                    },
                                    "symbolic": {
                                        "type": "boolean",
                                        "description": "符号验证通过"
                                    }
                                }
                            },
                            "confidence": {
                                "type": ["number", "null"],
                                "description": "置信度",
                                "minimum": 0,
                                "maximum": 1
                            },
                            "failure_conditions": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "失效条件",
                                "minItems": 0
                            }
                        },
                        "additionalProperties": False
                    }
                }
            }

            schema_json = json.dumps(graph_schema)
            graph_schema = json.loads(schema_json)
            data_json = json.dumps(data, default=str)
            data = json.loads(data_json)

            jsonschema.validate(data, graph_schema)
            return True, [], {"validated_schema": "graph"}

        except jsonschema.ValidationError as e:
            error_msg = f"图谱schema验证失败: {e.message}"
            if e.path:
                error_msg += f" (路径: {'/'.join(str(p) for p in e.path)})"
            return False, [error_msg], {"validation_error": str(e), "schema": "graph"}

        except Exception as e:
            return False, [f"图谱schema验证异常: {str(e)}"], {"exception": str(e), "schema": "graph"}

    def validate_build_report(self, report_data: Union[Dict, BuildReport]) -> Tuple[bool, List[str]]:
        """
        验证构建报告schema

        Args:
            report_data: 构建报告数据（字典或BuildReport对象）

        Returns:
            (是否通过, 错误信息列表)
        """
        try:
            # 转换为字典
            if isinstance(report_data, BuildReport):
                data = report_data.model_dump(by_alias=True)
            else:
                data = report_data

            schema = self._load_schema("build_report")
            jsonschema.validate(data, schema)
            return True, []

        except jsonschema.ValidationError as e:
            error_msg = f"构建报告schema验证失败: {e.message}"
            if e.path:
                error_msg += f" (路径: {'/'.join(str(p) for p in e.path)})"
            return False, [error_msg]

        except Exception as e:
            return False, [f"构建报告schema验证异常: {str(e)}"]

    def validate_nodes_batch(self, nodes: List[Union[Dict, Node]]) -> Tuple[bool, List[str], Dict]:
        """
        批量验证节点

        Args:
            nodes: 节点列表

        Returns:
            (是否全部通过, 错误信息列表, 详细结果)
        """
        all_valid = True
        all_errors = []
        details = {
            "total": len(nodes),
            "valid": 0,
            "invalid": 0,
            "node_errors": {}
        }

        for i, node in enumerate(nodes):
            valid, errors = self.validate_node(node)

            if valid:
                details["valid"] += 1
            else:
                all_valid = False
                details["invalid"] += 1
                node_id = node.get("id") if isinstance(node, dict) else node.id
                details["node_errors"][node_id] = errors
                all_errors.extend([f"{node_id}: {e}" for e in errors])

        return all_valid, all_errors, details

    def validate_edges_batch(self, edges: List[Union[Dict, Edge]]) -> Tuple[bool, List[str], Dict]:
        """
        批量验证边

        Args:
            edges: 边列表

        Returns:
            (是否全部通过, 错误信息列表, 详细结果)
        """
        all_valid = True
        all_errors = []
        details = {
            "total": len(edges),
            "valid": 0,
            "invalid": 0,
            "edge_errors": {}
        }

        for i, edge in enumerate(edges):
            valid, errors = self.validate_edge(edge)

            if valid:
                details["valid"] += 1
            else:
                all_valid = False
                details["invalid"] += 1
                edge_id = edge.get("id") if isinstance(edge, dict) else edge.id
                details["edge_errors"][edge_id] = errors
                all_errors.extend([f"{edge_id}: {e}" for e in errors])

        return all_valid, all_errors, details

    def validate_seed_file(self, domain: str) -> Tuple[bool, List[str], Dict]:
        """
        验证种子文件

        Args:
            domain: 学科域

        Returns:
            (是否通过, 错误信息列表, 详细结果)
        """
        try:
            seed_data = self.loader.load_seed_file(domain)
            nodes = self.loader.parse_nodes_from_seed(seed_data)
            edges = self.loader.parse_edges_from_seed(seed_data)

            # 验证节点
            nodes_valid, nodes_errors, nodes_details = self.validate_nodes_batch(nodes)

            # 验证边
            edges_valid, edges_errors, edges_details = self.validate_edges_batch(edges)

            all_valid = nodes_valid and edges_valid
            all_errors = nodes_errors + edges_errors

            details = {
                "domain": domain,
                "nodes": nodes_details,
                "edges": edges_details,
                "node_count": len(nodes),
                "edge_count": len(edges)
            }

            return all_valid, all_errors, details

        except Exception as e:
            return False, [f"验证种子文件 {domain} 异常: {str(e)}"], {}

    def validate_all_seeds(self) -> Dict[str, Any]:
        """
        验证所有种子文件

        Returns:
            验证结果摘要
        """
        seeds = self.loader.load_all_seeds()
        results = {
            "total_domains": 0,
            "valid_domains": 0,
            "invalid_domains": 0,
            "domain_results": {},
            "all_errors": []
        }

        for domain in seeds.keys():
            valid, errors, details = self.validate_seed_file(domain)

            results["total_domains"] += 1
            if valid:
                results["valid_domains"] += 1
            else:
                results["invalid_domains"] += 1

            results["domain_results"][domain] = {
                "valid": valid,
                "error_count": len(errors),
                "details": details
            }
            results["all_errors"].extend(errors)

        return results