# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：MyToDo（onedir 模式）。

必须用 onedir：onefile 模式 sys.executable 指向临时解压目录，
用户数据（.sticky_tasks）每次启动都会丢。

打包命令：python -m PyInstaller mytodo.spec
产物：dist/MyToDo/MyToDo.exe
"""

# assets/icon.ico 放到产物根目录的 assets/ 下,
# 与 main.py 的 software_dir()/assets/icon.ico 路径一致
datas = [("assets/icon.ico", "assets")]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest"],  # 剔除开发/测试依赖
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MyToDo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,            # 不弹控制台黑窗
    icon="assets/icon.ico",
    version="version_info.txt",  # exe 右键属性里的版本信息
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MyToDo",
)
