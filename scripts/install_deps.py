#!/usr/bin/env python
"""
一键安装依赖脚本
使用清华镜像源快速安装所有依赖
"""
import subprocess
import sys
import os

def install_requirements():
    """安装requirements.txt中的依赖"""
    print("正在安装项目依赖...")

    # 获取项目根目录（脚本在scripts/子目录下）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    requirements_path = os.path.join(project_dir, "requirements.txt")

    if not os.path.exists(requirements_path):
        print(f"错误: 找不到 requirements.txt 文件: {requirements_path}")
        return False

    # 使用清华镜像源
    cmd = [
        sys.executable, "-m", "pip", "install",
        "-r", requirements_path,
        "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("安装成功！")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"安装失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False

def install_additional_deps():
    """安装前端应用额外依赖"""
    print("\n正在安装前端应用额外依赖...")

    # Streamlit用于前端界面
    extra_deps = [
        "streamlit>=1.28.0",
        "watchdog>=3.0.0",
    ]

    for dep in extra_deps:
        cmd = [
            sys.executable, "-m", "pip", "install",
            dep,
            "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"
        ]

        try:
            print(f"安装 {dep}...")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"  [OK] {dep} 安装成功")
        except subprocess.CalledProcessError as e:
            print(f"  [FAIL] {dep} 安装失败: {e}")
            return False

    return True

def check_dependencies():
    """检查关键依赖是否已安装"""
    print("\n检查关键依赖...")

    required_modules = [
        "openai",
        "pydantic",
        "jsonschema",
        "networkx",
        "sympy",
        "yaml",
        "dotenv",
        "jinja2",
        "streamlit",
    ]

    all_installed = True
    for module in required_modules:
        try:
            __import__(module)
            print(f"  [OK] {module}")
        except ImportError:
            print(f"  [FAIL] {module} 未安装")
            all_installed = False

    return all_installed

def setup_environment():
    """设置环境"""
    print("\n设置环境...")

    # 检查.env文件
    env_file = os.path.join(project_dir, ".env")
    env_example_file = os.path.join(project_dir, ".env.example")

    if not os.path.exists(env_file):
        print("创建.env配置文件...")
        if os.path.exists(env_example_file):
            with open(env_example_file, "r", encoding="utf-8") as f:
                example_content = f.read()

            with open(env_file, "w", encoding="utf-8") as f:
                f.write(example_content)
            print(f"  [OK] 已创建 {env_file}，请编辑此文件填入DeepSeek API密钥")
        else:
            print(f"  [WARN] 找不到 .env.example 文件，将创建空的 .env 文件")
            with open(env_file, "w", encoding="utf-8") as f:
                f.write("# DeepSeek API配置\nDEEPSEEK_API_KEY=\n")
            print(f"  [OK] 已创建空的 {env_file}，请编辑此文件填入DeepSeek API密钥")
    else:
        print(f"  [OK] {env_file} 已存在")

    # 确保artifacts目录存在
    artifacts_dir = os.path.join(project_dir, "artifacts")
    if not os.path.exists(artifacts_dir):
        os.makedirs(artifacts_dir)
        print(f"  [OK] 创建 {artifacts_dir} 目录")

    latest_dir = os.path.join(artifacts_dir, "latest")
    if not os.path.exists(latest_dir):
        os.makedirs(latest_dir)
        print(f"  [OK] 创建 {latest_dir} 目录")

def main():
    """主函数"""
    print("=" * 60)
    print("物理知识图谱系统 - 依赖安装")
    print("=" * 60)

    # 安装项目依赖
    if not install_requirements():
        print("项目依赖安装失败，请检查网络连接")
        sys.exit(1)

    # 安装前端额外依赖
    if not install_additional_deps():
        print("前端依赖安装失败")
        sys.exit(1)

    # 检查依赖
    if not check_dependencies():
        print("部分依赖未安装成功，请手动安装")
        sys.exit(1)

    # 设置环境
    setup_environment()

    print("\n" + "=" * 60)
    print("安装完成！")
    print("\n下一步：")
    print("1. 编辑 .env 文件，填入您的 DeepSeek API 密钥")
    print("2. 运行 python run.py 启动前端应用")
    print("3. 在浏览器中输入提示的URL访问应用")
    print("=" * 60)

if __name__ == "__main__":
    main()