import sys
import os
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QTextEdit,
    QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem
)
from PyQt6.QtGui import QPixmap, QImage, QColor, QPen, QBrush
from PyQt6.QtCore import Qt, QRectF, pyqtSignal

class FloatingEditor(QTextEdit):
    editing_finished = pyqtSignal(str, int)  # new text, block index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.block_index = -1
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow)
        self.setStyleSheet("QTextEdit { background-color: rgba(255, 255, 255, 240); border: 2px solid blue; }")
        self.hide()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.editing_finished.emit(self.toPlainText(), self.block_index)
        self.hide()

class ClickableRectItem(QGraphicsRectItem):
    def __init__(self, rect, block_index, callback, parent=None):
        super().__init__(rect, parent)
        self.block_index = block_index
        self.callback = callback
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setPen(QPen(QColor(0, 0, 0, 0))) # Transparent by default
        self.setBrush(QBrush(QColor(0, 0, 255, 30)))  # Light blue, slightly transparent

    def hoverEnterEvent(self, event):
        self.setPen(QPen(QColor(255, 0, 0), 2))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setPen(QPen(QColor(0, 0, 0, 0)))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.callback(self.block_index, self.rect())
        super().mousePressEvent(event)


class PDFEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WYSIWYG PDF Editor")
        self.setGeometry(100, 100, 1200, 800)

        self.doc = None
        self.current_page_num = 0
        self.current_page = None
        self.blocks = []
        self.zoom = 2.0

        self.init_ui()

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
            self.doc = fitz.open(filepath)
            self.current_page_num = 0
            self.render_page()

    def save_pdf(self):
        if not self.doc:
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if filepath:
            self.doc.save(filepath)
            QMessageBox.information(self, "Success", f"Saved to {filepath}")

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

        self.blocks = self.current_page.get_text("blocks")

        for i, b in enumerate(self.blocks):
            if b[6] == 0:  # If it's a text block
                x0, y0, x1, y1 = b[:4]
                rect = QRectF(x0 * self.zoom, y0 * self.zoom, (x1 - x0) * self.zoom, (y1 - y0) * self.zoom)
                rect_item = ClickableRectItem(rect, i, self.block_clicked)
                self.scene.addItem(rect_item)

    def block_clicked(self, block_index, rect):
        self.floating_editor.block_index = block_index
        block = self.blocks[block_index]
        text = block[4]

        view_rect = self.view.mapFromScene(rect).boundingRect()

        padding = 5
        self.floating_editor.setGeometry(view_rect.x() - padding, view_rect.y() - padding,
                                         view_rect.width() + padding*2, view_rect.height() + padding*2)
        self.floating_editor.setText(text)
        self.floating_editor.show()
        self.floating_editor.setFocus()

    def push_elements_down_destructive(self, threshold_y, shift_amount):
        """
        Physically shifts text blocks and images below the threshold down by shift_amount.
        This re-embeds the original font streams to preserve visual formatting.
        """
        all_blocks = self.current_page.get_text("dict")["blocks"]
        text_elements_to_redraw = []
        images_to_redraw = []

        for b in all_blocks:
            bbox = fitz.Rect(b["bbox"])
            if bbox.y0 >= threshold_y - 2:
                if b["type"] == 0:  # Text
                    text_elements_to_redraw.append(b)
                    for line in b.get("lines", []):
                        for span in line.get("spans", []):
                            self.current_page.add_redact_annot(fitz.Rect(span["bbox"]))
                elif b["type"] == 1: # Image
                    images_to_redraw.append({
                        "bbox": bbox,
                        "image": b.get("image", None),
                        "ext": b.get("ext", "png")
                    })
                    self.current_page.add_redact_annot(bbox)

        self.current_page.apply_redactions()

        for b in text_elements_to_redraw:
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    span_bbox = fitz.Rect(span["bbox"])
                    text = span["text"]
                    font_size = span["size"]
                    font_name = span["font"]

                    shifted_rect = fitz.Rect(span_bbox.x0, span_bbox.y0 + shift_amount,
                                             self.current_page.rect.width, span_bbox.y1 + shift_amount)

                    font_buffer = None
                    try:
                        fonts = self.doc.get_page_fonts(self.current_page_num)
                        for f in fonts:
                            if f[3] in font_name:
                                font_buffer = self.doc.extract_font(f[0])[3]
                                break
                    except Exception:
                        pass

                    font_args = {}
                    if font_buffer:
                        font_args['fontbuffer'] = font_buffer
                        font_args['fontname'] = font_name

                    try:
                        self.current_page.insert_textbox(shifted_rect, text, fontsize=font_size, **font_args)
                    except Exception:
                        self.current_page.insert_textbox(shifted_rect, text, fontsize=font_size)

        for img in images_to_redraw:
            if img["image"]:
                bbox = img["bbox"]
                shifted_rect = fitz.Rect(bbox.x0, bbox.y0 + shift_amount,
                                         bbox.x1, bbox.y1 + shift_amount)
                self.current_page.insert_image(shifted_rect, stream=img["image"])


    def apply_changes(self, new_text, block_index):
        if not self.doc or block_index == -1:
            return

        block = self.blocks[block_index]
        old_text = block[4]

        if new_text == old_text:
            return

        block_dict = self.current_page.get_text("dict")["blocks"][block_index]

        original_lines_data = []
        if "lines" in block_dict and len(block_dict["lines"]) > 0:
            for line in block_dict["lines"]:
                if len(line["spans"]) > 0:
                    span = line["spans"][0]
                    original_lines_data.append({
                        "x0": span["bbox"][0],
                        "y0": span["bbox"][1],
                        "x1": span["bbox"][2],
                        "size": span["size"],
                        "font": span["font"]
                    })

        if not original_lines_data:
            return

        first_span = original_lines_data[0]
        font_size = first_span["size"]
        start_y = first_span["y0"]
        font_name = first_span["font"]

        font_file = None
        reply = QMessageBox.question(self, 'Font Check',
                                     f'Do you want to provide a local font file (.ttf/.otf) for this text? Otherwise, the embedded font or standard Helvetica will be used.',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            font_file, _ = QFileDialog.getOpenFileName(self, "Select Font File", "", "Font Files (*.ttf *.otf)")
            if not font_file:
                font_file = None

        # To avoid destroying adjacent columns, we only redact the EXACT bounding box of the old text span.
        for l_data in original_lines_data:
            # We use x1 to constrain the right side of the redaction to the actual word width,
            # NOT the edge of the page, preventing destruction of nearby tabular data.
            span_rect = fitz.Rect(l_data["x0"], l_data["y0"], l_data["x1"], l_data["y0"] + l_data["size"] * 1.2)
            self.current_page.add_redact_annot(span_rect)

        self.current_page.apply_redactions()

        old_lines = [l for l in old_text.split('\n') if l.strip()]
        new_lines = [l for l in new_text.split('\n') if l.strip()]
        line_diff = len(new_lines) - len(old_lines)

        if line_diff > 0:
            shift_amount = line_diff * font_size * 1.2
            self.push_elements_down_destructive(start_y + font_size * 1.2, shift_amount)

        font_args = {}
        if font_file:
            font_args['fontfile'] = font_file
            font_args['fontname'] = 'custom'
        else:
            # Attempt to use embedded buffer
            try:
                fonts = self.doc.get_page_fonts(self.current_page_num)
                for f in fonts:
                    if f[3] in font_name:
                        font_args['fontbuffer'] = self.doc.extract_font(f[0])[3]
                        font_args['fontname'] = font_name
                        break
            except Exception:
                pass

        for i, line_text in enumerate(new_lines):
            if i < len(original_lines_data):
                # Use EXACT original coordinates
                l_data = original_lines_data[i]
                target_x0 = l_data["x0"]
                target_y0 = l_data["y0"]
                f_size = l_data["size"]
            else:
                target_x0 = original_lines_data[-1]["x0"]
                target_y0 = start_y + (i * font_size * 1.2)
                f_size = font_size

            line_rect = fitz.Rect(target_x0, target_y0, self.current_page.rect.width, self.current_page.rect.height)
            try:
                self.current_page.insert_textbox(line_rect, line_text, fontsize=f_size, **font_args)
            except Exception:
                self.current_page.insert_textbox(line_rect, line_text, fontsize=f_size)

        self.render_page()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PDFEditorWindow()
    window.show()
    sys.exit(app.exec())
