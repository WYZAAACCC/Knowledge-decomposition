"""
日志工具

提供结构化的日志记录，支持文件和控制台输出。
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logger(name: str = "physics_graph",
                 log_level: str = "INFO",
                 log_file: Optional[str] = None) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        log_level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        log_file: 日志文件路径，如果为None则只输出到控制台

    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # 移除现有的处理器（避免重复）
    logger.handlers.clear()

    # 创建格式化器
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


class BuildLogger:
    """构建过程日志记录器"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化

        Args:
            logger: 基础日志记录器，如果为None则创建新的
        """
        if logger is None:
            self.logger = setup_logger("build")
        else:
            self.logger = logger

        self.stage_start_times = {}

    def stage_start(self, stage: str, topic: str = None):
        """记录阶段开始"""
        message = f"开始阶段: {stage}"
        if topic:
            message += f" (主题: {topic})"

        self.logger.info(message)
        self.stage_start_times[stage] = datetime.now()

    def stage_end(self, stage: str, success: bool = True,
                  details: str = None):
        """记录阶段结束"""
        end_time = datetime.now()
        start_time = self.stage_start_times.get(stage)

        duration = ""
        if start_time:
            duration_seconds = (end_time - start_time).total_seconds()
            duration = f" 耗时: {duration_seconds:.2f}s"

        status = "成功" if success else "失败"
        message = f"结束阶段: {stage} - {status}{duration}"

        if details:
            message += f" | {details}"

        if success:
            self.logger.info(message)
        else:
            self.logger.error(message)

    def info(self, message: str):
        """记录信息"""
        self.logger.info(message)

    def warning(self, message: str):
        """记录警告"""
        self.logger.warning(message)

    def error(self, message: str, exception: Exception = None):
        """记录错误"""
        if exception:
            self.logger.error(f"{message}: {exception}", exc_info=True)
        else:
            self.logger.error(message)

    def debug(self, message: str):
        """记录调试信息"""
        self.logger.debug(message)

    def agent_call(self, agent_name: str, input_data: dict, output_data: dict):
        """记录Agent调用"""
        self.logger.debug(f"Agent调用: {agent_name}")
        self.logger.debug(f"输入: {_truncate_dict(input_data)}")
        self.logger.debug(f"输出: {_truncate_dict(output_data)}")

    def validation_result(self, validator_name: str, passed: bool,
                          details: list):
        """记录验证结果"""
        status = "通过" if passed else "失败"
        message = f"验证器 {validator_name}: {status}"

        if details:
            details_str = "; ".join(details[:3])  # 只显示前3个详情
            if len(details) > 3:
                details_str += f" ... (共{len(details)}条)"
            message += f" | {details_str}"

        if passed:
            self.logger.info(message)
        else:
            self.logger.warning(message)


def _truncate_dict(data: dict, max_length: int = 200) -> str:
    """截断字典的字符串表示"""
    str_repr = str(data)
    if len(str_repr) <= max_length:
        return str_repr
    else:
        return str_repr[:max_length] + "..."


# 全局日志记录器
_default_logger: Optional[logging.Logger] = None
_default_build_logger: Optional[BuildLogger] = None


def get_default_logger() -> logging.Logger:
    """获取默认日志记录器"""
    global _default_logger
    if _default_logger is None:
        _default_logger = setup_logger()
    return _default_logger


def get_build_logger() -> BuildLogger:
    """获取构建日志记录器"""
    global _default_build_logger
    if _default_build_logger is None:
        _default_build_logger = BuildLogger(get_default_logger())
    return _default_build_logger