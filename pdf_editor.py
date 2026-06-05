import sys
import os
import fitz  # PyMuPDF
import requests
import tempfile
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QTextEdit, QSplitter,
    QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem
)
from PyQt6.QtGui import QPixmap, QImage, QColor, QPen, QBrush
from PyQt6.QtCore import Qt, QRectF

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
            self.callback(self.block_index)
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
        self.selected_block_index = -1
        self.temp_dir = tempfile.mkdtemp()

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

        # Splitter for Canvas and Editor
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # PDF Canvas
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        splitter.addWidget(self.view)

        # Editor Pane
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        self.editor_text = QTextEdit()
        self.btn_apply = QPushButton("Apply Changes")
        self.btn_apply.clicked.connect(self.apply_changes)

        editor_layout.addWidget(QLabel("Edit Text Block:"))
        editor_layout.addWidget(self.editor_text)
        editor_layout.addWidget(self.btn_apply)
        splitter.addWidget(editor_widget)

        # Set splitter sizes
        splitter.setSizes([800, 400])

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

        # Get pixmap of the page
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        pix = self.current_page.get_pixmap(matrix=mat)

        # Convert fitz pixmap to QPixmap properly to avoid memory issues
        samples = pix.samples
        img = QImage(samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        qpixmap = QPixmap.fromImage(img)

        # Add to scene
        pixmap_item = QGraphicsPixmapItem(qpixmap)
        self.scene.addItem(pixmap_item)
        self.scene.setSceneRect(0.0, 0.0, float(pix.width), float(pix.height))

        # Extract text blocks and add clickable overlays
        self.blocks = self.current_page.get_text("blocks")

        for i, b in enumerate(self.blocks):
            if b[6] == 0:  # If it's a text block
                x0, y0, x1, y1 = b[:4]
                # Scale coordinates to match zoom
                rect = QRectF(x0 * zoom, y0 * zoom, (x1 - x0) * zoom, (y1 - y0) * zoom)
                rect_item = ClickableRectItem(rect, i, self.block_clicked)
                self.scene.addItem(rect_item)

    def block_clicked(self, block_index):
        self.selected_block_index = block_index
        block = self.blocks[block_index]
        text = block[4]
        self.editor_text.setText(text)

    def attempt_font_download(self, font_name):
        """
        Attempts to download the font if it looks like a known open-source font.
        """
        # Clean font name (e.g., 'ABCDEF+Roboto-Regular' -> 'Roboto-Regular')
        clean_name = font_name.split('+')[-1]
        base_name = clean_name.split('-')[0]

        # We use a known Google Fonts repository structure as a fallback check
        url = f"https://github.com/google/fonts/raw/main/ofl/{base_name.lower()}/{clean_name}.ttf"

        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                filepath = os.path.join(self.temp_dir, f"{clean_name}.ttf")
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                return filepath
        except Exception:
            pass

        return None

    def apply_changes(self):
        if not self.doc or self.selected_block_index == -1:
            return

        new_text = self.editor_text.toPlainText()
        block = self.blocks[self.selected_block_index]
        old_text = block[4]

        if new_text == old_text:
            return

        # Get font info from the block
        block_dict = self.current_page.get_text("dict")["blocks"][self.selected_block_index]

        font_name = "helv"
        font_size = 11
        if "lines" in block_dict and len(block_dict["lines"]) > 0:
            if "spans" in block_dict["lines"][0] and len(block_dict["lines"][0]["spans"]) > 0:
                span = block_dict["lines"][0]["spans"][0]
                font_name = span["font"]
                font_size = span["size"]

        font_file = self.attempt_font_download(font_name)

        if not font_file:
            reply = QMessageBox.question(self, 'Font Replacement',
                                         f'Original Font ({font_name}) is either proprietary or subsetted, and could not be downloaded.\nDo you want to provide a local font file (.ttf/.otf) for this text? Otherwise standard Helvetica will be used.',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                font_file, _ = QFileDialog.getOpenFileName(self, "Select Font File", "", "Font Files (*.ttf *.otf)")
                if not font_file:
                    font_file = None
        else:
            QMessageBox.information(self, "Font Downloaded", f"Automatically downloaded font: {font_name}")

        rect = fitz.Rect(block[:4])

        # Calculate new height
        test_doc = fitz.open()
        test_page = test_doc.new_page(width=self.current_page.rect.width, height=self.current_page.rect.height)

        font_args = {}
        if font_file:
            font_args['fontfile'] = font_file
            font_args['fontname'] = 'custom'

        test_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, self.current_page.rect.y1)
        test_page.insert_textbox(test_rect, new_text, fontsize=font_size, **font_args)

        test_blocks = test_page.get_text("blocks")
        new_height = 0
        if len(test_blocks) > 0:
            new_height = test_blocks[0][3] - test_blocks[0][1]

        old_height = rect.y1 - rect.y0
        height_diff = new_height - old_height

        if height_diff > 5:
            self.push_elements_down_destructive(rect.y1, height_diff)

        # Wipe the old text
        self.current_page.add_redact_annot(rect)
        self.current_page.apply_redactions()

        # Insert text
        self.current_page.insert_textbox(test_rect, new_text, fontsize=font_size, **font_args)

        if height_diff > 5:
            QMessageBox.information(self, "Reflow Complete",
                                    f"Text block expanded. Pushed subsequent elements down by {height_diff:.2f} points.")

        self.render_page()

    def push_elements_down_destructive(self, threshold_y, shift_amount):
        """
        Physically shifts text blocks and images below the threshold by redacting
        and redrawing them lower.
        """
        all_blocks = self.current_page.get_text("dict")["blocks"]

        text_elements_to_redraw = []
        images_to_redraw = []

        for b in all_blocks:
            bbox = fitz.Rect(b["bbox"])
            if bbox.y0 >= threshold_y - 2: # Give a small margin
                self.current_page.add_redact_annot(bbox)

                if b["type"] == 0:  # Text
                    text_elements_to_redraw.append(b)
                elif b["type"] == 1: # Image
                    # PyMuPDF extracts image block dictionary
                    images_to_redraw.append({
                        "bbox": bbox,
                        "image": b.get("image", None),
                        "ext": b.get("ext", "png")
                    })

        self.current_page.apply_redactions()

        # Redraw text blocks shifted
        for b in text_elements_to_redraw:
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    span_bbox = fitz.Rect(span["bbox"])
                    text = span["text"]
                    font_size = span["size"]
                    font_name = span["font"]
                    shifted_rect = fitz.Rect(span_bbox.x0, span_bbox.y0 + shift_amount,
                                             span_bbox.x1, span_bbox.y1 + shift_amount)

                    self.current_page.insert_textbox(shifted_rect, text, fontsize=font_size)

        # Redraw images shifted
        for img in images_to_redraw:
            if img["image"]:
                bbox = img["bbox"]
                shifted_rect = fitz.Rect(bbox.x0, bbox.y0 + shift_amount,
                                         bbox.x1, bbox.y1 + shift_amount)
                # insert_image requires a bytes stream
                self.current_page.insert_image(shifted_rect, stream=img["image"])


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PDFEditorWindow()
    window.show()
    sys.exit(app.exec())
