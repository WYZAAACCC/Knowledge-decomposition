"""
IO工具

文件读写和序列化工具。
"""

import json
import yaml
import pickle
from pathlib import Path
from typing import Any, Dict, Optional, Union
import orjson


def read_json(file_path: Union[str, Path]) -> Any:
    """读取JSON文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(data: Any, file_path: Union[str, Path], indent: int = 2):
    """写入JSON文件"""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 使用orjson加速（如果可用）
    try:
        with open(file_path, 'wb') as f:
            f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))
    except Exception:
        # 回退到标准json
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)


def read_yaml(file_path: Union[str, Path]) -> Any:
    """读取YAML文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def write_yaml(data: Any, file_path: Union[str, Path]):
    """写入YAML文件"""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def read_text(file_path: Union[str, Path]) -> str:
    """读取文本文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def write_text(content: str, file_path: Union[str, Path]):
    """写入文本文件"""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def save_pickle(data: Any, file_path: Union[str, Path]):
    """保存pickle文件"""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, 'wb') as f:
        pickle.dump(data, f)


def load_pickle(file_path: Union[str, Path]) -> Any:
    """加载pickle文件"""
    with open(file_path, 'rb') as f:
        return pickle.load(f)


class ArtifactWriter:
    """工件写入器"""

    def __init__(self, artifacts_dir: Union[str, Path] = "artifacts/latest"):
        """
        初始化

        Args:
            artifacts_dir: 工件输出目录
        """
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def write_graph_json(self, graph_data: Dict[str, Any]):
        """写入graph.json"""
        file_path = self.artifacts_dir / "graph.json"
        write_json(graph_data, file_path)
        return file_path

    def write_report_md(self, report_content: str):
        """写入report.md"""
        file_path = self.artifacts_dir / "report.md"
        write_text(report_content, file_path)
        return file_path

    def write_debug_json(self, debug_data: Dict[str, Any]):
        """写入debug.json"""
        file_path = self.artifacts_dir / "debug.json"
        write_json(debug_data, file_path)
        return file_path

    def write_eval_report_json(self, eval_data: Dict[str, Any]):
        """写入eval_report.json"""
        file_path = self.artifacts_dir / "eval_report.json"
        write_json(eval_data, file_path)
        return file_path

    def write_intermediate(self, stage: str, data: Dict[str, Any]):
        """写入中间结果"""
        intermediate_dir = self.artifacts_dir.parent / "intermediate"
        intermediate_dir.mkdir(exist_ok=True)

        file_path = intermediate_dir / f"{stage}_output.json"
        write_json(data, file_path)
        return file_path

    def read_intermediate(self, stage: str) -> Optional[Dict[str, Any]]:
        """读取中间结果"""
        intermediate_dir = self.artifacts_dir.parent / "intermediate"
        file_path = intermediate_dir / f"{stage}_output.json"

        if file_path.exists():
            return read_json(file_path)
        return None

    def clear_intermediate(self):
        """清空中间结果"""
        intermediate_dir = self.artifacts_dir.parent / "intermediate"
        if intermediate_dir.exists():
            for file in intermediate_dir.glob("*_output.json"):
                try:
                    file.unlink()
                except Exception:
                    pass


def ensure_dir(dir_path: Union[str, Path]) -> Path:
    """确保目录存在"""
    path = Path(dir_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_exists(file_path: Union[str, Path]) -> bool:
    """检查文件是否存在"""
    return Path(file_path).exists()


def get_file_size(file_path: Union[str, Path]) -> int:
    """获取文件大小（字节）"""
    return Path(file_path).stat().st_size if Path(file_path).exists() else 0