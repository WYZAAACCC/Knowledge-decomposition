"""
RendererAgent

输出图结构与静态展示结果。
生成graph.json、report.md、graph.html、debug.json、eval_report.json等工件。
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from ..models import KnowledgeGraph
from ..core.view_model import GraphViewModel, NODE_STYLE_REGISTRY


@dataclass
class RendererOutput:
    artifacts: Dict[str, str]
    render_stats: Dict[str, Any]
    warnings: List[str]


class RendererAgent:

    def __init__(self, output_dir: str = "artifacts/latest"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, ranker_output: Dict[str, Any],
            verification_output: Optional[Dict[str, Any]] = None) -> RendererOutput:
        subgraph = ranker_output.get("subgraph") if ranker_output else None
        if isinstance(subgraph, dict):
            try:
                subgraph = KnowledgeGraph(**subgraph)
            except Exception as e:
                return self._create_error_output(f"无效的图谱数据: {e}")

        if not subgraph:
            return self._create_error_output("没有图谱数据")

        artifacts = {}
        warnings = []
        render_stats = {
            "start_time": time.time(),
            "artifacts_generated": 0
        }

        try:
            graph_path = self.output_dir / "graph.json"
            self._generate_graph_json(subgraph, graph_path)
            artifacts["graph_json"] = str(graph_path)
            render_stats["artifacts_generated"] += 1

            report_path = self.output_dir / "report.md"
            self._generate_report_md(subgraph, verification_output, ranker_output, report_path)
            artifacts["report_md"] = str(report_path)
            render_stats["artifacts_generated"] += 1

            if verification_output:
                debug_path = self.output_dir / "debug.json"
                self._generate_debug_json(subgraph, verification_output, ranker_output, debug_path)
                artifacts["debug_json"] = str(debug_path)
                render_stats["artifacts_generated"] += 1

            eval_path = self.output_dir / "eval_report.json"
            self._generate_eval_report(subgraph, verification_output, eval_path)
            artifacts["eval_report_json"] = str(eval_path)
            render_stats["artifacts_generated"] += 1

            html_path = self.output_dir / "graph.html"
            self._generate_graph_html(subgraph, html_path)
            artifacts["graph_html"] = str(html_path)
            render_stats["artifacts_generated"] += 1

            try:
                from ..exporters.ontology_exporter import OntologyExporter
                exporter = OntologyExporter(subgraph)
                ontology_dir = self.output_dir / "ontology"
                ontology_dir.mkdir(parents=True, exist_ok=True)
                exporter.export_all(str(ontology_dir))
                artifacts["ontology_dir"] = str(ontology_dir)
                render_stats["artifacts_generated"] += 3
            except Exception as e:
                warnings.append(f"导出本体格式时出错: {e}")

        except Exception as e:
            warnings.append(f"生成工件时出错: {e}")

        render_stats["end_time"] = time.time()
        render_stats["duration"] = render_stats["end_time"] - render_stats["start_time"]

        return RendererOutput(
            artifacts=artifacts,
            render_stats=render_stats,
            warnings=warnings
        )

    def _create_error_output(self, error_message: str) -> RendererOutput:
        return RendererOutput(
            artifacts={},
            render_stats={"error": error_message, "artifacts_generated": 0},
            warnings=[error_message]
        )

    def _generate_graph_json(self, graph: KnowledgeGraph, output_path: Path):
        graph_dict = graph.model_dump(by_alias=True) if hasattr(graph, 'model_dump') else graph.dict()
        required_fields = ["topic", "nodes", "edges", "canonical_path", "alternate_paths"]
        for field in required_fields:
            if field not in graph_dict:
                graph_dict[field] = getattr(graph, field, None)
        if "build_metadata" not in graph_dict or graph_dict["build_metadata"] is None:
            graph_dict["build_metadata"] = {}
        graph_dict["build_metadata"]["render_timestamp"] = time.time()
        graph_dict["build_metadata"]["render_version"] = "2.0"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(graph_dict, f, ensure_ascii=False, indent=2)

    def _generate_report_md(self, graph: KnowledgeGraph,
                           verification_output: Optional[Dict[str, Any]],
                           ranker_output: Optional[Dict[str, Any]],
                           output_path: Path):
        lines = []
        lines.append(f"# 知识图谱报告: {graph.topic}")
        lines.append("")
        lines.append("## 摘要")
        lines.append(f"- **主题**: {graph.topic}")
        lines.append(f"- **节点数**: {len(graph.nodes)}")
        lines.append(f"- **边数**: {len(graph.edges)}")
        lines.append(f"- **规范路径**: {graph.canonical_path if graph.canonical_path else '无'}")
        lines.append(f"- **备用路径数**: {len(graph.alternate_paths) if graph.alternate_paths else 0}")
        lines.append("")
        lines.append("## 节点类型统计")
        node_type_counts = {}
        for node in graph.nodes:
            node_type_counts[node.type] = node_type_counts.get(node.type, 0) + 1
        for node_type, count in sorted(node_type_counts.items()):
            lines.append(f"- **{node_type}**: {count}")
        lines.append("")
        lines.append("## 边类型统计")
        edge_type_counts = {}
        for edge in graph.edges:
            edge_type_counts[edge.type] = edge_type_counts.get(edge.type, 0) + 1
        for edge_type, count in sorted(edge_type_counts.items()):
            lines.append(f"- **{edge_type}**: {count}")
        lines.append("")
        if graph.canonical_path:
            lines.append("## 规范路径")
            path_edges = [e for e in graph.edges if e.path_id == graph.canonical_path]
            if path_edges:
                path_nodes = self._reconstruct_path(path_edges)
                lines.append("路径节点:")
                for i, node_id in enumerate(path_nodes):
                    node = next((n for n in graph.nodes if n.id == node_id), None)
                    node_title = getattr(node, 'title', node_id) if node else node_id
                    lines.append(f"{i+1}. {node_title} ({node_id})")
                lines.append("")
                all_assumptions = set()
                for edge in path_edges:
                    if edge.assumptions:
                        all_assumptions.update(edge.assumptions)
                if all_assumptions:
                    lines.append("### 路径假设")
                    for assumption in sorted(all_assumptions):
                        lines.append(f"- {assumption}")
                    lines.append("")
        if verification_output:
            lines.append("## 验证结果")
            lines.append(f"- **总体通过**: {'是' if verification_output.get('passed', False) else '否'}")
            lines.append(f"- **总体分数**: {verification_output.get('overall_score', 0):.2f}")
            if verification_output.get('critical_errors'):
                lines.append("### 关键错误")
                for error in verification_output['critical_errors']:
                    lines.append(f"- {error}")
                lines.append("")
            if verification_output.get('warnings'):
                lines.append("### 警告")
                for warning in verification_output['warnings'][:5]:
                    lines.append(f"- {warning}")
                if len(verification_output['warnings']) > 5:
                    lines.append(f"- ... 还有 {len(verification_output['warnings']) - 5} 个警告")
                lines.append("")
        if ranker_output and ranker_output.get('ranking_scores'):
            lines.append("## 路径排名")
            for path_id, score in ranker_output['ranking_scores'].items():
                is_canonical = (path_id == graph.canonical_path)
                canonical_mark = "✓ " if is_canonical else "  "
                lines.append(f"- {canonical_mark}**{path_id}**: {score:.2f}")
            lines.append("")
        lines.append("## 重要节点")
        important_nodes = []
        for node in graph.nodes:
            if node.type in ["law", "equation", "concept"]:
                title = getattr(node, 'title', node.id)
                important_nodes.append((node.type, title, node.id))
        for node_type, title, node_id in sorted(important_nodes)[:10]:
            lines.append(f"- **{title}** ({node_type}, {node_id})")
        if len(important_nodes) > 10:
            lines.append(f"- ... 还有 {len(important_nodes) - 10} 个重要节点")
        lines.append("")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

    def _generate_debug_json(self, graph: KnowledgeGraph,
                            verification_output: Dict[str, Any],
                            ranker_output: Dict[str, Any],
                            output_path: Path):
        debug_info = {
            "topic": graph.topic,
            "generated_at": time.time(),
            "graph_stats": {
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "canonical_path": graph.canonical_path,
                "alternate_paths": graph.alternate_paths
            },
            "verification_summary": {
                "passed": verification_output.get('passed', False),
                "overall_score": verification_output.get('overall_score', 0),
                "critical_error_count": len(verification_output.get('critical_errors', [])),
                "warning_count": len(verification_output.get('warnings', [])),
                "suggested_actions": verification_output.get('suggested_actions', [])
            },
            "ranking_summary": {
                "selected_canonical_path": ranker_output.get('selected_canonical_path', ''),
                "ranking_scores": ranker_output.get('ranking_scores', {}),
                "alternate_paths": ranker_output.get('alternate_paths', [])
            },
            "node_types": {},
            "edge_types": {}
        }
        for node in graph.nodes:
            debug_info["node_types"][node.type] = debug_info["node_types"].get(node.type, 0) + 1
        for edge in graph.edges:
            debug_info["edge_types"][edge.type] = debug_info["edge_types"].get(edge.type, 0) + 1
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(debug_info, f, ensure_ascii=False, indent=2)

    def _generate_eval_report(self, graph: KnowledgeGraph,
                             verification_output: Optional[Dict[str, Any]],
                             output_path: Path):
        eval_info = {
            "topic": graph.topic,
            "evaluated_at": time.time(),
            "basic_metrics": {
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "has_canonical_path": bool(graph.canonical_path),
                "alternate_path_count": len(graph.alternate_paths) if graph.alternate_paths else 0
            },
            "validation_metrics": {
                "overall_score": verification_output.get('overall_score', 0) if verification_output else 0,
                "passed": verification_output.get('passed', False) if verification_output else False,
                "assumption_coverage": self._extract_assumption_coverage(verification_output),
                "dimension_pass_rate": self._extract_dimension_pass_rate(verification_output)
            },
            "quality_metrics": {
                "derives_from_with_assumptions": self._count_edges_with_assumptions(graph),
                "average_derivation_steps": self._average_derivation_steps(graph),
                "math_tool_usage": self._count_math_tool_usage(graph)
            }
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(eval_info, f, ensure_ascii=False, indent=2)

    def _get_node_shape(self, node_type: str) -> str:
        shape_map = {
            'law': 'box',
            'equation': 'box',
            'concept': 'box',
            'quantity': 'box',
            'assumption': 'box',
            'math_tool': 'box',
            'definition': 'box',
            'model': 'box',
            'application': 'box',
            'experiment': 'box',
            'warning': 'box',
            'intuition_card': 'box',
        }
        return shape_map.get(node_type, 'box')

    def _get_node_color_obj(self, node_type: str) -> dict:
        color_map = {
            'law': {'background': '#2ecc71', 'border': '#27ae60', 'highlight': {'background': '#27ae60', 'border': '#1e8449'}, 'hover': {'background': '#2ecc71', 'border': '#27ae60'}},
            'equation': {'background': '#e74c3c', 'border': '#c0392b', 'highlight': {'background': '#c0392b', 'border': '#922b21'}, 'hover': {'background': '#e74c3c', 'border': '#c0392b'}},
            'concept': {'background': '#3498db', 'border': '#2980b9', 'highlight': {'background': '#2980b9', 'border': '#1f618d'}, 'hover': {'background': '#3498db', 'border': '#2980b9'}},
            'quantity': {'background': '#f39c12', 'border': '#e67e22', 'highlight': {'background': '#e67e22', 'border': '#ca6f1e'}, 'hover': {'background': '#f39c12', 'border': '#e67e22'}},
            'assumption': {'background': '#f1c40f', 'border': '#d4ac0d', 'highlight': {'background': '#d4ac0d', 'border': '#b7950b'}, 'hover': {'background': '#f1c40f', 'border': '#d4ac0d'}},
            'math_tool': {'background': '#9b59b6', 'border': '#8e44ad', 'highlight': {'background': '#8e44ad', 'border': '#6c3483'}, 'hover': {'background': '#9b59b6', 'border': '#8e44ad'}},
            'definition': {'background': '#e91e63', 'border': '#c2185b', 'highlight': {'background': '#c2185b', 'border': '#880e4f'}, 'hover': {'background': '#e91e63', 'border': '#c2185b'}},
            'model': {'background': '#1abc9c', 'border': '#16a085', 'highlight': {'background': '#16a085', 'border': '#0e6655'}, 'hover': {'background': '#1abc9c', 'border': '#16a085'}},
            'application': {'background': '#3f51b5', 'border': '#303f9f', 'highlight': {'background': '#303f9f', 'border': '#1a237e'}, 'hover': {'background': '#3f51b5', 'border': '#303f9f'}},
            'experiment': {'background': '#8bc34a', 'border': '#689f38', 'highlight': {'background': '#689f38', 'border': '#558b2f'}, 'hover': {'background': '#8bc34a', 'border': '#689f38'}},
            'warning': {'background': '#f44336', 'border': '#d32f2f', 'highlight': {'background': '#d32f2f', 'border': '#b71c1c'}, 'hover': {'background': '#f44336', 'border': '#d32f2f'}},
            'intuition_card': {'background': '#00bcd4', 'border': '#0097a7', 'highlight': {'background': '#0097a7', 'border': '#006064'}, 'hover': {'background': '#00bcd4', 'border': '#0097a7'}},
        }
        return color_map.get(node_type, {'background': '#bdc3c7', 'border': '#95a5a6', 'highlight': {'background': '#95a5a6', 'border': '#7f8c8d'}, 'hover': {'background': '#d5dbdb', 'border': '#95a5a6'}})

    def _get_node_color(self, node_type: str) -> str:
        simple_map = {
            'law': '#2ecc71', 'equation': '#e74c3c', 'concept': '#3498db',
            'quantity': '#f39c12', 'assumption': '#f1c40f', 'math_tool': '#9b59b6',
            'definition': '#e91e63', 'model': '#1abc9c', 'application': '#3f51b5',
            'experiment': '#8bc34a', 'warning': '#f44336', 'intuition_card': '#00bcd4'
        }
        return simple_map.get(node_type, '#bdc3c7')

    def _get_edge_color(self, edge_type: str) -> str:
        color_map = {
            'derives_from': '#3366cc',
            'requires': '#ff9900',
            'uses_math': '#109618',
            'assumes': '#990099',
            'equivalent_to': '#0099c6',
            'special_case_of': '#dd4477',
            'approximation_of': '#66aa00',
            'applies_to': '#994499',
            'motivated_by': '#22aa99',
            'related_to': '#aaaa11'
        }
        return color_map.get(edge_type, '#888888')

    def _generate_graph_html(self, graph: KnowledgeGraph, output_path: Path):
        # Fix 10: Use GraphViewModel for consistent, safe data
        view_model = GraphViewModel.from_graph(graph)
        nodes_data = view_model["nodes"]
        edges_data = view_model["edges"]

        # Main node identification
        main_node_id = graph.topic.replace(' ', '_')
        for n in nodes_data:
            if n["id"] == main_node_id or n["id"] == main_node_id.lower():
                main_node_id = n["id"]
                break

        # Type counts from view model
        node_type_counts = {}
        for n in nodes_data:
            t = n.get("type", "unknown")
            node_type_counts[t] = node_type_counts.get(t, 0) + 1
        node_types_str = "\n".join([f"{ntype}: {count}" for ntype, count in sorted(node_type_counts.items())])

        # Fix 10: Use unified NODE_STYLE_REGISTRY for legend
        shape_legend = {}
        legend_labels = {
            'law': '定律/法则', 'equation': '方程', 'concept': '概念',
            'quantity': '物理量', 'assumption': '假设', 'math_tool': '数学工具',
            'definition': '定义', 'model': '模型', 'application': '应用',
            'experiment': '实验', 'warning': '警告', 'intuition_card': '直觉卡',
        }
        for ntype, style in NODE_STYLE_REGISTRY.items():
            shape_legend[ntype] = {"shape": style["shape"], "label": legend_labels.get(ntype, ntype)}

        topic_id = graph.topic.replace(' ', '_')
        # Fix 10: Use safe JSON script tag injection instead of base64
        graph_json_str = GraphViewModel.to_json_script(graph)
        colors_json = json.dumps({k: self._get_node_color(k) for k in shape_legend}, ensure_ascii=False)
        shapes_json = json.dumps(shape_legend, ensure_ascii=False)

        # Improvement 6: Cytoscape.js + dagre layout
        # Improvement 5: 三种视图切换 (decomposition/derivation/application)
        # Improvement 2: 三层图 (knowledge + assumption + proofstep)
        html_content = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>物理知识图谱 - ''' + graph.topic + '''</title>
<script src="https://unpkg.com/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
<script src="https://unpkg.com/cytoscape-dagre@2.5.0/cytoscape-dagre.js"></script>
<script src="https://unpkg.com/dagre@0.8.5/dist/dagre.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--primary:#4a6cf7;--primary-light:#6b8cff;--primary-dark:#3451d1;--accent:#6c5ce7;--bg:#f8f9fc;--surface:#fff;--border:#e8ecf1;--text:#2d3436;--text-light:#8395a7;--radius:10px;--shadow:0 2px 12px rgba(74,108,247,0.08);--shadow-hover:0 4px 20px rgba(74,108,247,0.15)}
body{font-family:"Microsoft YaHei","SimHei","PingFang SC",sans-serif;background:var(--bg);color:var(--text);line-height:1.6;overflow:hidden;height:100vh}
.header{background:linear-gradient(135deg,var(--primary) 0%,var(--accent) 100%);color:#fff;padding:10px 20px;text-align:center;position:relative;z-index:10}
.header h1{font-size:1.3rem;font-weight:600;letter-spacing:1px}
.header h2{font-size:.85rem;opacity:.8;font-weight:400}
.header-toggle{position:absolute;right:12px;top:50%;transform:translateY(-50%);background:rgba(255,255,255,.15);border:none;color:#fff;width:24px;height:24px;border-radius:50%;cursor:pointer;font-size:12px;display:flex;align-items:center;justify-content:center;transition:all .25s cubic-bezier(.4,0,.2,1)}
.header-toggle:hover{background:rgba(255,255,255,.3);transform:translateY(-50%) scale(1.1)}
.header-toggle:active{transform:translateY(-50%) scale(.95)}
.main-layout{display:flex;height:calc(100vh - 48px);overflow:hidden}
.graph-panel{flex:1;min-width:200px;display:flex;flex-direction:column;position:relative;background:var(--bg)}
.detail-panel{width:360px;min-width:250px;max-width:700px;background:var(--surface);border-left:1px solid var(--border);overflow-y:auto;transition:all .3s cubic-bezier(.4,0,.2,1);box-shadow:-2px 0 12px rgba(0,0,0,.03)}
.detail-panel.collapsed{width:0;min-width:0;overflow:hidden;border:none;padding:0}
.resize-handle{width:5px;cursor:col-resize;background:var(--border);flex-shrink:0;transition:background .2s}
.resize-handle:hover,.resize-handle.active{background:var(--primary)}
.stats{display:flex;gap:6px;padding:6px 12px;background:var(--surface);border-bottom:1px solid var(--border)}
.stat-card{flex:1;background:var(--bg);border-radius:var(--radius);padding:5px 6px;text-align:center;transition:all .2s}
.stat-card:hover{box-shadow:var(--shadow-hover);transform:translateY(-1px)}
.stat-value{font-size:15px;font-weight:700;color:var(--primary)}
.stat-label{color:var(--text-light);font-size:9px;letter-spacing:.5px}
.controls{background:var(--surface);padding:5px 12px;display:flex;gap:5px;flex-wrap:wrap;align-items:center;border-bottom:1px solid var(--border)}
.controls button{padding:4px 12px;background:var(--primary);color:#fff;border:none;border-radius:16px;cursor:pointer;font-size:11px;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden}
.controls button:hover{background:var(--primary-dark);box-shadow:0 2px 8px rgba(74,108,247,.3);transform:translateY(-1px)}
.controls button:active{transform:translateY(0) scale(.97);box-shadow:none}
.controls select{padding:4px 8px;border:1px solid var(--border);border-radius:16px;font-size:11px;background:var(--surface);outline:none;transition:border-color .2s}
.controls select:focus{border-color:var(--primary)}
#network-container{flex:1;background:var(--surface);position:relative;overflow:hidden;min-height:300px}
.zoom-controls{position:absolute;bottom:16px;right:16px;display:flex;flex-direction:column;gap:4px;z-index:5}
.zoom-btn{width:32px;height:32px;border-radius:50%;background:var(--surface);border:1px solid var(--border);color:var(--text);font-size:16px;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:var(--shadow);transition:all .25s cubic-bezier(.4,0,.2,1)}
.zoom-btn:hover{background:var(--primary);color:#fff;border-color:var(--primary);box-shadow:var(--shadow-hover);transform:scale(1.1)}
.zoom-btn:active{transform:scale(.95)}
.zoom-level{background:var(--surface);border-radius:10px;padding:2px 6px;font-size:10px;color:var(--text-light);text-align:center;border:1px solid var(--border)}
.toggle-sidebar{position:absolute;top:8px;right:8px;z-index:5;background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:4px 12px;font-size:11px;cursor:pointer;color:var(--text-light);transition:all .25s cubic-bezier(.4,0,.2,1);box-shadow:var(--shadow)}
.toggle-sidebar:hover{background:var(--primary);color:#fff;border-color:var(--primary);box-shadow:var(--shadow-hover);transform:translateY(-1px)}
.toggle-sidebar:active{transform:translateY(0) scale(.97)}
#loading-indicator{position:absolute;top:50%;left:calc(50% - 150px);transform:translate(-50%,-50%);text-align:center;color:var(--text-light);z-index:5;pointer-events:none}
.spinner{display:inline-block;width:32px;height:32px;border:3px solid var(--border);border-top:3px solid var(--primary);border-radius:50%;animation:spin .7s linear infinite;margin-bottom:8px}
@keyframes spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@keyframes slideIn{from{opacity:0;transform:translateX(16px)}to{opacity:1;transform:translateX(0)}}
@keyframes pulseGlow{0%,100%{box-shadow:0 0 0 0 rgba(74,108,247,0)}50%{box-shadow:0 0 12px 4px rgba(74,108,247,.25)}}
.legend{padding:5px 12px;background:var(--surface);border-bottom:1px solid var(--border);overflow:hidden;transition:max-height .3s}
.legend.collapsed{max-height:24px}
.legend h3{font-size:11px;margin-bottom:3px;color:var(--text-light);cursor:pointer;display:flex;align-items:center;justify-content:space-between;transition:color .2s}
.legend h3:hover{color:var(--primary)}
.legend h3::after{content:'▾';transition:transform .25s;font-size:9px}
.legend.collapsed h3::after{transform:rotate(-90deg)}
.legend-items{display:flex;flex-wrap:wrap;gap:3px}
.legend-item{display:flex;align-items:center;gap:3px;padding:2px 6px;border-radius:8px;background:var(--bg);font-size:10px;border:1px solid var(--border);cursor:pointer;transition:all .2s}
.legend-item:hover{border-color:var(--primary);color:var(--primary);box-shadow:0 0 6px rgba(74,108,247,.15)}
.legend-shape{width:12px;height:12px;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700}
.detail-content{padding:14px;animation:slideIn .3s cubic-bezier(.4,0,.2,1)}
.detail-header{font-size:15px;font-weight:700;color:var(--primary);margin-bottom:10px;padding-bottom:8px;border-bottom:2px solid var(--primary);display:flex;align-items:center;gap:6px;animation:fadeIn .3s ease}
.detail-section{margin-bottom:10px;animation:fadeIn .25s ease}
.detail-section h4{font-size:12px;color:var(--text-light);margin-bottom:4px;padding-left:6px;border-left:3px solid var(--primary)}
.detail-field{margin-bottom:4px;font-size:12px}
.detail-field strong{color:var(--text)}
.formula-block{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:8px;margin:4px 0;overflow-x:auto}
.assumption-chip{display:inline-block;background:#fef9e7;border:1px solid #f9e79f;border-radius:10px;padding:1px 8px;margin:1px;font-size:10px;color:#b7950b;transition:all .2s}
.assumption-chip:hover{box-shadow:0 0 6px rgba(183,149,11,.2);transform:scale(1.03)}
.step-item{background:var(--bg);border-radius:var(--radius);padding:6px 8px;margin:3px 0;border-left:3px solid var(--primary);font-size:12px;transition:all .2s}
.step-item:hover{background:#eef1ff;transform:translateX(3px)}
.merge-detail{background:#fef5f5;border:1px solid #f5c6cb;border-radius:var(--radius);padding:10px;margin:6px 0}
.merge-detail h4{color:#c0392b;border-left-color:#c0392b}
.source-node-tag{display:inline-block;background:#eafaf1;border:1px solid #a9dfbf;border-radius:10px;padding:1px 8px;margin:1px;font-size:10px;color:#1e8449;cursor:pointer;transition:all .2s}
.source-node-tag:hover{background:#d5f5e3;box-shadow:0 0 6px rgba(30,132,73,.2)}
.target-node-tag{display:inline-block;background:#ebf5fb;border:1px solid #aed6f1;border-radius:10px;padding:1px 8px;margin:1px;font-size:10px;color:#2471a3;font-weight:600;cursor:pointer;transition:all .2s}
.target-node-tag:hover{background:#d6eaf8;box-shadow:0 0 6px rgba(36,113,163,.2)}
.no-detail{color:var(--text-light);font-style:italic;text-align:center;padding:30px 16px}
.render-status{background:#fff3cd;border:1px solid #ffc107;border-radius:var(--radius);padding:6px;margin:6px 12px;display:none;font-size:12px}
[data-theme="dark"]{--primary:#6b8cff;--primary-light:#8fa8ff;--primary-dark:#4a6cf7;--accent:#a78bfa;--bg:#1a1b2e;--surface:#252640;--border:#3a3b5c;--text:#e2e8f0;--text-light:#94a3b8;--shadow:0 2px 12px rgba(0,0,0,.3);--shadow-hover:0 4px 20px rgba(107,140,255,.2)}
[data-theme="dark"] .stat-card{background:#2d2e4a}
[data-theme="dark"] .formula-block{background:#2d2e4a;border-color:#3a3b5c}
[data-theme="dark"] .step-item{background:#2d2e4a}
[data-theme="dark"] .step-item:hover{background:#36375a}
[data-theme="dark"] .assumption-chip{background:#3a3520;border-color:#6b5f2a;color:#d4a84b}
[data-theme="dark"] .source-node-tag{background:#1a3a2a;border-color:#2d6b4a;color:#4ade80}
[data-theme="dark"] .target-node-tag{background:#1a2a4a;border-color:#2d4a6b;color:#60a5fa}
[data-theme="dark"] .merge-detail{background:#3a2020;border-color:#6b2d2d}
[data-theme="dark"] .legend-item{background:#2d2e4a;border-color:#3a3b5c}
.search-bar{display:flex;align-items:center;gap:4px;flex:1;min-width:120px;max-width:260px}
.search-bar input{flex:1;padding:4px 10px;border:1px solid var(--border);border-radius:16px;font-size:11px;background:var(--surface);color:var(--text);outline:none;transition:border-color .2s}
.search-bar input:focus{border-color:var(--primary);box-shadow:0 0 0 2px rgba(74,108,247,.15)}
.search-bar input::placeholder{color:var(--text-light)}
.search-results{position:absolute;top:100%;left:0;right:0;background:var(--surface);border:1px solid var(--border);border-radius:8px;max-height:200px;overflow-y:auto;z-index:20;box-shadow:var(--shadow-hover);display:none}
.search-results.visible{display:block}
.search-result-item{padding:6px 10px;cursor:pointer;font-size:11px;border-bottom:1px solid var(--border);transition:background .15s}
.search-result-item:hover{background:rgba(74,108,247,.08)}
.search-result-item:last-child{border-bottom:none}
.search-result-type{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.path-highlight-btn{padding:4px 10px!important;font-size:10px!important;border-radius:12px!important}
.path-highlight-btn.active{box-shadow:0 0 0 2px rgba(74,108,247,.4)!important;animation:pulseGlow 1.5s ease infinite}
.export-btn{background:#27ae60!important}
.export-btn:hover{background:#219a52!important}
.theme-toggle{background:transparent!important;border:1px solid rgba(255,255,255,.3)!important;padding:4px 8px!important;font-size:14px!important;min-width:28px}
.minimap-container{position:absolute;bottom:60px;right:16px;width:180px;height:120px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);z-index:5;overflow:hidden;transition:all .3s}
.minimap-container.hidden{width:0;height:0;opacity:0;pointer-events:none}
.minimap-label{position:absolute;top:2px;left:6px;font-size:8px;color:var(--text-light);z-index:1}
.stats-overlay{position:absolute;top:8px;left:8px;width:220px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);z-index:5;overflow:hidden;transition:all .3s;max-height:calc(100% - 16px)}
.stats-overlay.hidden{width:0;opacity:0;pointer-events:none;overflow:hidden}
.stats-overlay-header{padding:8px 12px;background:linear-gradient(135deg,var(--primary),var(--accent));color:#fff;font-size:12px;font-weight:600;cursor:pointer;display:flex;justify-content:space-between;align-items:center}
.stats-overlay-body{padding:8px 12px;overflow-y:auto;max-height:300px}
.stats-row{display:flex;justify-content:space-between;padding:3px 0;font-size:11px;border-bottom:1px solid var(--border)}
.stats-row:last-child{border-bottom:none}
.stats-label{color:var(--text-light)}
.stats-value{font-weight:600;color:var(--primary)}
.level-indicator{position:absolute;left:0;top:0;bottom:0;width:36px;background:var(--surface);border-right:1px solid var(--border);z-index:2;display:flex;flex-direction:column;justify-content:space-around;padding:4px 0}
.level-dot{width:8px;height:8px;border-radius:50%;margin:0 auto;position:relative;cursor:pointer;transition:all .2s}
.level-dot:hover{transform:scale(1.5)}
.level-dot::after{content:attr(data-level);position:absolute;left:14px;top:50%;transform:translateY(-50%);font-size:9px;color:var(--text-light);white-space:nowrap;opacity:0;transition:opacity .2s}
.level-dot:hover::after{opacity:1}
.toolbar-separator{width:1px;height:20px;background:var(--border);margin:0 2px}
.tooltip{position:absolute;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:8px 12px;font-size:11px;box-shadow:var(--shadow-hover);z-index:30;pointer-events:none;max-width:280px;opacity:0;transition:opacity .15s}
.tooltip.visible{opacity:1}
.tooltip-title{font-weight:700;color:var(--primary);margin-bottom:4px}
.tooltip-formula{color:var(--text);font-family:serif}
</style>
</head>
<body>
<div class="header" id="header">
<h1>物理知识图谱</h1>
<h2>主题: ''' + graph.topic + '''</h2>
<button class="header-toggle" onclick="toggleHeader()" title="折叠标题">▾</button>
<button class="theme-toggle" onclick="toggleTheme()" title="切换暗色模式" style="position:absolute;left:12px;top:50%;transform:translateY(-50%)">🌙</button>
</div>
<div class="main-layout">
<div class="graph-panel">
<div class="stats" id="stats-bar">
<div class="stat-card"><div class="stat-value">''' + str(len(graph.nodes)) + '''</div><div class="stat-label">节点</div></div>
<div class="stat-card"><div class="stat-value">''' + str(len(graph.edges)) + '''</div><div class="stat-label">边</div></div>
<div class="stat-card"><div class="stat-value">''' + ("✓" if graph.canonical_path else "✗") + '''</div><div class="stat-label">规范路径</div></div>
<div class="stat-card"><div class="stat-value">''' + str(len(graph.alternate_paths) if graph.alternate_paths else 0) + '''</div><div class="stat-label">备用路径</div></div>
</div>
<div class="legend" id="legend-bar"><h3 onclick="toggleLegend()">图例</h3><div class="legend-items" id="legend-items"></div></div>
<div class="controls" id="controls-bar">
<div class="search-bar" style="position:relative">
<input type="text" id="search-input" placeholder="搜索节点..." oninput="handleSearch(this.value)" onfocus="handleSearch(this.value)" onblur="setTimeout(function(){document.getElementById('search-results').classList.remove('visible')},200)">
<div class="search-results" id="search-results"></div>
</div>
<div class="toolbar-separator"></div>
<!-- Improvement 5: 三种视图切换 -->
<button onclick="switchView('decomposition')" id="btn-decomp" style="background:#6c5ce7">分解视图</button>
<button onclick="switchView('derivation')" id="btn-deriv" style="background:#4a6cf7">推导视图</button>
<button onclick="switchView('application')" id="btn-app" style="background:#00b894">应用视图</button>
<button onclick="fitNetwork()">适应窗口</button>
<button onclick="togglePhysics()">切换物理</button>
<button class="path-highlight-btn" id="btn-highlight-canonical" onclick="highlightCanonicalPath()">规范路径</button>
<button class="path-highlight-btn" id="btn-highlight-all" onclick="highlightAllPaths()">全部路径</button>
<button class="path-highlight-btn" id="btn-highlight-clear" onclick="clearHighlight()">清除高亮</button>
<div class="toolbar-separator"></div>
<button class="export-btn" onclick="exportSVG()">导出SVG</button>
<button class="export-btn" onclick="exportPNG()">导出PNG</button>
<button onclick="toggleStats()">统计</button>
<button onclick="toggleMinimap()">小地图</button>
<div class="toolbar-separator"></div>
<label style="font-size:11px;color:var(--text-light)">层高</label>
<input type="range" id="level-sep-slider" min="200" max="1000" value="450" style="width:70px" oninput="updateLayout()">
<span id="level-sep-val" style="font-size:10px;color:var(--text-light);min-width:28px">450</span>
<label style="font-size:11px;color:var(--text-light);margin-left:6px">间距</label>
<input type="range" id="node-spac-slider" min="100" max="800" value="400" style="width:70px" oninput="updateLayout()">
<span id="node-spac-val" style="font-size:10px;color:var(--text-light);min-width:28px">400</span>
<div class="toolbar-separator"></div>
<button onclick="toggleTopBar()">折叠</button>
<select onchange="filterByType(this.value)">
<option value="">全部类型</option>
<option value="law">定律</option>
<option value="equation">方程</option>
<option value="concept">概念</option>
<option value="quantity">物理量</option>
<option value="assumption">假设</option>
<option value="math_tool">数学工具</option>
<option value="definition">定义</option>
<option value="model">模型</option>
<option value="application">应用</option>
<option value="experiment">实验</option>
<option value="warning">警告</option>
<option value="intuition_card">直觉卡</option>
</select>
</div>
<div id="network-container"></div>
<div id="loading-indicator"><div class="spinner"></div><p>加载中...</p></div>
<button class="toggle-sidebar" onclick="toggleDetailPanel()" title="详情面板">详情</button>
<div class="stats-overlay hidden" id="stats-overlay">
<div class="stats-overlay-header" onclick="toggleStats()"><span>图谱统计</span><span>✕</span></div>
<div class="stats-overlay-body" id="stats-overlay-body"></div>
</div>
<div class="minimap-container hidden" id="minimap-container">
<div class="minimap-label">概览</div>
<canvas id="minimap-canvas" width="180" height="120"></canvas>
</div>
<div class="tooltip" id="tooltip"></div>
<div class="zoom-controls">
<button class="zoom-btn" onclick="zoomIn()" title="放大">+</button>
<div class="zoom-level" id="zoom-level">100%</div>
<button class="zoom-btn" onclick="zoomOut()" title="缩小">−</button>
<button class="zoom-btn" onclick="fitNetwork()" title="适应" style="font-size:12px">⊡</button>
</div>
</div>
<div class="resize-handle" id="resize-handle"></div>
<div class="detail-panel" id="detail-panel">
<div class="detail-content" id="detail-content">
<div class="no-detail">点击节点或推导箭头查看详情</div>
</div>
</div>
</div>
<script>
var rawNodes=graphData.nodes;
var rawEdges=graphData.edges;
var nodeTypeColors=JSON.parse('__COLORS_JSON__');
var shapeLegend=JSON.parse('__SHAPES_JSON__');
var cy=null;
var physicsEnabled=true;
var currentView='derivation';
var visLoaded=true;
var topic_id="''' + topic_id + '''";

var nodeDetailsMap={};
rawNodes.forEach(function(n){nodeDetailsMap[n.id]=n});

var edgeDetailsMap={};
rawEdges.forEach(function(e){edgeDetailsMap[e.id]=e});

var mergeGroups={};
var sameLevelDerives=[];

rawEdges.forEach(function(e){
    if(e.type==='derives_from'){
        var target=e.from;
        var source=e.to;
        var targetNode=nodeDetailsMap[target];
        var sourceNode=nodeDetailsMap[source];
        if(!targetNode||!sourceNode)return;
        var tLevel=targetNode.level;
        var sLevel=sourceNode.level;
        if(sLevel>tLevel){
            sameLevelDerives.push(e);
            return;
        }
        if(!mergeGroups[target])mergeGroups[target]={sources:[],edges:[],assumptionEdges:[]};
        if(mergeGroups[target].sources.indexOf(source)===-1){
            mergeGroups[target].sources.push(source);
        }
        mergeGroups[target].edges.push(e);
    }
});

rawEdges.forEach(function(e){
    if(e.type==='requires'||e.type==='assumes'){
        var target=e.from;
        if(mergeGroups[target]){
            mergeGroups[target].assumptionEdges.push(e);
        }
    }
});

var visNodes=[];
var visEdges=[];
var mergeNodeDetails={};

var nodeOrigColors={};
rawNodes.forEach(function(n){
    var isMain=!!n.is_main;
    var origColor=JSON.parse(JSON.stringify(n.color));
    nodeOrigColors[n.id]=origColor;
    var vn={
        id:n.id,
        label:n.label,
        group:n.group,
        shape:'box',
        color:origColor,
        level:n.level,
        font:{size:isMain?24:16,color:'#ffffff',face:'"Microsoft YaHei","SimHei","PingFang SC",sans-serif',multi:true,strokeWidth:0,strokeColor:'transparent'},
        shadow:{enabled:true,color:isMain?'rgba(231,76,60,0.5)':'rgba(0,0,0,0.15)',size:isMain?20:10,x:2,y:2},
        borderWidth:isMain?6:2,
        borderWidthSelected:6,
        margin:{top:isMain?16:12,bottom:isMain?16:12,left:isMain?20:16,right:isMain?20:16},
        chosen:false
    };
    if(isMain){
        vn.font.size=26;
        vn.font.strokeWidth=0;
        vn.color={background:'#e74c3c',border:'#c0392b',highlight:{background:'#c0392b',border:'#922b21'},hover:{background:'#e74c3c',border:'#c0392b'}};
        vn.shadow={enabled:true,color:'rgba(231,76,60,0.6)',size:24,x:0,y:0};
        vn.borderWidth=6;
        vn.margin={top:20,bottom:20,left:28,right:28};
    }
    visNodes.push(vn);
});

for(var target in mergeGroups){
    var group=mergeGroups[target];
    if(group.sources.length===0)continue;
    var mergeId='merge_'+target.replace(/\\./g,'_');
    var targetNode=nodeDetailsMap[target];
    var targetLevel=targetNode?targetNode.level:2;
    var sourceLevels=group.sources.map(function(s){var sn=nodeDetailsMap[s];return sn?sn.level:0});
    var maxSourceLevel=Math.max.apply(null,sourceLevels);
    var mergeLevel=targetLevel-0.5;

    visNodes.push({
        id:mergeId,
        label:'\u63A8\u5BFC',
        shape:'diamond',
        size:16,
        color:{background:'#ff6b6b',border:'#c0392b',highlight:{background:'#ff6b6b',border:'#c0392b'},hover:{background:'#ff6b6b',border:'#c0392b'}},
        level:mergeLevel,
        font:{size:11,color:'#fff',face:'"Microsoft YaHei",sans-serif',multi:true},
        shadow:{enabled:true,color:'rgba(255,107,107,0.3)',size:8,x:0,y:0},
        borderWidth:2,
        borderWidthSelected:4,
        fixed:false,
        chosen:false
    });

    var allAssumptions=[];
    var allDerivationSteps=[];
    var allMathUsed=[];
    group.edges.forEach(function(e){
        if(e.assumptions)allAssumptions=allAssumptions.concat(e.assumptions);
        if(e.derivation_steps)allDerivationSteps=allDerivationSteps.concat(e.derivation_steps);
        if(e.math_used)allMathUsed=allMathUsed.concat(e.math_used);
    });
    var assumptionNodeIds=[];
    group.assumptionEdges.forEach(function(ae){
        assumptionNodeIds.push(ae.to);
        if(ae.assumptions)allAssumptions=allAssumptions.concat(ae.assumptions);
    });
    mergeNodeDetails[mergeId]={
        target:target,
        targetTitle:targetNode?targetNode.cn_title:target,
        targetFormula:targetNode?targetNode.formula_latex:'',
        targetStatement:targetNode?targetNode.statement:'',
        sources:group.sources.map(function(s){var sn=nodeDetailsMap[s];return{id:s,title:sn?sn.cn_title:s,formula:sn?sn.formula_latex:'',statement:sn?sn.statement:''}}),
        assumptions:allAssumptions.filter(function(v,i,a){return a.indexOf(v)===i}),
        derivationSteps:allDerivationSteps,
        mathUsed:allMathUsed.filter(function(v,i,a){return a.indexOf(v)===i}),
        assumptionNodeIds:assumptionNodeIds,
        edges:group.edges
    };

    group.sources.forEach(function(source){
        visEdges.push({
            id:'edge_'+source+'_to_'+mergeId,
            from:source,
            to:mergeId,
            color:{color:'#3366cc',highlight:'#3366cc',hover:'#3366cc',opacity:0.7},
            width:2,
            arrows:{to:{enabled:true,scaleFactor:0.5,type:'arrow'}},
            smooth:{enabled:true,type:'cubicBezier',roundness:0.3},
            dashes:false
        });
    });

    visEdges.push({
        id:'edge_'+mergeId+'_to_'+target,
        from:mergeId,
        to:target,
        color:{color:'#e74c3c',highlight:'#e74c3c',hover:'#e74c3c',opacity:1},
        width:4,
        arrows:{to:{enabled:true,scaleFactor:1.2,type:'arrow'}},
        smooth:{enabled:true,type:'cubicBezier',roundness:0.15},
        dashes:false
    });

    group.assumptionEdges.forEach(function(ae){
        visEdges.push({
            id:'edge_assumption_'+ae.to+'_to_'+mergeId,
            from:ae.to,
            to:mergeId,
            color:{color:'#f39c12',highlight:'#f39c12',hover:'#f39c12',opacity:0.6},
            width:1.5,
            arrows:{to:{enabled:true,scaleFactor:0.4,type:'arrow'}},
            smooth:{enabled:true,type:'cubicBezier',roundness:0.5},
            dashes:[5,5]
        });
    });
}

rawEdges.forEach(function(e){
    if(e.type==='derives_from')return;
    if((e.type==='requires'||e.type==='assumes')&&mergeGroups[e.from])return;
    var edgeColor='#888';
    var edgeWidth=1.5;
    var edgeDashes=false;
    var edgeLabel=e.type.replace(/_/g,' ');
    var edgeFrom=e.from;
    var edgeTo=e.to;
    if(e.type==='uses_math'){edgeColor='#109618';edgeLabel='使用数学'}
    else if(e.type==='equivalent_to'){edgeColor='#0099c6';edgeLabel='等价'}
    else if(e.type==='special_case_of'){edgeColor='#dd4477';edgeLabel='特例'}
    else if(e.type==='approximation_of'){edgeColor='#66aa00';edgeLabel='近似'}
    else if(e.type==='applies_to'){edgeColor='#994499';edgeLabel='应用于';edgeFrom=e.to;edgeTo=e.from}
    else if(e.type==='motivated_by'){edgeColor='#22aa99';edgeLabel='动机'}
    else if(e.type==='related_to'){edgeColor='#aaaa11';edgeLabel='相关'}
    else if(e.type==='requires'){edgeColor='#ff9900';edgeLabel='需要'}
    else if(e.type==='assumes'){edgeColor='#990099';edgeLabel='假设'}
    visEdges.push({
        id:e.id,
        from:edgeFrom,
        to:edgeTo,
        color:{color:edgeColor,highlight:edgeColor,hover:edgeColor,opacity:0.7},
        width:edgeWidth,
        arrows:{to:{enabled:true,scaleFactor:0.6,type:'arrow'}},
        smooth:{enabled:true,type:'cubicBezier',roundness:0.4},
        dashes:edgeDashes,
        label:edgeLabel,
        font:{size:10,color:edgeColor,face:'"Microsoft YaHei",sans-serif',align:'middle',strokeWidth:2,strokeColor:'#fff'},
        labelHighlightBold:true
    });
});

sameLevelDerives.forEach(function(e){
    visEdges.push({
        id:e.id+'_samelvl',
        from:e.from,
        to:e.to,
        color:{color:'#3366cc',highlight:'#3366cc',hover:'#3366cc',opacity:0.5},
        width:1.5,
        arrows:{to:{enabled:true,scaleFactor:0.6,type:'arrow'}},
        smooth:{enabled:true,type:'cubicBezier',roundness:0.4},
        dashes:[5,5],
        label:'推导(同层)',
        font:{size:9,color:'#3366cc',face:'"Microsoft YaHei",sans-serif',align:'middle',strokeWidth:2,strokeColor:'#fff'},
        labelHighlightBold:true
    });
});

function initGraph(){
    visLoaded=true;
    var container=document.getElementById('network-container');

    // Improvement 6: Cytoscape.js initialization
    cy=cytoscape({
        container:container,
        elements:{nodes:visNodes,edges:visEdges},
        style:[
            {selector:'node',style:{'label':'data(label)','text-valign':'center','text-halign':'center','font-size':14,'color':'#fff','text-outline-width':2,'text-outline-color':'#555','background-color':'#4a6cf7','border-width':2,'border-color':'#3451d1','shape':'ellipse','width':'mapData(importance,0,10,40,100)','height':'mapData(importance,0,10,40,100)'}},
            {selector:'node[group="concept"]',style:{'background-color':'#4A90D9','shape':'ellipse'}},
            {selector:'node[group="quantity"]',style:{'background-color':'#50C878','shape':'ellipse'}},
            {selector:'node[group="definition"]',style:{'background-color':'#9370DB','shape':'rectangle'}},
            {selector:'node[group="law"]',style:{'background-color':'#FF6B6B','shape':'hexagon'}},
            {selector:'node[group="equation"]',style:{'background-color':'#FFA500','shape':'rectangle'}},
            {selector:'node[group="assumption"]',style:{'background-color':'#87CEEB','shape':'diamond','border-style':'dashed'}},
            {selector:'node[group="application"]',style:{'background-color':'#FFD700','shape':'roundrectangle'}},
            {selector:'node[group="warning"]',style:{'background-color':'#FF4500','shape':'triangle'}},
            {selector:'node[group="math_tool"]',style:{'background-color':'#98FB98','shape':'star'}},
            {selector:'node[is_main]',style:{'background-color':'#e74c3c','border-width':6,'border-color':'#c0392b','font-size':22,'width':120,'height':120}},
            {selector:'edge',style:{'width':2,'line-color':'#aaa','target-arrow-color':'#aaa','target-arrow-shape':'triangle','curve-style':'bezier','arrow-scale':1.2}},
            {selector:'edge[type="derives"]',style:{'line-color':'#4a6cf7','target-arrow-color':'#4a6cf7','width':3}},
            {selector:'edge[type="derives_from"]',style:{'line-color':'#4a6cf7','target-arrow-color':'#4a6cf7','width':3}},
            {selector:'edge[type="requires"]',style:{'line-color':'#e17055','target-arrow-color':'#e17055','line-style':'dashed'}},
            {selector:'edge[type="assumes"]',style:{'line-color':'#f39c12','target-arrow-color':'#f39c12','line-style':'dotted'}},
            {selector:'edge[type="uses_math"]',style:{'line-color':'#00b894','target-arrow-color':'#00b894','line-style':'dashed'}},
            {selector:'edge[type="applies_to"]',style:{'line-color':'#6c5ce7','target-arrow-color':'#6c5ce7','line-style':'dashed'}},
            {selector:'edge[dashes]',style:{'line-style':'dashed','line-color':'#ff6b6b','target-arrow-color':'#ff6b6b'}},
            // Improvement 2: proofstep nodes as diamonds
            {selector:'node[group="proof_step"]',style:{'background-color':'#fd79a8','shape':'diamond','width':50,'height':50,'font-size':11}},
        ],
        layout:{name:'dagre',rankDir:'LR',nodeSep:60,rankSep:150,fit:true,padding:40,animate:true,animationDuration:500},
        wheelSensitivity:0.3,
        minZoom:0.1,
        maxZoom:5,
    });

    cy.on('tap','node',function(evt){
        var nodeId=evt.target.id();
        showNodeDetail(nodeId);
    });
    cy.on('tap','edge',function(evt){
        var edgeId=evt.target.id();
        showEdgeDetail(edgeId);
    });
    cy.on('tap',function(evt){
        if(evt.target===cy){showDefaultDetail();}
    });

    // zoom controls
    window.cy=cy;
    updateZoomLevel();
                showMergeDetails(nodeId);
            }else{
                showNodeDetails(nodeId);
            }
        }else if(params.edges.length>0){
            var edgeId=params.edges[0];
            if(edgeId.startsWith('edge_')&&edgeId.includes('_to_merge_')){
                var mergeId=edgeId.split('_to_')[1]||edgeId.replace('edge_','').split('_to_')[1];
                if(mergeNodeDetails[mergeId]){
                    showMergeDetails(mergeId);
                }
            }else if(edgeDetailsMap[edgeId]){
                showEdgeDetails(edgeId);
            }
        }else{
            hideDetails();
        }
    });
    network.on('selectNode',function(params){
        if(params.nodes.length>0){
            var nodeId=params.nodes[0];
            var origColor=nodeOrigColors[nodeId];
            if(origColor){
                setTimeout(function(){
                    cy.nodes().update({id:nodeId,color:JSON.parse(JSON.stringify(origColor))});
                },10);
            }
        }
    });
    network.on('deselectNode',function(params){
        params.previousSelection.nodes.forEach(function(nodeId){
            var origColor=nodeOrigColors[nodeId];
            if(origColor){
                cy.nodes().update({id:nodeId,color:JSON.parse(JSON.stringify(origColor))});
            }
        });
    });
    network.on('doubleClick',function(params){
        if(params.nodes.length>0){
            var nodeId=params.nodes[0];
            if(network)network.focus(nodeId,{scale:1.5,animation:{duration:500,easingFunction:'easeInOutQuad'}});
        }
    });
    network.on('zoom',function(){updateZoomLevel();drawMinimap()});
    network.on('dragEnd',function(){updateZoomLevel();drawMinimap()});
    setupTooltip();
    document.addEventListener('keydown',function(e){
        if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA')return;
        if(e.key==='='||e.key==='+'){e.preventDefault();zoomIn()}
        else if(e.key==='-'){e.preventDefault();zoomOut()}
        else if(e.key==='0'){e.preventDefault();fitNetwork()}
        else if(e.key==='f'||e.key==='F'){e.preventDefault();fitNetwork()}
        else if(e.key==='p'||e.key==='P'){e.preventDefault();togglePhysics()}
        else if(e.key==='d'||e.key==='D'){e.preventDefault();toggleDetailPanel()}
        else if(e.key==='h'||e.key==='H'){e.preventDefault();toggleTopBar()}
        else if(e.key==='s'||e.key==='S'){e.preventDefault();document.getElementById('search-input').focus()}
        else if(e.key==='t'||e.key==='T'){e.preventDefault();toggleTheme()}
        else if(e.key==='m'||e.key==='M'){e.preventDefault();toggleMinimap()}
        else if(e.key==='Escape'){hideDetails();clearHighlight()}
    });
}

function renderLatex(element){
    if(typeof renderMathInElement==='function'){
        renderMathInElement(element,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],throwOnError:false});
    }
}

function showNodeDetails(nodeId){
    var node=nodeDetailsMap[nodeId];
    if(!node){document.getElementById('detail-content').innerHTML='<div class="no-detail">未找到节点信息</div>';return}
    var html='<div class="detail-header">';
    var typeLabels={law:'定律',equation:'方程',concept:'概念',quantity:'物理量',assumption:'假设',math_tool:'数学工具',definition:'定义',model:'模型',application:'应用',experiment:'实验',warning:'警告',intuition_card:'直觉卡'};
    html+='<span style="font-size:20px">'+(typeLabels[node.group]||node.group)+'</span> '+node.cn_title;
    html+='<div style="font-size:12px;color:var(--text-light);font-weight:400;margin-top:2px">'+node.en_name+'</div>';
    html+='</div>';
    if(node.statement){
        html+='<div class="detail-section"><h4>描述</h4><div class="detail-field">'+node.statement+'</div></div>';
    }
    if(node.formula_latex&&node.formula_latex!=='N/A'){
        var formula=node.formula_latex;
        if(formula.indexOf('$')<0&&formula.indexOf('\\\\')>=0){
            formula='$$'+formula+'$$';
        }else if(formula.indexOf('$')<0){
            formula='$$'+formula+'$$';
        }
        html+='<div class="detail-section"><h4>公式</h4><div class="formula-block">'+formula+'</div></div>';
    }
    if(node.dimension){
        html+='<div class="detail-section"><h4>量纲</h4><div class="detail-field"><strong>符号:</strong> '+node.dimension.symbol+'</div><div class="detail-field"><strong>单位:</strong> '+node.dimension.unit+'</div></div>';
    }
    html+='<div class="detail-section"><h4>基本信息</h4>';
    html+='<div class="detail-field"><strong>ID:</strong> '+node.id+'</div>';
    html+='<div class="detail-field"><strong>学科域:</strong> '+node.domain+'</div>';
    html+='<div class="detail-field"><strong>抽象层级:</strong> '+node.level+'</div>';
    if(node.aliases&&node.aliases.length>0){
        html+='<div class="detail-field"><strong>别名:</strong> '+node.aliases.join(', ')+'</div>';
    }
    html+='</div>';
    var inEdges=rawEdges.filter(function(e){return e.to===nodeId&&e.type==='derives_from'});
    var outEdges=rawEdges.filter(function(e){return e.from===nodeId&&e.type==='derives_from'});
    if(inEdges.length>0){
        html+='<div class="detail-section"><h4>被推导出</h4>';
        inEdges.forEach(function(e){
            var src=nodeDetailsMap[e.from];
            html+='<div class="source-node-tag">'+(src?src.cn_title:e.from)+'</div>';
        });
        html+='</div>';
    }
    if(outEdges.length>0){
        html+='<div class="detail-section"><h4>推导出</h4>';
        outEdges.forEach(function(e){
            var tgt=nodeDetailsMap[e.to];
            html+='<div class="target-node-tag">'+(tgt?tgt.cn_title:e.to)+'</div>';
        });
        html+='</div>';
    }
    document.getElementById('detail-content').innerHTML=html;
    renderLatex(document.getElementById('detail-content'));
}

function showMergeDetails(mergeId){
    var info=mergeNodeDetails[mergeId];
    if(!info){document.getElementById('detail-content').innerHTML='<div class="no-detail">未找到推导信息</div>';return}
    var html='<div class="detail-header" style="border-bottom-color:#e74c3c"><span style="font-size:20px">推导</span> → '+info.targetTitle+'</div>';
    html+='<div class="merge-detail">';
    html+='<h4>目标定理</h4>';
    html+='<div class="target-node-tag" style="font-size:13px;padding:4px 12px">'+info.targetTitle+'</div>';
    if(info.targetStatement){
        html+='<div class="detail-field" style="margin-top:6px">'+info.targetStatement+'</div>';
    }
    if(info.targetFormula){
        html+='<div class="formula-block">$$'+info.targetFormula+'$$</div>';
    }
    html+='</div>';
    html+='<div class="detail-section"><h4>来源 ('+info.sources.length+')</h4>';
    info.sources.forEach(function(s){
        html+='<div style="margin:4px 0"><span class="source-node-tag">'+s.title+'</span>';
        if(s.statement)html+='<div style="font-size:11px;color:#666;margin-left:8px">'+s.statement+'</div>';
        if(s.formula)html+='<div class="formula-block" style="font-size:12px;padding:4px 8px">$$'+s.formula+'$$</div>';
        html+='</div>';
    });
    html+='</div>';
    if(info.assumptions.length>0){
        html+='<div class="detail-section"><h4>假设条件</h4>';
        info.assumptions.forEach(function(a){
            html+='<span class="assumption-chip">'+a.replace(/assumption\\./g,'').replace(/_/g,' ')+'</span>';
        });
        html+='</div>';
    }
    if(info.derivationSteps.length>0){
        html+='<div class="detail-section"><h4>推导步骤</h4>';
        info.derivationSteps.forEach(function(s,i){
            html+='<div class="step-item"><strong>'+(i+1)+'.</strong> '+s+'</div>';
        });
        html+='</div>';
    }
    if(info.mathUsed.length>0){
        html+='<div class="detail-section"><h4>使用的数学工具</h4>';
        info.mathUsed.forEach(function(m){
            html+='<span class="assumption-chip" style="background:#f3e5f5;border-color:#ce93d8;color:#7b1fa2">'+m.replace(/_/g,' ')+'</span>';
        });
        html+='</div>';
    }
    document.getElementById('detail-content').innerHTML=html;
    renderLatex(document.getElementById('detail-content'));
}

function showEdgeDetails(edgeId){
    var edge=edgeDetailsMap[edgeId];
    if(!edge){document.getElementById('detail-content').innerHTML='<div class="no-detail">未找到边信息</div>';return}
    var fromNode=nodeDetailsMap[edge.from];
    var toNode=nodeDetailsMap[edge.to];
    var html='<div class="detail-header">边详情</div>';
    html+='<div class="detail-section"><h4>连接</h4>';
    html+='<div class="source-node-tag">'+(fromNode?fromNode.label:edge.from)+'</div>';
    html+=' <span style="margin:0 6px">→</span> ';
    html+='<div class="target-node-tag">'+(toNode?toNode.label:edge.to)+'</div>';
    html+='</div>';
    html+='<div class="detail-section"><h4>基本信息</h4>';
    html+='<div class="detail-field"><strong>类型:</strong> '+edge.type+'</div>';
    html+='<div class="detail-field"><strong>ID:</strong> '+edge.id+'</div>';
    html+='<div class="detail-field"><strong>路径:</strong> '+edge.path_id+'</div>';
    html+='</div>';
    if(edge.assumptions&&edge.assumptions.length>0){
        html+='<div class="detail-section"><h4>假设</h4>';
        edge.assumptions.forEach(function(a){html+='<span class="assumption-chip">'+a.replace(/assumption\\./g,'').replace(/_/g,' ')+'</span>'});
        html+='</div>';
    }
    if(edge.derivation_steps&&edge.derivation_steps.length>0){
        html+='<div class="detail-section"><h4>推导步骤</h4>';
        edge.derivation_steps.forEach(function(s,i){html+='<div class="step-item"><strong>'+(i+1)+'.</strong> '+s+'</div>'});
        html+='</div>';
    }
    if(edge.math_used&&edge.math_used.length>0){
        html+='<div class="detail-section"><h4>数学工具</h4>';
        edge.math_used.forEach(function(m){html+='<span class="assumption-chip" style="background:#f3e5f5;border-color:#ce93d8;color:#7b1fa2">'+m.replace(/_/g,' ')+'</span>'});
        html+='</div>';
    }
    document.getElementById('detail-content').innerHTML=html;
    renderLatex(document.getElementById('detail-content'));
}

function hideDetails(){
    document.getElementById('detail-content').innerHTML='<div class="no-detail">点击节点或推导箭头查看详情</div>';
}

function fitNetwork(){
    if(cy){cy.fit(null,50);updateZoomLevel();}
}
function zoomIn(){
    if(!cy)return;
    cy.zoom({level:cy.zoom()*1.3,renderedPosition:{x:cy.width()/2,y:cy.height()/2}});
    setTimeout(updateZoomLevel,350);
}
function zoomOut(){
    if(!cy)return;
    cy.zoom({level:cy.zoom()/1.3,renderedPosition:{x:cy.width()/2,y:cy.height()/2}});
    setTimeout(updateZoomLevel,350);
}
function updateZoomLevel(){
    if(!cy)return;
    var el=document.getElementById('zoom-level');
    if(!el)return;
    var pct=Math.round(cy.zoom()*100);
    el.textContent=pct+'%';
}

// Improvement 5: 三种视图切换
function switchView(view){
    currentView=view;
    if(!cy)return;
    var derivEdges=cy.edges('[type="derives"],[type="derives_from"],[type="requires"],[type="uses_math"]');
    var appEdges=cy.edges('[type="applies_to"]');
    var decompEdges=cy.edges('[type="requires"],[type="uses_math"],[type="assumes"]');
    if(view==='decomposition'){
        // 分解视图：显示所有依赖关系（目标向下分解）
        cy.elements().style('display','element');
    }else if(view==='derivation'){
        // 推导视图：基础→结论，隐藏应用边
        appEdges.style('display','none');
        derivEdges.style('display','element');
        cy.layout({name:'dagre',rankDir:'LR',nodeSep:60,rankSep:150,fit:true,padding:40,animate:true}).run();
    }else if(view==='application'){
        // 应用视图：目标→应用
        derivEdges.style('display','none');
        appEdges.style('display','element');
        cy.layout({name:'dagre',rankDir:'LR',nodeSep:60,rankSep:150,fit:true,padding:40,animate:true}).run();
    }
    // 更新按钮样式
    ['decomposition','derivation','application'].forEach(function(v){
        var btn=document.getElementById('btn-'+v.substring(0,4));
        if(btn)btn.style.opacity=v===view?'1.0':'0.6';
    });
}
function togglePhysics(){
    // Cytoscape uses static layout, physics toggle toggles drag
    if(!cy)return;
    physicsEnabled=!physicsEnabled;
    cy.nodes().forEach(function(n){n.grabbable(physicsEnabled);});
}
function toggleHeader(){
    var h=document.getElementById('header');
    var h2=h.querySelector('h2');
    if(h2.style.display==='none'){h2.style.display='';h.querySelector('.header-toggle').textContent='▾'}
    else{h2.style.display='none';h.querySelector('.header-toggle').textContent='▴'}
}
function toggleLegend(){
    document.getElementById('legend-bar').classList.toggle('collapsed');
}
function toggleTopBar(){
    var stats=document.getElementById('stats-bar');
    var legend=document.getElementById('legend-bar');
    var controls=document.getElementById('controls-bar');
    var isHidden=stats.style.display==='none';
    stats.style.display=isHidden?'':'none';
    legend.style.display=isHidden?'':'none';
    controls.style.display=isHidden?'':'none';
}
function toggleDetailPanel(){
    var panel=document.getElementById('detail-panel');
    var handle=document.getElementById('resize-handle');
    var btn=document.querySelector('.toggle-sidebar');
    if(panel.classList.contains('collapsed')){
        panel.classList.remove('collapsed');
        panel.style.width='360px';
        panel.style.minWidth='250px';
        handle.style.display='';
        btn.textContent='详情';
    }else{
        panel.classList.add('collapsed');
        handle.style.display='none';
        btn.textContent='展开';
    }
}
function filterByType(type){
    if(!visLoaded||!network)return;
    if(!type){
        var nodeUpdates=[];var edgeUpdates=[];
        visNodes.forEach(function(n){nodeUpdates.push({id:n.id,opacity:1.0,hidden:false})});
        visEdges.forEach(function(e){edgeUpdates.push({id:e.id,opacity:1.0,hidden:false})});
        cy.nodes().update(nodeUpdates);
        cy.edges().update(edgeUpdates);
        return;
    }
    var typeIds={};visNodes.forEach(function(n){if(n.group===type||n.id.startsWith('merge_'))typeIds[n.id]=true});
    var nodeUpdates=[];var edgeUpdates=[];
    visNodes.forEach(function(n){nodeUpdates.push({id:n.id,opacity:typeIds[n.id]?1.0:0.1,hidden:false})});
    visEdges.forEach(function(e){edgeUpdates.push({id:e.id,opacity:(typeIds[e.from]&&typeIds[e.to])?1.0:0.05,hidden:false})});
    cy.nodes().update(nodeUpdates);
    cy.edges().update(edgeUpdates);
}

function generateLegend(){
    var container=document.getElementById('legend-items');
    container.innerHTML='';
    var shapeSymbols={diamond:'◆',circle:'●',hexagon:'⬡',triangleDown:'▽',star:'★',box:'■',square:'□',ellipse:'⬭',triangle:'△'};
    for(var type in shapeLegend){
        if(!shapeLegend.hasOwnProperty(type))continue;
        var info=shapeLegend[type];
        var item=document.createElement('div');
        item.className='legend-item';
        var sym=shapeSymbols[info.shape]||'●';
        item.innerHTML='<div class="legend-shape" style="color:'+nodeTypeColors[type]+'">'+sym+'</div><span>'+info.label+'</span>';
        container.appendChild(item);
    }
    var mergeItem=document.createElement('div');
    mergeItem.className='legend-item';
    mergeItem.innerHTML='<div class="legend-shape" style="color:#ff6b6b">\u25CF</div><span>\u63A8\u5BFC\u6C47\u805A\u70B9</span>';
    container.appendChild(mergeItem);
    var assumeItem=document.createElement('div');
    assumeItem.className='legend-item';
    assumeItem.innerHTML='<div class="legend-shape" style="color:#f39c12;font-size:8px">┈→</div><span>假设条件</span>';
    container.appendChild(assumeItem);
}

var canonicalPathId="__CANONICAL_PATH__";
var alternatePaths=__ALTERNATE_PATHS__;

function handleSearch(query){
    var resultsEl=document.getElementById('search-results');
    if(!query||query.length<1){resultsEl.classList.remove('visible');return}
    var matches=[];
    var q=query.toLowerCase();
    rawNodes.forEach(function(n){
        if(n.label.toLowerCase().indexOf(q)>=0||n.id.toLowerCase().indexOf(q)>=0||
           (n.statement&&n.statement.toLowerCase().indexOf(q)>=0)){
            matches.push(n);
        }
    });
    if(matches.length===0){resultsEl.classList.remove('visible');return}
    resultsEl.innerHTML='';
    matches.slice(0,10).forEach(function(m){
        var div=document.createElement('div');
        div.className='search-result-item';
        var color=nodeTypeColors[m.group]||'#bdc3c7';
        div.innerHTML='<span class="search-result-type" style="background:'+color+'"></span>'+m.label;
        div.addEventListener('mousedown',function(e){
            e.preventDefault();
            if(network){
                network.focus(m.id,{scale:1.5,animation:{duration:500,easingFunction:'easeInOutQuad'}});
                network.selectNodes([m.id]);
                if(mergeNodeDetails[m.id]){showMergeDetails(m.id)}else{showNodeDetails(m.id)}
            }
            resultsEl.classList.remove('visible');
            document.getElementById('search-input').value=m.label;
        });
        resultsEl.appendChild(div);
    });
    resultsEl.classList.add('visible');
}

function highlightCanonicalPath(){
    if(!visLoaded||!network)return;
    clearHighlight();
    if(!canonicalPathId)return;
    var pathEdges=rawEdges.filter(function(e){return e.path_id===canonicalPathId});
    var pathNodeIds=new Set();
    pathEdges.forEach(function(e){pathNodeIds.add(e.from);pathNodeIds.add(e.to)});
    var nodeUpdates=[];
    var edgeUpdates=[];
    visNodes.forEach(function(n){
        if(pathNodeIds.has(n.id)){
            nodeUpdates.push({id:n.id,borderWidth:4,shadow:{enabled:true,color:'rgba(74,108,247,0.5)',size:16,x:0,y:0}});
            n.borderWidth=4;n.shadow={enabled:true,color:'rgba(74,108,247,0.5)',size:16,x:0,y:0};
        }
    });
    visEdges.forEach(function(e){
        var rawEdge=rawEdges.find(function(re){return re.id===e.id});
        if(rawEdge&&rawEdge.path_id===canonicalPathId){
            edgeUpdates.push({id:e.id,width:5,dashes:false});
            e.width=5;e.dashes=false;
        }else{
            edgeUpdates.push({id:e.id,opacity:0.15,width:1});
            e.opacity=0.15;e.width=1;
        }
    });
    cy.nodes().update(nodeUpdates);
    cy.edges().update(edgeUpdates);
    document.getElementById('btn-highlight-canonical').classList.add('active');
}

function highlightAllPaths(){
    if(!visLoaded||!network)return;
    clearHighlight();
    var allPathIds=new Set();
    allPathIds.add(canonicalPathId);
    alternatePaths.forEach(function(p){allPathIds.add(p)});
    var pathEdges=rawEdges.filter(function(e){return allPathIds.has(e.path_id)});
    var pathNodeIds=new Set();
    pathEdges.forEach(function(e){pathNodeIds.add(e.from);pathNodeIds.add(e.to)});
    var nodeUpdates=[];
    var edgeUpdates=[];
    visNodes.forEach(function(n){
        if(pathNodeIds.has(n.id)){
            nodeUpdates.push({id:n.id,borderWidth:3,shadow:{enabled:true,color:'rgba(74,108,247,0.3)',size:12,x:0,y:0}});
            n.borderWidth=3;n.shadow={enabled:true,color:'rgba(74,108,247,0.3)',size:12,x:0,y:0};
        }
    });
    visEdges.forEach(function(e){
        var rawEdge=rawEdges.find(function(re){return re.id===e.id});
        if(rawEdge&&allPathIds.has(rawEdge.path_id)){
            edgeUpdates.push({id:e.id,width:4,dashes:false});
            e.width=4;e.dashes=false;
        }else{
            edgeUpdates.push({id:e.id,opacity:0.1,width:1});
            e.opacity=0.1;e.width=1;
        }
    });
    cy.nodes().update(nodeUpdates);
    cy.edges().update(edgeUpdates);
    document.getElementById('btn-highlight-all').classList.add('active');
}

function clearHighlight(){
    if(!visLoaded||!network)return;
    var nodeUpdates=[];
    var edgeUpdates=[];
    visNodes.forEach(function(n){
        nodeUpdates.push({id:n.id,borderWidth:undefined,shadow:undefined,opacity:undefined});
        n.borderWidth=undefined;n.shadow=undefined;n.opacity=undefined;
    });
    visEdges.forEach(function(e){
        edgeUpdates.push({id:e.id,width:undefined,dashes:undefined,opacity:undefined});
        e.width=undefined;e.dashes=undefined;e.opacity=undefined;
    });
    cy.nodes().update(nodeUpdates);
    cy.edges().update(edgeUpdates);
    document.querySelectorAll('.path-highlight-btn').forEach(function(b){b.classList.remove('active')});
}

function exportSVG(){
    if(!visLoaded||!network)return;
    var canvas=document.querySelector('#network-container canvas');
    if(!canvas)return;
    var svgStr='<svg xmlns="http://www.w3.org/2000/svg" width="'+canvas.width+'" height="'+canvas.height+'">'+
        '<foreignObject width="100%" height="100%">'+
        '<img xmlns="http://www.w3.org/1999/xhtml" src="'+canvas.toDataURL('image/png')+'" width="'+canvas.width+'" height="'+canvas.height+'"/>'+
        '</foreignObject></svg>';
    var blob=new Blob([svgStr],{type:'image/svg+xml'});
    var url=URL.createObjectURL(blob);
    var a=document.createElement('a');
    a.href=url;a.download=topic_id+'_graph.svg';a.click();
    URL.revokeObjectURL(url);
}

function exportPNG(){
    if(!visLoaded||!network)return;
    var canvas=document.querySelector('#network-container canvas');
    if(!canvas)return;
    var a=document.createElement('a');
    a.href=canvas.toDataURL('image/png');
    a.download=topic_id+'_graph.png';a.click();
}

function toggleTheme(){
    var html=document.documentElement;
    var isDark=html.getAttribute('data-theme')==='dark';
    html.setAttribute('data-theme',isDark?'light':'dark');
    var btn=document.querySelector('.theme-toggle');
    btn.textContent=isDark?'🌙':'☀️';
}

function toggleStats(){
    var el=document.getElementById('stats-overlay');
    el.classList.toggle('hidden');
    if(!el.classList.contains('hidden')){updateStatsOverlay()}
}

function updateLayout(){
    var levelSep=parseInt(document.getElementById('level-sep-slider').value);
    var nodeSpac=parseInt(document.getElementById('node-spac-slider').value);
    window.levelSep=levelSep;
    window.nodeSpac=nodeSpac;
    document.getElementById('level-sep-val').textContent=levelSep;
    document.getElementById('node-spac-val').textContent=nodeSpac;
    localStorage.setItem('pg_levelSep',levelSep);
    localStorage.setItem('pg_nodeSpac',nodeSpac);
    if(!network)return;
    // cy.style().update...({
        layout:{hierarchical:{levelSeparation:levelSep,nodeSpacing:nodeSpac}},
        physics:{enabled:true,stabilization:{enabled:true,iterations:200,updateInterval:10,fit:false}}
    });
    network.once('stabilizationIterationsDone',function(){
        // cy.style().update...({physics:{enabled:false}});
        physicsEnabled=false;
        cy.fit({padding:40,animation:{duration:400,easingFunction:'easeInOutQuad'}});
    });
}

function updateStatsOverlay(){
    var body=document.getElementById('stats-overlay-body');
    if(!body)return;
    var typeCounts={};
    var levelCounts={};
    var edgeTypeCounts={};
    var totalDegree=0;
    rawNodes.forEach(function(n){
        typeCounts[n.group]=(typeCounts[n.group]||0)+1;
        levelCounts[n.level]=(levelCounts[n.level]||0)+1;
    });
    rawEdges.forEach(function(e){edgeTypeCounts[e.type]=(edgeTypeCounts[e.type]||0)+1});
    var degreeMap={};
    rawEdges.forEach(function(e){
        degreeMap[e.from]=(degreeMap[e.from]||0)+1;
        degreeMap[e.to]=(degreeMap[e.to]||0)+1;
    });
    var maxDegree=0;var maxDegreeNode='';
    for(var nid in degreeMap){if(degreeMap[nid]>maxDegree){maxDegree=degreeMap[nid];maxDegreeNode=nid}}
    var maxNode=rawNodes.find(function(n){return n.id===maxDegreeNode});
    var html='<div class="stats-row"><span class="stats-label">节点总数</span><span class="stats-value">'+rawNodes.length+'</span></div>';
    html+='<div class="stats-row"><span class="stats-label">边总数</span><span class="stats-value">'+rawEdges.length+'</span></div>';
    html+='<div class="stats-row"><span class="stats-label">密度</span><span class="stats-value">'+(rawEdges.length/(rawNodes.length*(rawNodes.length-1)/2)||0).toFixed(3)+'</span></div>';
    html+='<div class="stats-row"><span class="stats-label">最高度节点</span><span class="stats-value">'+(maxNode?maxNode.label:'N/A')+' ('+maxDegree+')</span></div>';
    html+='<div style="margin:6px 0 4px;font-size:10px;color:var(--text-light);font-weight:600">节点类型分布</div>';
    for(var t in typeCounts){html+='<div class="stats-row"><span class="stats-label">'+t+'</span><span class="stats-value">'+typeCounts[t]+'</span></div>'}
    html+='<div style="margin:6px 0 4px;font-size:10px;color:var(--text-light);font-weight:600">层级分布</div>';
    var maxL=0;for(var l in levelCounts){if(parseInt(l)>maxL)maxL=parseInt(l)}
    for(var l=0;l<=maxL;l++){if(levelCounts[l]){html+='<div class="stats-row"><span class="stats-label">Level '+l+'</span><span class="stats-value">'+levelCounts[l]+'</span></div>'}}
    html+='<div style="margin:6px 0 4px;font-size:10px;color:var(--text-light);font-weight:600">边类型分布</div>';
    for(var et in edgeTypeCounts){html+='<div class="stats-row"><span class="stats-label">'+et+'</span><span class="stats-value">'+edgeTypeCounts[et]+'</span></div>'}
    body.innerHTML=html;
}

function toggleMinimap(){
    var el=document.getElementById('minimap-container');
    el.classList.toggle('hidden');
    if(!el.classList.contains('hidden')){drawMinimap()}
}

function drawMinimap(){
    var canvas=document.getElementById('minimap-canvas');
    if(!canvas||!network)return;
    var ctx=canvas.getContext('2d');
    ctx.clearRect(0,0,canvas.width,canvas.height);
    var positions=network.getPositions();
    if(!positions||Object.keys(positions).length===0)return;
    var minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
    for(var id in positions){
        var p=positions[id];
        if(p.x<minX)minX=p.x;if(p.x>maxX)maxX=p.x;
        if(p.y<minY)minY=p.y;if(p.y>maxY)maxY=p.y;
    }
    var rangeX=maxX-minX||1;var rangeY=maxY-minY||1;
    var scaleX=(canvas.width-20)/rangeX;var scaleY=(canvas.height-20)/rangeY;
    var scale=Math.min(scaleX,scaleY);
    var offsetX=(canvas.width-rangeX*scale)/2;var offsetY=(canvas.height-rangeY*scale)/2;
    rawEdges.forEach(function(e){
        var from=positions[e.from];var to=positions[e.to];
        if(!from||!to)return;
        ctx.beginPath();
        ctx.moveTo((from.x-minX)*scale+offsetX,(from.y-minY)*scale+offsetY);
        ctx.lineTo((to.x-minX)*scale+offsetX,(to.y-minY)*scale+offsetY);
        ctx.strokeStyle='rgba(74,108,247,0.2)';ctx.lineWidth=0.5;ctx.stroke();
    });
    rawNodes.forEach(function(n){
        var p=positions[n.id];if(!p)return;
        var x=(p.x-minX)*scale+offsetX;var y=(p.y-minY)*scale+offsetY;
        ctx.beginPath();ctx.arc(x,y,2,0,Math.PI*2);
        ctx.fillStyle=nodeTypeColors[n.group]||'#bdc3c7';ctx.fill();
    });
}

var tooltipEl=document.getElementById('tooltip');
var lastHoveredNode=null;
var highlightedNodes=new Set();
var highlightedEdges=new Set();

function getConnectedChain(nodeId,visited){
    if(!visited)visited=new Set();
    if(visited.has(nodeId))return;
    visited.add(nodeId);
    highlightedNodes.add(nodeId);
    rawEdges.forEach(function(e){
        if(e.from===nodeId&&!visited.has(e.to)){
            highlightedEdges.add(e.id);
            getConnectedChain(e.to,visited);
        }
        if(e.to===nodeId&&!visited.has(e.from)){
            highlightedEdges.add(e.id);
            getConnectedChain(e.from,visited);
        }
    });
}

function clearHoverHighlight(){
    if(highlightedNodes.size===0)return;
    var nodeUpdates=[];
    var edgeUpdates=[];
    visNodes.forEach(function(n){
        if(n.opacity!==undefined){
            var origColor=nodeOrigColors[n.id];
            if(n.id.startsWith('merge_')){
                origColor={background:'#ff6b6b',border:'#c0392b',highlight:{background:'#ff6b6b',border:'#c0392b'},hover:{background:'#ff6b6b',border:'#c0392b'}};
            }
            var restoreColor=origColor?JSON.parse(JSON.stringify(origColor)):undefined;
            nodeUpdates.push({id:n.id,opacity:undefined,borderWidth:undefined,shadow:undefined,color:restoreColor});
            n.opacity=undefined;n.borderWidth=undefined;n.shadow=undefined;
        }
    });
    visEdges.forEach(function(e){
        if(e.opacity!==undefined){
            edgeUpdates.push({id:e.id,opacity:undefined,width:undefined});
            e.opacity=undefined;e.width=undefined;
        }
    });
    if(network){
        if(nodeUpdates.length>0)cy.nodes().update(nodeUpdates);
        if(edgeUpdates.length>0)cy.edges().update(edgeUpdates);
    }
    highlightedNodes.clear();
    highlightedEdges.clear();
}

function applyHoverHighlight(nodeId){
    clearHoverHighlight();
    getConnectedChain(nodeId);
    var nodeUpdates=[];
    var edgeUpdates=[];
    visNodes.forEach(function(n){
        if(highlightedNodes.has(n.id)){
            nodeUpdates.push({id:n.id,opacity:1.0,borderWidth:4,shadow:{enabled:true,color:'rgba(74,108,247,0.5)',size:16,x:0,y:0}});
            n.opacity=1.0;n.borderWidth=4;n.shadow={enabled:true,color:'rgba(74,108,247,0.5)',size:16,x:0,y:0};
        }else{
            nodeUpdates.push({id:n.id,opacity:0.2});
            n.opacity=0.2;
        }
    });
    visEdges.forEach(function(e){
        var rawEdge=rawEdges.find(function(re){return re.id===e.id});
        if(rawEdge&&highlightedEdges.has(rawEdge.id)){
            edgeUpdates.push({id:e.id,opacity:1.0,width:4});
            e.opacity=1.0;e.width=4;
        }else{
            edgeUpdates.push({id:e.id,opacity:0.08,width:1});
            e.opacity=0.08;e.width=1;
        }
    });
    if(network){
        cy.nodes().update(nodeUpdates);
        cy.edges().update(edgeUpdates);
    }
}

function setupTooltip(){
    if(!network)return;
    var canvas=document.getElementById('network-container').querySelector('canvas');
    if(!canvas)return;
    canvas.addEventListener('mousemove',function(evt){
        var rect=canvas.getBoundingClientRect();
        var domX=evt.clientX-rect.left;
        var domY=evt.clientY-rect.top;
        var canvasCoord=network.DOMtoCanvas({x:domX,y:domY});
        var nodeId=network.getNodeAt({x:domX,y:domY});
        if(nodeId&&nodeId!==lastHoveredNode){
            lastHoveredNode=nodeId;
            applyHoverHighlight(nodeId);
            var node=nodeDetailsMap[nodeId];
            if(node){
                var html='<div class="tooltip-title">'+node.cn_title+'</div>';
                if(node.formula_latex&&node.formula_latex!=='N/A'){
                    html+='<div class="tooltip-formula" style="margin-top:4px">$'+node.formula_latex+'$</div>';
                }
                if(node.statement){html+='<div style="color:var(--text-light);font-size:10px;margin-top:3px">'+node.statement.substring(0,100)+(node.statement.length>100?'...':'')+'</div>'}
                tooltipEl.innerHTML=html;
                if(typeof renderMathInElement==='function'){
                    renderMathInElement(tooltipEl,{delimiters:[{left:'$',right:'$',display:false}],throwOnError:false});
                }
            }else if(mergeNodeDetails[nodeId]){
                var info=mergeNodeDetails[nodeId];
                var html='<div class="tooltip-title" style="color:#e74c3c">\u63A8\u5BFC\u6C47\u805A\u70B9</div>';
                html+='<div style="color:var(--text-light);font-size:10px">\u2192 '+info.targetTitle+'</div>';
                tooltipEl.innerHTML=html;
            }
            var canvasRect=document.getElementById('network-container').getBoundingClientRect();
            tooltipEl.style.left=(domX+15)+'px';
            tooltipEl.style.top=(domY-10)+'px';
            tooltipEl.classList.add('visible');
        }else if(!nodeId&&lastHoveredNode){
            lastHoveredNode=null;
            tooltipEl.classList.remove('visible');
            clearHoverHighlight();
        }else if(nodeId&&nodeId===lastHoveredNode){
            var canvasRect2=document.getElementById('network-container').getBoundingClientRect();
            tooltipEl.style.left=(domX+15)+'px';
            tooltipEl.style.top=(domY-10)+'px';
        }
    });
    canvas.addEventListener('mouseleave',function(){
        lastHoveredNode=null;
        tooltipEl.classList.remove('visible');
        clearHoverHighlight();
    });
}

var resizeHandle=document.getElementById('resize-handle');
var detailPanel=document.getElementById('detail-panel');
var graphPanel=document.querySelector('.graph-panel');
var isResizing=false;
var startX=0;
var startWidth=0;
resizeHandle.addEventListener('mousedown',function(e){
    isResizing=true;
    startX=e.clientX;
    startWidth=detailPanel.offsetWidth;
    document.body.style.cursor='col-resize';
    document.body.style.userSelect='none';
    e.preventDefault();
    e.stopPropagation();
});
document.addEventListener('mousemove',function(e){
    if(!isResizing)return;
    var dx=startX-e.clientX;
    var newWidth=startWidth+dx;
    newWidth=Math.max(250,Math.min(700,newWidth));
    detailPanel.style.width=newWidth+'px';
    detailPanel.style.minWidth=newWidth+'px';
    e.preventDefault();
});
document.addEventListener('mouseup',function(){
    if(isResizing){
        isResizing=false;
        document.body.style.cursor='';
        document.body.style.userSelect='';
    }
});

var initAttempted=false;
function attemptInit(){
    if(initAttempted)return;
    if(typeof cytoscape!=='undefined'){
        initAttempted=true;
        document.getElementById('loading-indicator').style.display='none';
        initGraph();
        generateLegend();
    }
}
attemptInit();
document.addEventListener('DOMContentLoaded',function(){
    attemptInit();
    var checks=0;
    var checkInterval=setInterval(function(){
        checks++;
        if(typeof cytoscape!=='undefined'){
            clearInterval(checkInterval);
            attemptInit();
        }else if(checks>=6){
            clearInterval(checkInterval);
            if(!initAttempted){
                initAttempted=true;
                document.getElementById('loading-indicator').style.display='none';
                var statusEl=document.getElementById('render-status');
                statusEl.style.display='block';
                statusEl.innerHTML='⚠️ Cytoscape.js CDN加载失败，请检查网络连接后刷新页面';
            }
        }
    },500);
});
</script>
</body>
</html>'''

        with open(output_path, 'w', encoding='utf-8') as f:
            canonical_path_val = graph.canonical_path or ''
            alternate_paths_val = json.dumps(graph.alternate_paths or [], ensure_ascii=False)
            # Fix 10: Safe JSON injection via script tag
            final_html = html_content.replace('__GRAPH_DATA__', graph_json_str).replace('__COLORS_JSON__', colors_json).replace('__SHAPES_JSON__', shapes_json).replace('__CANONICAL_PATH__', canonical_path_val).replace('__ALTERNATE_PATHS__', alternate_paths_val)
            f.write(final_html)

    def _reconstruct_path(self, path_edges: List) -> List[str]:
        if not path_edges:
            return []
        from_nodes = {edge.from_ for edge in path_edges}
        to_nodes = {edge.to for edge in path_edges}
        start_nodes = from_nodes - to_nodes
        if not start_nodes:
            return [path_edges[0].from_, path_edges[0].to]
        start_node = next(iter(start_nodes))
        path = [start_node]
        current = start_node
        while True:
            next_edges = [e for e in path_edges if e.from_ == current]
            if not next_edges:
                break
            next_edge = next_edges[0]
            path.append(next_edge.to)
            current = next_edge.to
        return path

    def _extract_assumption_coverage(self, verification_output: Optional[Dict[str, Any]]) -> float:
        if not verification_output or 'validation_results' not in verification_output:
            return 0.0
        validation_results = verification_output['validation_results']
        if 'assumptions' in validation_results and 'details' in validation_results['assumptions']:
            details = validation_results['assumptions']['details']
            if 'topic_coverage' in details and 'assumption_coverage' in details['topic_coverage']:
                return details['topic_coverage']['assumption_coverage']
        return 0.0

    def _extract_dimension_pass_rate(self, verification_output: Optional[Dict[str, Any]]) -> float:
        if not verification_output or 'validation_results' not in verification_output:
            return 0.0
        validation_results = verification_output['validation_results']
        if 'dimensions' in validation_results:
            return 1.0 if validation_results['dimensions'].get('passed', False) else 0.0
        return 0.0

    def _count_edges_with_assumptions(self, graph: KnowledgeGraph) -> int:
        count = 0
        for edge in graph.edges:
            if edge.type == "derives_from" and edge.assumptions:
                count += 1
        return count

    def _average_derivation_steps(self, graph: KnowledgeGraph) -> float:
        derive_edges = [e for e in graph.edges if e.type == "derives_from"]
        if not derive_edges:
            return 0.0
        total_steps = sum(len(e.derivation_steps) for e in derive_edges if e.derivation_steps)
        return total_steps / len(derive_edges)

    def _count_math_tool_usage(self, graph: KnowledgeGraph) -> int:
        count = 0
        for edge in graph.edges:
            if edge.math_used:
                count += len(edge.math_used)
        return count
