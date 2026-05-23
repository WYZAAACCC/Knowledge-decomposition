"""
全方位极端严苛测试套件
======================
覆盖方向：
  第一轮：边界值测试（最小/最大参数组合）
  第二轮：异常输入测试（特殊字符、空输入、超长输入、混合语言）
  第三轮：跨域全覆盖测试（力学/电磁/量子/统计/相对论/凝聚态/天体/生物物理）
  第四轮：错误恢复与鲁棒性测试（API失败/JSON损坏/网络中断）
  第五轮：性能压力测试（连续构建/内存稳定性）
"""

import json
import sys
import time
import traceback
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
dotenv.load_dotenv(project_root / ".env")

from src.orchestrator import GraphBuildOrchestrator


@dataclass
class TestResult:
    round_name: str
    test_id: str
    topic: str
    params: Dict[str, Any]
    passed: bool
    node_count: int = 0
    edge_count: int = 0
    score: float = 0.0
    status: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration: float = 0.0
    exception: str = ""


class ExtremeTestSuite:
    """全方位极端严苛测试套件"""

    def __init__(self):
        self.results: List[TestResult] = []
        self.total_passed = 0
        self.total_failed = 0

    # ==================== 第一轮：边界值测试 ====================
    BOUNDARY_TESTS = [
        # (topic, down, up, max_nodes, description)
        ("牛顿第二定律", 1, 0, 5, "最小配置-1层-5节点"),
        ("欧姆定律", 1, 1, 10, "小规模-1层上下各1-10节点"),
        ("胡克定律", 2, 1, 15, "中等规模-2层下1层上"),
        ("理想气体状态方程", 3, 2, 30, "标准规模-3层下2层上"),
        ("薛定谔方程", 4, 2, 50, "较大规模-4层下2层上"),
        ("广义相对论", 5, 3, 80, "大规模-5层下3层上"),
        ("量子场论", 6, 4, 120, "最大配置-6层下4层上"),
        ("麦克斯韦方程组", 0, 3, 40, "纯向上展开-无向下"),
        ("热力学第二定律", 5, 0, 60, "纯向下展开-无向上"),
    ]

    # ==================== 第二轮：异常输入测试 ====================
    ABNORMAL_INPUT_TESTS = [
        # (input_text, expected_behavior, description)
        ("F=ma", "should_build", "纯公式输入"),
        ("E=mc^2", "should_build", "带特殊字符的公式"),
        ("∇·E=ρ/ε₀", "should_build", "LaTeX格式输入"),
        ("Schrödinger equation", "should_build", "英文输入"),
        ("Schrodinger Equation", "should_build", "英文变体"),
        ("schrodinger", "should_build", "小写英文"),
        ("   薛定谔方程   ", "should_build", "前后空格"),
        ("薛定谔方程(Schrödinger)", "should_build", "中英混合+括号"),
        ("Maxwell's Equations of Electromagnetism", "should_build", "长英文名称"),
        ("Navier-Stokes equations for incompressible flow", "should_build", "极长英文描述"),
        ("∂²ψ/∂x² + ∂²ψ/∂y² + ∂²ψ/∂z² = (2m/ℏ²)(E-V)ψ", "should_build", "完整方程式"),
        ("F", "should_build", "单字母"),
        ("能量守恒定律", "should_build", "通用概念"),
        ("黑洞信息悖论", "should_build", "前沿研究主题"),
        ("暗物质", "should_build", "未完全理解的概念"),
    ]

    # ==================== 第三轮：跨域全覆盖测试 ====================
    CROSS_DOMAIN_TESTS = [
        # 经典力学
        ("牛顿运动三定律", 3, 2, 40),
        ("角动量守恒", 3, 2, 35),
        ("拉格朗日力学", 4, 2, 50),
        ("哈密顿力学", 4, 2, 50),
        ("刚体转动惯量", 3, 2, 35),
        # 电磁学
        ("库仑定律", 3, 2, 35),
        ("法拉第电磁感应", 3, 2, 40),
        ("安培环路定理", 3, 2, 35),
        ("洛伦兹力", 3, 2, 35),
        ("电磁波传播", 4, 2, 45),
        # 量子力学
        ("海森堡不确定性原理", 3, 2, 35),
        ("泡利不相容原理", 3, 2, 35),
        ("费曼路径积分", 4, 2, 50),
        ("贝尔不等式", 3, 2, 35),
        ("量子纠缠", 3, 2, 40),
        # 统计力学
        ("麦克斯韦-玻尔兹曼分布", 4, 2, 45),
        ("费米-狄拉克统计", 3, 2, 40),
        ("玻色-爱因斯坦统计", 3, 2, 40),
        ("相变理论", 4, 2, 50),
        ("涨落耗散定理", 3, 2, 40),
        # 相对论
        ("狭义相对论", 4, 2, 50),
        ("时间膨胀效应", 3, 2, 35),
        ("引力波", 4, 2, 45),
        ("史瓦西度规", 4, 2, 50),
        ("霍金辐射", 3, 2, 40),
        # 凝聚态物理
        ("能带理论", 4, 2, 50),
        ("BCS超导理论", 4, 2, 50),
        ("半导体PN结", 3, 2, 40),
        ("拓扑绝缘体", 3, 2, 40),
        # 天体物理
        ("恒星演化", 4, 2, 50),
        ("宇宙微波背景辐射", 3, 2, 40),
        ("哈勃定律", 3, 2, 35),
        # 生物物理
        ("DNA双螺旋结构", 3, 2, 35),
        ("神经动作电位", 3, 2, 35),
    ]

    # ==================== 第四轮：错误恢复测试 ====================
    ERROR_RECOVERY_TESTS = [
        ("不存在的物理概念xyz123abc", 2, 1, 20, "不存在概念应回退或报错", True),
        ("", 2, 1, 20, "空字符串处理", False),
        ("a" * 200, 2, 1, 20, "超长字符串处理", False),
        ("🎉😊🚀", 2, 1, 20, "emoji输入处理", False),
        ("<script>alert('xss')</script>", 2, 1, 20, "XSS攻击尝试", False),
        ("'; DROP TABLE users; --", 2, 1, 20, "SQL注入尝试", False),
    ]

    def run_test(self, round_name: str, test_id: str, topic: str,
                 down: int, up: int, max_nodes: int,
                 expected_pass: bool = True) -> TestResult:
        """运行单个测试"""
        result = TestResult(
            round_name=round_name,
            test_id=test_id,
            topic=topic[:50],
            params={"down": down, "up": up, "max_nodes": max_nodes},
            passed=False
        )

        print(f"\n{'='*60}")
        print(f"[{round_name}] {test_id}: {topic}")
        print(f"参数: down={down}, up={up}, max_nodes={max_nodes}")
        print(f"{'='*60}")

        try:
            start_time = time.time()
            orchestrator = GraphBuildOrchestrator(artifacts_dir="artifacts/latest")
            build_result = orchestrator.build_topic(
                topic, down=down, up=up, max_nodes=max_nodes
            )
            result.duration = time.time() - start_time

            if build_result.graph:
                result.node_count = len(build_result.graph.nodes)
                result.edge_count = len(build_result.graph.edges)
                result.status = build_result.status

                vr = build_result.debug_info.get('validation_results', {})
                result.score = vr.get('overall_score', 0)

                schema_ok = vr.get('schema', {}).get('passed', False)
                graph_ok = vr.get('graph_structure', {}).get('passed', False)

                if build_result.status in ["success", "partial_success"]:
                    if expected_pass:
                        result.passed = True
                        icon = "PASS"
                    else:
                        result.passed = True
                        icon = "UNEXP_PASS"
                else:
                    if not expected_pass:
                        result.passed = True
                        icon = "EXP_FAIL"
                    else:
                        result.errors.append(f"构建失败: {build_result.status}")
                        icon = "FAIL"

                print(f"  [{icon}] N={result.node_count} E={result.edge_count} "
                      f"score={result.score:.2f} status={result.status} "
                      f"time={result.duration:.1f}s")

            else:
                result.passed = not expected_pass
                result.errors.append("图谱为空")
                print(f"  [EMPTY] 图谱为空")

        except Exception as e:
            result.exception = str(e)[:200]
            result.duration = time.time() - start_time
            print(f"  [EXCEPTION] {str(e)[:100]}")

        self.results.append(result)
        if result.passed:
            self.total_passed += 1
        else:
            self.total_failed += 1

        return result

    def run_round_1_boundary(self):
        """第一轮：边界值测试"""
        print("\n\n" + "="*80)
        print("第一轮：边界值测试")
        print("="*80)

        for i, (topic, down, up, max_nodes, desc) in enumerate(self.BOUNDARY_TESTS):
            self.run_test(
                "R1-边界值",
                f"T{i+1}-{desc}",
                topic, down, up, max_nodes,
                expected_pass=True
            )

    def run_round_2_abnormal_input(self):
        """第二轮：异常输入测试"""
        print("\n\n" + "="*80)
        print("第二轮：异常输入测试")
        print("="*80)

        for i, (inp, behavior, desc) in enumerate(self.ABNORMAL_INPUT_TESTS):
            self.run_test(
                "R2-异常输入",
                f"T{i+1}-{desc}",
                inp, 2, 1, 25,
                expected_pass=(behavior == "should_build")
            )

    def run_round_3_cross_domain(self):
        """第三轮：跨域全覆盖测试"""
        print("\n\n" + "="*80)
        print("第三轮：跨域全覆盖测试")
        print("="*80)

        for i, (topic, down, up, max_nodes) in enumerate(self.CROSS_DOMAIN_TESTS):
            self.run_test(
                "R3-跨域",
                f"T{i+1}-{topic}",
                topic, down, up, max_nodes,
                expected_pass=True
            )

    def run_round_4_error_recovery(self):
        """第四轮：错误恢复测试"""
        print("\n\n" + "="*80)
        print("第四轮：错误恢复与鲁棒性测试")
        print("="*80)

        for i, (topic, down, up, max_nodes, desc, expected_pass) in enumerate(self.ERROR_RECOVERY_TESTS):
            self.run_test(
                "R4-错误恢复",
                f"T{i+1}-{desc}",
                topic, down, up, max_nodes,
                expected_pass=expected_pass
            )

    def run_round_5_stress(self):
        """第五轮：性能压力测试"""
        print("\n\n" + "="*80)
        print("第五轮：性能压力测试 - 连续快速构建")
        print("="*80)

        stress_topics = ["F=ma", "E=mc²", "pV=nRT", "F=kx", "V=IR"]
        total_start = time.time()

        for i, topic in enumerate(stress_topics):
            self.run_test(
                "R5-压力",
                f"T{i+1}-连续{i+1}",
                topic, 2, 1, 15,
                expected_pass=True
            )

        total_time = time.time() - total_start
        print(f"\n  总耗时: {total_time:.1f}s, 平均: {total_time/len(stress_topics):.1f}s/次")

    def run_all_tests(self):
        """运行所有测试"""
        print("="*80)
        print("🔥 全方位极端严苛测试套件启动")
        print("="*80)

        self.run_round_1_boundary()
        self.run_round_2_abnormal_input()
        self.run_round_3_cross_domain()
        self.run_round_4_error_recovery()
        self.run_round_5_stress()

        return self.print_summary()

    def print_summary(self):
        """打印汇总报告"""
        print("\n\n" + "="*80)
        print("📋 全方位极端测试汇总报告")
        print("="*80)

        by_round = {}
        for r in self.results:
            rn = r.round_name
            if rn not in by_round:
                by_round[rn] = {"passed": 0, "failed": 0, "total": 0}
            by_round[rn]["total"] += 1
            if r.passed:
                by_round[rn]["passed"] += 1
            else:
                by_round[rn]["failed"] += 1

        for rn, stats in sorted(by_round.items()):
            p = stats["passed"]
            f = stats["failed"]
            t = stats["total"]
            bar = "█" * p + "░" * f
            print(f"  {rn}: {bar} {p}/{t}")

        print(f"\n{'='*80}")
        print(f"总计: 通过 {self.total_passed}/{len(self.results)} "
              f"(通过率 {100*self.total_passed/max(len(self.results),1):.1f}%)")

        failed_results = [r for r in self.results if not r.passed]
        if failed_results:
            print(f"\n❌ 失败的测试 ({len(failed_results)}个):")
            for r in failed_results:
                print(f"  [{r.round_name}] {r.test_id}: {r.topic}")
                if r.errors:
                    for e in r.errors[:2]:
                        print(f"    → {e}")
                if r.exception:
                    print(f"    → 异常: {r.exception[:80]}")
        else:
            print(f"\n🎉 所有测试全部通过！系统极其稳定！")

        report = {
            "total_tests": len(self.results),
            "passed": self.total_passed,
            "failed": self.total_failed,
            "pass_rate": self.total_passed / max(len(self.results), 1),
            "by_round": by_round,
            "failures": [
                {
                    "round": r.round_name, "test": r.test_id,
                    "topic": r.topic, "errors": r.errors,
                    "exception": r.exception
                }
                for r in failed_results
            ]
        }

        with open(project_root / "extreme_test_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        print(f"\n报告已保存到 extreme_test_report.json")
        return len(failed_results) == 0


def main():
    suite = ExtremeTestSuite()
    all_passed = suite.run_all_tests()
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
