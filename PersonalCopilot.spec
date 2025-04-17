# -*- mode: python ; coding: utf-8 -*-

# 配置文件用于 PyInstaller 打包 Personal Copilot 项目

a = Analysis(
    ['main.py'],  # 入口文件
    pathex=['d:\\living\\skill\\living skills\\coding skill\\llm_latest'],  # 项目路径，确保 PyInstaller 能找到所有模块
    binaries=[],  # 可选：指定需要包含的二进制文件
    datas=[
        ('yellow_theme.json', '.'),  # 主题文件
        ('.env', '.'),  # 环境变量文件
    ],  # 需要包含的资源文件
    hiddenimports=[
        'customtkinter',  # 确保 UI 库被包含
        'customtkinter.windows',  # 包含 Windows 相关子模块
        'customtkinter.windows.widgets',  # 包含 widgets 子模块
        'customtkinter.windows.widgets.theme',  # 包含 theme 子模块
        'customtkinter.windows.widgets.utility',  # 包含 utility 子模块
        'PIL',  # 图像处理库
        'PIL.Image',  # 确保 PIL 的子模块被包含
        'PIL.ImageTk',  # 确保 PIL 的 ImageTk 子模块被包含
        'openai',  # API 客户端库
        'requests',  # 网络请求库
        'tavily',  # 搜索 API 库，注意：可能需要根据 API 变更调整
        'python-dotenv',  # 环境变量加载库
    ],  # 手动指定可能未被自动检测到的依赖模块
    hookspath=[],  # 自定义钩子路径（可选）
    hooksconfig={},  # 钩子配置（可选）
    runtime_hooks=[],  # 运行时钩子（可选）
    excludes=[],  # 排除的模块（可选）
    noarchive=False,  # 是否禁用归档
    optimize=0,  # 优化级别，0 表示不优化
)
pyz = PYZ(a.pure)  # 创建 PYZ 归档文件，包含纯 Python 代码

exe = EXE(
    pyz,  # PYZ 归档文件
    a.scripts,  # 脚本文件
    a.binaries,  # 二进制文件
    a.datas,  # 数据文件
    [],  # 其他依赖项（可选）
    name='PersonalCopilot',  # 输出文件名
    debug=False,  # 是否启用调试模式
    bootloader_ignore_signals=False,  # 是否忽略 bootloader 信号
    strip=False,  # 是否剥离符号表（减小文件大小）
    upx=True,  # 是否使用 UPX 压缩（减小文件大小）
    upx_exclude=[],  # UPX 排除的文件
    runtime_tmpdir=None,  # 运行时临时目录（可选）
    console=False,  # 不显示控制台窗口（适用于 GUI 应用）
    disable_windowed_traceback=False,  # 是否禁用窗口模式的回溯
    argv_emulation=False,  # 是否模拟 argv
    target_arch=None,  # 目标架构（可选）
    codesign_identity=None,  # 代码签名身份（适用于 macOS）
    entitlements_file=None,  # 权限文件（适用于 macOS）
    icon=['d:\\living\\skill\\living skills\\coding skill\\llm_latest\\Dango.ico'],  # 图标文件，确保文件存在于项目目录中
)
