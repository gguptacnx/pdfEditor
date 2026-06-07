import sys
import os
import fitz  # PyMuPDF
import tempfile
import shutil
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
import csv
from fpdf import FPDF

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QTextEdit,
    QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem, QInputDialog,
    QColorDialog, QToolBar, QComboBox, QSpinBox, QLineEdit, QCheckBox, QMenu,
    QTableWidget, QTableWidgetItem, QGraphicsProxyWidget
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
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
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

class ResizableImageItem(QGraphicsPixmapItem):
    def __init__(self, pixmap, img_dict, doc, page_num, parent=None):
        super().__init__(pixmap, parent)
        self.img_dict = img_dict
        self.doc = doc
        self.page_num = page_num
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.is_resizing = False
        self.resize_margin = 10
        self.start_pos = None
        self.start_rect = None

    def hoverMoveEvent(self, event):
        pos = event.pos()
        rect = self.boundingRect()
        if pos.x() >= rect.width() - self.resize_margin and pos.y() >= rect.height() - self.resize_margin:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            rect = self.boundingRect()
            if pos.x() >= rect.width() - self.resize_margin and pos.y() >= rect.height() - self.resize_margin:
                self.is_resizing = True
                self.start_pos = event.scenePos()
                self.start_rect = self.boundingRect()
            else:
                self.is_resizing = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_resizing:
            diff = event.scenePos() - self.start_pos
            new_w = max(10, self.start_rect.width() + diff.x())
            new_h = max(10, self.start_rect.height() + diff.y())
            scaled_pixmap = self.pixmap().scaled(int(new_w), int(new_h), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(scaled_pixmap)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_resizing = False
        scene = self.scene()
        if scene:
            view = scene.views()[0]
            zoom = view.parent_window.zoom
            self.img_dict["x0"] = self.x() / zoom
            self.img_dict["y0"] = self.y() / zoom
            self.img_dict["w"] = self.boundingRect().width() / zoom
            self.img_dict["h"] = self.boundingRect().height() / zoom
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu()
        delete_action = menu.addAction("Delete Signature/Image")
        action = menu.exec(event.screenPos())
        if action == delete_action:
            self.img_dict["deleted"] = True
            self.scene().removeItem(self)


class DraggableTableProxy(QGraphicsProxyWidget):
    def __init__(self, table_dict, parent=None):
        super().__init__(parent)
        self.table_dict = table_dict
        self.setFlag(QGraphicsProxyWidget.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsProxyWidget.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsProxyWidget.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        scene = self.scene()
        if scene:
            view = scene.views()[0]
            zoom = view.parent_window.zoom
            self.table_dict["x0"] = self.x() / zoom
            self.table_dict["y0"] = self.y() / zoom

    def contextMenuEvent(self, event):
        menu = QMenu()
        add_r = menu.addAction("Add Row")
        del_r = menu.addAction("Delete Row")
        add_c = menu.addAction("Add Column")
        del_c = menu.addAction("Delete Column")
        menu.addSeparator()
        del_t = menu.addAction("Delete Table")

        action = menu.exec(event.screenPos())
        table_widget = self.widget()

        if action == add_r:
            table_widget.insertRow(table_widget.rowCount())
            self.table_dict["rows"] += 1
        elif action == del_r:
            table_widget.removeRow(table_widget.currentRow() if table_widget.currentRow() >= 0 else table_widget.rowCount() - 1)
            self.table_dict["rows"] = max(1, self.table_dict["rows"] - 1)
        elif action == add_c:
            table_widget.insertColumn(table_widget.columnCount())
            self.table_dict["cols"] += 1
        elif action == del_c:
            table_widget.removeColumn(table_widget.currentColumn() if table_widget.currentColumn() >= 0 else table_widget.columnCount() - 1)
            self.table_dict["cols"] = max(1, self.table_dict["cols"] - 1)
        elif action == del_t:
            self.table_dict["deleted"] = True
            self.scene().removeItem(self)


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
        self.interactive_images = []
        self.interactive_tables = []
        self.search_highlights = []
        self.copied_format = None

        self.init_ui()

    def closeEvent(self, event):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.btn_format_painter.isChecked():
                self.btn_format_painter.setChecked(False)
                self.copied_format = None
        super().keyPressEvent(event)

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


        # New PDF, Convert, Print
        self.btn_new_pdf = QPushButton("New PDF")
        self.btn_new_pdf.clicked.connect(self.create_new_pdf)
        self.btn_convert_txt = QPushButton("TXT to PDF")
        self.btn_convert_txt.clicked.connect(self.convert_txt_to_pdf)
        self.btn_convert_img = QPushButton("Image to PDF")
        self.btn_convert_img.clicked.connect(self.convert_img_to_pdf)
        self.btn_convert_csv = QPushButton("CSV to PDF")
        self.btn_convert_csv.clicked.connect(self.convert_csv_to_pdf)
        self.btn_print = QPushButton("Print")
        self.btn_print.clicked.connect(self.print_pdf)

        toolbar_layout.addWidget(self.btn_new_pdf)
        toolbar_layout.addWidget(self.btn_convert_txt)
        toolbar_layout.addWidget(self.btn_convert_img)
        toolbar_layout.addWidget(self.btn_convert_csv)
        toolbar_layout.addWidget(self.btn_print)

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

        self.format_toolbar.addSeparator()

        self.btn_format_painter = QPushButton("Format Painter")
        self.btn_format_painter.setCheckable(True)
        self.btn_format_painter.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.format_toolbar.addWidget(self.btn_format_painter)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setFixedWidth(150)
        self.format_toolbar.addWidget(self.search_input)

        self.btn_search = QPushButton("Find")
        self.btn_search.clicked.connect(self.search_text)
        self.format_toolbar.addWidget(self.btn_search)

        self.scene = QGraphicsScene()
        self.view = PDFGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
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



    def print_pdf(self):
        if not self.doc: return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            from PyQt6.QtGui import QPainter
            painter = QPainter(printer)
            for page_num in range(len(self.doc)):
                if page_num > 0: printer.newPage()
                page = self.doc[page_num]
                # High res for print
                pix = page.get_pixmap(matrix=fitz.Matrix(4.0, 4.0))
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)

                # Scale to page
                rect = painter.viewport()
                size = img.size()
                size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
                painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
                painter.setWindow(img.rect())

                painter.drawImage(0, 0, img)
            painter.end()
            QMessageBox.information(self, "Print", "Print job sent.")


    def create_new_pdf(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Create New PDF", "", "PDF Files (*.pdf)")
        if filepath:
            pdf = fitz.open()
            pdf.new_page()
            pdf.save(filepath)
            pdf.close()
            self.original_filepath = filepath
            self.doc = fitz.open(filepath)
            self.current_page_num = 0
            self.render_page()

    def convert_txt_to_pdf(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Text File", "", "Text Files (*.txt)")
        if not filepath: return
        with open(filepath, 'r') as f: text_content = f.read()
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, text_content)
        out_path = filepath + ".pdf"
        pdf.output(out_path)
        QMessageBox.information(self, "Success", f"Converted to {out_path}")

    def convert_img_to_pdf(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Image File", "", "Images (*.png *.jpg *.jpeg)")
        if not filepath: return
        doc = fitz.open()
        img_doc = fitz.open(filepath)
        pdfbytes = img_doc.convert_to_pdf()
        img_pdf = fitz.open("pdf", pdfbytes)
        doc.insert_pdf(img_pdf)
        out_path = filepath + ".pdf"
        doc.save(out_path)
        doc.close()
        img_doc.close()
        QMessageBox.information(self, "Success", f"Converted to {out_path}")

    def convert_csv_to_pdf(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)")
        if not filepath: return
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                line = " | ".join(row)
                pdf.cell(0, 10, txt=line, ln=True)
        out_path = filepath + ".pdf"
        pdf.output(out_path)
        QMessageBox.information(self, "Success", f"Converted to {out_path}")

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
                # Burn interactive tables
                if hasattr(self, 'interactive_tables'):
                    for t_dict in self.interactive_tables:
                        if not t_dict.get("deleted", False):
                            target_page = self.doc[t_dict.get("page_num", 0)]
                            # If not currently on screen, we just rely on dictionary state. If on screen, grab from UI if needed.
                            # The dictionary state is now fully synced via signals, so we can just use the dictionary.
                            x0 = t_dict["x0"]
                            y0 = t_dict["y0"]
                            curr_y = y0
                            cell_data = t_dict.get("cells", {})
                            for r in range(t_dict["rows"]):
                                curr_x = x0
                                row_h = 30 # Fixed default in this MVP
                                for c in range(t_dict["cols"]):
                                    col_w = 100
                                    rect = fitz.Rect(curr_x, curr_y, curr_x + col_w, curr_y + row_h)
                                    target_page.draw_rect(rect, color=(0,0,0), width=1)

                                    val = cell_data.get((r, c), "")
                                    if val:
                                        text_rect = fitz.Rect(curr_x + 2, curr_y + 2, curr_x + col_w, curr_y + row_h)
                                        target_page.insert_textbox(text_rect, val, fontsize=11, fontname="helv")

                                    curr_x += col_w
                                curr_y += row_h
                    self.interactive_tables = []

                # Burn interactive images
                for img_dict in self.interactive_images:
                    if not img_dict.get("deleted", False):
                        target_page = self.doc[img_dict.get("page_num", 0)]
                        rect = fitz.Rect(img_dict["x0"], img_dict["y0"], img_dict["x0"] + img_dict["w"], img_dict["y0"] + img_dict["h"])
                        target_page.insert_image(rect, stream=img_dict["bytes"])
                self.interactive_images = []

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

    def insert_table(self):
        if not self.doc: return
        rows, ok1 = QInputDialog.getInt(self, "Insert Table", "Number of Rows:", 3, 1, 100)
        if not ok1: return
        cols, ok2 = QInputDialog.getInt(self, "Insert Table", "Number of Columns:", 3, 1, 100)
        if not ok2: return

        table_dict = {
            "rows": rows,
            "cols": cols,
            "x0": 50,
            "y0": 50,
            "deleted": False,
            "page_num": self.current_page_num
        }
        self.interactive_tables.append(table_dict)
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

    def add_signature(self, scene_pos):
        if not self.doc: return
        self.btn_add_signature.setChecked(False)

        filepath, _ = QFileDialog.getOpenFileName(self, "Select Signature Image", "", "Images (*.png *.jpg *.jpeg)")
        if not filepath: return

        with open(filepath, "rb") as f:
            img_bytes = f.read()

        pdf_x = scene_pos.x() / self.zoom
        pdf_y = scene_pos.y() / self.zoom

        img_dict = {
            "bytes": img_bytes,
            "x0": pdf_x,
            "y0": pdf_y,
            "w": 150,
            "h": 50,
            "deleted": False,
            "page_num": self.current_page_num,
            "is_new": True
        }
        self.interactive_images.append(img_dict)
        self.render_page()

    def search_text(self):
        if not self.current_page: return
        query = self.search_input.text()

        for item in self.search_highlights:
            self.scene.removeItem(item)
        self.search_highlights = []

        if not query: return

        rects = self.current_page.search_for(query)
        for r in rects:
            scaled_rect = QRectF(r.x0 * self.zoom, r.y0 * self.zoom, (r.x1 - r.x0) * self.zoom, (r.y1 - r.y0) * self.zoom)
            rect_item = QGraphicsRectItem(scaled_rect)
            rect_item.setBrush(QBrush(QColor(255, 255, 0, 100)))
            rect_item.setPen(QPen(Qt.PenStyle.NoPen))
            self.scene.addItem(rect_item)
            self.search_highlights.append(rect_item)

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
        self.search_highlights = []
        if self.btn_toggle_grid.isChecked():
            self.toggle_grid(True)

        self.current_page = self.doc[self.current_page_num]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = self.current_page.get_pixmap(matrix=mat)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        self.scene.addItem(QGraphicsPixmapItem(QPixmap.fromImage(img)))
        self.scene.setSceneRect(0.0, 0.0, float(pix.width), float(pix.height))

        # Render form fields
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

        # Render interactive tables
        if not hasattr(self, 'interactive_tables'): self.interactive_tables = []
        for t_dict in self.interactive_tables:
            if t_dict.get("deleted", False) or t_dict.get("page_num", 0) != self.current_page_num: continue

            table = QTableWidget(t_dict["rows"], t_dict["cols"])
            table.horizontalHeader().setVisible(False)
            table.verticalHeader().setVisible(False)
            table.setStyleSheet("QTableWidget { background-color: transparent; } QTableWidget::item { border: 1px solid black; }")
            for c in range(t_dict["cols"]): table.setColumnWidth(c, int(100 * self.zoom))
            for r in range(t_dict["rows"]): table.setRowHeight(r, int(30 * self.zoom))

            # Restore data
            cell_data = t_dict.get("cells", {})
            for (r, c), val in cell_data.items():
                if r < table.rowCount() and c < table.columnCount():
                    item = QTableWidgetItem(val)
                    table.setItem(r, c, item)

            table.itemChanged.connect(lambda item, d=t_dict, t=table: self.update_table_data(d, t))

            proxy = DraggableTableProxy(t_dict)
            proxy.setWidget(table)
            proxy.setPos(t_dict["x0"] * self.zoom, t_dict["y0"] * self.zoom)
            self.scene.addItem(proxy)

        # Render interactive images
        for img_dict in self.interactive_images:
            if img_dict.get("deleted", False) or img_dict.get("page_num", 0) != self.current_page_num: continue

            qimg = QImage.fromData(img_dict["bytes"])
            qpix = QPixmap.fromImage(qimg)
            scaled_pix = qpix.scaled(int(img_dict["w"] * self.zoom), int(img_dict["h"] * self.zoom), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

            item = ResizableImageItem(scaled_pix, img_dict, self.doc, self.current_page_num)
            item.setPos(img_dict["x0"] * self.zoom, img_dict["y0"] * self.zoom)
            self.scene.addItem(item)

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

    def update_table_data(self, t_dict, table):
        if "cells" not in t_dict: t_dict["cells"] = {}
        for r in range(table.rowCount()):
            for c in range(table.columnCount()):
                item = table.item(r, c)
                if item: t_dict["cells"][(r, c)] = item.text()

    def update_form_field(self, pdf_widget, value):
        pdf_widget.field_value = value
        pdf_widget.update()

    def line_clicked(self, line_data, rect):
        if self.btn_format_painter.isChecked():
            if self.copied_format is None:
                self.copied_format = {
                    "font": line_data["font"],
                    "size": line_data["size"],
                    "color": line_data["color"],
                    "flags": line_data.get("flags", 0)
                }
            else:
                fmt = self.copied_format
                self.spin_size.setValue(int(round(fmt["size"])))
                font_name_lower = fmt["font"].lower()
                self.btn_bold.setChecked("bold" in font_name_lower or fmt["flags"] & 16)
                self.btn_italic.setChecked("italic" in font_name_lower or fmt["flags"] & 2)
                if "times" in font_name_lower: self.combo_font.setCurrentText("Times-Roman")
                elif "cour" in font_name_lower: self.combo_font.setCurrentText("Courier")
                else: self.combo_font.setCurrentText("Helvetica")
                rgb = self.int_to_rgb_tuple(fmt["color"])
                self.current_color = QColor(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))

                self.apply_changes(line_data["text"], line_data, force_format=True)
                self.btn_format_painter.setChecked(False)
                self.copied_format = None
            return

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

        self.floating_editor.line_data = line_data
        view_rect = self.view.mapFromScene(rect).boundingRect()
        padding = 4
        self.floating_editor.setGeometry(view_rect.x() - padding, view_rect.y() - padding,
                                         view_rect.width() + padding*2 + 50, view_rect.height() + padding*2)
        font = QFont()
        font.setPointSizeF(line_data["size"] * self.zoom * 0.75)
        if self.btn_bold.isChecked(): font.setBold(True)
        if self.btn_italic.isChecked(): font.setItalic(True)
        self.floating_editor.setFont(font)
        self.floating_editor.setText(line_data["text"])
        self.floating_editor.show()
        self.floating_editor.setFocus()

    def get_fallback_font(self, original_font_name, flags):
        name = original_font_name.lower()
        is_bold = "bold" in name or (flags & 16)
        is_italic = "italic" in name or "oblique" in name or (flags & 2)
        if "times" in name:
            if is_bold and is_italic: return "times-bolditalic"
            elif is_bold: return "times-bold"
            elif is_italic: return "times-italic"
            else: return "times-roman"
        elif "cour" in name:
            if is_bold and is_italic: return "co-boit"
            elif is_bold: return "co-bo"
            elif is_italic: return "co-it"
            else: return "cour"
        else:
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

    def apply_changes(self, new_text, line_data, force_format=False):
        if not self.doc or not line_data: return

        flags = 0
        if self.btn_bold.isChecked(): flags |= 16
        if self.btn_italic.isChecked(): flags |= 2

        ui_font_size = float(self.spin_size.value())
        ui_color = (self.current_color.redF(), self.current_color.greenF(), self.current_color.blueF())
        rgb = self.int_to_rgb_tuple(line_data["color"])

        text_changed = new_text.strip() != line_data["text"].strip()
        fmt_changed = force_format or (
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
        font_size = float(self.spin_size.value())
        color = (self.current_color.redF(), self.current_color.greenF(), self.current_color.blueF())

        flags = 0
        if self.btn_bold.isChecked(): flags |= 16
        if self.btn_italic.isChecked(): flags |= 2

        combo_val = self.combo_font.currentText()
        if combo_val == "Helvetica": base_f = "helv"
        elif combo_val == "Times-Roman": base_f = "times-roman"
        else: base_f = "cour"

        orig_font_name = line_data.get("font", "helv")
        registered_font_name = None

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

        try:
            self.current_page.insert_text(origin, text, fontsize=font_size, fontname=registered_font_name, color=color)
        except Exception:
            self.current_page.insert_text(origin, text, fontsize=font_size, fontname=self.get_fallback_font(base_f, flags), color=color)

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
