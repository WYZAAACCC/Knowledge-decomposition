"""
OWL/RDF/JSON-LD本体格式导出验证测试
=====================================
验证导出文件的格式正确性、内容完整性和与其他知识图谱工具的互通性
"""

import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import dotenv
dotenv.load_dotenv(project_root / ".env")

from src.orchestrator import GraphBuildOrchestrator
from src.exporters.ontology_exporter import OntologyExporter
from src.models import KnowledgeGraph, NodeType


@dataclass
class ExportTestResult:
    test_name: str
    passed: bool
    details: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class OntologyExportValidator:
    """本体导出验证器"""

    def __init__(self):
        self.results: List[ExportTestResult] = []

    def validate_owl_xml(self, owl_content: str, graph: KnowledgeGraph) -> ExportTestResult:
        """验证OWL XML格式"""
        result = ExportTestResult(test_name="OWL_XML格式验证", passed=True)

        try:
            root = ET.fromstring(owl_content)
            result.details.append("XML解析成功")

            has_ontology = False
            has_classes = False
            has_properties = False
            has_individuals = False

            for elem in root.iter():
                tag = elem.tag
                if "Ontology" in tag:
                    has_ontology = True
                if "Class" in tag:
                    has_classes = True
                if "ObjectProperty" in tag or "DatatypeProperty" in tag:
                    has_properties = True
                if "NamedIndividual" in tag:
                    has_individuals = True

            if not has_ontology:
                result.errors.append("缺少Ontology声明")
                result.passed = False
            else:
                result.details.append("包含Ontology声明")

            if not has_classes:
                result.errors.append("缺少Class声明")
                result.passed = False
            else:
                result.details.append("包含Class声明")

            if not has_properties:
                result.errors.append("缺少Property声明")
                result.passed = False
            else:
                result.details.append("包含Property声明")

            if not has_individuals:
                result.errors.append("缺少NamedIndividual声明")
                result.passed = False
            else:
                result.details.append("包含NamedIndividual声明")

            individual_count = sum(1 for _ in root.iter() if "NamedIndividual" in _.tag)
            if individual_count != len(graph.nodes):
                result.errors.append(
                    f"个体数量不匹配: XML中{individual_count}个 vs 图谱中{len(graph.nodes)}个"
                )
                result.passed = False
            else:
                result.details.append(f"个体数量匹配: {individual_count}个")

            RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
            node_types_in_xml = set()
            for elem in root.iter():
                if "NamedIndividual" in elem.tag:
                    for child in elem:
                        if "type" in child.tag:
                            type_uri = child.get(f"{{{RDF_NS}}}resource", "")
                            if not type_uri:
                                for attr_name, attr_val in child.attrib.items():
                                    if attr_name.endswith("}resource") or attr_name == "resource":
                                        type_uri = attr_val
                                        break
                            if type_uri:
                                type_name = type_uri.split("/")[-1]
                                node_types_in_xml.add(type_name)

            if node_types_in_xml:
                result.details.append(f"包含节点类型: {', '.join(sorted(node_types_in_xml))}")
            else:
                result.errors.append("未找到节点类型声明")
                result.passed = False

        except ET.ParseError as e:
            result.errors.append(f"XML解析失败: {e}")
            result.passed = False
        except Exception as e:
            result.errors.append(f"验证异常: {e}")
            result.passed = False

        self.results.append(result)
        return result

    def validate_rdf_turtle(self, turtle_content: str, graph: KnowledgeGraph) -> ExportTestResult:
        """验证RDF Turtle格式"""
        result = ExportTestResult(test_name="RDF_Turtle格式验证", passed=True)

        try:
            lines = turtle_content.strip().split("\n")
            result.details.append(f"Turtle内容共{len(lines)}行")

            has_prefix = any("@prefix" in line for line in lines)
            if not has_prefix:
                result.errors.append("缺少@prefix声明")
                result.passed = False
            else:
                prefix_count = sum(1 for line in lines if "@prefix" in line)
                result.details.append(f"包含{prefix_count}个@prefix声明")

            has_ontology = any("owl:Ontology" in line for line in lines)
            if not has_ontology:
                result.errors.append("缺少owl:Ontology声明")
                result.passed = False
            else:
                result.details.append("包含owl:Ontology声明")

            has_class = any("owl:Class" in line for line in lines)
            if not has_class:
                result.errors.append("缺少owl:Class声明")
                result.passed = False
            else:
                result.details.append("包含owl:Class声明")

            has_object_property = any("owl:ObjectProperty" in line for line in lines)
            if not has_object_property:
                result.errors.append("缺少owl:ObjectProperty声明")
                result.passed = False
            else:
                result.details.append("包含owl:ObjectProperty声明")

            individual_lines = [l for l in lines if " a pg:" in l and "owl:" not in l]
            if len(individual_lines) < len(graph.nodes):
                result.errors.append(
                    f"个体声明不足: 找到{len(individual_lines)}行 vs 图谱{len(graph.nodes)}节点"
                )
                result.passed = False
            else:
                result.details.append(f"个体声明充足: {len(individual_lines)}行")

            edge_triple_count = 0
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("@") and not stripped.startswith("#"):
                    if " pg:derivesFrom " in stripped or " pg:requires " in stripped or \
                       " pg:usesMath " in stripped or " pg:assumes " in stripped:
                        edge_triple_count += 1

            if edge_triple_count == 0:
                result.errors.append("未找到任何边关系三元组")
                result.passed = False
            else:
                result.details.append(f"找到{edge_triple_count}个边关系三元组")

            for line in lines:
                if " a pg:" in line and "owl:" not in line:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        node_id = parts[0]
                        if ":" not in node_id and not node_id.startswith("pg:"):
                            result.errors.append(f"无效的节点ID格式: {node_id}")
                            result.passed = False
                            break

        except Exception as e:
            result.errors.append(f"验证异常: {e}")
            result.passed = False

        self.results.append(result)
        return result

    def validate_jsonld(self, jsonld_content: str, graph: KnowledgeGraph) -> ExportTestResult:
        """验证JSON-LD格式"""
        result = ExportTestResult(test_name="JSON-LD格式验证", passed=True)

        try:
            data = json.loads(jsonld_content)
            result.details.append("JSON解析成功")

            if "@context" not in data:
                result.errors.append("缺少@context")
                result.passed = False
            else:
                ctx = data["@context"]
                required_prefixes = ["pg", "rdf", "rdfs", "owl", "xsd"]
                for prefix in required_prefixes:
                    if prefix not in ctx:
                        result.errors.append(f"@context缺少{prefix}前缀")
                        result.passed = False
                    else:
                        result.details.append(f"@context包含{prefix}前缀")

                required_props = ["derivesFrom", "requires", "usesMath", "assumes"]
                for prop in required_props:
                    if prop not in ctx:
                        result.errors.append(f"@context缺少{prop}属性映射")
                        result.passed = False

            if "@graph" not in data:
                result.errors.append("缺少@graph")
                result.passed = False
            else:
                graph_items = data["@graph"]
                result.details.append(f"@graph包含{len(graph_items)}个元素")

                ontology_item = None
                node_items = []
                for item in graph_items:
                    if item.get("@type") == "owl:Ontology":
                        ontology_item = item
                    elif "@id" in item and "node/" in item.get("@id", ""):
                        node_items.append(item)

                if not ontology_item:
                    result.errors.append("@graph中缺少owl:Ontology声明")
                    result.passed = False
                else:
                    result.details.append("@graph包含owl:Ontology声明")

                if len(node_items) != len(graph.nodes):
                    result.errors.append(
                        f"节点数量不匹配: JSON-LD中{len(node_items)}个 vs 图谱中{len(graph.nodes)}个"
                    )
                    result.passed = False
                else:
                    result.details.append(f"节点数量匹配: {len(node_items)}个")

                for item in node_items:
                    if "@id" not in item:
                        result.errors.append(f"节点缺少@id: {item}")
                        result.passed = False
                        break
                    if "@type" not in item:
                        result.errors.append(f"节点缺少@type: {item.get('@id', '?')}")
                        result.passed = False
                        break
                    if "title" not in item:
                        result.errors.append(f"节点缺少title: {item.get('@id', '?')}")
                        result.passed = False
                        break
                    if "abstractionLevel" not in item:
                        result.errors.append(f"节点缺少abstractionLevel: {item.get('@id', '?')}")
                        result.passed = False
                        break

                has_relations = False
                for item in node_items:
                    for key in ["derivesFrom", "requires", "usesMath", "assumes"]:
                        if key in item:
                            has_relations = True
                            break
                    if has_relations:
                        break

                if not has_relations:
                    result.errors.append("节点中未找到任何关系属性")
                    result.passed = False
                else:
                    result.details.append("节点包含关系属性")

        except json.JSONDecodeError as e:
            result.errors.append(f"JSON解析失败: {e}")
            result.passed = False
        except Exception as e:
            result.errors.append(f"验证异常: {e}")
            result.passed = False

        self.results.append(result)
        return result

    def validate_interoperability(self, owl_content: str, turtle_content: str,
                                  jsonld_content: str, graph: KnowledgeGraph) -> ExportTestResult:
        """验证三种格式之间的数据一致性（互通性验证）"""
        result = ExportTestResult(test_name="格式间互通性验证", passed=True)

        try:
            owl_root = ET.fromstring(owl_content)
            RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
            owl_individuals = set()
            for elem in owl_root.iter():
                if "NamedIndividual" in elem.tag:
                    about = elem.get(f"{{{RDF_NS}}}about", "")
                    if not about:
                        for attr_name, attr_val in elem.attrib.items():
                            if attr_name.endswith("}about") or attr_name == "about":
                                about = attr_val
                                break
                    if about and "/node/" in about:
                        node_id = about.split("/node/")[-1]
                        owl_individuals.add(node_id)

            jsonld_data = json.loads(jsonld_content)
            jsonld_ids = set()
            for item in jsonld_data.get("@graph", []):
                item_id = item.get("@id", "")
                if "node/" in item_id:
                    node_id = item_id.split("node/")[-1]
                    jsonld_ids.add(node_id)

            if owl_individuals != jsonld_ids:
                only_owl = owl_individuals - jsonld_ids
                only_jsonld = jsonld_ids - owl_individuals
                if only_owl:
                    result.errors.append(f"OWL有但JSON-LD没有的节点: {only_owl}")
                if only_jsonld:
                    result.errors.append(f"JSON-LD有但OWL没有的节点: {only_jsonld}")
                result.passed = False
            else:
                result.details.append(f"OWL与JSON-LD节点集合一致({len(owl_individuals)}个)")

            graph_node_ids = {n.id for n in graph.nodes}
            if owl_individuals != graph_node_ids:
                only_graph = graph_node_ids - owl_individuals
                only_owl = owl_individuals - graph_node_ids
                if only_graph:
                    result.errors.append(f"图谱有但OWL没有的节点: {only_graph}")
                if only_owl:
                    result.errors.append(f"OWL有但图谱没有的节点: {only_owl}")
                result.passed = False
            else:
                result.details.append(f"导出节点与图谱节点完全一致({len(graph_node_ids)}个)")

        except Exception as e:
            result.errors.append(f"互通性验证异常: {e}")
            result.passed = False

        self.results.append(result)
        return result

    def print_summary(self):
        """打印汇总"""
        print("\n" + "=" * 70)
        print("📋 OWL/RDF/JSON-LD导出验证报告")
        print("=" * 70)

        for r in self.results:
            icon = "✅" if r.passed else "❌"
            print(f"\n{icon} {r.test_name}")
            for d in r.details:
                print(f"   ✓ {d}")
            for e in r.errors:
                print(f"   ✗ {e}")

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        print(f"\n{'='*70}")
        print(f"总计: {passed}/{total} 通过 ({100*passed/max(total,1):.0f}%)")

        return all(r.passed for r in self.results)


def run_export_test(topic: str = "牛顿第二定律", down: int = 3, up: int = 2, max_nodes: int = 30):
    """运行完整的导出验证测试"""
    print("=" * 70)
    print(f"🧪 OWL/RDF/JSON-LD导出验证测试")
    print(f"主题: {topic}")
    print("=" * 70)

    print("\n[1/3] 构建知识图谱...")
    orchestrator = GraphBuildOrchestrator(artifacts_dir="artifacts/latest")
    build_result = orchestrator.build_topic(topic, down=down, up=up, max_nodes=max_nodes)

    if not build_result.graph:
        print("❌ 图谱构建失败，无法测试导出")
        return False

    graph = build_result.graph
    print(f"  图谱构建成功: {len(graph.nodes)}节点, {len(graph.edges)}边")

    print("\n[2/3] 执行导出...")
    exporter = OntologyExporter(graph)
    output_dir = project_root / "artifacts" / "ontology_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        owl_content = exporter.export_owl_xml(str(output_dir / f"{graph.topic}.owl.xml"))
        print(f"  OWL XML导出成功 ({len(owl_content)}字符)")
    except Exception as e:
        print(f"  ❌ OWL XML导出失败: {e}")
        owl_content = ""

    try:
        turtle_content = exporter.export_rdf_turtle(str(output_dir / f"{graph.topic}.ttl"))
        print(f"  RDF Turtle导出成功 ({len(turtle_content)}字符)")
    except Exception as e:
        print(f"  ❌ RDF Turtle导出失败: {e}")
        turtle_content = ""

    try:
        jsonld_content = exporter.export_jsonld(str(output_dir / f"{graph.topic}.jsonld"))
        print(f"  JSON-LD导出成功 ({len(jsonld_content)}字符)")
    except Exception as e:
        print(f"  ❌ JSON-LD导出失败: {e}")
        jsonld_content = ""

    print("\n[3/3] 验证导出内容...")
    validator = OntologyExportValidator()

    if owl_content:
        validator.validate_owl_xml(owl_content, graph)
    if turtle_content:
        validator.validate_rdf_turtle(turtle_content, graph)
    if jsonld_content:
        validator.validate_jsonld(jsonld_content, graph)
    if owl_content and turtle_content and jsonld_content:
        validator.validate_interoperability(owl_content, turtle_content, jsonld_content, graph)

    all_passed = validator.print_summary()

    print(f"\n导出文件保存在: {output_dir}")
    for f in output_dir.iterdir():
        print(f"  - {f.name} ({f.stat().st_size} bytes)")

    return all_passed


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "牛顿第二定律"
    success = run_export_test(topic)
    sys.exit(0 if success else 1)
