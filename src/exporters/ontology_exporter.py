"""
知识图谱标准格式导出器
支持：OWL (Web Ontology Language), RDF (Turtle格式), JSON-LD
"""

import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Optional
from pathlib import Path

from ..models import KnowledgeGraph, Node, Edge, NodeType


BASE_URI = "http://physics-graph.org/ontology"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
OWL_NS = "http://www.w3.org/2002/07/owl#"
XSD_NS = "http://www.w3.org/2001/XMLSchema#"
PG_NS = f"{BASE_URI}/"


NODE_TYPE_MAP = {
    NodeType.CONCEPT: "Concept",
    NodeType.QUANTITY: "Quantity",
    NodeType.DEFINITION: "Definition",
    NodeType.LAW: "Law",
    NodeType.EQUATION: "Equation",
    NodeType.MODEL: "Model",
    NodeType.ASSUMPTION: "Assumption",
    NodeType.MATH_TOOL: "MathTool",
    NodeType.APPLICATION: "Application",
    NodeType.EXPERIMENT: "Experiment",
    NodeType.WARNING: "Warning",
    NodeType.INTUITION_CARD: "IntuitionCard",
}

EDGE_TYPE_MAP = {
    "derives_from": "derivesFrom",
    "requires": "requires",
    "uses_math": "usesMath",
    "assumes": "assumes",
    "equivalent_to": "equivalentTo",
    "generalizes": "generalizes",
    "specializes": "specializes",
    "contradicts": "contradicts",
    "approximates": "approximates",
    "limits": "limits",
}


class OntologyExporter:
    """知识图谱本体导出器"""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
        self.topic = graph.topic

    def export_owl_xml(self, output_path: Optional[str] = None) -> str:
        """导出OWL XML格式"""
        root = ET.Element("Ontology", xmlns=OWL_NS)
        root.set(f"{{{RDF_NS}}}about", f"{BASE_URI}/{self.topic}")

        prefix_elem = ET.SubElement(root, "Prefix")
        prefix_elem.set("name", "pg")
        prefix_elem.set("IRI", f"{BASE_URI}/")

        prefix_elem2 = ET.SubElement(root, "Prefix")
        prefix_elem2.set("name", "rdf")
        prefix_elem2.set("IRI", RDF_NS)

        prefix_elem3 = ET.SubElement(root, "Prefix")
        prefix_elem3.set("name", "rdfs")
        prefix_elem3.set("IRI", RDFS_NS)

        # 声明类
        for nt in NodeType:
            class_elem = ET.SubElement(root, f"{{{OWL_NS}}}Class")
            class_elem.set(f"{{{RDF_NS}}}about", f"{BASE_URI}/{NODE_TYPE_MAP.get(nt, 'Entity')}")
            label = ET.SubElement(class_elem, f"{{{RDFS_NS}}}label")
            label.text = NODE_TYPE_MAP.get(nt, "Entity")

        # 声明对象属性
        for edge_type, prop_name in EDGE_TYPE_MAP.items():
            prop_elem = ET.SubElement(root, f"{{{OWL_NS}}}ObjectProperty")
            prop_elem.set(f"{{{RDF_NS}}}about", f"{BASE_URI}/{prop_name}")
            label = ET.SubElement(prop_elem, f"{{{RDFS_NS}}}label")
            label.text = prop_name

        # 声明数据属性
        data_props = ["hasTitle", "hasStatement", "hasFormulaLatex", "hasDomain",
                       "hasAbstractionLevel", "hasPedagogicalLevel", "hasTheoryContext"]
        for dp in data_props:
            dp_elem = ET.SubElement(root, f"{{{OWL_NS}}}DatatypeProperty")
            dp_elem.set(f"{{{RDF_NS}}}about", f"{BASE_URI}/{dp}")
            label = ET.SubElement(dp_elem, f"{{{RDFS_NS}}}label")
            label.text = dp

        # 添加节点个体
        for node in self.graph.nodes:
            ind_elem = ET.SubElement(root, f"{{{OWL_NS}}}NamedIndividual")
            ind_elem.set(f"{{{RDF_NS}}}about", f"{BASE_URI}/node/{node.id}")

            type_elem = ET.SubElement(ind_elem, f"{{{RDF_NS}}}type")
            type_elem.set(f"{{{RDF_NS}}}resource",
                          f"{BASE_URI}/{NODE_TYPE_MAP.get(node.type, 'Entity')}")

            if node.title:
                title_elem = ET.SubElement(ind_elem, f"{{{BASE_URI}/}}hasTitle")
                title_elem.set(f"{{{RDF_NS}}}datatype", f"{{{XSD_NS}}}string")
                title_elem.text = node.title

            if node.statement:
                stmt_elem = ET.SubElement(ind_elem, f"{{{BASE_URI}/}}hasStatement")
                stmt_elem.set(f"{{{RDF_NS}}}datatype", f"{{{XSD_NS}}}string")
                stmt_elem.text = node.statement

            if node.formula_latex and node.formula_latex != "N/A":
                formula_elem = ET.SubElement(ind_elem, f"{{{BASE_URI}/}}hasFormulaLatex")
                formula_elem.set(f"{{{RDF_NS}}}datatype", f"{{{XSD_NS}}}string")
                formula_elem.text = node.formula_latex

            if node.domain:
                domain_elem = ET.SubElement(ind_elem, f"{{{BASE_URI}/}}hasDomain")
                domain_elem.set(f"{{{RDF_NS}}}datatype", f"{{{XSD_NS}}}string")
                domain_elem.text = str(node.domain.value) if hasattr(node.domain, 'value') else str(node.domain)

            level_elem = ET.SubElement(ind_elem, f"{{{BASE_URI}/}}hasAbstractionLevel")
            level_elem.set(f"{{{RDF_NS}}}datatype", f"{{{XSD_NS}}}integer")
            level_elem.text = str(node.abstraction_level)

        # 添加边（关系）
        for edge in self.graph.edges:
            from_uri = f"{BASE_URI}/node/{edge.from_}"
            to_uri = f"{BASE_URI}/node/{edge.to}"
            prop_name = EDGE_TYPE_MAP.get(edge.type, "relatedTo")

            # 创建关系断言
            rel_elem = ET.SubElement(root, f"{{{BASE_URI}/}}{prop_name}")
            rel_elem.set(f"{{{RDF_NS}}}about", from_uri)
            rel_elem.set(f"{{{RDF_NS}}}resource", to_uri)

        xml_str = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")

        if output_path:
            Path(output_path).write_text(xml_str, encoding="utf-8")

        return xml_str

    def export_rdf_turtle(self, output_path: Optional[str] = None) -> str:
        """导出RDF Turtle格式"""
        lines = [
            f"@prefix pg: <{BASE_URI}/> .",
            f"@prefix rdf: <{RDF_NS}> .",
            f"@prefix rdfs: <{RDFS_NS}> .",
            f"@prefix owl: <{OWL_NS}> .",
            f"@prefix xsd: <{XSD_NS}> .",
            "",
            f"pg:{self.topic} a owl:Ontology ;",
            f'    rdfs:label "Physics Knowledge Graph: {self.topic}" ;',
            f'    rdfs:comment "Auto-generated physics knowledge graph ontology" .',
            "",
        ]

        # 类声明
        for nt in NodeType:
            cls_name = NODE_TYPE_MAP.get(nt, "Entity")
            lines.append(f"pg:{cls_name} a owl:Class ;")
            lines.append(f'    rdfs:label "{cls_name}" .')
            lines.append("")

        # 对象属性
        for edge_type, prop_name in EDGE_TYPE_MAP.items():
            lines.append(f"pg:{prop_name} a owl:ObjectProperty ;")
            lines.append(f'    rdfs:label "{prop_name}" .')
            lines.append("")

        # 数据属性
        for dp in ["hasTitle", "hasStatement", "hasFormulaLatex", "hasDomain",
                    "hasAbstractionLevel"]:
            lines.append(f"pg:{dp} a owl:DatatypeProperty ;")
            lines.append(f'    rdfs:label "{dp}" .')
            lines.append("")

        # 节点个体
        for node in self.graph.nodes:
            safe_id = node.id.replace(".", "_")
            cls_name = NODE_TYPE_MAP.get(node.type, "Entity")
            lines.append(f"pg:{safe_id} a pg:{cls_name} ;")

            props = []
            if node.title:
                props.append(f'    pg:hasTitle "{_escape_turtle(node.title)}"^^xsd:string')
            if node.statement:
                props.append(f'    pg:hasStatement "{_escape_turtle(node.statement[:500])}"^^xsd:string')
            if node.formula_latex and node.formula_latex != "N/A":
                props.append(f'    pg:hasFormulaLatex "{_escape_turtle(node.formula_latex)}"^^xsd:string')
            if node.domain:
                dv = str(node.domain.value) if hasattr(node.domain, 'value') else str(node.domain)
                props.append(f'    pg:hasDomain "{dv}"^^xsd:string')
            props.append(f'    pg:hasAbstractionLevel "{node.abstraction_level}"^^xsd:integer')

            for i, prop in enumerate(props):
                if i < len(props) - 1:
                    lines.append(prop + " ;")
                else:
                    lines.append(prop + " .")
            lines.append("")

        # 边关系
        for edge in self.graph.edges:
            from_id = edge.from_.replace(".", "_")
            to_id = edge.to.replace(".", "_")
            prop_name = EDGE_TYPE_MAP.get(edge.type, "relatedTo")
            lines.append(f"pg:{from_id} pg:{prop_name} pg:{to_id} .")

        turtle_str = "\n".join(lines)

        if output_path:
            Path(output_path).write_text(turtle_str, encoding="utf-8")

        return turtle_str

    def export_jsonld(self, output_path: Optional[str] = None) -> str:
        """导出JSON-LD格式"""
        context = {
            "pg": BASE_URI + "/",
            "rdf": RDF_NS,
            "rdfs": RDFS_NS,
            "owl": OWL_NS,
            "xsd": XSD_NS,
            "title": "pg:hasTitle",
            "statement": "pg:hasStatement",
            "formulaLatex": "pg:hasFormulaLatex",
            "domain": "pg:hasDomain",
            "abstractionLevel": {"@id": "pg:hasAbstractionLevel", "@type": "xsd:integer"},
            "pedagogicalLevel": {"@id": "pg:hasPedagogicalLevel", "@type": "xsd:integer"},
            "theoryContext": "pg:hasTheoryContext",
            "derivesFrom": {"@id": "pg:derivesFrom", "@type": "@id"},
            "requires": {"@id": "pg:requires", "@type": "@id"},
            "usesMath": {"@id": "pg:usesMath", "@type": "@id"},
            "assumes": {"@id": "pg:assumes", "@type": "@id"},
        }

        nodes_jsonld = []
        for node in self.graph.nodes:
            node_dict = {
                "@id": f"pg:node/{node.id}",
                "@type": f"pg:{NODE_TYPE_MAP.get(node.type, 'Entity')}",
                "title": node.title or "",
                "abstractionLevel": node.abstraction_level,
            }
            if node.statement:
                node_dict["statement"] = node.statement
            if node.formula_latex and node.formula_latex != "N/A":
                node_dict["formulaLatex"] = node.formula_latex
            if node.domain:
                dv = str(node.domain.value) if hasattr(node.domain, 'value') else str(node.domain)
                node_dict["domain"] = dv
            if node.theory_context:
                tc = str(node.theory_context.value) if hasattr(node.theory_context, 'value') else str(node.theory_context)
                node_dict["theoryContext"] = tc

            # 添加边关系
            for edge in self.graph.edges:
                if edge.from_ == node.id:
                    prop_name = EDGE_TYPE_MAP.get(edge.type, "relatedTo")
                    camel_prop = prop_name[0].lower() + prop_name[1:]
                    if camel_prop in context:
                        if camel_prop not in node_dict:
                            node_dict[camel_prop] = []
                        node_dict[camel_prop].append(f"pg:node/{edge.to}")

            nodes_jsonld.append(node_dict)

        jsonld = {
            "@context": context,
            "@graph": [
                {
                    "@id": f"pg:{self.topic}",
                    "@type": "owl:Ontology",
                    "rdfs:label": f"Physics Knowledge Graph: {self.topic}",
                }
            ] + nodes_jsonld
        }

        jsonld_str = json.dumps(jsonld, ensure_ascii=False, indent=2)

        if output_path:
            Path(output_path).write_text(jsonld_str, encoding="utf-8")

        return jsonld_str

    def export_all(self, output_dir: str):
        """导出所有格式"""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        self.export_owl_xml(str(out / f"{self.topic}.owl.xml"))
        self.export_rdf_turtle(str(out / f"{self.topic}.ttl"))
        self.export_jsonld(str(out / f"{self.topic}.jsonld"))

        print(f"[导出完成] OWL/RDF/JSON-LD 已保存到 {output_dir}/")


def _escape_turtle(text: str) -> str:
    """转义Turtle格式中的特殊字符"""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
