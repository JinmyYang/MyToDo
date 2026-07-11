# 桌面任务便签

一个本地运行的 Windows 桌面任务便签软件,半透明置顶在桌面上,能看到壁纸,类似精简版 Microsoft To Do。

## 功能

- 📌 **半透明置顶**:无边框、半透明、常驻桌面顶层,能看到壁纸
- ✏️ **直接编辑**:任务文本在桌面上直接点击编辑
- ➕ **一键新建**:点 `+` 创建任务并自动聚焦输入
- ✅ **点圆点完成**:点任务左侧小圆点 → 任务从桌面消失 → 进入"已完成"隐藏栏
- ↩️ **一键恢复**:展开"已完成"栏,点 ↩ 把任务恢复回主列表
- 💾 **持久化**:数据存 JSON,关掉重开任务还在,不过夜刷新
- 🚫 **无登录、无用户管理、无每日重置**:开箱即用

## 安装

需要 Python 3.10+(在 3.13 上开发)。

```bash
python -m pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

首次运行会在 `~/.sticky_tasks/tasks.json` 创建数据文件。

## 使用

| 操作 | 方式 |
|---|---|
| 新建任务 | 点右上方 `+`,输入文字,回车或点别处保存 |
| 编辑任务 | 直接点击任务文字 |
| 完成任务 | 点任务左侧的圆点 → 任务消失,进入已完成栏 |
| 查看已完成 | 点底部"已完成 (N)"展开/收起 |
| 恢复任务 | 在已完成栏点任务右侧的 ↩ |
| 移动便签 | 拖动标题栏空白处 |
| 关闭 | 点标题栏 `✕`(数据已自动保存) |

> 新建后留空(没输入文字)的任务,在失焦或完成时会被自动删除,不会留下空行。

## 测试

```bash
# 全部测试(数据层单测 + GUI 冒烟)
python -m pytest tests/ -v

# 仅数据层
python -m pytest tests/test_task_store.py -v

# GUI 冒烟(无界面,不弹窗)
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_gui_smoke.py -v
```

共 13 个测试:10 个数据层单测 + 3 个 GUI 冒烟(创建/完成/恢复/编辑/持久化全流程)。

## 技术栈

- **Python 3.13** + **PySide6 6.11**(Qt for Python)
- 数据持久化:JSON(`~/.sticky_tasks/tasks.json`)
- 测试:pytest

## 目录结构

```
project0711/
├── main.py                  # 入口
├── requirements.txt
├── sticky_tasks/
│   ├── task_store.py        # 数据层(Task / TaskStore)
│   ├── task_item.py         # 任务项 widget(圆点 + 可编辑文本)
│   ├── main_window.py       # 主窗口(半透明/无边框/置顶/拖动)
│   └── completed_panel.py   # 已完成面板
└── tests/
    ├── test_task_store.py   # 数据层单测
    └── test_gui_smoke.py    # GUI 冒烟测试
```

## 设计要点

- **数据与 UI 分离**:`TaskStore` 不依赖 Qt,可单独测试;UI 只在交互时调用 store。
- **半透明 + 圆角**:窗口 `WA_TranslucentBackground` + 容器 `rgba` 背景,文字保持不透明清晰;圆角外区域透明。
- **拖动**:无边框窗口重写鼠标事件,点标题栏空白处拖动。
- **空任务自清理**:新建留空的任务在失焦/完成时删除,避免空行堆积。
