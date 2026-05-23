"""
验证器简单测试（无Unicode）
"""

import sys
import os

def main():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    # 测试导入
    try:
        from src.validators.schema_validator import SchemaValidator
        from src.validators.graph_validator import GraphValidator
        from src.validators.assumption_validator import AssumptionValidator
        from src.validators.dimension_validator import DimensionValidator
        from src.validators.duplicate_validator import DuplicateValidator
        print("PASS: 所有验证器导入成功")
    except ImportError as e:
        print(f"FAIL: 导入失败 - {e}")
        return 1

    # 测试实例化
    try:
        schema_validator = SchemaValidator()
        graph_validator = GraphValidator()
        assumption_validator = AssumptionValidator()
        dimension_validator = DimensionValidator()
        duplicate_validator = DuplicateValidator()
        print("PASS: 所有验证器实例化成功")
    except Exception as e:
        print(f"FAIL: 实例化失败 - {e}")
        return 1

    # 测试方法存在性
    validators = [
        ("SchemaValidator", schema_validator, ['validate_node', 'validate_edge', 'validate_graph', 'validate_build_report']),
        ("GraphValidator", graph_validator, ['validate_dag', 'find_dangling_edges', 'find_isolated_nodes', 'validate_canonical_path']),
        ("AssumptionValidator", assumption_validator, ['validate_edge_assumptions', 'validate_topic_assumptions', 'validate_graph_assumptions']),
        ("DimensionValidator", dimension_validator, ['validate_node_dimension', 'validate_equation_dimensions', 'validate_canonical_path_dimensions', 'validate_graph_dimensions']),
        ("DuplicateValidator", duplicate_validator, ['find_duplicate_nodes_by_alias', 'find_similar_formulas', 'find_semantically_similar_nodes', 'find_potential_merges', 'validate_graph_uniqueness']),
    ]

    all_passed = True
    for name, validator, expected_methods in validators:
        for method in expected_methods:
            if not hasattr(validator, method):
                print(f"FAIL: {name} 缺少方法 {method}")
                all_passed = False

    if all_passed:
        print("PASS: 所有验证器方法检查通过")
    else:
        print("FAIL: 方法检查失败")
        return 1

    print("\n所有基本测试通过！")
    return 0

if __name__ == "__main__":
    sys.exit(main())