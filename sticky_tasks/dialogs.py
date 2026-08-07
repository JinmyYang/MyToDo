"""提示弹窗统一入口。

QMessageBox 以带自定义样式的窗口为父对象时,会继承其深色主题
QSS——浅色文字落在系统浅灰背景的弹窗上,对比度极低。这里统一
给弹窗设一段"空规则"样式表,切断样式继承,恢复系统默认外观。
"""

from PySide6.QtWidgets import QMessageBox

# 空规则不能切断继承:弹窗自身样式表未定义的属性会继续向上命中
# 父窗口的深色主题规则。必须显式写回系统调色板颜色(palette() 角色,
# 浅色/深色系统主题下都正确),才能压住继承来的深色主题文字色。
_NEUTRAL_QSS = (
    "QMessageBox { background: palette(window); }"
    "QLabel { color: palette(window-text); background: transparent; }"
    "QPushButton { color: palette(button-text); }"
)


def message_box(parent=None) -> QMessageBox:
    """创建样式中立的 QMessageBox(自定义按钮的弹窗用这个)。"""
    box = QMessageBox(parent)
    box.setStyleSheet(_NEUTRAL_QSS)
    return box


def warning(parent, title, text):
    box = message_box(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    return box.exec()


def critical(parent, title, text):
    box = message_box(parent)
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle(title)
    box.setText(text)
    return box.exec()


def information(parent, title, text):
    box = message_box(parent)
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle(title)
    box.setText(text)
    return box.exec()


def question(parent, title, text, default=QMessageBox.No):
    box = message_box(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.addButton(QMessageBox.Yes)
    box.addButton(QMessageBox.No)
    box.setDefaultButton(default)
    box.exec()
    return box.standardButton(box.clickedButton())
