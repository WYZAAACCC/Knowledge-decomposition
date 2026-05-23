#!/usr/bin/env python
"""
启动物理知识图谱前端应用
"""
import subprocess
import sys
import os

# 设置控制台编码为UTF-8，避免中文字符编码问题
if sys.platform.startswith('win'):
    try:
        # Windows下尝试设置控制台编码
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, LookupError):
        # 如果reconfigure不可用，尝试其他方法
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

def main():
    """主函数"""
    print("=" * 60)
    print("物理知识图谱系统 - 前端启动")
    print("=" * 60)

    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 检查依赖
    try:
        import streamlit
        print("[OK] Streamlit 已安装")
    except ImportError:
        print("[FAIL] Streamlit 未安装，请运行 install_deps.py")
        sys.exit(1)

    # 检查.env文件
    env_file = os.path.join(script_dir, ".env")
    if not os.path.exists(env_file):
        print("[WARN] 未找到 .env 文件，将使用默认环境变量")
        print("   您可以在前端界面中设置 DeepSeek API 密钥")

    # 检查app.py文件
    app_file = os.path.join(script_dir, "app.py")
    if not os.path.exists(app_file):
        print(f"[FAIL] 找不到 app.py 文件: {app_file}")
        sys.exit(1)

    # 启动Streamlit应用
    print("[RUN] 启动前端应用...")
    print("   请在浏览器中打开提示的URL（通常是 http://localhost:8501）")
    print("   按 Ctrl+C 停止应用")
    print("=" * 60)

    # 运行streamlit，使用绝对路径
    subprocess.run([sys.executable, "-m", "streamlit", "run", app_file])

if __name__ == "__main__":
    main()