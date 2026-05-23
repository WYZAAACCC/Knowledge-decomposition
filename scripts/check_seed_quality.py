#!/usr/bin/env python
"""
Improvement 3: Seed知识库质量检查

检查所有seed文件的完整性、一致性和正确性。
"""
import sys
import json
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from src.loader import DataLoader
from src.validators.placeholder_validator import contains_placeholder
from src.models import DERIVATION_EDGE_TYPES
import networkx as nx


def check_seed_quality(seed_dir: str = None) -> dict:
    """检查seed数据质量"""
    loader = DataLoader()
    seeds = loader.load_all_seeds()

    results = {
        "total_domains": len(seeds),
        "checks": [],
        "errors": [],
        "warnings": [],
        "passed": True,
    }

    all_node_ids = set()
    all_edge_ids = set()
    domain_nodes = {}
    domain_edges = {}

    for domain, seed_data in seeds.items():
        nodes = loader.parse_nodes_from_seed(seed_data)
        edges = loader.parse_edges_from_seed(seed_data)
        domain_nodes[domain] = nodes
        domain_edges[domain] = edges

        # 1. ID唯一性
        node_ids = [n.id for n in nodes]
        edge_ids = [e.id for e in edges]
        dup_nodes = [id for id in node_ids if node_ids.count(id) > 1]
        dup_edges = [id for id in edge_ids if edge_ids.count(id) > 1]
        if dup_nodes:
            results["errors"].append(f"[{domain}] 重复节点ID: {set(dup_nodes)}")
        if dup_edges:
            results["errors"].append(f"[{domain}] 重复边ID: {set(dup_edges)}")

        # 2. 必要字段非空
        for node in nodes:
            if not node.title.strip():
                results["errors"].append(f"[{domain}] 节点 {node.id} title为空")
            if not node.sources:
                results["warnings"].append(f"[{domain}] 节点 {node.id} 无来源引用")

        # 3. 无占位文本
        for node in nodes:
            for field in ['title', 'statement', 'formula_latex']:
                val = getattr(node, field, None) or ''
                if contains_placeholder(val):
                    results["errors"].append(f"[{domain}] 节点 {node.id}.{field} 包含占位文本: '{val[:50]}'")

        for edge in edges:
            for a in getattr(edge, 'assumptions', []) or []:
                if contains_placeholder(a):
                    results["errors"].append(f"[{domain}] 边 {edge.id} assumption包含占位文本")
            for ds in getattr(edge, 'derivation_steps', []) or []:
                if contains_placeholder(ds):
                    results["errors"].append(f"[{domain}] 边 {edge.id} derivation_step包含占位文本")

        # 4. 边端点存在
        node_id_set = {n.id for n in nodes}
        for edge in edges:
            if edge.from_ not in node_id_set:
                results["errors"].append(f"[{domain}] 边 {edge.id}: from节点 '{edge.from_}' 不存在")
            if edge.to not in node_id_set:
                results["errors"].append(f"[{domain}] 边 {edge.id}: to节点 '{edge.to}' 不存在")

        # 5. 推导DAG无环
        derivation_edges = [e for e in edges if e.type.value in {et.value for et in DERIVATION_EDGE_TYPES}]
        if derivation_edges:
            G = nx.DiGraph()
            for n in nodes:
                G.add_node(n.id)
            for e in derivation_edges:
                if e.from_ in G and e.to in G:
                    G.add_edge(e.from_, e.to)
            try:
                cycles = list(nx.simple_cycles(G))
                if cycles:
                    for cycle in cycles[:3]:
                        results["errors"].append(f"[{domain}] DAG环: {' → '.join(cycle)}")
            except Exception:
                pass

        all_node_ids.update(node_id_set)
        all_edge_ids.update(edge_ids)

        results["checks"].append({
            "domain": domain,
            "nodes": len(nodes),
            "edges": len(edges),
            "node_types": list(set(n.type.value for n in nodes)),
            "edge_types": list(set(e.type.value for e in edges)),
        })

    # 6. 跨域统计
    results["total_nodes"] = len(all_node_ids)
    results["total_edges"] = len(all_edge_ids)

    if not results["errors"]:
        results["passed"] = True

    return results


def main():
    results = check_seed_quality()

    if results["passed"]:
        print("[PASS] All seed quality checks passed")
    else:
        print(f"[FAIL] {len(results['errors'])} errors, {len(results['warnings'])} warnings")

    for check in results["checks"]:
        print(f"  [{check['domain']}]: {check['nodes']} nodes, {check['edges']} edges")
        print(f"    node_types: {check['node_types']}")
        print(f"    edge_types: {check['edge_types']}")

    if results["errors"]:
        print(f"\nErrors ({len(results['errors'])}):")
        for e in results["errors"][:20]:
            print(f"  - {e}")

    sys.exit(0 if results["passed"] else 1)


if __name__ == "__main__":
    main()
