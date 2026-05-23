"""
数据加载器

负责加载种子数据、配置文件和schema。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml

from .models import Node, Edge, KnowledgeGraph


def _find_project_root() -> Path:
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "data").is_dir() and (parent / "configs").is_dir():
            return parent
        if (parent / "src").is_dir() and (parent / "data").is_dir():
            return parent
    return current.parent


class DataLoader:

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            self.base_dir = _find_project_root()
        else:
            self.base_dir = Path(base_dir)

        self.configs_dir = self.base_dir / "configs"
        self.data_dir = self.base_dir / "data"
        self.schemas_dir = self.base_dir / "schemas"
        self.seeds_dir = self.data_dir / "seeds"

        for dir_path in [self.configs_dir, self.data_dir, self.schemas_dir, self.seeds_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        self._seeds_cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._aliases_cache: Optional[Dict[str, List[str]]] = None

    def load_yaml(self, file_path: Union[str, Path]) -> Any:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def load_json(self, file_path: Union[str, Path]) -> Any:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_schema(self, schema_name: str) -> Dict[str, Any]:
        schema_file = self.schemas_dir / f"{schema_name}.schema.json"
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema文件不存在: {schema_file}")
        return self.load_json(schema_file)

    def load_config(self, config_name: str) -> Any:
        config_file = self.configs_dir / f"{config_name}.yaml"
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
        return self.load_yaml(config_file)

    def load_domain_rules(self, domain: str) -> Dict[str, Any]:
        rules_file = self.configs_dir / "domain_rules" / f"{domain}.yaml"
        if not rules_file.exists():
            raise FileNotFoundError(f"学科域规则文件不存在: {rules_file}")
        return self.load_yaml(rules_file)

    def load_aliases(self) -> Dict[str, List[str]]:
        if self._aliases_cache is not None:
            return self._aliases_cache
        aliases_file = self.data_dir / "aliases.yaml"
        if not aliases_file.exists():
            self._aliases_cache = {}
            return self._aliases_cache
        data = self.load_yaml(aliases_file)
        self._aliases_cache = data.get("aliases", {})
        return self._aliases_cache

    def load_benchmark_topics(self) -> List[Dict[str, Any]]:
        benchmark_file = self.data_dir / "benchmark_topics.yaml"
        if not benchmark_file.exists():
            return []
        data = self.load_yaml(benchmark_file)
        return data.get("topics", [])

    def load_seed_file(self, domain: str) -> Dict[str, Any]:
        seed_file = self.seeds_dir / f"{domain}.yaml"
        if not seed_file.exists():
            raise FileNotFoundError(f"种子文件不存在: {seed_file}")
        return self.load_yaml(seed_file)

    def load_all_seeds(self) -> Dict[str, Dict[str, Any]]:
        if self._seeds_cache is not None:
            return self._seeds_cache
        seeds = {}
        for seed_file in self.seeds_dir.glob("*.yaml"):
            domain = seed_file.stem
            try:
                seeds[domain] = self.load_seed_file(domain)
            except Exception as e:
                print(f"警告: 加载种子文件 {seed_file} 失败: {e}")
        self._seeds_cache = seeds
        return self._seeds_cache

    def invalidate_cache(self):
        self._seeds_cache = None
        self._aliases_cache = None

    def parse_nodes_from_seed(self, seed_data: Dict[str, Any]) -> List[Node]:
        nodes = []
        for node_data in seed_data.get("nodes", []):
            try:
                nodes.append(Node(**node_data))
            except Exception as e:
                print(f"警告: 解析节点失败: {node_data.get('id', 'unknown')}, 错误: {e}")
        return nodes

    def parse_edges_from_seed(self, seed_data: Dict[str, Any]) -> List[Edge]:
        edges = []
        for edge_data in seed_data.get("edges", []):
            try:
                edges.append(Edge(**edge_data))
            except Exception as e:
                print(f"警告: 解析边失败: {edge_data.get('id', 'unknown')}, 错误: {e}")
        return edges

    def get_node_by_id(self, node_id: str, seeds: Optional[Dict[str, Dict[str, Any]]] = None) -> Optional[Node]:
        if seeds is None:
            seeds = self.load_all_seeds()
        for domain_data in seeds.values():
            for node_data in domain_data.get("nodes", []):
                if node_data.get("id") == node_id:
                    try:
                        return Node(**node_data)
                    except Exception:
                        return None
        return None

    def get_edge_by_id(self, edge_id: str, seeds: Optional[Dict[str, Dict[str, Any]]] = None) -> Optional[Edge]:
        if seeds is None:
            seeds = self.load_all_seeds()
        for domain_data in seeds.values():
            for edge_data in domain_data.get("edges", []):
                if edge_data.get("id") == edge_id:
                    try:
                        return Edge(**edge_data)
                    except Exception:
                        return None
        return None

    def search_nodes_by_pattern(self, pattern: str, seeds: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Node]:
        if seeds is None:
            seeds = self.load_all_seeds()
        results = []
        for domain_data in seeds.values():
            for node_data in domain_data.get("nodes", []):
                node_id = node_data.get("id", "")
                if pattern in node_id:
                    try:
                        results.append(Node(**node_data))
                    except Exception:
                        pass
        return results

    def get_domain_seeds(self, domain: str) -> Dict[str, Any]:
        seed_data = self.load_seed_file(domain)
        nodes = self.parse_nodes_from_seed(seed_data)
        edges = self.parse_edges_from_seed(seed_data)
        return {
            "domain": domain,
            "version": seed_data.get("version", "1.0.0"),
            "nodes": nodes,
            "edges": edges,
            "raw_data": seed_data
        }


_default_loader: Optional[DataLoader] = None


def get_loader() -> DataLoader:
    global _default_loader
    if _default_loader is None:
        _default_loader = DataLoader()
    return _default_loader
