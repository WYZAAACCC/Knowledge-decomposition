#!/usr/bin/env python
"""
单主题构建脚本

用法:
  python build_topic.py --topic "伯努利方程" --down 2 --up 1
  python build_topic.py --topic "伯努利方程" --offline --strict
  python build_topic.py --topic "伯努利方程" --allow-proposals --show-proposals
"""

import argparse
import json
import sys
from pathlib import Path
import dotenv

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.orchestrator import GraphBuildOrchestrator
from src.utils.logging import get_default_logger


def parse_args():
    """Fix 14: 升级CLI参数"""
    parser = argparse.ArgumentParser(description="构建物理知识图谱主题")
    parser.add_argument("--topic", "-t", required=True, help="主题文本")
    parser.add_argument("--down", "-d", type=int, default=3, help="向下展开层数(1-8)")
    parser.add_argument("--up", "-u", type=int, default=2, help="向上展开层数(0-5)")
    parser.add_argument("--max-nodes", "-n", type=int, default=40, help="最大节点数(15-150)")
    parser.add_argument("--include-alternates", "-a", action="store_true", help="包含备用路径")
    parser.add_argument("--output-dir", "-o", default="artifacts/latest", help="输出目录")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--retries", "-r", type=int, default=1, help="最大重试次数")
    # Fix 14: 新增参数
    parser.add_argument("--offline", action="store_true", help="不调用任何LLM，仅使用本地seed")
    parser.add_argument("--strict", action="store_true", help="不允许proposal/unknown/placeholder进入正式图")
    parser.add_argument("--no-llm", action="store_true", help="禁止LLM参与图构建")
    parser.add_argument("--allow-proposals", action="store_true", help="LLM提议保存到proposals.json")
    parser.add_argument("--show-proposals", action="store_true", help="未验证proposal在graph.html中默认隐藏")
    parser.add_argument("--fail-on-warning", action="store_true", help="有warning也返回非零exit code")
    parser.add_argument("--seed-dir", default=None, help="指定seed目录")
    parser.add_argument("--schema-version", default=None, help="指定schema版本")

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 加载环境变量
    dotenv.load_dotenv()

    # 配置日志
    logger = get_default_logger()
    if args.verbose:
        logger.setLevel("DEBUG")

    logger.info(f"开始构建主题: {args.topic}")
    logger.info(f"参数: down={args.down}, up={args.up}, max_nodes={args.max_nodes}, "
                f"offline={args.offline}, strict={args.strict}")

    try:
        # 创建编排器 (Fix 14: 传递offline和strict参数)
        orchestrator = GraphBuildOrchestrator(
            artifacts_dir=args.output_dir,
            offline=args.offline,
            strict=args.strict,
            no_llm=getattr(args, 'no_llm', False),
            allow_proposals=args.allow_proposals,
        )

        # 构建主题
        result = orchestrator.build_topic(
            args.topic,
            max_retries=args.retries,
            down=args.down,
            up=args.up,
            max_nodes=args.max_nodes
        )

        # 输出结果
        print("\n" + "=" * 60)
        print(f"构建结果: {result.topic}")
        print("=" * 60)

        if result.status == "success":
            print(f"[OK] 构建成功!")
        elif result.status == "partial_success":
            print(f"[WARN] 部分成功")
        else:
            print(f"[FAIL] 构建失败")

        print(f"\n[STAT] 统计:")
        if result.graph:
            print(f"   节点数: {len(result.graph.nodes)}")
            print(f"   边数: {len(result.graph.edges)}")
            if hasattr(result.graph, 'canonical_path') and result.graph.canonical_path:
                print(f"   规范路径: {result.graph.canonical_path}")

        print(f"\n[TIME] 耗时:")
        for stage, duration in result.timing.items():
            print(f"   {stage}: {duration:.2f}s")

        if result.warnings:
            print(f"\n[WARN] 警告 ({len(result.warnings)}个):")
            for warning in result.warnings[:3]:
                print(f"   - {warning}")
            if len(result.warnings) > 3:
                print(f"   ... 还有 {len(result.warnings) - 3} 个警告")

        if result.errors:
            print(f"\n[FAIL] 错误 ({len(result.errors)}个):")
            for error in result.errors:
                print(f"   - {error}")

        # 输出工件路径
        if result.artifacts:
            print(f"\n[FILE] 生成工件:")
            for name, path in result.artifacts.items():
                print(f"   {name}: {path}")

        # 输出验证分数
        if hasattr(result, 'debug_info') and 'validation_results' in result.debug_info:
            validation = result.debug_info['validation_results']
            if validation and 'overall_score' in validation:
                print(f"\n[SCORE] 验证分数: {validation['overall_score']:.2f}")

        print("\n" + "=" * 60)

        # Fix 14: 根据参数决定退出码
        if result.status == "failed":
            sys.exit(1)
        if args.fail_on_warning and result.warnings:
            print("[FAIL] --fail-on-warning 已启用，存在警告，返回非零退出码")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n构建被用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error(f"构建过程中发生异常: {e}")
        print(f"\n[FAIL] 构建失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
