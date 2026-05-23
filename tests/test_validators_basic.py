"""
验证器基本测试

测试验证器的导入和基本功能。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.validators.schema_validator import SchemaValidator
from src.validators.graph_validator import GraphValidator
from src.validators.assumption_validator import AssumptionValidator
from src.validators.dimension_validator import DimensionValidator
from src.validators.duplicate_validator import DuplicateValidator


def test_imports():
    """测试导入"""
    assert SchemaValidator is not None
    assert GraphValidator is not None
    assert AssumptionValidator is not None
    assert DimensionValidator is not None
    assert DuplicateValidator is not None
    print("✓ 所有验证器导入成功")


def test_instantiation():
    """测试实例化"""
    schema_validator = SchemaValidator()
    graph_validator = GraphValidator()
    assumption_validator = AssumptionValidator()
    dimension_validator = DimensionValidator()
    duplicate_validator = DuplicateValidator()

    assert schema_validator is not None
    assert graph_validator is not None
    assert assumption_validator is not None
    assert dimension_validator is not None
    assert duplicate_validator is not None
    print("✓ 所有验证器实例化成功")


def test_schema_validator_has_methods():
    """测试SchemaValidator有预期的方法"""
    validator = SchemaValidator()
    assert hasattr(validator, 'validate_node')
    assert hasattr(validator, 'validate_edge')
    assert hasattr(validator, 'validate_graph')
    assert hasattr(validator, 'validate_build_report')
    print("✓ SchemaValidator方法检查通过")


def test_graph_validator_has_methods():
    """测试GraphValidator有预期的方法"""
    validator = GraphValidator()
    assert hasattr(validator, 'validate_dag')
    assert hasattr(validator, 'find_dangling_edges')
    assert hasattr(validator, 'find_isolated_nodes')
    assert hasattr(validator, 'validate_canonical_path')
    print("✓ GraphValidator方法检查通过")


def test_assumption_validator_has_methods():
    """测试AssumptionValidator有预期的方法"""
    validator = AssumptionValidator()
    assert hasattr(validator, 'validate_edge_assumptions')
    assert hasattr(validator, 'validate_topic_assumptions')
    assert hasattr(validator, 'validate_graph_assumptions')
    print("✓ AssumptionValidator方法检查通过")


def test_dimension_validator_has_methods():
    """测试DimensionValidator有预期的方法"""
    validator = DimensionValidator()
    assert hasattr(validator, 'validate_node_dimension')
    assert hasattr(validator, 'validate_equation_dimensions')
    assert hasattr(validator, 'validate_canonical_path_dimensions')
    assert hasattr(validator, 'validate_graph_dimensions')
    print("✓ DimensionValidator方法检查通过")


def test_duplicate_validator_has_methods():
    """测试DuplicateValidator有预期的方法"""
    validator = DuplicateValidator()
    assert hasattr(validator, 'find_duplicate_nodes_by_alias')
    assert hasattr(validator, 'find_similar_formulas')
    assert hasattr(validator, 'find_semantically_similar_nodes')
    assert hasattr(validator, 'find_potential_merges')
    assert hasattr(validator, 'validate_graph_uniqueness')
    print("✓ DuplicateValidator方法检查通过")


if __name__ == "__main__":
    test_imports()
    test_instantiation()
    test_schema_validator_has_methods()
    test_graph_validator_has_methods()
    test_assumption_validator_has_methods()
    test_dimension_validator_has_methods()
    test_duplicate_validator_has_methods()
    print("\n✅ 所有基本测试通过！")