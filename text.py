import sys
import json
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDialog, QLineEdit, QDateTimeEdit, QFormLayout,
    QSizePolicy, QSystemTrayIcon, QMenu, QAction
)
from PyQt5.QtCore import Qt, QTimer, QDateTime
from PyQt5.QtGui import QIcon, QPixmap

class AddTaskDialog(QDialog):
    """添加任务的输入面板"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("添加任务")

        layout = QFormLayout()
        self.task_input = QLineEdit()
        self.deadline_input = QDateTimeEdit()
        # 显示到秒，便于点击选择小时/分钟/秒
        self.deadline_input.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.deadline_input.setDateTime(QDateTime.currentDateTime())
        self.deadline_input.setCalendarPopup(True)
        # 显示上下箭头，使用户可以点击增减时间段
        from PyQt5.QtWidgets import QAbstractSpinBox
        try:
            self.deadline_input.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
        except Exception:
            pass
        # 强调可以点击调整
        self.deadline_input.setToolTip("点击或使用上下箭头调整 年/月/日 时:分:秒")

        layout.addRow("任务内容：", self.task_input)
        layout.addRow("目标时间：", self.deadline_input)

        self.ok_btn = QPushButton("确认")
        self.ok_btn.clicked.connect(self.accept)
        layout.addWidget(self.ok_btn)

        self.setLayout(layout)

    def get_data(self):
        return self.task_input.text().strip(), self.deadline_input.dateTime()

class TodoItem(QWidget):
    def __init__(self, text, deadline, parent=None):
        super().__init__(parent)
        self.deadline = deadline

        layout = QHBoxLayout()
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(8)
        self.setLayout(layout)

        # 任务内容（允许自动换行、字体更醒目）
        self.label = QLabel(text)
        self.label.setWordWrap(True)  # 自动换行
        self.label.setStyleSheet("font-size:15px; font-weight:600; color:white;")
        self.label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout.addWidget(self.label, stretch=3)

        # 剩余时间 — 保持固定宽度以约束任务文本宽度
        self.time_label = QLabel("")
        self.time_label.setFixedWidth(62)
        self.time_label.setStyleSheet("font-size:12px; color:#FFD700;")
        layout.addWidget(self.time_label, stretch=0, alignment=Qt.AlignCenter)

        # 完成按钮
        self.done_btn = QPushButton("✔")
        self.done_btn.setFixedSize(28, 22)
        self.done_btn.setStyleSheet("""
            QPushButton {
                background-color: #8bc34a;
                color: white;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #7cb342; }
        """)
        self.done_btn.clicked.connect(self.mark_done)
        layout.addWidget(self.done_btn)

        # 倒计时刷新 — 把 QTimer 的 parent 设为 self，确保随 widget 销毁
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()

        # 行样式：扁平（保持不太不透明）
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 30);
                border-radius: 6px;
            }
        """)

        # 防止垂直拉伸，固定高度（允许多行时高度随内容增长）
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setMinimumHeight(30)

    def update_time(self):
        now = QDateTime.currentDateTime()
        remaining = now.secsTo(self.deadline)
        if remaining > 0:
            h = remaining // 3600
            m = (remaining % 3600) // 60
            self.time_label.setText(f"{h:02d}:{m:02d}")
        else:
            self.time_label.setText("超时")

    def mark_done(self):
        try:
            if hasattr(self, "timer") and self.timer.isActive():
                self.timer.stop()
        except Exception:
            pass
        self.deleteLater()

    def __del__(self):
        # 不需要手动停止 QTimer，PyQt 会自动处理
        pass

class StickyNote(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Todo")
        self.setGeometry(200, 200, 280, 380)

        # 隐藏任务栏图标，设置为工具窗口
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 拖动
        self.dragging = False
        self.locked = False

        # 主布局
        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)

        bg = QWidget()
        bg.setStyleSheet("""
            QWidget {
                /* 整体透明度增加一点：把 alpha 从 200 降低到 150 */
                background-color: rgba(60, 60, 60, 150);
                border-radius: 12px;
            }
        """)
        wrapper.addWidget(bg)

        self.layout = QVBoxLayout(bg)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(6)

        # 顶部栏
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        self.lock_btn = QPushButton("🔓")
        self.lock_btn.setFixedSize(32, 28)
        self.lock_btn.setStyleSheet(self.btn_style())
        self.lock_btn.clicked.connect(self.toggle_lock)
        top_bar.addWidget(self.lock_btn, alignment=Qt.AlignLeft)

        self.add_btn = QPushButton("➕")
        self.add_btn.setFixedSize(36, 30)
        # 右上角加号样式：浅白、字体更醒目
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.6);
                color: #111;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.75);
            }
        """)
        self.add_btn.clicked.connect(self.add_task)
        top_bar.addWidget(self.add_btn, alignment=Qt.AlignRight)

        self.layout.addLayout(top_bar)

        # 任务区
        self.task_area = QVBoxLayout()
        self.task_area.setSpacing(4)
        self.task_area.setAlignment(Qt.AlignTop)  # 任务从顶部对齐
        self.layout.addLayout(self.task_area)

        # 添加伸展项，将内容推到顶部
        self.layout.addStretch(1)

        # 系统托盘：父对象设为 QApplication.instance()，避免窗口销毁时托盘一起被删除
        placeholder_icon = QPixmap(32, 32)
        placeholder_icon.fill(Qt.black)  # 填充为黑色
        self.tray_icon = QSystemTrayIcon(QIcon(placeholder_icon), QApplication.instance())
        self.tray_icon.setToolTip("Todo App")
        tray_menu = QMenu()
        show_action = QAction("显示", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)
        add_task_action = QAction("添加任务", self)
        add_task_action.triggered.connect(self.add_task)
        tray_menu.addAction(add_task_action)
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.quit)
        tray_menu.addAction(exit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # 加载保存的任务
        self.load_tasks()

    def btn_style(self):
        return """
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                color: white;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.3);
            }
        """

    def add_task(self):
        try:
            print("DEBUG: open AddTaskDialog")  # 调试输出
            dialog = AddTaskDialog()
            if dialog.exec_():
                print("DEBUG: dialog accepted")
                text, deadline = dialog.get_data()
                print(f"DEBUG: got data: text({len(text)}) deadline({deadline.toString() if isinstance(deadline, QDateTime) else str(deadline)})")
                if text:
                    item = TodoItem(text, deadline, parent=self)
                    item.done_btn.clicked.connect(self.save_tasks)
                    self.task_area.addWidget(item)
                    self.task_area.update()
                    self.save_tasks()
                    self.show()
                    print("DEBUG: task added and UI updated")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"添加任务异常: {e}")

    def toggle_lock(self):
        self.locked = not self.locked
        self.lock_btn.setText("🔒" if self.locked else "🔓")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.locked:
            self.dragging = True
            self.drag_start = event.globalPos() - self.pos()

    def mouseMoveEvent(self, event):
        if self.dragging and not self.locked:
            self.move(event.globalPos() - self.drag_start)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False

    def save_tasks(self):
        tasks = []
        for i in range(self.task_area.count()):
            widget = self.task_area.itemAt(i).widget()
            if widget and isinstance(widget, TodoItem):
                tasks.append({
                    "text": widget.label.text(),
                    "deadline": widget.deadline.toString(Qt.ISODate)
                })
        try:
            tasks_file = os.path.expanduser("~/tasks.json")
            with open(tasks_file, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=2, ensure_ascii=False)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error saving tasks: {e}")

    def load_tasks(self):
        try:
            tasks_file = os.path.expanduser("~/tasks.json")
            if os.path.exists(tasks_file):
                # 指定 utf-8-sig 以兼容可能存在的 BOM，并确保正确解码
                with open(tasks_file, "r", encoding="utf-8-sig") as f:
                    try:
                        tasks = json.load(f)
                    except Exception:
                        # 退回到宽松读取，避免整个程序崩溃
                        f.seek(0)
                        raw = f.read()
                        try:
                            tasks = json.loads(raw)
                        except Exception:
                            print("Error parsing tasks.json, ignoring contents")
                            tasks = []

                for task in tasks:
                    text = task.get("text", "")
                    deadline_str = task.get("deadline", "")
                    deadline = QDateTime.fromString(deadline_str, Qt.ISODate)
                    if text:
                        item = TodoItem(text, deadline)
                        item.done_btn.clicked.connect(self.save_tasks)
                        self.task_area.addWidget(item)
                self.task_area.update()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error loading tasks: {e}")

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def quit(self):
        # 保存任务并停止所有定时器
        try:
            self.save_tasks()
        except Exception:
            pass

        for i in range(self.task_area.count()):
            widget = self.task_area.itemAt(i).widget()
            if widget and isinstance(widget, TodoItem):
                try:
                    if hasattr(widget, "timer") and widget.timer.isActive():
                        widget.timer.stop()
                except Exception:
                    pass

        # 隐藏并移除托盘图标，防止 Windows 上图标残留
        try:
            if hasattr(self, "tray_icon") and isinstance(self.tray_icon, QSystemTrayIcon):
                self.tray_icon.hide()
                self.tray_icon.setContextMenu(None)
        except Exception:
            pass

        QApplication.quit()

if __name__ == "__main__":
    try:
        import faulthandler, sys
        # 在打包为 exe 时 sys.stderr 可能为 None，只有在可用时才启用 faulthandler
        if getattr(sys, "stderr", None):
            faulthandler.enable()
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 禁止最后一个窗口关闭时退出
    window = StickyNote()
    window.show()
    sys.exit(app.exec_())