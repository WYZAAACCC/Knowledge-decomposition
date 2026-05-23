#!/usr/bin/env python
"""
物理知识图谱系统 - 前端应用
基于Streamlit的交互式界面
"""
import os
import sys
import json
import time
import re
from pathlib import Path
import streamlit as st
import subprocess
import threading
import queue
from typing import Dict, List, Any, Optional

src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

st.set_page_config(
    page_title="物理知识图谱系统",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)


def parse_progress_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    progress_match = re.match(r'^\[PROGRESS\]\s+(\w+):\s+(\w+)\s+-\s+(.+)$', line)
    if progress_match:
        stage, status, message = progress_match.groups()
        return {"type": "progress", "stage": stage, "status": status,
                "message": message, "timestamp": time.time()}

    detail_match = re.match(r'^\s+(\w+):\s+(.+)$', line)
    if detail_match:
        key, value = detail_match.groups()
        return {"type": "detail", "key": key, "value": value}

    if "ERROR" in line or "error" in line.lower():
        return {"type": "error", "message": line}
    elif "WARNING" in line or "warning" in line.lower():
        return {"type": "warning", "message": line}

    return None


def detect_and_fix_errors(output_lines: List[str]) -> List[str]:
    fixes = []
    for line in output_lines:
        ll = line.lower()
        if "validation error" in ll or "validation failed" in ll:
            if "canonical_path" in line and "pattern" in line:
                fixes.append("检测到canonical_path验证错误: 已自动修复路径格式")
            elif "topic" in line and "pattern" in line:
                fixes.append("检测到topic验证错误: 建议使用英文主题或标准ID")
            elif "path_id" in line and "pattern" in line:
                fixes.append("检测到path_id验证错误: 已自动修复边路径ID")
        elif "api key" in ll or "authentication" in ll:
            fixes.append("检测到API密钥错误: 请检查DeepSeek API密钥配置")
        elif "timeout" in ll or "连接超时" in ll:
            fixes.append("检测到超时错误: 建议增加REQUEST_TIMEOUT_SECONDS环境变量")
    return fixes


def check_dependencies():
    try:
        import openai
        import pydantic
        import networkx
        import sympy
        import streamlit
        return True, "所有依赖已安装"
    except ImportError as e:
        return False, f"依赖未安装: {e}"


def _update_env_file(key: str, value: str):
    env_path = Path(".env")
    lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def load_env_file():
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
        return True
    return False


def _decode_line(byte_line):
    if not byte_line:
        return ""
    for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
        try:
            return byte_line.decode(encoding).rstrip('\n\r')
        except UnicodeDecodeError:
            continue
    try:
        return byte_line.decode('utf-8', errors='replace').rstrip('\n\r')
    except Exception:
        return "[无法解码的行]"


def run_build_process(topic, down_levels, up_levels, max_nodes, output_queue, progress_callback=None):
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cmd = [
            sys.executable, "scripts/build_topic.py",
            "--topic", topic,
            "--down", str(down_levels),
            "--up", str(up_levels),
            "--max-nodes", str(max_nodes),
            "--verbose"
        ]

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=False, cwd=script_dir, bufsize=1
        )

        stdout_lines, stderr_lines, progress_updates = [], [], []

        while True:
            stdout_bytes = process.stdout.readline()
            if stdout_bytes:
                stdout_line = _decode_line(stdout_bytes)
                stdout_lines.append(stdout_line)
                parsed = parse_progress_line(stdout_line)
                if parsed:
                    progress_updates.append(parsed)
                    if progress_callback:
                        progress_callback(parsed)

            stderr_bytes = process.stderr.readline()
            if stderr_bytes:
                stderr_line = _decode_line(stderr_bytes)
                stderr_lines.append(stderr_line)
                parsed = parse_progress_line(stderr_line)
                if parsed:
                    progress_updates.append(parsed)
                    if progress_callback:
                        progress_callback(parsed)

            if process.poll() is not None:
                for byte_line in process.stdout:
                    line = _decode_line(byte_line)
                    stdout_lines.append(line)
                    parsed = parse_progress_line(line)
                    if parsed:
                        progress_updates.append(parsed)
                        if progress_callback:
                            progress_callback(parsed)
                for byte_line in process.stderr:
                    line = _decode_line(byte_line)
                    stderr_lines.append(line)
                    parsed = parse_progress_line(line)
                    if parsed:
                        progress_updates.append(parsed)
                        if progress_callback:
                            progress_callback(parsed)
                break

        returncode = process.wait()
        all_output = stdout_lines + stderr_lines
        error_fixes = detect_and_fix_errors(all_output)

        output_queue.put({
            "returncode": returncode,
            "stdout": "\n".join(stdout_lines),
            "stderr": "\n".join(stderr_lines),
            "topic": topic,
            "progress_updates": progress_updates,
            "error_fixes": error_fixes
        })

    except Exception as e:
        output_queue.put({
            "error": str(e), "topic": topic,
            "progress_updates": [], "error_fixes": []
        })


def _find_artifact_path(relative_path: str) -> Optional[Path]:
    script_dir = Path(__file__).parent
    candidate = script_dir / relative_path
    if candidate.exists():
        return candidate
    candidate = Path(relative_path)
    if candidate.exists():
        return candidate
    return None


def load_graph_data(force_reload=False):
    if not force_reload and "graph_data" in st.session_state:
        return st.session_state.graph_data

    graph_path = _find_artifact_path("artifacts/latest/graph.json")
    if not graph_path:
        if "graph_data" in st.session_state:
            del st.session_state.graph_data
        return None

    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)
            st.session_state.graph_data = graph_data
            return graph_data
    except Exception as e:
        st.error(f"加载图谱数据失败: {e}")
        if "graph_data" in st.session_state:
            del st.session_state.graph_data
        return None


def load_report():
    report_path = _find_artifact_path("artifacts/latest/report.md")
    if not report_path:
        return "# 报告未生成"
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"# 加载报告失败\n\n{e}"


def display_node_details(node):
    st.markdown(f"### 📍 {node.get('title', node.get('id', '未知节点'))}")
    cols = st.columns(2)
    with cols[0]:
        st.metric("节点类型", node.get('type', '未知'))
        st.metric("学科域", node.get('domain', '未知'))
    with cols[1]:
        if 'abstraction_level' in node:
            st.metric("抽象层级", node.get('abstraction_level'))
        if 'pedagogical_level' in node:
            st.metric("教学层级", node.get('pedagogical_level'))

    if 'statement' in node and node['statement']:
        st.markdown("**描述:**")
        st.info(node['statement'])
    if 'formula_latex' in node and node['formula_latex']:
        st.markdown("**公式:**")
        st.latex(node['formula_latex'])
    if 'aliases' in node and node['aliases']:
        st.markdown("**别名:**")
        st.write(", ".join(node['aliases']))
    if 'sources' in node and node['sources']:
        st.markdown("**来源:**")
        st.write(", ".join(node['sources']))


def display_edge_details(edge, nodes):
    from_node = next((n for n in nodes if n['id'] == edge.get('from')), {})
    to_node = next((n for n in nodes if n['id'] == edge.get('to')), {})

    st.markdown(f"### 🔗 {edge.get('type', '未知边类型')}")
    cols = st.columns(2)
    with cols[0]:
        st.metric("源节点", from_node.get('title', edge.get('from')))
    with cols[1]:
        st.metric("目标节点", to_node.get('title', edge.get('to')))

    st.markdown(f"**边ID:** `{edge.get('id', '未知')}`")
    st.markdown(f"**路径ID:** `{edge.get('path_id', '未知')}`")

    if 'assumptions' in edge and edge['assumptions']:
        st.markdown("**假设:**")
        for assumption in edge['assumptions']:
            st.markdown(f"- {assumption}")

    if 'derivation_steps' in edge and edge['derivation_steps']:
        st.markdown("**推导步骤:**")
        for i, step in enumerate(edge['derivation_steps'], 1):
            st.markdown(f"{i}. {step}")

    if 'math_used' in edge and edge['math_used']:
        st.markdown("**使用的数学工具:**")
        for math in edge['math_used']:
            st.code(math)

    if 'approximation_tags' in edge and edge['approximation_tags']:
        st.markdown("**近似标签:**")
        for tag in edge['approximation_tags']:
            st.markdown(f"`{tag}`")

    if 'confidence' in edge and edge['confidence'] is not None:
        st.progress(float(edge['confidence']))
        st.markdown(f"**置信度:** {edge['confidence']:.2%}")


def _display_progress_updates(progress_updates, expanded=True):
    if not progress_updates:
        return
    with st.expander("查看构建进度详情", expanded=expanded):
        for update in progress_updates:
            if update.get("type") == "progress":
                stage = update.get("stage", "")
                status = update.get("status", "")
                message = update.get("message", "")
                if status == "started":
                    st.write(f"[开始] **{stage}**: {message}")
                elif status == "completed":
                    st.write(f"[完成] **{stage}**: {message}")
                elif status == "failed":
                    st.write(f"[失败] **{stage}**: {message}")
                else:
                    st.write(f"[信息] **{stage}**: {message}")
            elif update.get("type") == "detail":
                st.write(f"    {update.get('key')}: {update.get('value')}")
            elif update.get("type") == "error":
                st.error(update.get("message", ""))
            elif update.get("type") == "warning":
                st.warning(update.get("message", ""))


def _display_error_fixes(error_fixes, expanded=True):
    if not error_fixes:
        return
    with st.expander("错误修复建议", expanded=expanded):
        for fix in error_fixes:
            st.info(f"[修复] {fix}")


def _display_build_result(result):
    is_error = "error" in result
    is_success = not is_error and result.get("returncode") == 0
    progress_updates = result.get("progress_updates", [])
    error_fixes = result.get("error_fixes", [])

    if is_error:
        st.error(f"构建失败: {result['error']}")
        _display_progress_updates(progress_updates, expanded=True)
        _display_error_fixes(error_fixes, expanded=True)
    elif is_success:
        st.success("[OK] 构建完成！")
        st.balloons()

        graph_data = load_graph_data(force_reload=True)
        if graph_data:
            node_count = len(graph_data.get("nodes", []))
            edge_count = len(graph_data.get("edges", []))
            st.info(f"图谱数据已加载: {node_count}个节点, {edge_count}条边")
        else:
            st.warning("构建完成但未找到图谱数据，请检查artifacts目录")

        _display_progress_updates(progress_updates, expanded=False)
        _display_error_fixes(error_fixes, expanded=False)

        with st.expander("查看完整构建日志", expanded=False):
            st.code(result.get("stdout", ""))
    else:
        st.error("[FAIL] 构建失败")
        _display_progress_updates(progress_updates, expanded=True)
        _display_error_fixes(error_fixes, expanded=True)

        if result.get("stdout"):
            with st.expander("查看构建输出", expanded=False):
                st.code(result.get("stdout", ""))
        if result.get("stderr"):
            with st.expander("查看错误详情", expanded=True):
                st.code(result.get("stderr", ""))
        if not result.get("stdout") and not result.get("stderr"):
            st.info("构建失败，但未捕获到输出信息。请检查DeepSeek API密钥是否配置正确。")


def _display_detailed_build_log(build_result: Dict[str, Any]):
    st.subheader("📋 详细构建日志")
    log_tab1, log_tab2, log_tab3, log_tab4 = st.tabs(
        ["🔄 构建时间线", "🤖 Agent详情", "📝 原始日志", "⚠️ 错误与警告"]
    )
    with log_tab1:
        _display_timeline_view(build_result)
    with log_tab2:
        _display_agent_details(build_result)
    with log_tab3:
        _display_raw_logs(build_result)
    with log_tab4:
        _display_errors_warnings(build_result)


_AGENT_STAGES = {
    "start": {"name": "初始化", "icon": "🚀", "color": "#6366f1"},
    "router": {"name": "RouterAgent", "icon": "🧭", "color": "#3b82f6"},
    "planner": {"name": "PlannerAgent", "icon": "📋", "color": "#10b981"},
    "retrieval": {"name": "RetrieverAgent", "icon": "🔍", "color": "#f59e0b"},
    "decomposer": {"name": "DecomposerAgent", "icon": "🧩", "color": "#ef4444"},
    "verification": {"name": "VerifierAgent", "icon": "✅", "color": "#8b5cf6"},
    "ranker": {"name": "RankerAgent", "icon": "🏆", "color": "#ec4899"},
    "renderer": {"name": "RendererAgent", "icon": "🎨", "color": "#06b6d4"},
    "finalize": {"name": "最终化", "icon": "🎯", "color": "#84cc16"},
    "complete": {"name": "完成", "icon": "✨", "color": "#22c55e"}
}


def _display_timeline_view(build_result: Dict[str, Any]):
    progress_updates = build_result.get("progress_updates", [])
    if not progress_updates:
        st.info("暂无构建进度信息")
        return

    stage_stats = {}
    for update in progress_updates:
        if update.get("type") == "progress":
            stage = update.get("stage", "")
            status = update.get("status", "")
            message = update.get("message", "")
            if stage not in stage_stats:
                stage_stats[stage] = {"started": None, "completed": None,
                                       "failed": None, "messages": [], "details": []}
            if status == "started":
                stage_stats[stage]["started"] = update.get("timestamp")
                stage_stats[stage]["messages"].append(("start", message))
            elif status == "completed":
                stage_stats[stage]["completed"] = update.get("timestamp")
                stage_stats[stage]["messages"].append(("complete", message))
            elif status == "failed":
                stage_stats[stage]["failed"] = update.get("timestamp")
                stage_stats[stage]["messages"].append(("fail", message))
            else:
                stage_stats[stage]["messages"].append(("info", message))
        elif update.get("type") == "detail" and stage_stats:
            last_stage = list(stage_stats.keys())[-1]
            stage_stats[last_stage]["details"].append(
                {"key": update.get("key"), "value": update.get("value")})

    st.markdown("### ⏱️ 构建流程时间线")
    for i, (stage_key, stats) in enumerate(stage_stats.items()):
        agent_info = _AGENT_STAGES.get(stage_key, {"name": stage_key, "icon": "⚙️", "color": "#6b7280"})

        if stats["failed"]:
            status_icon, status_color, status_text = "❌", "#ef4444", "失败"
        elif stats["completed"]:
            status_icon, status_color, status_text = "✅", "#22c55e", "完成"
        elif stats["started"]:
            status_icon, status_color, status_text = "⏳", "#f59e0b", "进行中"
        else:
            status_icon, status_color, status_text = "⏸️", "#9ca3af", "等待"

        duration = ""
        if stats["started"] and stats["completed"]:
            duration = f" 耗时: {(stats['completed'] - stats['started']):.2f}s"

        with st.expander(
            f"{agent_info['icon']} **{agent_info['name']}** {status_icon} {status_text}{duration}",
            expanded=(status_text == "失败" or i == len(stage_stats) - 1)
        ):
            for msg_type, msg in stats["messages"]:
                if msg_type == "start":
                    st.success(f"▶ 开始: {msg}")
                elif msg_type == "complete":
                    st.info(f"✔ 完成: {msg}")
                elif msg_type == "fail":
                    st.error(f"✖ 失败: {msg}")
                else:
                    st.write(f"ℹ {msg}")

            if stats["details"]:
                st.markdown("**详细信息:**")
                details_cols = st.columns(3)
                for j, detail in enumerate(stats["details"]):
                    with details_cols[j % 3]:
                        st.caption(f"{detail['key']}: `{detail['value']}`")


_AGENTS_INFO = {
    "router": {"name": "RouterAgent（路由器）", "description": "识别标准主题ID，确定学科域", "color": "#3b82f6"},
    "planner": {"name": "PlannerAgent（规划器）", "description": "制定向下/向上展开计划", "color": "#10b981"},
    "retrieval": {"name": "RetrieverAgent（检索器）", "description": "从本地知识库检索候选节点", "color": "#f59e0b"},
    "decomposer": {"name": "DecomposerAgent（分解器）", "description": "组装候选子图，添加假设和推导步骤", "color": "#ef4444"},
    "verification": {"name": "VerifierAgent（验证器）", "description": "执行schema、DAG、量纲等校验", "color": "#8b5cf6"},
    "ranker": {"name": "RankerAgent（排名器）", "description": "选择规范路径，优化图谱质量", "color": "#ec4899"},
    "renderer": {"name": "RendererAgent（渲染器）", "description": "生成最终输出工件（JSON、HTML、报告）", "color": "#06b6d4"},
}


def _display_agent_details(build_result: Dict[str, Any]):
    progress_updates = build_result.get("progress_updates", [])
    st.markdown("### 🤖 各Agent执行详情")

    for agent_key, agent_info in _AGENTS_INFO.items():
        agent_updates = [
            u for u in progress_updates
            if u.get("type") == "progress" and u.get("stage") == agent_key
        ]

        has_started = any(u.get("status") == "started" for u in agent_updates)
        has_completed = any(u.get("status") == "completed" for u in agent_updates)
        has_failed = any(u.get("status") == "failed" for u in agent_updates)

        if has_failed:
            status_badge, bg_color, border_color = "❌ 失败", "#fef2f2", "#ef4444"
        elif has_completed:
            status_badge, bg_color, border_color = "✅ 完成", "#f0fdf4", "#22c55e"
        elif has_started:
            status_badge, bg_color, border_color = "⏳ 运行中", "#fffbeb", "#f59e0b"
        else:
            status_badge, bg_color, border_color = "⏸️ 未运行", "#f9fafb", "#9ca3af"

        st.markdown(
            f"""<div style="background-color:{bg_color};border-left:4px solid {border_color};padding:12px;margin:8px 0;border-radius:6px;">
                <div style="font-weight:bold;color:{border_color};font-size:16px;">
                    {agent_info['name']} <span style="float:right;">{status_badge}</span>
                </div>
                <div style="color:#666;font-size:13px;margin-top:4px;">{agent_info['description']}</div>
            </div>""",
            unsafe_allow_html=True
        )

        if agent_updates:
            with st.expander(f"查看{agent_info['name']}详细输出"):
                for update in agent_updates:
                    status = update.get("status", "")
                    message = update.get("message", "")
                    if status == "started":
                        st.success(f"[开始] {message}")
                    elif status == "completed":
                        st.info(f"[完成] {message}")
                    elif status == "failed":
                        st.error(f"[失败] {message}")
                    else:
                        st.write(f"[信息] {message}")

                related_details = [u for u in progress_updates if u.get("type") == "detail"]
                if related_details:
                    st.divider()
                    st.markdown("**关联数据:**")
                    for detail in related_details[:5]:
                        st.code(f"{detail.get('key')}: {detail.get('value')}", language=None)


def _display_raw_logs(build_result: Dict[str, Any]):
    st.markdown("### 📝 原始构建日志")
    stdout = build_result.get("stdout", "")
    stderr = build_result.get("stderr", "")
    if stdout:
        st.markdown("**标准输出 (stdout):**")
        st.code(stdout, language="text")
    else:
        st.info("无标准输出")
    if stderr:
        st.markdown("**标准错误 (stderr):**")
        st.code(stderr, language="text")
    else:
        st.info("无标准错误")


def _display_errors_warnings(build_result: Dict[str, Any]):
    progress_updates = build_result.get("progress_updates", [])
    error_fixes = build_result.get("error_fixes", [])

    st.markdown("### ⚠️ 错误与警告汇总")

    errors, warnings_list = [], []
    for update in progress_updates:
        if update.get("type") == "error":
            errors.append(update.get("message", ""))
        elif update.get("type") == "warning":
            warnings_list.append(update.get("message", ""))
    for update in progress_updates:
        if update.get("type") == "progress" and update.get("status") == "failed":
            errors.append(f"[{update.get('stage')}] {update.get('message', '')}")

    stat_col1, stat_col2, stat_col3 = st.columns(3)
    with stat_col1:
        st.metric("错误数", len(errors), delta_color="inverse")
    with stat_col2:
        st.metric("警告数", len(warnings_list), delta_color="inverse")
    with stat_col3:
        st.metric("修复建议", len(error_fixes))

    if errors:
        st.markdown("**❌ 错误列表:**")
        for i, error in enumerate(errors, 1):
            st.error(f"{i}. {error}")
    else:
        st.success("✅ 未发现错误")

    if warnings_list:
        st.markdown("**⚠️ 警告列表:**")
        for i, warning in enumerate(warnings_list, 1):
            st.warning(f"{i}. {warning}")

    if error_fixes:
        st.markdown("**🔧 自动修复建议:**")
        for i, fix in enumerate(error_fixes, 1):
            st.info(f"{i}. {fix}")


def _save_build_result(result, down, up, max_nodes):
    is_error = "error" in result
    is_success = not is_error and result.get("returncode") == 0
    st.session_state.last_build_result = {
        "topic": result.get("topic"),
        "returncode": result.get("returncode"),
        "status": "成功" if is_success else "失败",
        "progress_updates": result.get("progress_updates", []),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "error_fixes": result.get("error_fixes", []),
        "timestamp": time.time(),
        "build_params": {"down": down, "up": up, "max_nodes": max_nodes}
    }


def main():
    st.markdown("""
    <style>
    .stApp { background: #f8f9fc; }
    .stButton>button { background: linear-gradient(135deg,#4a6cf7,#6c5ce7); color: #fff; border: none; border-radius: 20px; transition: all .25s; }
    .stButton>button:hover { background: linear-gradient(135deg,#3451d1,#5b4bd5); box-shadow: 0 4px 12px rgba(74,108,247,.3); transform: translateY(-1px); }
    .stButton>button:active { transform: translateY(0) scale(.97); }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; padding: 8px 16px; }
    .stMetric { background: #fff; border-radius: 10px; padding: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.05); }
    h1, h2, h3 { color: #2d3436; }
    .stSidebar { background: #fff; }
    </style>
    """, unsafe_allow_html=True)

    st.title("📚 物理知识图谱系统")
    st.markdown("构建、验证和可视化物理知识图谱")

    with st.sidebar:
        st.header("配置")
        st.subheader("API配置")
        if not load_env_file():
            st.warning("未找到.env文件，请先运行安装脚本")

        api_key = st.text_input("DeepSeek API密钥",
                               value=os.environ.get("DEEPSEEK_API_KEY", ""),
                               type="password",
                               help="在DeepSeek官网获取API密钥")

        if api_key and api_key != os.environ.get("DEEPSEEK_API_KEY", ""):
            if api_key.startswith("sk-") or len(api_key) > 20:
                os.environ["DEEPSEEK_API_KEY"] = api_key
                _update_env_file("DEEPSEEK_API_KEY", api_key)
                st.success("API密钥已保存")
            else:
                st.warning("请输入有效的DeepSeek API密钥（以sk-开头）")

        st.subheader("构建参数")
        topic = st.text_input("主题", "伯努利方程",
                             help="输入要构建的物理主题，如：牛顿第二定律、热力学第一定律等")

        complexity_preset = st.selectbox(
            "复杂度预设",
            ["简单", "中等", "复杂", "超复杂"],
            index=1,
            help="根据复杂度自动调整参数"
        )

        preset_map = {
            "简单": {"down": 2, "up": 1, "max_nodes": 25},
            "中等": {"down": 3, "up": 2, "max_nodes": 50},
            "复杂": {"down": 5, "up": 3, "max_nodes": 100},
            "超复杂": {"down": 8, "up": 4, "max_nodes": 150},
        }
        preset = preset_map.get(complexity_preset, preset_map["中等"])

        down_levels = st.slider("向下展开层数", 1, 10, preset["down"],
                               help="向下依赖展开的层数（1-10，复杂主题建议5+，超复杂建议8+）")
        up_levels = st.slider("向上展开层数", 0, 5, preset["up"],
                             help="向上应用展开的层数（0-5）")
        max_nodes = st.slider("最大节点数", 15, 200, preset["max_nodes"],
                             help="图谱中最大节点数量（15-200，复杂主题建议100+）")

        current_model = os.environ.get("DEEPSEEK_MODEL_FLASH", "deepseek-chat")
        st.caption(f"当前模型: `{current_model}`")

        if st.button("开始构建", type="primary", use_container_width=True):
            if not api_key:
                st.error("请先输入DeepSeek API密钥")
            else:
                st.session_state.build_topic = topic
                st.session_state.build_down = down_levels
                st.session_state.build_up = up_levels
                st.session_state.build_max_nodes = max_nodes
                st.session_state.build_in_progress = True

        st.subheader("快速构建")
        st.markdown("选择预设主题快速构建：")

        test_topics = [
            ("牛顿第二定律", "🟢 牛顿第二定律", 2, 1, 25),
            ("伯努利方程", "🟢 伯努利方程", 2, 1, 25),
            ("热力学第一定律", "🟡 热力学第一定律", 3, 2, 40),
            ("麦克斯韦方程组", "🟡 麦克斯韦方程组", 3, 2, 50),
            ("薛定谔方程", "🔴 薛定谔方程", 5, 3, 80),
            ("纳维-斯托克斯方程", "🔴 纳维-斯托克斯方程", 5, 3, 100),
            ("爱因斯坦场方程", "🔴 爱因斯坦场方程", 5, 3, 100),
            ("杨-米尔斯场论", "🔴 杨-米尔斯场论", 5, 3, 100),
        ]

        test_col1, test_col2 = st.columns(2)
        for idx, (test_topic, btn_label, test_down, test_up, test_max) in enumerate(test_topics):
            col = test_col1 if idx % 2 == 0 else test_col2
            with col:
                if st.button(btn_label, use_container_width=True, key=f"test_{idx}"):
                    st.session_state.build_topic = test_topic
                    st.session_state.build_down = test_down
                    st.session_state.build_up = test_up
                    st.session_state.build_max_nodes = test_max
                    st.session_state.build_in_progress = True
                    st.rerun()

        st.subheader("系统状态")
        deps_ok, deps_msg = check_dependencies()
        if deps_ok:
            st.success("[OK] 依赖检查通过")
        else:
            st.error(f"[FAIL] {deps_msg}")

        st.subheader("快速链接")
        html_path = _find_artifact_path("artifacts/latest/graph.html")
        if html_path:
            if st.button("🌐 打开完整可视化界面", use_container_width=True):
                try:
                    import webbrowser
                    webbrowser.open(f'file://{html_path.absolute()}')
                    st.success(f"已在浏览器中打开: {html_path.name}")
                except Exception as e:
                    st.error(f"无法打开浏览器: {e}")
                    st.info(f"请手动打开文件: {html_path.absolute()}")

        if st.button("运行测试套件", use_container_width=True):
            st.info("测试运行中...")
            with st.spinner("运行测试..."):
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "-v"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    st.success("[OK] 所有测试通过！")
                else:
                    st.error(f"[FAIL] 测试失败\n\n{result.stderr}")

    tab1, tab2, tab3, tab4 = st.tabs(["🏗️ 构建", "📊 可视化", "📝 报告", "ℹ️ 关于"])

    with tab1:
        st.header("知识图谱构建")

        if "last_build_result" in st.session_state:
            col_btn1, col_btn2 = st.columns([1, 4])
            with col_btn1:
                show_details = st.button(
                    "📋 查看详细构建日志",
                    type="secondary", use_container_width=True,
                    help="点击展开/收起每个Agent的详细输出和构建进度"
                )
            with col_btn2:
                last_topic = st.session_state.last_build_result.get("topic", "")
                last_status = st.session_state.last_build_result.get("status", "未知")
                st.markdown(
                    f"<span style='color: #666;'>上次构建: <b>{last_topic}</b> | 状态: <b>{last_status}</b></span>",
                    unsafe_allow_html=True
                )

            if show_details:
                _display_detailed_build_log(st.session_state.last_build_result)
            st.divider()

        if "build_in_progress" in st.session_state and st.session_state.build_in_progress:
            topic = st.session_state.build_topic
            down = st.session_state.build_down
            up = st.session_state.build_up
            max_nodes_val = st.session_state.build_max_nodes

            st.info(f"正在构建主题: **{topic}**")
            st.write(f"参数: 向下{down}层, 向上{up}层, 最大{max_nodes_val}个节点")

            with st.status("构建中...", expanded=True) as status:
                progress_queue = queue.Queue()

                def progress_callback(progress_data):
                    progress_queue.put(progress_data)

                output_queue = queue.Queue()
                build_thread = threading.Thread(
                    target=run_build_process,
                    args=(topic, down, up, max_nodes_val, output_queue, progress_callback)
                )
                build_thread.start()

                progress_updates = []

                def display_progress_data(progress_data):
                    if progress_data.get("type") == "progress":
                        stage = progress_data.get("stage", "")
                        status_msg = progress_data.get("status", "")
                        message = progress_data.get("message", "")
                        status.update(label=f"构建中... [{stage}: {status_msg}]", state="running")
                        if status_msg == "started":
                            st.write(f"[开始] **{stage}**: {message}")
                        elif status_msg == "completed":
                            st.write(f"[完成] **{stage}**: {message}")
                        elif status_msg == "failed":
                            st.write(f"[失败] **{stage}**: {message}")
                        else:
                            st.write(f"[信息] **{stage}**: {message}")
                    elif progress_data.get("type") == "detail":
                        st.write(f"    {progress_data.get('key')}: {progress_data.get('value')}")
                    elif progress_data.get("type") == "error":
                        st.error(progress_data.get("message", ""))
                    elif progress_data.get("type") == "warning":
                        st.warning(progress_data.get("message", ""))

                while build_thread.is_alive():
                    try:
                        while True:
                            progress_data = progress_queue.get_nowait()
                            progress_updates.append(progress_data)
                            display_progress_data(progress_data)
                    except queue.Empty:
                        pass
                    time.sleep(0.1)

                try:
                    while True:
                        progress_data = progress_queue.get_nowait()
                        progress_updates.append(progress_data)
                        display_progress_data(progress_data)
                except queue.Empty:
                    pass

                build_thread.join()
                result = output_queue.get()
                result["progress_updates"] = progress_updates

                _save_build_result(result, down, up, max_nodes_val)
                st.session_state.build_in_progress = False

                if "error" in result:
                    status.update(label="构建失败", state="error")
                elif result.get("returncode") == 0:
                    status.update(label="构建完成", state="complete")
                else:
                    status.update(label="构建失败", state="error")

            _display_build_result(result)

        elif _find_artifact_path("artifacts/latest/graph.json"):
            st.info("检测到已有构建结果，点击上方按钮开始新的构建")
            if st.button("加载最新构建结果", use_container_width=True):
                if "graph_data" in st.session_state:
                    del st.session_state.graph_data
                st.rerun()
        else:
            st.info("输入主题和参数，点击「开始构建」按钮构建知识图谱")

    with tab2:
        st.header("图谱可视化")
        graph_data = load_graph_data()

        if graph_data:
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])
            st.subheader("交互式图谱")

            html_path = _find_artifact_path("artifacts/latest/graph.html")
            if html_path:
                try:
                    import streamlit.components.v1 as components
                    with open(html_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    components.html(html_content, height=800, scrolling=True)
                except Exception as e:
                    st.error(f"渲染可视化失败: {e}")
                    st.info("请尝试点击左侧边栏的「打开完整可视化界面」按钮")
                    if st.button("🌐 在新窗口中打开可视化", type="primary"):
                        try:
                            import webbrowser
                            webbrowser.open(f'file://{html_path.absolute()}')
                        except Exception:
                            st.warning("无法自动打开浏览器，请手动打开: " + str(html_path))
            else:
                st.warning("可视化文件未生成，请先完成构建")

            stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
            with stat_col1:
                st.metric("节点数", len(nodes))
            with stat_col2:
                st.metric("边数", len(edges))
            with stat_col3:
                canonical_path = graph_data.get("canonical_path")
                st.metric("规范路径", "有" if canonical_path else "无")
            with stat_col4:
                validation = graph_data.get("validation_summary", {})
                score = "通过" if validation.get("schema_valid") else "未通过"
                st.metric("验证状态", score)

            with st.expander("📊 图谱统计详情", expanded=False):
                detail_col1, detail_col2 = st.columns(2)
                with detail_col1:
                    st.markdown("**节点类型分布**")
                    node_type_counts = {}
                    for node in nodes:
                        nt = node.get("type", "unknown")
                        node_type_counts[nt] = node_type_counts.get(nt, 0) + 1
                    type_labels = {
                        "law": "定律", "equation": "方程", "concept": "概念",
                        "quantity": "物理量", "assumption": "假设", "math_tool": "数学工具",
                        "definition": "定义", "model": "模型", "application": "应用",
                        "experiment": "实验", "warning": "警告", "intuition_card": "直觉卡"
                    }
                    for nt, count in sorted(node_type_counts.items(), key=lambda x: -x[1]):
                        label = type_labels.get(nt, nt)
                        st.markdown(f"- **{label}** ({nt}): {count}")

                with detail_col2:
                    st.markdown("**边类型分布**")
                    edge_type_counts = {}
                    for edge in edges:
                        et = edge.get("type", "unknown")
                        edge_type_counts[et] = edge_type_counts.get(et, 0) + 1
                    edge_labels = {
                        "derives_from": "推导", "requires": "需要", "uses_math": "使用数学",
                        "assumes": "假设", "equivalent_to": "等价", "special_case_of": "特例",
                        "approximation_of": "近似", "applies_to": "应用于",
                        "motivated_by": "动机", "related_to": "相关"
                    }
                    for et, count in sorted(edge_type_counts.items(), key=lambda x: -x[1]):
                        label = edge_labels.get(et, et)
                        st.markdown(f"- **{label}** ({et}): {count}")

                    st.markdown("**层级分布**")
                    level_counts = {}
                    for node in nodes:
                        lvl = node.get("abstraction_level", 0)
                        level_counts[lvl] = level_counts.get(lvl, 0) + 1
                    for lvl in sorted(level_counts.keys()):
                        bar = "█" * level_counts[lvl]
                        st.markdown(f"L{lvl}: {bar} ({level_counts[lvl]})")
        else:
            st.info("暂无图谱数据，请先完成构建")

    with tab3:
        st.header("构建报告")
        report_content = load_report()
        st.markdown(report_content)

    with tab4:
        st.header("关于物理知识图谱系统")
        st.markdown("""
        ### 项目概述
        这是一个基于图结构的大学物理学习系统，支持知识点拆解、推导路径展示和假设显式化。

        ### 核心特性
        1. **受限知识库优先** - LLM只拼装，不从零发明
        2. **图与层级分离** - 底层是图，层级只是视图
        3. **假设显式化** - 推导边必须带assumptions
        4. **本地验证优先** - schema、DAG、量纲等必须本地验证
        5. **文件驱动与测试先行** - 所有中间结果落盘，失败有debug.json
        6. **多阶段扩展** - 复杂主题可达 100+ 节点
        7. **量化层级压缩** - 深层 DAG 自动压缩到 [0..10] 层级范围

        ### 系统架构
        ```
        用户输入 topic
        → RouterAgent：识别标准主题，确定学科域
        → PlannerAgent：制定展开计划（向下/向上层数、最大节点数）
        → RetrieverAgent：从本地知识库检索候选节点
        → DecomposerAgent：组装候选子图（多阶段LLM扩展）
          ├─ 初始骨架组装
          ├─ 多阶段扩展（达标前持续扩展）
          ├─ 层级约束与方向修复
          ├─ 环检测与打破
          ├─ 弱连通分量桥接
          └─ 量化层级压缩（>11层 → 0-10）
        → VerifierAgent：执行多项校验（Schema/DAG/假设/量纲/重复）
        → RankerAgent：选择canonical path
        → RendererAgent：输出最终工件（JSON/HTML/报告/本体）
        ```

        ### 数据模型
        - **节点类型** (12种): concept, quantity, definition, law, equation, model, assumption, math_tool, application, experiment, warning, intuition_card
        - **边类型** (10种): derives_from, requires, uses_math, assumes, equivalent_to, special_case_of, approximation_of, applies_to, motivated_by, related_to
        - **层级范围**: abstraction_level 0-10, pedagogical_level 1-10
        - **理论上下文**: classical, relativistic, quantum_intro, quantum_advanced, statistical, phenomenological

        ### 验证体系
        系统包含5个验证器：
        1. **Schema验证器** - JSON Schema 全字段校验
        2. **图结构验证器** - DAG无环、无悬空边、无孤立节点
        3. **假设验证器** - derives_from边必须有assumptions
        4. **量纲验证器** - 物理量量纲一致性
        5. **重复验证器** - 节点/边去重

        ### 测试覆盖
        - **381项逻辑压力测试** - 映射一致性、领域推断、层级推导、去重逻辑等
        - **63项复杂推导测试** - 广义相对论(91节点)、杨-米尔斯(82节点)、麦克斯韦(78节点)
        - **端到端构建测试** - 纳维-斯托克斯、狄拉克方程等高难度方程

        ### LLM配置
        当前统一使用 **DeepSeek V4 Flash** (`deepseek-chat`) 模型。
        所有任务（路由/规划/组装/扩展/排名）均使用同一模型，通过 `TaskComplexity` 评估任务复杂度。
        """)


if __name__ == "__main__":
    load_env_file()
    main()
