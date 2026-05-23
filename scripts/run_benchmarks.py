#!/usr/bin/env python
"""
Improvement 11: Benchmark主题运行器

对预定义的benchmark主题进行构建和验证。
"""
import sys
import json
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.orchestrator import GraphBuildOrchestrator


BENCHMARK_TOPICS = [
    {
        "topic": "伯努利方程",
        "target_node_id": "equation.bernoulli",
        "domain": "mechanics",
        "must_pass": ["graph", "assumption", "dimension"],
    },
    {
        "topic": "牛顿第二定律",
        "target_node_id": "law.newton_second",
        "domain": "mechanics",
        "must_pass": ["graph", "assumption"],
    },
    {
        "topic": "欧姆定律",
        "target_node_id": "law.ohm",
        "domain": "electromagnetism",
        "must_pass": ["graph", "dimension"],
    },
    {
        "topic": "理想气体状态方程",
        "target_node_id": "equation.ideal_gas_law",
        "domain": "thermodynamics",
        "must_pass": ["graph", "assumption"],
    },
    {
        "topic": "库仑定律",
        "target_node_id": "law.coulomb",
        "domain": "electromagnetism",
        "must_pass": ["graph", "dimension"],
    },
    {
        "topic": "胡克定律",
        "target_node_id": "law.hooke",
        "domain": "mechanics",
        "must_pass": ["graph"],
    },
    {
        "topic": "动能定理",
        "target_node_id": "law.kinetic_energy_theorem",
        "domain": "mechanics",
        "must_pass": ["graph", "assumption"],
    },
    {
        "topic": "热力学第一定律",
        "target_node_id": "law.thermodynamics_first",
        "domain": "thermodynamics",
        "must_pass": ["graph", "assumption"],
    },
]


def run_benchmarks(offline: bool = True, strict: bool = True):
    results = []

    for spec in BENCHMARK_TOPICS:
        topic = spec["topic"]
        print(f"\n[Benchmark] {topic} ...")

        try:
            orch = GraphBuildOrchestrator(
                artifacts_dir=f"artifacts/benchmark_{spec['target_node_id']}",
                offline=offline,
                strict=strict,
                no_llm=True,
            )
            result = orch.build_topic(topic, down=3, up=1, max_nodes=30)

            checks = {
                "graph": bool(result.graph and len(result.graph.nodes) > 0),
                "dag": result.graph and all(
                    e.from_ != e.to for e in result.graph.edges
                ) if result.graph else False,
                "target_exists": any(
                    n.id == spec["target_node_id"]
                    for n in result.graph.nodes
                ) if result.graph else False,
            }

            mandatory = all(checks.get(p, False) for p in spec["must_pass"])

            results.append({
                "topic": topic,
                "status": result.status,
                "nodes": len(result.graph.nodes) if result.graph else 0,
                "edges": len(result.graph.edges) if result.graph else 0,
                "checks": checks,
                "mandatory_pass": mandatory,
                "passed": mandatory,
            })

            status = "PASS" if mandatory else "FAIL"
            print(f"  [{status}] nodes={checks.get('graph', 0)}, target_exists={checks.get('target_exists', False)}")

        except Exception as e:
            print(f"  [FAIL] Exception: {e}")
            results.append({
                "topic": topic, "status": "error", "error": str(e), "passed": False,
            })

    # 汇总
    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    print(f"\n{'='*60}")
    print(f"Benchmark Results: {passed}/{total} passed")

    for r in results:
        status = "PASS" if r.get("passed") else "FAIL"
        print(f"  [{status}] {r['topic']}: {r.get('status', 'error')}")

    return passed == total, results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="运行Benchmark主题测试")
    parser.add_argument("--offline", action="store_true", default=True)
    parser.add_argument("--strict", action="store_true", default=True)
    parser.add_argument("--output", default="artifacts/benchmark_report.json")
    args = parser.parse_args()

    ok, results = run_benchmarks(offline=args.offline, strict=args.strict)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
