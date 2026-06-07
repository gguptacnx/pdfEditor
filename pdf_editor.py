import sys
import os
import fitz  # PyMuPDF
import tempfile
import shutil
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QTextEdit,
    QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem
)
from PyQt6.QtGui import QPixmap, QImage, QColor, QPen, QBrush, QFont
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QPointF
from PyQt6.QtWidgets import QInputDialog, QGraphicsLineItem, QGraphicsItem

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
            # Insert spaces instead of actual tab for better PDF rendering
            self.insertPlainText("    ")
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.editing_finished.emit(self.toPlainText(), self.line_data)
        self.hide()

class ClickableRectItem(QGraphicsRectItem):
    def __init__(self, rect, line_data, callback, drag_callback, parent=None):
        super().__init__(rect, parent)
        self.line_data = line_data
        self.callback = callback
        self.drag_callback = drag_callback
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
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
            self._is_dragging = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._is_dragging:
                # It was a click
                self.callback(self.line_data, self.sceneBoundingRect())
            else:
                # It was a drag
                end_pos = self.pos()
                if self._start_pos:
                    dx = end_pos.x() - self._start_pos.x()
                    dy = end_pos.y() - self._start_pos.y()
                    if dx != 0 or dy != 0:
                        self.drag_callback(self.line_data, dx, dy)
        super().mouseReleaseEvent(event)


class PDFGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.parent_window = None

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if not event.isAccepted() and self.parent_window and self.parent_window.btn_add_text.isChecked():
            # Clicked empty space while in "Add Text" mode
            scene_pos = self.mapToScene(event.pos())
            self.parent_window.add_new_text(scene_pos)

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
        self.btn_prev = QPushButton("Previous Page")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next = QPushButton("Next Page")
        self.btn_next.clicked.connect(self.next_page)
        self.lbl_page = QLabel("Page: 0 / 0")

        toolbar_layout.addWidget(self.btn_open)
        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addStretch()

        # New buttons
        self.btn_toggle_grid = QPushButton("Toggle Grid")
        self.btn_toggle_grid.setCheckable(True)
        self.btn_toggle_grid.toggled.connect(self.toggle_grid)
        self.btn_add_text = QPushButton("Add Text")
        self.btn_add_text.setCheckable(True)
        self.btn_insert_table = QPushButton("Insert Table")
        self.btn_insert_table.clicked.connect(self.insert_table)

        toolbar_layout.addWidget(self.btn_toggle_grid)
        toolbar_layout.addWidget(self.btn_add_text)
        toolbar_layout.addWidget(self.btn_insert_table)
        toolbar_layout.addStretch()

        toolbar_layout.addWidget(self.btn_prev)
        toolbar_layout.addWidget(self.lbl_page)
        toolbar_layout.addWidget(self.btn_next)

        main_layout.addLayout(toolbar_layout)

        self.scene = QGraphicsScene()
        self.view = PDFGraphicsView(self.scene)
        self.view.parent_window = self
        main_layout.addWidget(self.view)

        self.floating_editor = FloatingEditor(self.view)
        self.floating_editor.editing_finished.connect(self.apply_changes)

    def open_pdf(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if filepath:
            self.original_filepath = filepath
            self.doc = fitz.open(filepath)
            self.current_page_num = 0
            self.render_page()

    def save_pdf(self):
        if not self.doc:
            return
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
                QMessageBox.critical(self, "Error", f"Failed to save PDF:\n{str(e)}")


    def prev_page(self):
        if self.doc and self.current_page_num > 0:
            self.current_page_num -= 1
            self.render_page()

    def next_page(self):
        if self.doc and self.current_page_num < len(self.doc) - 1:
            self.current_page_num += 1
            self.render_page()

    def render_page(self):
        if not self.doc:
            return

        self.lbl_page.setText(f"Page: {self.current_page_num + 1} / {len(self.doc)}")
        self.scene.clear()

        self.current_page = self.doc[self.current_page_num]

        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = self.current_page.get_pixmap(matrix=mat)

        samples = pix.samples
        img = QImage(samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        qpixmap = QPixmap.fromImage(img)

        pixmap_item = QGraphicsPixmapItem(qpixmap)
        self.scene.addItem(pixmap_item)
        self.scene.setSceneRect(0.0, 0.0, float(pix.width), float(pix.height))

        page_dict = self.current_page.get_text("dict")
        for b_idx, b in enumerate(page_dict.get("blocks", [])):
            if b.get("type") == 0:
                for l_idx, line in enumerate(b.get("lines", [])):
                    if len(line.get("spans", [])) == 0:
                        continue

                    full_text = "".join(s["text"] for s in line["spans"])

                    first_span = line["spans"][0]
                    line_data = {
                        "block_index": b_idx,
                        "line_index": l_idx,
                        "text": full_text,
                        "bbox": line["bbox"],
                        "origin": first_span.get("origin", (line["bbox"][0], line["bbox"][3])), # X/Y baseline
                        "font": first_span["font"],
                        "flags": first_span.get("flags", 0),
                        "size": first_span["size"],
                        "color": first_span.get("color", 0)
                    }

                    x0, y0, x1, y1 = line["bbox"]
                    rect = QRectF(x0 * self.zoom, y0 * self.zoom, (x1 - x0) * self.zoom, (y1 - y0) * self.zoom)
                    rect_item = ClickableRectItem(rect, line_data, self.line_clicked, self.line_dragged)
                    self.scene.addItem(rect_item)

    def line_clicked(self, line_data, rect):
        self.floating_editor.line_data = line_data
        view_rect = self.view.mapFromScene(rect).boundingRect()
        padding = 4
        self.floating_editor.setGeometry(view_rect.x() - padding, view_rect.y() - padding,
                                         view_rect.width() + padding*2 + 50, view_rect.height() + padding*2)
        font = QFont()
        font.setPointSizeF(line_data["size"] * self.zoom * 0.75)

        font_name_lower = line_data["font"].lower()
        if "bold" in font_name_lower or line_data["flags"] & 16:
            font.setBold(True)
        if "italic" in font_name_lower or line_data["flags"] & 2:
            font.setItalic(True)

        self.floating_editor.setFont(font)
        self.floating_editor.setText(line_data["text"])
        self.floating_editor.show()
        self.floating_editor.setFocus()


    def toggle_grid(self, checked):
        if not hasattr(self, 'grid_items'):
            self.grid_items = []

        if checked:
            # Draw grid
            if self.current_page:
                width = self.current_page.rect.width * self.zoom
                height = self.current_page.rect.height * self.zoom
                step = 50 * self.zoom

                pen = QPen(QColor(0, 0, 255, 100), 1, Qt.PenStyle.DotLine)

                # Vertical lines
                for x in range(0, int(width), int(step)):
                    line = self.scene.addLine(x, 0, x, height, pen)
                    self.grid_items.append(line)

                # Horizontal lines
                for y in range(0, int(height), int(step)):
                    line = self.scene.addLine(0, y, width, y, pen)
                    self.grid_items.append(line)
        else:
            # Remove grid
            for item in self.grid_items:
                self.scene.removeItem(item)
            self.grid_items = []

    def insert_table(self):
        if not self.doc:
            return

        rows, ok1 = QInputDialog.getInt(self, "Insert Table", "Number of Rows:", 3, 1, 100)
        if not ok1: return
        cols, ok2 = QInputDialog.getInt(self, "Insert Table", "Number of Columns:", 3, 1, 100)
        if not ok2: return

        # Hardcoded size for simplicity in MVP, anchored top-left
        cell_width = 100
        cell_height = 30
        start_x = 50
        start_y = 50

        table_width = cols * cell_width
        table_height = rows * cell_height

        # Draw outer box
        self.current_page.draw_rect(fitz.Rect(start_x, start_y, start_x + table_width, start_y + table_height), color=(0,0,0), width=1)

        # Draw vertical lines
        for i in range(1, cols):
            x = start_x + (i * cell_width)
            self.current_page.draw_line(fitz.Point(x, start_y), fitz.Point(x, start_y + table_height), color=(0,0,0), width=1)

        # Draw horizontal lines
        for i in range(1, rows):
            y = start_y + (i * cell_height)
            self.current_page.draw_line(fitz.Point(start_x, y), fitz.Point(start_x + table_width, y), color=(0,0,0), width=1)

        self.render_page()
        self.btn_toggle_grid.setChecked(True) # Auto show grid to help align text

    def add_new_text(self, scene_pos):
        if not self.doc: return

        # Unscale coordinates
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
            "color": 0 # black
        }

        view_rect = self.view.mapFromScene(QRectF(scene_pos.x(), scene_pos.y(), 100, 20)).boundingRect()

        self.floating_editor.line_data = line_data
        self.floating_editor.setGeometry(view_rect)
        self.floating_editor.setText("")
        self.floating_editor.show()
        self.floating_editor.setFocus()
        self.btn_add_text.setChecked(False) # Reset mode

    def line_dragged(self, line_data, dx, dy):
        if not self.doc: return

        pdf_dx = dx / self.zoom
        pdf_dy = dy / self.zoom

        # Redact old text
        rect = fitz.Rect(line_data["bbox"])
        self.current_page.add_redact_annot(rect)
        self.current_page.apply_redactions()

        # Write at new position
        font_name = line_data["font"]
        font_size = line_data["size"]
        color = self.int_to_rgb_tuple(line_data["color"])

        new_origin = fitz.Point(line_data["origin"][0] + pdf_dx, line_data["origin"][1] + pdf_dy)

        font_args = {}
        try:
            fonts = self.doc.get_page_fonts(self.current_page_num)
            for f in fonts:
                if font_name in f[3]:
                    font_args['fontbuffer'] = self.doc.extract_font(f[0])[3]
                    font_args['fontname'] = font_name
                    break
        except Exception:
            pass

        if not font_args:
            font_args['fontname'] = self.get_fallback_font(font_name, line_data.get("flags", 0))

        try:
            self.current_page.insert_text(new_origin, line_data["text"], fontsize=font_size, color=color, **font_args)
        except Exception:
            fallback = self.get_fallback_font(font_name, line_data.get("flags", 0))
            self.current_page.insert_text(new_origin, line_data["text"], fontsize=font_size, fontname=fallback, color=color)

        self.render_page()

    def get_fallback_font(self, original_font_name, flags):
        name = original_font_name.lower()
        is_bold = "bold" in name or (flags & 16)
        is_italic = "italic" in name or "oblique" in name or (flags & 2)

        if is_bold and is_italic:
            return "hebi"
        elif is_bold:
            return "hebo"
        elif is_italic:
            return "heit"
        else:
            return "helv"

    def int_to_rgb_tuple(self, color_int):
        """Converts PyMuPDF integer color to an RGB tuple (r, g, b)."""
        b = color_int & 255
        g = (color_int >> 8) & 255
        r = (color_int >> 16) & 255
        return (r/255.0, g/255.0, b/255.0)

    def apply_changes(self, new_text, line_data):
        if not self.doc or not line_data:
            return

        old_text = line_data["text"]
        if new_text.strip() == old_text.strip():
            return


        is_new = line_data.get("is_new", False)
        if not is_new:
            rect = fitz.Rect(line_data["bbox"])
            self.current_page.add_redact_annot(rect)
            self.current_page.apply_redactions()

        font_name = line_data["font"]

        font_size = line_data["size"]
        flags = line_data.get("flags", 0)
        color = self.int_to_rgb_tuple(line_data["color"])
        origin = fitz.Point(line_data["origin"])

        # We must insert the font into the page to use it with PyMuPDF
        registered_font_name = None
        try:
            fonts = self.doc.get_page_fonts(self.current_page_num)
            for f in fonts:
                if font_name in f[3]:
                    # Extract the raw binary font
                    font_buffer = self.doc.extract_font(f[0])[3]
                    # Create a fitz.Font object from the buffer
                    extracted_font = fitz.Font(fontbuffer=font_buffer)
                    # Register it to the page
                    registered_font_name = self.current_page.insert_font(fontname="F0", fontbuffer=extracted_font.buffer)
                    break
        except Exception:
            pass

        if not registered_font_name:
            # Fallback to prompting user as documented in README
            reply = QMessageBox.question(self, 'Font Check',
                                         f'Original font "{font_name}" is subsetted or proprietary.\nWould you like to select a local .ttf/.otf file? If No, a standard substitute will be used.',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                local_font_file, _ = QFileDialog.getOpenFileName(self, "Select Font File", "", "Font Files (*.ttf *.otf)")
                if local_font_file:
                    try:
                        registered_font_name = self.current_page.insert_font(fontfile=local_font_file, fontname="F0")
                    except Exception:
                        pass

        if not registered_font_name:
            registered_font_name = self.get_fallback_font(font_name, flags)

        # Use insert_text anchored directly to the baseline origin to prevent vertical shift!
        try:
            self.current_page.insert_text(origin, new_text, fontsize=font_size, fontname=registered_font_name, color=color)
        except Exception:
            fallback = self.get_fallback_font(font_name, flags)
            self.current_page.insert_text(origin, new_text, fontsize=font_size, fontname=fallback, color=color)

        self.render_page()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PDFEditorWindow()
    window.show()
    sys.exit(app.exec())
# Additional functions to be integrated later: toggle_grid, insert_table
