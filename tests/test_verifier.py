import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from src.models import KnowledgeGraph
from src.agents.verifier_agent import VerifierAgent

with open(project_root / 'artifacts' / 'latest' / 'graph.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

graph = KnowledgeGraph(**data)
print(f'Graph loaded: {len(graph.nodes)} nodes, {len(graph.edges)} edges')

decomposer_output = {"subgraph": graph}
verifier = VerifierAgent()
result = verifier.run(decomposer_output)

print(f'Passed: {result.passed}')
print(f'Score: {result.overall_score}')
print(f'Critical errors: {result.critical_errors}')
print(f'Warnings: {result.warnings[:5]}')
print()
for name, res in result.validation_results.items():
    print(f'  {name}: passed={res.get("passed")}, score={res.get("score")}')
