"""
Agent导入测试
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 测试导入
try:
    from src.agents.router_agent import RouterAgent
    print("PASS: RouterAgent导入成功")
except ImportError as e:
    print(f"FAIL: RouterAgent导入失败 - {e}")

try:
    from src.agents.planner_agent import PlannerAgent
    print("PASS: PlannerAgent导入成功")
except ImportError as e:
    print(f"FAIL: PlannerAgent导入失败 - {e}")

try:
    from src.agents.retriever_agent import RetrieverAgent
    print("PASS: RetrieverAgent导入成功")
except ImportError as e:
    print(f"FAIL: RetrieverAgent导入失败 - {e}")

try:
    from src.agents.decomposer_agent import DecomposerAgent
    print("PASS: DecomposerAgent导入成功")
except ImportError as e:
    print(f"FAIL: DecomposerAgent导入失败 - {e}")

try:
    from src.agents.verifier_agent import VerifierAgent
    print("PASS: VerifierAgent导入成功")
except ImportError as e:
    print(f"FAIL: VerifierAgent导入失败 - {e}")

try:
    from src.agents.ranker_agent import RankerAgent
    print("PASS: RankerAgent导入成功")
except ImportError as e:
    print(f"FAIL: RankerAgent导入失败 - {e}")

print("\n导入测试完成")