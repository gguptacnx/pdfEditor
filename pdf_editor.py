import sys
import os
import fitz  # PyMuPDF
import tempfile
import shutil
from PyQt6.QtWidgets import (
    QColorDialog, QToolBar, QComboBox, QSpinBox, QLineEdit, QCheckBox,
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QTextEdit,
    QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem, QInputDialog
)
from PyQt6.QtGui import QPixmap, QImage, QColor, QPen, QBrush, QFont, QTextCharFormat
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QPointF

class FloatingEditor(QTextEdit):
    editing_finished = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_data = None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow)
        self.setStyleSheet("QTextEdit { background-color: white; border: 1px solid #0055cc; padding: 2px; }")
        self.hide()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.editing_finished.emit(self.toPlainText(), self.line_data)
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Tab:
            self.insertPlainText("    ")
        else:
            super().keyPressEvent(event)

class ClickableRectItem(QGraphicsRectItem):
    def __init__(self, rect, line_data, callback, drag_callback, parent=None):
        super().__init__(rect, parent)
        self.line_data = line_data
        self.callback = callback
        self.drag_callback = drag_callback
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setPen(QPen(QColor(0, 0, 0, 0)))
        self.setBrush(QColor(0, 0, 0, 0))
        self._is_dragging = False
        self._start_pos = None

    def hoverEnterEvent(self, event):
        self.setPen(QPen(QColor(150, 150, 150), 1, Qt.PenStyle.DashLine))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setPen(QPen(QColor(0, 0, 0, 0)))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = self.pos()
            self._is_dragging = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            if self._start_pos and (self.pos() - self._start_pos).manhattanLength() > QApplication.startDragDistance():
                self._is_dragging = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        is_drag = False
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_dragging:
                end_pos = self.pos()
                if self._start_pos:
                    dx = end_pos.x() - self._start_pos.x()
                    dy = end_pos.y() - self._start_pos.y()
                    if dx != 0 or dy != 0:
                        is_drag = True

        super().mouseReleaseEvent(event)

        if event.button() == Qt.MouseButton.LeftButton:
            if not self._is_dragging:
                self.callback(self.line_data, self.sceneBoundingRect())
            elif is_drag:
                self.drag_callback(self.line_data, dx, dy)

class PDFGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.parent_window = None

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if not event.isAccepted() and self.parent_window:
            scene_pos = self.mapToScene(event.pos())
            if self.parent_window.btn_add_text.isChecked():
                self.parent_window.add_new_text(scene_pos)
            elif self.parent_window.btn_add_signature.isChecked():
                self.parent_window.add_signature(scene_pos)



class PDFEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WYSIWYG PDF Editor")
        self.setGeometry(100, 100, 1200, 800)

        self.doc = None
        self.original_filepath = None
        self.current_page_num = 0
        self.current_page = None
        self.zoom = 2.0
        self.temp_dir = tempfile.mkdtemp()
        self.grid_items = []
        self.form_widgets = []

        self.init_ui()

    def closeEvent(self, event):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        super().closeEvent(event)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        toolbar_layout = QHBoxLayout()
        self.btn_open = QPushButton("Open PDF")
        self.btn_open.clicked.connect(self.open_pdf)
        self.btn_save = QPushButton("Save PDF")
        self.btn_save.clicked.connect(self.save_pdf)

        self.btn_toggle_grid = QPushButton("Toggle Grid")
        self.btn_toggle_grid.setCheckable(True)
        self.btn_toggle_grid.toggled.connect(self.toggle_grid)
        self.btn_add_text = QPushButton("Add Text")
        self.btn_add_text.setCheckable(True)
        self.btn_insert_table = QPushButton("Insert Table")
        self.btn_insert_table.clicked.connect(self.insert_table)

        self.btn_prev = QPushButton("Previous Page")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next = QPushButton("Next Page")
        self.btn_next.clicked.connect(self.next_page)
        self.lbl_page = QLabel("Page: 0 / 0")

        toolbar_layout.addWidget(self.btn_open)
        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addWidget(self.btn_toggle_grid)
        toolbar_layout.addWidget(self.btn_add_text)
        toolbar_layout.addWidget(self.btn_insert_table)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.btn_prev)
        toolbar_layout.addWidget(self.lbl_page)
        toolbar_layout.addWidget(self.btn_next)

        main_layout.addLayout(toolbar_layout)

                # Formatting Toolbar
        self.format_toolbar = QToolBar("Formatting")
        self.addToolBar(self.format_toolbar)

        self.combo_font = QComboBox()
        self.combo_font.addItems(["Helvetica", "Times-Roman", "Courier"])
        self.combo_font.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.format_toolbar.addWidget(self.combo_font)

        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 100)
        self.spin_size.setValue(11)
        self.spin_size.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.format_toolbar.addWidget(self.spin_size)

        self.btn_bold = QPushButton("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setStyleSheet("font-weight: bold;")
        self.btn_bold.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.format_toolbar.addWidget(self.btn_bold)

        self.btn_italic = QPushButton("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setStyleSheet("font-style: italic;")
        self.btn_italic.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.format_toolbar.addWidget(self.btn_italic)

        self.btn_underline = QPushButton("U")
        self.btn_underline.setCheckable(True)
        self.btn_underline.setStyleSheet("text-decoration: underline;")
        self.btn_underline.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.format_toolbar.addWidget(self.btn_underline)

        self.btn_strike = QPushButton("S")
        self.btn_strike.setCheckable(True)
        self.btn_strike.setStyleSheet("text-decoration: line-through;")
        self.btn_strike.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.format_toolbar.addWidget(self.btn_strike)

        self.btn_color = QPushButton("Color")
        self.btn_color.clicked.connect(self.choose_color)
        self.btn_color.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.format_toolbar.addWidget(self.btn_color)
        self.current_color = QColor(0, 0, 0)

        self.btn_bg_color = QPushButton("BG Color")
        self.btn_bg_color.clicked.connect(self.choose_bg_color)
        self.btn_bg_color.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.format_toolbar.addWidget(self.btn_bg_color)
        self.current_bg_color = None

        self.btn_add_signature = QPushButton("Signature")
        self.btn_add_signature.setCheckable(True)
        self.btn_add_signature.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.format_toolbar.addWidget(self.btn_add_signature)

        self.scene = QGraphicsScene()
        self.view = PDFGraphicsView(self.scene)
        self.view.parent_window = self
        main_layout.addWidget(self.view)

        self.floating_editor = FloatingEditor(self.view)
        self.floating_editor.editing_finished.connect(self.apply_changes)

    def choose_color(self):
        color = QColorDialog.getColor(self.current_color, self)
        if color.isValid():
            self.current_color = color
            self.update_editor_format()

    def choose_bg_color(self):
        color = QColorDialog.getColor(Qt.GlobalColor.white, self)
        if color.isValid():
            self.current_bg_color = color
            self.update_editor_format()

    def update_editor_format(self):
        if not self.floating_editor.isVisible(): return
        fmt = QTextCharFormat()
        fmt.setForeground(self.current_color)
        if self.current_bg_color:
            fmt.setBackground(self.current_bg_color)
        self.floating_editor.mergeCurrentCharFormat(fmt)

    def update_editor_font(self):
        if not self.floating_editor.isVisible(): return
        font = self.floating_editor.font()
        font.setBold(self.btn_bold.isChecked())
        font.setItalic(self.btn_italic.isChecked())
        font.setPointSizeF(self.spin_size.value() * self.zoom * 0.75)
        self.floating_editor.setFont(font)

    def open_pdf(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if filepath:
            self.original_filepath = filepath
            self.doc = fitz.open(filepath)
            self.current_page_num = 0
            self.render_page()

    def save_pdf(self):
        if not self.doc: return
        filepath, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if filepath:
            try:
                if filepath == self.original_filepath:
                    temp_save_path = os.path.join(self.temp_dir, "temp_save.pdf")
                    self.doc.save(temp_save_path)
                    self.doc.close()
                    shutil.move(temp_save_path, filepath)
                    self.doc = fitz.open(filepath)
                    self.render_page()
                else:
                    self.doc.save(filepath)
                QMessageBox.information(self, "Success", f"Saved to {filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save PDF:\\n{str(e)}")

    def toggle_grid(self, checked):
        if checked:
            if self.current_page:
                width = self.current_page.rect.width * self.zoom
                height = self.current_page.rect.height * self.zoom
                step = 50 * self.zoom
                pen = QPen(QColor(0, 0, 255, 100), 1, Qt.PenStyle.DotLine)
                for x in range(0, int(width), int(step)):
                    line = self.scene.addLine(x, 0, x, height, pen)
                    self.grid_items.append(line)
                for y in range(0, int(height), int(step)):
                    line = self.scene.addLine(0, y, width, y, pen)
                    self.grid_items.append(line)
        else:
            for item in self.grid_items:
                self.scene.removeItem(item)
            self.grid_items = []
        self.form_widgets = []

    def insert_table(self):
        if not self.doc: return
        rows, ok1 = QInputDialog.getInt(self, "Insert Table", "Number of Rows:", 3, 1, 100)
        if not ok1: return
        cols, ok2 = QInputDialog.getInt(self, "Insert Table", "Number of Columns:", 3, 1, 100)
        if not ok2: return

        cell_width = 100
        cell_height = 30
        start_x = 50
        start_y = 50
        table_width = cols * cell_width
        table_height = rows * cell_height

        self.current_page.draw_rect(fitz.Rect(start_x, start_y, start_x + table_width, start_y + table_height), color=(0,0,0), width=1)
        for i in range(1, cols):
            x = start_x + (i * cell_width)
            self.current_page.draw_line(fitz.Point(x, start_y), fitz.Point(x, start_y + table_height), color=(0,0,0), width=1)
        for i in range(1, rows):
            y = start_y + (i * cell_height)
            self.current_page.draw_line(fitz.Point(start_x, y), fitz.Point(start_x + table_width, y), color=(0,0,0), width=1)

        self.render_page()
        self.btn_toggle_grid.setChecked(True)


    def add_signature(self, scene_pos):
        if not self.doc: return
        self.btn_add_signature.setChecked(False) # reset mode

        filepath, _ = QFileDialog.getOpenFileName(self, "Select Signature Image", "", "Images (*.png *.jpg *.jpeg)")
        if not filepath: return

        # Unscale coordinates
        pdf_x = scene_pos.x() / self.zoom
        pdf_y = scene_pos.y() / self.zoom

        rect = fitz.Rect(pdf_x, pdf_y, pdf_x + 150, pdf_y + 50)
        self.current_page.insert_image(rect, filename=filepath)
        self.render_page()

    def add_new_text(self, scene_pos):
        if not self.doc: return
        pdf_x = scene_pos.x() / self.zoom
        pdf_y = scene_pos.y() / self.zoom
        line_data = {
            "is_new": True,
            "text": "",
            "bbox": [pdf_x, pdf_y, pdf_x + 100, pdf_y + 20],
            "origin": (pdf_x, pdf_y + 10),
            "font": "helv",
            "flags": 0,
            "size": 11,
            "color": 0
        }
        view_rect = self.view.mapFromScene(QRectF(scene_pos.x(), scene_pos.y(), 100, 20)).boundingRect()
        self.floating_editor.line_data = line_data
        self.floating_editor.setGeometry(view_rect)
        self.floating_editor.setText("")
        self.floating_editor.show()
        self.floating_editor.setFocus()
        self.btn_add_text.setChecked(False)

    def prev_page(self):
        if self.doc and self.current_page_num > 0:
            self.current_page_num -= 1
            self.render_page()

    def next_page(self):
        if self.doc and self.current_page_num < len(self.doc) - 1:
            self.current_page_num += 1
            self.render_page()

    def render_page(self):
        if not self.doc: return
        self.lbl_page.setText(f"Page: {self.current_page_num + 1} / {len(self.doc)}")
        self.scene.clear()
        self.grid_items = []
        self.form_widgets = []
        if self.btn_toggle_grid.isChecked():
            self.toggle_grid(True)

        self.current_page = self.doc[self.current_page_num]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = self.current_page.get_pixmap(matrix=mat)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        self.scene.addItem(QGraphicsPixmapItem(QPixmap.fromImage(img)))
        self.scene.setSceneRect(0.0, 0.0, float(pix.width), float(pix.height))

        # Render interactive form fields
        for proxy in self.form_widgets:
            self.scene.removeItem(proxy)
        self.form_widgets = []

        for widget in self.current_page.widgets():
            x0, y0, x1, y1 = widget.rect
            ui_x = x0 * self.zoom
            ui_y = y0 * self.zoom
            ui_w = (x1 - x0) * self.zoom
            ui_h = (y1 - y0) * self.zoom

            if widget.field_type == fitz.PDF_WIDGET_TYPE_TEXT:
                ui_elem = QLineEdit()
                ui_elem.setFixedSize(int(ui_w), int(ui_h))
                ui_elem.setText(widget.field_value)
                ui_elem.textChanged.connect(lambda text, w=widget: self.update_form_field(w, text))
                proxy = self.scene.addWidget(ui_elem)
                proxy.setPos(ui_x, ui_y)
                self.form_widgets.append(proxy)

            elif widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                ui_elem = QCheckBox()
                ui_elem.setFixedSize(int(ui_w), int(ui_h))
                ui_elem.setChecked(widget.field_value)
                ui_elem.stateChanged.connect(lambda state, w=widget: self.update_form_field(w, bool(state)))
                proxy = self.scene.addWidget(ui_elem)
                proxy.setPos(ui_x, ui_y)
                self.form_widgets.append(proxy)

            elif widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                ui_elem = QCheckBox(self.view)
                ui_elem.setGeometry(int(ui_x), int(ui_y), int(ui_w), int(ui_h))
                ui_elem.setChecked(widget.field_value)
                ui_elem.stateChanged.connect(lambda state, w=widget: self.update_form_field(w, bool(state)))
                ui_elem.show()
                self.form_widgets.append(ui_elem)

        for b_idx, b in enumerate(self.current_page.get_text("dict").get("blocks", [])):
            if b.get("type") == 0:
                for l_idx, line in enumerate(b.get("lines", [])):
                    if len(line.get("spans", [])) == 0: continue
                    full_text = "".join(s["text"] for s in line["spans"])
                    first_span = line["spans"][0]
                    line_data = {
                        "block_index": b_idx,
                        "line_index": l_idx,
                        "text": full_text,
                        "bbox": line["bbox"],
                        "origin": first_span.get("origin", (line["bbox"][0], line["bbox"][3])),
                        "font": first_span["font"],
                        "flags": first_span.get("flags", 0),
                        "size": first_span["size"],
                        "color": first_span.get("color", 0)
                    }
                    x0, y0, x1, y1 = line["bbox"]
                    rect = QRectF(x0 * self.zoom, y0 * self.zoom, (x1 - x0) * self.zoom, (y1 - y0) * self.zoom)
                    self.scene.addItem(ClickableRectItem(rect, line_data, self.line_clicked, self.line_dragged))


    def update_form_field(self, pdf_widget, value):
        pdf_widget.field_value = value
        pdf_widget.update()

    def line_clicked(self, line_data, rect):
        self.floating_editor.line_data = line_data
        view_rect = self.view.mapFromScene(rect).boundingRect()
        padding = 4
        self.floating_editor.setGeometry(view_rect.x() - padding, view_rect.y() - padding,
                                         view_rect.width() + padding*2 + 50, view_rect.height() + padding*2)

        self.spin_size.setValue(int(round(line_data["size"])))
        font_name_lower = line_data["font"].lower()
        self.btn_bold.setChecked("bold" in font_name_lower or line_data["flags"] & 16)
        self.btn_italic.setChecked("italic" in font_name_lower or line_data["flags"] & 2)

        if "times" in font_name_lower: self.combo_font.setCurrentText("Times-Roman")
        elif "cour" in font_name_lower: self.combo_font.setCurrentText("Courier")
        else: self.combo_font.setCurrentText("Helvetica")

        rgb = self.int_to_rgb_tuple(line_data.get("color", 0))
        self.current_color = QColor(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
        self.current_bg_color = None

        try: self.btn_bold.clicked.disconnect()
        except: pass
        try: self.btn_italic.clicked.disconnect()
        except: pass
        try: self.spin_size.valueChanged.disconnect()
        except: pass
        try: self.combo_font.currentTextChanged.disconnect()
        except: pass

        self.btn_bold.clicked.connect(self.update_editor_font)
        self.btn_italic.clicked.connect(self.update_editor_font)
        self.spin_size.valueChanged.connect(self.update_editor_font)
        self.combo_font.currentTextChanged.connect(self.update_editor_font)

        font = QFont()
        font.setPointSizeF(line_data["size"] * self.zoom * 0.75)

        font_name_lower = line_data["font"].lower()
        if "bold" in font_name_lower or line_data["flags"] & 16: font.setBold(True)
        if "italic" in font_name_lower or line_data["flags"] & 2: font.setItalic(True)
        self.floating_editor.setFont(font)
        self.floating_editor.setText(line_data["text"])
        self.floating_editor.show()
        self.floating_editor.setFocus()

    def get_fallback_font(self, original_font_name, flags):
        name = original_font_name.lower()
        is_bold = "bold" in name or (flags & 16)
        is_italic = "italic" in name or "oblique" in name or (flags & 2)
        if is_bold and is_italic: return "hebi"
        elif is_bold: return "hebo"
        elif is_italic: return "heit"
        else: return "helv"

    def int_to_rgb_tuple(self, color_int):
        b = color_int & 255
        g = (color_int >> 8) & 255
        r = (color_int >> 16) & 255
        return (r/255.0, g/255.0, b/255.0)

    def line_dragged(self, line_data, dx, dy):
        if not self.doc: return
        pdf_dx = dx / self.zoom
        pdf_dy = dy / self.zoom
        rect = fitz.Rect(line_data["bbox"])
        self.current_page.add_redact_annot(rect)
        self.current_page.apply_redactions()
        new_origin = fitz.Point(line_data["origin"][0] + pdf_dx, line_data["origin"][1] + pdf_dy)

        # Bypass UI styling and use explicit original styling for drags
        font_name = line_data["font"]
        font_size = line_data["size"]
        flags = line_data.get("flags", 0)
        color = self.int_to_rgb_tuple(line_data["color"])

        base14_fonts = ["helv", "hebo", "heit", "hebi", "times-roman", "times-bold", "times-italic", "times-bolditalic", "cour", "co-bo", "co-it", "co-boit", "symb", "zadb", "arial", "helvetica", "times", "courier"]
        is_standard = any(b14 in font_name.lower() for b14 in base14_fonts)

        registered_font_name = None
        if not is_standard:
            try:
                for f in self.doc.get_page_fonts(self.current_page_num):
                    if font_name in f[3]:
                        font_buffer = self.doc.extract_font(f[0])[3]
                        extracted_font = fitz.Font(fontbuffer=font_buffer)
                        registered_font_name = self.current_page.insert_font(fontname="F0", fontbuffer=extracted_font.buffer)
                        break
            except Exception: pass

        if not registered_font_name:
            registered_font_name = self.get_fallback_font(font_name, flags)

        try:
            self.current_page.insert_text(new_origin, line_data["text"], fontsize=font_size, fontname=registered_font_name, color=color)
        except Exception:
            self.current_page.insert_text(new_origin, line_data["text"], fontsize=font_size, fontname=self.get_fallback_font(font_name, flags), color=color)

        self.render_page()


    def apply_changes(self, new_text, line_data):
        if not self.doc or not line_data: return

        # Check formatting states from the UI
        flags = 0
        if self.btn_bold.isChecked(): flags |= 16
        if self.btn_italic.isChecked(): flags |= 2

        ui_font_size = float(self.spin_size.value())
        ui_color = (self.current_color.redF(), self.current_color.greenF(), self.current_color.blueF())
        rgb = self.int_to_rgb_tuple(line_data["color"])

        # Determine if anything changed (text content OR formatting)
        text_changed = new_text.strip() != line_data["text"].strip()
        fmt_changed = (
            flags != line_data.get("flags", 0) or
            abs(ui_font_size - float(line_data["size"])) > 0.6 or
            abs(ui_color[0] - rgb[0]) > 0.01 or
            abs(ui_color[1] - rgb[1]) > 0.01 or
            abs(ui_color[2] - rgb[2]) > 0.01 or
            self.btn_underline.isChecked() or
            self.btn_strike.isChecked() or
            self.current_bg_color is not None
        )

        is_new = line_data.get("is_new", False)

        if not text_changed and not fmt_changed and not is_new:
            return

        if not is_new:
            rect = fitz.Rect(line_data["bbox"])
            self.current_page.add_redact_annot(rect)
            self.current_page.apply_redactions()

        self.insert_text_with_font(fitz.Point(line_data["origin"]), new_text, line_data)

    def insert_text_with_font(self, origin, text, line_data):
        # Override original line_data with UI selections
        font_size = float(self.spin_size.value())
        color = (self.current_color.redF(), self.current_color.greenF(), self.current_color.blueF())

        flags = 0
        if self.btn_bold.isChecked(): flags |= 16
        if self.btn_italic.isChecked(): flags |= 2

        # Base font handling based on UI combobox
        combo_val = self.combo_font.currentText()
        if combo_val == "Helvetica": base_f = "helv"
        elif combo_val == "Times-Roman": base_f = "times-roman"
        else: base_f = "cour"

        orig_font_name = line_data.get("font", "helv")
        registered_font_name = None

        # Use exact original font if the family wasn't radically changed
        if base_f in orig_font_name.lower() and not line_data.get("is_new", False):
            try:
                for f in self.doc.get_page_fonts(self.current_page_num):
                    if orig_font_name in f[3]:
                        font_buffer = self.doc.extract_font(f[0])[3]
                        extracted_font = fitz.Font(fontbuffer=font_buffer)
                        registered_font_name = self.current_page.insert_font(fontname="F0", fontbuffer=extracted_font.buffer)
                        break
            except Exception:
                pass

        if not registered_font_name:
            registered_font_name = self.get_fallback_font(base_f, flags)

        # Draw the main text
        try:
            self.current_page.insert_text(origin, text, fontsize=font_size, fontname=registered_font_name, color=color)
        except Exception:
            self.current_page.insert_text(origin, text, fontsize=font_size, fontname=self.get_fallback_font(base_f, flags), color=color)

        # Apply Annotations (Underline, Strike, Background Color)
        if self.btn_underline.isChecked() or self.btn_strike.isChecked() or self.current_bg_color:
            approx_width = len(text) * font_size * 0.55
            bbox = fitz.Rect(origin.x, origin.y - font_size, origin.x + approx_width, origin.y + font_size * 0.3)

            if self.current_bg_color:
                bg = (self.current_bg_color.redF(), self.current_bg_color.greenF(), self.current_bg_color.blueF())
                self.current_page.draw_rect(bbox, color=None, fill=bg, fill_opacity=0.3)

            if self.btn_underline.isChecked():
                self.current_page.draw_line(fitz.Point(bbox.x0, origin.y + 2), fitz.Point(bbox.x1, origin.y + 2), color=color, width=1)

            if self.btn_strike.isChecked():
                self.current_page.draw_line(fitz.Point(bbox.x0, origin.y - font_size * 0.3), fitz.Point(bbox.x1, origin.y - font_size * 0.3), color=color, width=1)

        self.render_page()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PDFEditorWindow()
    window.show()
    sys.exit(app.exec())
