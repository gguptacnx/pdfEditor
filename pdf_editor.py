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
from PyQt6.QtCore import Qt, QRectF, pyqtSignal

class FloatingEditor(QTextEdit):
    editing_finished = pyqtSignal(str, dict)  # new text, line_data dictionary

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_data = None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow)
        # Add padding to make it look like Acrobat
        self.setStyleSheet("QTextEdit { background-color: white; border: 1px solid #0055cc; padding: 2px; }")
        self.hide()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.editing_finished.emit(self.toPlainText(), self.line_data)
        self.hide()

class ClickableRectItem(QGraphicsRectItem):
    def __init__(self, rect, line_data, callback, parent=None):
        super().__init__(rect, parent)
        self.line_data = line_data
        self.callback = callback
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.IBeamCursor) # Acrobat uses text cursor
        self.setPen(QPen(QColor(0, 0, 0, 0)))
        self.setBrush(QColor(0, 0, 0, 0)) # Fully transparent by default

    def hoverEnterEvent(self, event):
        self.setPen(QPen(QColor(150, 150, 150), 1, Qt.PenStyle.DashLine)) # Acrobat-like subtle hover
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setPen(QPen(QColor(0, 0, 0, 0)))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.callback(self.line_data, self.rect())
        super().mousePressEvent(event)


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

        # Toolbar
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
        toolbar_layout.addWidget(self.btn_prev)
        toolbar_layout.addWidget(self.lbl_page)
        toolbar_layout.addWidget(self.btn_next)

        main_layout.addLayout(toolbar_layout)

        # PDF Canvas
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        main_layout.addWidget(self.view)

        # Floating Editor
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
                # PyMuPDF cannot save directly over the open file.
                if filepath == self.original_filepath:
                    temp_save_path = os.path.join(self.temp_dir, "temp_save.pdf")
                    self.doc.save(temp_save_path)
                    self.doc.close()
                    shutil.move(temp_save_path, filepath)
                    # Reopen the document
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

        # Extract dictionary and create clickable regions per LINE, not block
        page_dict = self.current_page.get_text("dict")
        for b_idx, b in enumerate(page_dict.get("blocks", [])):
            if b.get("type") == 0:  # Text block
                for l_idx, line in enumerate(b.get("lines", [])):
                    if len(line.get("spans", [])) == 0:
                        continue

                    full_text = "".join(s["text"] for s in line["spans"])

                    first_span = line["spans"][0]
                    line_data = {
                        "block_index": b_idx,
                        "line_index": l_idx,
                        "text": full_text,
                        "bbox": line["bbox"], # x0, y0, x1, y1
                        "font": first_span["font"],
                        "size": first_span["size"],
                        "color": first_span.get("color", 0) # integer color
                    }

                    x0, y0, x1, y1 = line["bbox"]
                    rect = QRectF(x0 * self.zoom, y0 * self.zoom, (x1 - x0) * self.zoom, (y1 - y0) * self.zoom)
                    rect_item = ClickableRectItem(rect, line_data, self.line_clicked)
                    self.scene.addItem(rect_item)

    def line_clicked(self, line_data, rect):
        self.floating_editor.line_data = line_data

        # Map scene coordinates to view coordinates
        view_rect = self.view.mapFromScene(rect).boundingRect()

        padding = 4
        # We make the box slightly wider so typing doesn't instantly wrap
        self.floating_editor.setGeometry(view_rect.x() - padding, view_rect.y() - padding,
                                         view_rect.width() + padding*2 + 50, view_rect.height() + padding*2)

        font = QFont()
        # Estimate UI font size to match PDF zoom
        font.setPointSizeF(line_data["size"] * self.zoom * 0.75)
        self.floating_editor.setFont(font)

        self.floating_editor.setText(line_data["text"])
        self.floating_editor.show()
        self.floating_editor.setFocus()

    def apply_changes(self, new_text, line_data):
        if not self.doc or not line_data:
            return

        old_text = line_data["text"]

        # If user just clicked away without changing, do nothing
        if new_text.strip() == old_text.strip():
            return

        # We only redact the specific line's bounding box to preserve adjacent tabular columns!
        rect = fitz.Rect(line_data["bbox"])
        self.current_page.add_redact_annot(rect)
        self.current_page.apply_redactions()

        font_name = line_data["font"]
        font_size = line_data["size"]

        # Attempt to use embedded buffer
        font_args = {}
        try:
            fonts = self.doc.get_page_fonts(self.current_page_num)
            for f in fonts:
                if f[3] in font_name:
                    font_args['fontbuffer'] = self.doc.extract_font(f[0])[3]
                    font_args['fontname'] = font_name
                    break
        except Exception:
            pass

        # The bounding box height for insert_textbox needs to be sufficiently large
        # otherwise PyMuPDF silently fails to draw the text inside the box.
        new_rect = fitz.Rect(rect.x0, rect.y0, self.current_page.rect.width, rect.y1 + font_size * 2)

        try:
            self.current_page.insert_textbox(new_rect, new_text, fontsize=font_size, **font_args)
        except Exception:
            self.current_page.insert_textbox(new_rect, new_text, fontsize=font_size)

        self.render_page()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PDFEditorWindow()
    window.show()
    sys.exit(app.exec())
