# MyToDo —— 桌面任务便签

一个本地运行的 Windows 桌面任务便签软件,半透明无边框地显示在桌面上,能看到壁纸,类似精简版 Microsoft To Do。

**🌐 官网 / 下载**：https://jinmyyang.github.io/MyToDo/ （免安装，解压即用）

## 功能

- 📌 **半透明无边框**:无边框、半透明、能看到壁纸
- ✏️ **快速编辑**:双击任务文字进入编辑,回车保存、Shift+回车换行
- ➕ **一键新建**:点任务列表末尾的 `+` 或按 `Ctrl+N` 创建任务并自动聚焦输入
- ✅ **点圆点完成**:点任务左侧小圆点 → 任务从桌面消失 → 进入"已完成"隐藏栏
- ↩️ **一键恢复**:展开"已完成"栏,点 ↩ 把任务恢复回主列表
- 💾 **持久化**:数据存 JSON,关掉重开任务还在,不过夜刷新
- 🎨 **外观设置**:自定义主题、字体、字号和透明度
- 🔒 **锁定模式**:隐藏编辑控件,避免误操作;窗口边缘支持八方向缩放
- 🗂️ **历史任务**:已完成和已删除任务统一管理,支持批量恢复或永久删除
- 🔎 **字体搜索**:输入字体名即可筛选,不再显示字体符号预览
- 🎨 **自定义预设**:颜色与外观可保存为自己的预设,自定义色会记住
- 📐 **记住窗口**:重启后恢复上次的位置和大小
- 🔄 **检查更新**:设置窗口内一键检查新版本(对接 GitHub Releases)
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

首次运行会在软件所在目录的 `.sticky_tasks/tasks.json` 创建数据文件。

## 使用

| 操作 | 方式 |
|---|---|
| 新建任务 | 点任务列表末尾的 `+`,输入文字,回车或点别处保存 |
| 编辑任务 | 双击任务文字,或右键任务文字 → 编辑 |
| 完成任务 | 点任务左侧的圆点 → 任务消失,进入已完成栏 |
| 查看已完成 | 点底部"已完成 (N)"展开/收起 |
| 恢复任务 | 在已完成栏点任务右侧的 ↩ |
| 删除任务 | 右键任务或已完成任务 → 删除(移入历史任务) |
| 移动便签 | 拖动标题栏空白处 |
| 调整大小 | 拖动窗口边缘或四角 |
| 锁定/解锁 | 点标题栏右侧锁头或按 `Ctrl+L`;锁定后移入窗口可再次看到锁头 |
| 历史任务 | 设置 → 查看历史任务;可批量恢复或永久删除 |
| 外观设置 | 点右下角齿轮;字体输入框可搜索,可保存自定义预设 |
| 退出 | 右键标题栏空白处 → 退出 |

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

测试覆盖数据持久化、损坏文件恢复、外观设置以及主要 GUI 交互流程。

## 技术栈

- **Python 3.13** + **PySide6 6.11**(Qt for Python)
- 数据持久化:JSON(`软件目录/.sticky_tasks/tasks.json`)
- 测试:pytest

## 目录结构

```
project0711/
├── main.py                  # 入口
├── requirements.txt
├── assets/
│   └── icon.ico             # 应用图标
├── sticky_tasks/
│   ├── app_paths.py         # 数据/日志等路径解析
│   ├── task_store.py        # 数据层(Task / TaskStore)
│   ├── json_io.py           # 原子文件写入
│   ├── app_settings.py      # 外观设置模型与主题派生
│   ├── updater.py           # 检查更新(GitHub Releases API)
│   ├── task_item.py         # 任务项 widget(圆点 + 可编辑文本)
│   ├── completed_panel.py   # 已完成面板
│   ├── history_window.py    # 历史任务批量管理窗口
│   ├── settings_dialog.py   # 外观设置窗口
│   └── main_window.py       # 主窗口(半透明/无边框/拖动/缩放)
└── tests/
    ├── test_app_settings.py # 外观设置测试
    ├── test_task_store.py   # 数据层单测
    ├── test_updater.py      # 检查更新测试
    └── test_gui_smoke.py    # GUI 冒烟测试
```

## 设计要点

- **数据与 UI 分离**:`TaskStore` 不依赖 Qt,可单独测试;UI 只在交互时调用 store。
- **半透明 + 圆角**:窗口 `WA_TranslucentBackground` + 容器 `rgba` 背景,文字保持不透明清晰;圆角外区域透明。
- **拖动**:无边框窗口重写鼠标事件,点标题栏空白处拖动。
- **空任务自清理**:新建留空的任务在失焦/完成时删除,避免空行堆积。
