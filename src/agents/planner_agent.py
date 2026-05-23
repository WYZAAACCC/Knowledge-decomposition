"""
PlannerAgent

根据目标topic生成本次构图计划。
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass

from ..deepseek_client import get_deepseek_client, TaskComplexity
from ..loader import DataLoader


@dataclass
class PlannerOutput:
    """PlannerAgent输出"""
    target: str
    expand_down: int
    expand_up: int
    max_nodes: int
    include_alternates: bool
    require_validation: bool
    include_math_expansion: bool
    domain: str
    node_type: str


class PlannerAgent:
    """PlannerAgent"""

    def __init__(self, loader: Optional[DataLoader] = None):
        """
        初始化

        Args:
            loader: 数据加载器
        """
        self.loader = loader or DataLoader()
        self.client = get_deepseek_client()

    def run(self, router_output: Dict[str, Any]) -> PlannerOutput:
        """
        运行PlannerAgent

        Args:
            router_output: RouterAgent的输出

        Returns:
            PlannerOutput对象
        """
        target = router_output.get("normalized_topic")
        domain = router_output.get("domain", "mechanics")
        node_type = router_output.get("node_type", "concept")
        confidence = router_output.get("confidence", 0.5)

        expand_down = router_output.get('down') if router_output.get('down') is not None else None
        expand_up = router_output.get('up') if router_output.get('up') is not None else None
        max_nodes = router_output.get('max_nodes') if router_output.get('max_nodes') is not None else None
        include_alternates = router_output.get('include_alternates', False)

        if expand_down is None:
            if confidence < 0.7:
                expand_down = 2
            elif node_type in ["equation", "law"]:
                expand_down = 4
            else:
                expand_down = 3

        if expand_up is None:
            if confidence < 0.7:
                expand_up = 1
            elif node_type in ["equation", "law"]:
                expand_up = 2
            else:
                expand_up = 2

        if max_nodes is None:
            if confidence < 0.7:
                max_nodes = 20
            elif node_type in ["equation", "law"]:
                max_nodes = 50
            else:
                max_nodes = 30

        if not include_alternates:
            include_alternates = (confidence > 0.8)

        # 根据学科域调整
        if domain == "mechanics":
            # 力学通常有明确的推导路径
            include_math_expansion = True
        elif domain == "modern_physics":
            # 近代物理可能需要数学展开
            include_math_expansion = True
        else:
            include_math_expansion = False

        # 总是需要验证
        require_validation = True

        return PlannerOutput(
            target=target,
            expand_down=expand_down,
            expand_up=expand_up,
            max_nodes=max_nodes,
            include_alternates=include_alternates,
            require_validation=require_validation,
            include_math_expansion=include_math_expansion,
            domain=domain,
            node_type=node_type
        )

    def run_with_llm(self, router_output: Dict[str, Any]) -> PlannerOutput:
        """
        使用LLM生成计划（可选）

        Args:
            router_output: RouterAgent的输出

        Returns:
            PlannerOutput对象
        """
        system_prompt = """你是一个专业的物理知识图谱规划器，负责根据目标主题制定最优的构图策略。

你的核心能力：
1. 评估主题的复杂度和知识深度
2. 确定合理的展开范围和节点数量
3. 判断是否需要数学工具和备用路径

规划原则：
- 方程和定律类主题通常有明确的推导链，需要向下展开更多层来追溯基础
- 概念类主题需要向上展开更多层来展示应用
- 复杂主题（如涉及多个学科域交叉）需要更多节点和备用路径
- 数学展开对于需要微积分、矢量分析等工具的主题是必要的

展开策略参考：
- 简单概念：expand_down=2, expand_up=1, max_nodes=20
- 标准方程/定律：expand_down=3, expand_up=2, max_nodes=40
- 复杂推导链：expand_down=4, expand_up=2, max_nodes=60
- 高级理论（广义相对论、量子场论等）：expand_down=5, expand_up=3, max_nodes=80
- 跨学科主题：expand_down=4, expand_up=3, max_nodes=80, include_alternates=true

输出必须是严格的JSON格式：
{
  "expand_down": 整数(1-8),
  "expand_up": 整数(0-5),
  "max_nodes": 整数(15-150),
  "include_alternates": 布尔值,
  "require_validation": 布尔值,
  "include_math_expansion": 布尔值,
  "rationale": "详细解释规划理由，包括主题复杂度评估和展开策略选择依据"
}
"""

        target = router_output.get("normalized_topic")
        domain = router_output.get("domain", "mechanics")
        node_type = router_output.get("node_type", "concept")

        user_prompt = f"""为目标主题生成构图计划：
- 主题: {target}
- 学科域: {domain}
- 节点类型: {node_type}
"""

        try:
            response = self.client.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                complexity=TaskComplexity.SIMPLE  # 规划是简单任务
            )

            # 解析响应
            expand_down = response.get("expand_down", 3)
            expand_up = response.get("expand_up", 2)
            max_nodes = response.get("max_nodes", 40)
            include_alternates = response.get("include_alternates", False)
            require_validation = response.get("require_validation", True)
            include_math_expansion = response.get("include_math_expansion", False)

            # 验证范围（支持大规模复杂图谱）
            expand_down = max(1, min(expand_down, 8))
            expand_up = max(0, min(expand_up, 5))
            max_nodes = max(15, min(max_nodes, 150))

            return PlannerOutput(
                target=target,
                expand_down=expand_down,
                expand_up=expand_up,
                max_nodes=max_nodes,
                include_alternates=include_alternates,
                require_validation=require_validation,
                include_math_expansion=include_math_expansion,
                domain=domain,
                node_type=node_type
            )

        except Exception as e:
            # LLM失败时回退到规则-based
            error_msg = f"PlannerAgent LLM调用失败，使用规则-based: {e}"
            print(f"[ERROR] {error_msg}")
            return self.run(router_output)