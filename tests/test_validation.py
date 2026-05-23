import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from src.models import KnowledgeGraph
from src.validators.schema_validator import SchemaValidator
from src.validators.graph_validator import GraphValidator
from src.validators.assumption_validator import AssumptionValidator
from src.validators.dimension_validator import DimensionValidator
from src.validators.duplicate_validator import DuplicateValidator

with open(project_root / 'artifacts' / 'latest' / 'graph.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

try:
    graph = KnowledgeGraph(**data)
    print(f'Graph loaded: {len(graph.nodes)} nodes, {len(graph.edges)} edges')

    sv = SchemaValidator()
    passed, errors, details = sv.validate_graph(graph)
    print(f'Schema: passed={passed}, errors={errors[:3]}')

    gv = GraphValidator()
    passed, errors, details = gv.validate_complete(graph)
    print(f'Graph: passed={passed}, errors={errors[:5]}')
    print(f'  dag_valid={details.get("dag_valid")}, dangling={details.get("dangling_edge_count")}, isolated={details.get("isolated_node_count")}, path_valid={details.get("canonical_path_valid")}')

    av = AssumptionValidator()
    passed, errors, details = av.validate_graph_assumptions(graph)
    print(f'Assumption: passed={passed}, errors={errors[:3]}')
    if 'topic_coverage' in details:
        tc = details['topic_coverage']
        print(f'  coverage={tc.get("assumption_coverage")}, missing_edges={tc.get("missing_assumption_edges")}')

    dv = DimensionValidator()
    passed, errors, details = dv.validate_graph_dimensions(graph)
    print(f'Dimension: passed={passed}, errors={errors[:3]}')
    print(f'  qty_nodes={details.get("quantity_nodes")}, eq_nodes={details.get("equation_nodes")}, with_dim={details.get("nodes_with_dimension")}, invalid={details.get("nodes_invalid")}')

    dupv = DuplicateValidator()
    passed, warnings, details = dupv.validate_graph_uniqueness(graph)
    print(f'Duplicate: passed={passed}, warnings={warnings[:3]}')

except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
