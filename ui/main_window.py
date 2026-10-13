# ui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QProgressBar, QFileDialog, QMessageBox,
    QLineEdit, QCheckBox
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QVariantAnimation, QEasingCurve, QEvent
)
from PySide6.QtGui import QIcon, QPixmap, QPainter
from pathlib import Path
from core import PDFtoPPTXConverter, get_app_dir


class RotatingArrowButton(QPushButton):
    """带动画的箭头按钮，绘制 arrow.png 并可以旋转"""
    def __init__(self, arrow_path, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self._angle = 0
        self._pixmap = QPixmap(arrow_path)
        if not self._pixmap.isNull():
            self._pixmap = self._pixmap.scaled(12, 12, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            self.setText("▶")
            self.setStyleSheet("font-size:14px; color:#87878F;")

        # 动画驱动器
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._anim.valueChanged.connect(self._on_anim_value_changed)

    def rotate_to(self, target_angle):
        """带动画旋转到目标角度"""
        self._anim.stop()
        self._anim.setStartValue(self._angle)
        self._anim.setEndValue(target_angle)
        self._anim.start()

    def _on_anim_value_changed(self, value):
        self._angle = value
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._pixmap and not self._pixmap.isNull():
            center = self.rect().center()
            painter.translate(center)
            painter.rotate(self._angle)
            painter.drawPixmap(
                -self._pixmap.width() // 2,
                -self._pixmap.height() // 2,
                self._pixmap
            )
        else:
            painter.drawText(self.rect(), Qt.AlignCenter, self.text())
        painter.end()


class ConvertThread(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, pdf_path, template_dir, output_path, target_ratio, zoom, cache_dir=None):
        super().__init__()
        self.pdf_path = pdf_path
        self.template_dir = template_dir
        self.output_path = output_path
        self.target_ratio = target_ratio
        self.zoom = zoom
        self.cache_dir = cache_dir

    def run(self):
        try:
            converter = PDFtoPPTXConverter(
                self.pdf_path, self.template_dir, self.output_path,
                self.target_ratio, zoom=self.zoom, cache_dir=self.cache_dir
            )

            def update_progress(current, total):
                percent = int((current / total) * 100)
                self.progress.emit(percent)

            result = converter.run_with_progress(update_progress)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF to PPTX Converter")
        self.setMinimumSize(600, 400)
        self.pdf_path = None
        self.output_dir = None

        # 窗口图标
        icon_path = Path(__file__).resolve().parent.parent / "icon" / "logo.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.init_ui()
        self.apply_style()

        # 事件过滤器，监听下拉菜单关闭
        self.ratio_combo.view().installEventFilter(self)
        self.quality_combo.view().installEventFilter(self)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 30, 40, 30)

        # ---- PDF 选择行 ----
        pdf_layout = QHBoxLayout()
        pdf_label = QLabel("PDF 文件：")
        self.pdf_path_edit = QLineEdit()
        self.pdf_path_edit.setReadOnly(True)
        self.pdf_path_edit.setPlaceholderText("未选择文件...")
        pdf_btn = QPushButton("选择 PDF")
        pdf_btn.clicked.connect(self.select_pdf)
        pdf_layout.addWidget(pdf_label)
        pdf_layout.addWidget(self.pdf_path_edit, 1)
        pdf_layout.addWidget(pdf_btn)
        main_layout.addLayout(pdf_layout)

        # ---- 比例检测显示 ----
        self.detect_label = QLabel("📐 检测比例：尚未检测")
        main_layout.addWidget(self.detect_label)

        # ---- 目标比例选择（带旋转箭头） ----
        arrow_path = str(Path(__file__).resolve().parent.parent / "icon" / "arrow.png")
        ratio_layout = QHBoxLayout()
        ratio_layout.addWidget(QLabel("目标 PPT 比例："))
        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems(["16:9", "16:10", "4:3", "A4"])
        self.ratio_combo.setCurrentText("16:9")
        # 隐藏自带的箭头
        self.ratio_combo.setStyleSheet("QComboBox::down-arrow { image: none; } QComboBox::drop-down { width: 0px; border: none; }")
        self.ratio_arrow = RotatingArrowButton(arrow_path)
        self.ratio_arrow.clicked.connect(lambda: self._show_combo_popup(self.ratio_combo, self.ratio_arrow))
        # 容器包裹，使其看起来像一个框
        self.ratio_container = self._wrap_combo_with_arrow(self.ratio_combo, self.ratio_arrow)
        ratio_layout.addWidget(self.ratio_container)
        ratio_layout.addStretch()
        main_layout.addLayout(ratio_layout)

        # ---- 清晰度选择（带旋转箭头） ----
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("图片清晰度："))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["极致（x10）", "高清（x5）", "标准（x2）"])
        self.quality_combo.setCurrentIndex(0)
        self.quality_combo.setStyleSheet("QComboBox::down-arrow { image: none; } QComboBox::drop-down { width: 0px; border: none; }")
        self.quality_arrow = RotatingArrowButton(arrow_path)
        self.quality_arrow.clicked.connect(lambda: self._show_combo_popup(self.quality_combo, self.quality_arrow))
        self.quality_container = self._wrap_combo_with_arrow(self.quality_combo, self.quality_arrow)
        quality_layout.addWidget(self.quality_container)
        quality_layout.addStretch()
        main_layout.addLayout(quality_layout)

        # ---- 输出路径 ----
        out_layout = QHBoxLayout()
        out_label = QLabel("输出位置：")
        self.out_path_edit = QLineEdit()
        self.out_path_edit.setReadOnly(True)
        self.out_path_edit.setPlaceholderText("默认同 PDF 目录...")
        self.out_btn = QPushButton("选择路径")
        self.out_btn.clicked.connect(self.select_output)
        out_layout.addWidget(out_label)
        out_layout.addWidget(self.out_path_edit, 1)
        out_layout.addWidget(self.out_btn)
        main_layout.addLayout(out_layout)

        # ---- 桌面保存选项 ----
        desktop_layout = QHBoxLayout()
        self.desktop_checkbox = QCheckBox("保存到桌面")
        self.desktop_checkbox.stateChanged.connect(self.toggle_output_to_desktop)
        desktop_layout.addWidget(self.desktop_checkbox)
        desktop_layout.addStretch()
        main_layout.addLayout(desktop_layout)

        # ---- 进度条 ----
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        main_layout.addWidget(self.progress)

        # ---- 转换按钮 ----
        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.setObjectName("convertBtn")
        self.convert_btn.clicked.connect(self.start_conversion)
        main_layout.addWidget(self.convert_btn, alignment=Qt.AlignCenter)

        # ---- 状态信息 ----
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

    def _wrap_combo_with_arrow(self, combo, arrow):
        """将箭头按钮用负边距叠加到 ComboBox 右侧，视觉上融为一体"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ComboBox 只隐藏原生箭头，其他样式完全不动
        combo.setStyleSheet("""
            QComboBox::down-arrow { image: none; }
            QComboBox::drop-down { width: 0px; border: none; }
        """)
        # 给文字右侧留出箭头空间，同时稍微增加上下内边距让文字更居中
        combo.setMinimumHeight(28)   # 适当加高
        combo.setStyleSheet(combo.styleSheet() + """
            QComboBox {
                padding-right: 28px;
                padding-top: 4px;
                padding-bottom: 4px;
            }
        """)

        # 设置最小宽度，保证文字完整显示（可根据实际最长文字调整）
        combo.setMinimumWidth(180)

        # 箭头按钮：透明背景，无边框，固定大小，用负左外边距盖在 ComboBox 右侧
        arrow.setFixedSize(24, 24)
        arrow.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                margin-left: -24px;   /* 向左移动自身宽度，叠加到 ComboBox 上 */
            }
        """)

        layout.addWidget(combo)
        layout.addWidget(arrow)
        return container

    def apply_style(self):
        style = """
        QMainWindow {
            background-color: #F5F5F7;
        }
        QLabel {
            color: #1D1D1F;
            font-size: 14px;
        }
        QLineEdit {
            background-color: #FFFFFF;
            border: 1px solid #D1D1D6;
            border-radius: 6px;
            padding: 6px;
            font-size: 13px;
        }
        QPushButton {
            background-color: #007AFF;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 8px 18px;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: #0062CC;
        }
        QPushButton:pressed {
            background-color: #004A99;
        }
        /* 容器样式，模拟原有的 QComboBox 外观 */
        /* QWidget#comboContainer {
            background-color: white;
            border: 1px solid #D1D1D6;
            border-radius: 8px;
        } */
        /* 下拉列表保持原有圆角样式 */
        QComboBox QAbstractItemView {
            background-color: white;
            border: 1px solid #D1D1D6;
            border-radius: 8px;
            padding: 4px;
            outline: none;
        }
        QComboBox QAbstractItemView::item {
            padding: 6px 12px;
            border-radius: 6px;
        }
        QComboBox QAbstractItemView::item:hover {
            background-color: #007AFF;
            color: white;
        }
        QProgressBar {
            border: none;
            border-radius: 3px;
            background-color: #E5E5EA;
            max-height: 6px;
        }
        QProgressBar::chunk {
            background-color: #007AFF;
            border-radius: 3px;
        }
        #convertBtn {
            background-color: #007AFF;
            font-weight: bold;
            font-size: 15px;
            padding: 10px 30px;
        }
        #convertBtn:hover {
            background-color: #0062CC;
        }
        """
        self.setStyleSheet(style)

    def select_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self.pdf_path = file_path
            self.pdf_path_edit.setText(file_path)
            try:
                import fitz
                doc = fitz.open(file_path)
                page = doc[0]
                w, h = page.rect.width, page.rect.height
                ratio = w / h
                if abs(ratio - 1.33) < 0.1:
                    detected = "4:3"
                elif abs(ratio - 1.77) < 0.1:
                    detected = "16:9"
                elif abs(ratio - 1.6) < 0.1:
                    detected = "16:10"
                elif abs(ratio - 1.41) < 0.1:
                    detected = "A4"
                else:
                    detected = f"{w:.0f}x{h:.0f}"
                self.detect_label.setText(f"📐 检测比例：{detected}")
                if detected in ["4:3", "16:9", "16:10", "A4"]:
                    self.ratio_combo.setCurrentText(detected)
            except Exception:
                self.detect_label.setText("检测比例失败")

    def select_output(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if dir_path:
            self.output_dir = dir_path
            self.out_path_edit.setText(dir_path)

    def toggle_output_to_desktop(self, state):
        if state:
            desktop = Path.home() / "Desktop"
            self.output_dir = str(desktop)
            self.out_path_edit.setText(str(desktop))
            self.out_path_edit.setEnabled(False)
            self.out_btn.setEnabled(False)
        else:
            self.output_dir = None
            self.out_path_edit.clear()
            self.out_path_edit.setPlaceholderText("默认同 PDF 目录...")
            self.out_path_edit.setEnabled(True)
            self.out_btn.setEnabled(True)

    def start_conversion(self):
        if not self.pdf_path:
            QMessageBox.warning(self, "警告", "请先选择 PDF 文件！")
            return

        pdf_path = Path(self.pdf_path)

        if self.desktop_checkbox.isChecked():
            out_dir = Path.home() / "Desktop"
        elif self.output_dir:
            out_dir = Path(self.output_dir)
        else:
            out_dir = pdf_path.parent
        output_file = out_dir / f"{pdf_path.stem}_converted.pptx"

        target_ratio = self.ratio_combo.currentText()
        zoom_map = {
            "极致（x10）": 10,
            "高清（x5）": 5,
            "标准（x2）": 2
        }
        zoom = zoom_map[self.quality_combo.currentText()]

        template_dir = Path(__file__).resolve().parent.parent / "template"
        app_dir = get_app_dir()
        cache_dir = app_dir / "cache"

        self.convert_btn.setEnabled(False)
        self.status_label.setText("转换中，请稍候...")
        self.progress.setValue(0)

        self.thread = ConvertThread(
            str(pdf_path),
            str(template_dir),
            str(output_file),
            target_ratio,
            zoom,
            cache_dir
        )
        self.thread.progress.connect(self.progress.setValue)
        self.thread.finished.connect(self.on_finished)
        self.thread.error.connect(self.on_error)
        self.thread.start()

    def on_finished(self, result):
        self.convert_btn.setEnabled(True)
        self.progress.setValue(100)
        self.status_label.setText(f"✅ 转换完成：{result}")

    def on_error(self, err_msg):
        self.convert_btn.setEnabled(True)
        self.progress.setValue(0)
        self.status_label.setText("转换失败")
        QMessageBox.critical(self, "错误", f"转换过程中出现错误：\n{err_msg}")

    def _show_combo_popup(self, combo, arrow):
        """显示下拉菜单并旋转箭头"""
        if combo.view().isVisible():
            combo.hidePopup()
            return
        arrow.rotate_to(90)
        combo.showPopup()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Hide:
            if watched == self.ratio_combo.view():
                self.ratio_arrow.rotate_to(0)
            elif watched == self.quality_combo.view():
                self.quality_arrow.rotate_to(0)
        return super().eventFilter(watched, event)