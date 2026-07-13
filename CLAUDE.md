# CLAUDE.md

本文件是 Claude Code 在本仓库工作时的项目指南。Claude 每次会话都会自动读取它。

## 项目概述

project0711 — 一个**桌面任务便签软件**(本地运行,Windows 自用)。

- 半透明、无边框、普通窗口层级(非置顶),能看到壁纸
- 点加号创建任务,任务文本可直接在桌面上编辑
- 点任务左侧小圆点 → 任务从桌面消失并标记完成 → 进入"已完成"隐藏栏
- 已完成栏可展开,一键把任务恢复回主列表
- 数据持久化到 JSON,关掉重开任务还在(不过夜刷新)
- 不需要用户管理、不需要每日重置

- **状态**: 开发中
- **维护**: 一人项目

## 技术栈

- 语言: Python 3.13
- GUI 框架: PySide6 (Qt for Python) 6.11
- 数据持久化: JSON 文件(存于 `~/.sticky_tasks/tasks.json`)
- 测试: pytest
- 包管理: pip + requirements.txt

## 目录结构

```
project0711/
├── CLAUDE.md            # 本文件
├── README.md
├── requirements.txt
├── main.py              # 入口:启动 QApplication + MainWindow
├── sticky_tasks/        # 应用包
│   ├── __init__.py
│   ├── task_store.py        # 数据层:Task / TaskStore(增删、完成、恢复、JSON 持久化)
│   ├── task_item.py         # UI:单个任务项(圆点 + 可编辑文本)
│   ├── main_window.py       # UI:主窗口(半透明/无边框/置顶/拖动/列表/加号)
│   └── completed_panel.py   # UI:已完成面板(恢复任务)
└── tests/
    ├── test_task_store.py   # 数据层单元测试
    └── test_gui_smoke.py    # GUI 冒烟测试(offscreen 平台)
```

## 常用命令

```bash
# 安装依赖
python -m pip install -r requirements.txt

# 运行(开发模式)
python main.py

# 运行测试(用 -m 确保 sticky_tasks 包可被 import)
python -m pytest tests/ -v

# 只跑数据层单测
python -m pytest tests/test_task_store.py -v

# 无界面冒烟测试(GUI 逻辑,不弹窗)
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_gui_smoke.py -v
```

## 架构要点

- **数据与 UI 分离**:`TaskStore` 只管数据和持久化,不依赖 Qt UI;`MainWindow` 持有 store 并在 UI 交互时调用它。这使数据层可单独单测。
- **任务对象同一引用**:`TaskItem.task` 与 `store.tasks` 中的对象是同一个,UI 改文本时本地与 store 同步。
- **完成动作的边界**:空任务被点完成时直接删除,不进已完成栏(避免空任务堆积)。
- **圆点不抢焦点**:`TaskItem.dot` 设 `Qt.NoFocus`,点完成时不会触发文本框的 `editingFinished`,避免完成与保存逻辑冲突。

## 开发约定

- **语言**: 与用户交流用中文,代码、命令、标识符用英文。
- **代码风格**: 匹配现有文件风格(4 空格缩进、双引号字符串、模块级 docstring)。
- **改动前先看**: 修改既有代码前先读取相关文件,匹配周围风格。
- **不过度工程**: 优先简单可读的实现;这是自用小工具,不引入非必要依赖。
- **验证再报告**: 说"完成"前实际运行过测试;失败就如实说明,不粉饰。

## 环境备注

- 操作系统: Windows 11,Shell 为 Git Bash(POSIX 语法)。
  - 路径用正斜杠 `/`,空设备用 `/dev/null` 而非 `NUL`。
  - 环境变量用 `$VAR`,不用 `%VAR%` 或 `$env:VAR`。
- GUI 测试在无头环境用 `QT_QPA_PLATFORM=offscreen`,不弹真实窗口。
- 需要用户亲自执行的命令(如交互式登录),建议用 `! <command>` 在会话中运行。

## Claude 工作约定

- 优先使用专用工具(Read/Edit/Glob/Grep)而非等价的 shell 命令。
- 路径引用用 `file_path:line_number` 格式,便于点击跳转。
- 涉及不可逆或对外的操作前先确认,除非已获明确授权。
- 不确定时先给建议再行动,不要罗列不会采用的方案。
