import os
import fitz  # PyMuPDF
from PyQt6.QtWidgets import QMainWindow, QFileDialog, QMessageBox
from PyQt6 import uic
from PyQt6.QtGui import QAction

from src.canvas.pdf_canvas import PDFGraphicsScene, PDFGraphicsView
from src.commands.command_manager import CommandManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Load the UI dynamically
        ui_path = os.path.join(os.path.dirname(__file__), "main_window.ui")
        uic.loadUi(ui_path, self)

        # Initialize Core Systems
        self.cmd_manager = CommandManager()
        self.doc = None  # Holds the fitz.Document

        # Setup Canvas
        self.scene = PDFGraphicsScene(self)
        self.view = PDFGraphicsView(self.scene, self)

        # Add view to the canvasLayout defined in the UI
        self.canvasLayout.addWidget(self.view)

        # Connect Actions
        self.actionNew.triggered.connect(self.new_pdf)
        self.actionOpen.triggered.connect(self.open_pdf)
        self.actionSave.triggered.connect(self.save_pdf)
        self.actionSaveAs.triggered.connect(lambda: self.save_pdf(save_as=True))
        self.actionUndo.triggered.connect(self.cmd_manager.undo)
        self.actionRedo.triggered.connect(self.cmd_manager.redo)

        # Connect Stack state to UI (enable/disable based on stack)
        self.cmd_manager.undo_stack.canUndoChanged.connect(self.actionUndo.setEnabled)
        self.cmd_manager.undo_stack.canRedoChanged.connect(self.actionRedo.setEnabled)

        # Connect Canvas Signals
        self.scene.text_item_added.connect(self._on_text_item_added)
        self.scene.selectionChanged.connect(self._on_selection_changed)
        self.scene.canvas_double_clicked.connect(self._on_canvas_double_clicked)

        # Track current state
        self.original_filepath = None
        self._is_formatting_programmatically = False
        self.scene.selectionChanged.connect(self._on_selection_changed)

        # Track current state
        self.original_filepath = None
        self._is_formatting_programmatically = False

        # Initial states
        self.actionUndo.setEnabled(False)
        self.actionRedo.setEnabled(False)

        # Populate Formatting Toolbar
        self._init_formatting_toolbar()

        self.statusbar.showMessage("Ready")

    def _init_formatting_toolbar(self):
        """Initialize the UI elements in the formatting toolbar programmatically."""
        from PyQt6.QtWidgets import QComboBox, QSpinBox, QPushButton

        # 1. Add Text Tool
        self.addTextButton = QPushButton("Add Text")
        self.addTextButton.setCheckable(True)
        self.addTextButton.setToolTip("Click to add text to the PDF")
        self.addTextButton.toggled.connect(self._on_add_text_toggled)
        self.toolBar.addWidget(self.addTextButton)

        self.toolBar.addSeparator()

        # 2. Font Family
        self.fontFamilyComboBox = QComboBox()
        base_fonts = ["Helvetica", "Times-Roman", "Courier", "Symbol", "ZapfDingbats"]
        self.fontFamilyComboBox.addItems(base_fonts)
        self.fontFamilyComboBox.setToolTip("Font Family")
        self.toolBar.addWidget(self.fontFamilyComboBox)

        # 3. Font Size
        self.fontSizeSpinBox = QSpinBox()
        self.fontSizeSpinBox.setRange(6, 144)
        self.fontSizeSpinBox.setValue(12)
        self.fontSizeSpinBox.setToolTip("Font Size")
        self.toolBar.addWidget(self.fontSizeSpinBox)

        self.toolBar.addSeparator()

        # 4. Bold, Italic, Underline
        self.boldButton = QPushButton("B")
        self.boldButton.setCheckable(True)
        self.toolBar.addWidget(self.boldButton)

        self.italicButton = QPushButton("I")
        self.italicButton.setCheckable(True)
        self.toolBar.addWidget(self.italicButton)

        self.underlineButton = QPushButton("U")
        self.underlineButton.setCheckable(True)
        self.toolBar.addWidget(self.underlineButton)

        self.toolBar.addSeparator()

        # 5. Color & Opacity
        self.colorButton = QPushButton("Color")
        self.toolBar.addWidget(self.colorButton)

        self.opacitySpinBox = QSpinBox()
        self.opacitySpinBox.setRange(0, 100)
        self.opacitySpinBox.setValue(100)
        self.opacitySpinBox.setSuffix("%")
        self.opacitySpinBox.setToolTip("Opacity")
        self.toolBar.addWidget(self.opacitySpinBox)

        self.toolBar.addSeparator()

        # 6. Format Painter
        self.formatPainterButton = QPushButton("Format Painter")
        self.formatPainterButton.setCheckable(True)
        self.toolBar.addWidget(self.formatPainterButton)

        self.toolBar.addSeparator()

        # 7. Business Features (Conversions & Tools)
        self.txtToPdfButton = QPushButton("TXT to PDF")
        self.toolBar.addWidget(self.txtToPdfButton)

        self.imgToPdfButton = QPushButton("Image to PDF")
        self.toolBar.addWidget(self.imgToPdfButton)

        self.csvToPdfButton = QPushButton("CSV to PDF")
        self.toolBar.addWidget(self.csvToPdfButton)

        self.printButton = QPushButton("Print")
        self.toolBar.addWidget(self.printButton)

        self.toggleGridButton = QPushButton("Toggle Grid")
        self.toggleGridButton.setCheckable(True)
        self.toolBar.addWidget(self.toggleGridButton)

        self.insertTableButton = QPushButton("Insert Table")
        self.toolBar.addWidget(self.insertTableButton)

        # Connect Signals
        self.fontFamilyComboBox.currentTextChanged.connect(self._on_format_changed)
        self.fontSizeSpinBox.valueChanged.connect(self._on_format_changed)
        self.boldButton.toggled.connect(self._on_format_changed)
        self.italicButton.toggled.connect(self._on_format_changed)
        self.underlineButton.toggled.connect(self._on_format_changed)
        self.colorButton.clicked.connect(self._on_color_clicked)
        self.opacitySpinBox.valueChanged.connect(self._on_format_changed)
        self.formatPainterButton.toggled.connect(self._on_format_painter_toggled)
        self.txtToPdfButton.clicked.connect(self.convert_txt_to_pdf)
        self.imgToPdfButton.clicked.connect(self.convert_img_to_pdf)
        self.csvToPdfButton.clicked.connect(self.convert_csv_to_pdf)
        self.printButton.clicked.connect(self.print_pdf)
        self.toggleGridButton.toggled.connect(self.toggle_grid)
        self.insertTableButton.clicked.connect(self.insert_table)

    def _on_add_text_toggled(self, checked):
        if checked:
            self.view.set_tool("add_text")
            self.statusbar.showMessage("Add Text Mode: Click anywhere on the canvas to add text.")
            # Uncheck if format painter is on
            self.formatPainterButton.setChecked(False)
        else:
            self.view.set_tool("select")
            self.statusbar.showMessage("Select Mode.")

    def _on_selection_changed(self):
        """Syncs the toolbar to the currently selected item."""
        items = self.scene.selectedItems()
        if not items:
            return

        item = items[0]
        from PyQt6.QtWidgets import QGraphicsTextItem
        if isinstance(item, QGraphicsTextItem):
            self._is_formatting_programmatically = True

            # Extract actual formatting from cursor if available
            cursor = item.textCursor()
            fmt = cursor.charFormat()
            font = fmt.font() if fmt.font().family() else item.font()
            color = fmt.foreground().color() if fmt.foreground().color().isValid() else item.defaultTextColor()

            # Update UI safely without triggering signals
            idx = self.fontFamilyComboBox.findText(font.family())
            if idx >= 0: self.fontFamilyComboBox.setCurrentIndex(idx)

            self.fontSizeSpinBox.setValue(font.pointSize())
            self.boldButton.setChecked(font.bold())
            self.italicButton.setChecked(font.italic())
            self.underlineButton.setChecked(font.underline())
            self.colorButton.setStyleSheet(f"background-color: {color.name()};")

            self._is_formatting_programmatically = False

    def _get_current_format_dict(self):
        from PyQt6.QtGui import QFont, QColor
        font = QFont(self.fontFamilyComboBox.currentText(), self.fontSizeSpinBox.value())
        font.setBold(self.boldButton.isChecked())
        font.setItalic(self.italicButton.isChecked())
        font.setUnderline(self.underlineButton.isChecked())

        # Extract color from stylesheet
        color = QColor("black") # Default
        style = self.colorButton.styleSheet()
        if "background-color" in style:
            hex_str = style.split("background-color:")[1].split(";")[0].strip()
            color = QColor(hex_str)

        return {"font": font, "color": color}

    def _on_format_changed(self, *args):
        if getattr(self, '_is_formatting_programmatically', False):
            return

        items = self.scene.selectedItems()
        if not items:
            return

        item = items[0]
        from PyQt6.QtWidgets import QGraphicsTextItem
        from src.commands.command_manager import ChangeFormatCommand

        if isinstance(item, QGraphicsTextItem):
            old_format = {"font": item.font(), "color": item.defaultTextColor()}
            new_format = self._get_current_format_dict()

            # Recreate QFont object explicitly. There is a PyQt6 bug where pulling from UI elements directly
            # sometimes doesn't persist through the command stack due to garbage collection bindings.
            from PyQt6.QtGui import QFont, QColor
            clean_new_font = QFont(new_format['font'].family(), new_format['font'].pointSize())
            clean_new_font.setBold(new_format['font'].bold())
            clean_new_font.setItalic(new_format['font'].italic())
            clean_new_font.setUnderline(new_format['font'].underline())

            clean_new = {"font": clean_new_font, "color": QColor(new_format['color'])}

            cmd = ChangeFormatCommand(item, old_format, clean_new, "Change Format")
            self.cmd_manager.push(cmd)

    def _on_color_clicked(self):
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor()
        if color.isValid():
            self.colorButton.setStyleSheet(f"background-color: {color.name()};")
            self._on_format_changed()

    def _on_format_painter_toggled(self, checked):
        if checked:
            self.statusbar.showMessage("Format Painter: Active. Click an item to copy its format.")
        else:
            self.statusbar.showMessage("Format Painter: Inactive.")


    def new_pdf(self):
        """Initializes a new, empty in-memory PDF Document."""
        if self.doc:
            self.doc.close()

        self.doc = fitz.Document()

        # Create a default blank page (A4 size: 595 x 842 points)
        page = self.doc.new_page(width=595, height=842)

        self.cmd_manager.clear()
        self.scene.clear()

        # Draw the blank page on the scene
        self._render_page(page)
        self.statusbar.showMessage("New PDF created.")

    def open_pdf(self):
        """Placeholder for opening an existing PDF."""
        filepath, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if filepath:
            if self.doc:
                self.doc.close()
            self.doc = fitz.open(filepath)
            self.cmd_manager.clear()
            self.scene.clear()

            if len(self.doc) > 0:
                self._render_page(self.doc[0])
            self.original_filepath = filepath
            self.statusbar.showMessage(f"Opened {os.path.basename(filepath)}")

    def save_pdf(self, save_as=False):
        """Compiles the canvas objects back onto the fitz document and saves it."""
        if not self.doc:
            QMessageBox.warning(self, "Warning", "No document to save.")
            return

        if save_as or getattr(self, 'original_filepath', None) is None:
            filepath, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
            if not filepath:
                return
            self.original_filepath = filepath

        try:
            page = self.doc[0]

            # Map QGraphicsItems to PyMuPDF
            for item in self.scene.items():
                if item.zValue() >= 0:
                    from PyQt6.QtWidgets import QGraphicsTextItem, QGraphicsPixmapItem, QGraphicsRectItem
                    zoom_factor = 2.0
                    x = item.x() / zoom_factor
                    y = item.y() / zoom_factor

                    if isinstance(item, QGraphicsTextItem):
                        text = item.toPlainText()

                        # Use internal QTextCursor format if available, fallback to item font
                        cursor = item.textCursor()
                        fmt = cursor.charFormat()
                        qfont = fmt.font() if fmt.font().family() else item.font()
                        qcolor = fmt.foreground().color() if fmt.foreground().color().isValid() else item.defaultTextColor()

                        fontsize = qfont.pointSizeF()
                        if fontsize <= 0: fontsize = qfont.pointSize()
                        if fontsize <= 0: fontsize = 12 # Fallback

                        pdf_color = (qcolor.red() / 255.0, qcolor.green() / 255.0, qcolor.blue() / 255.0)

                        family = "helv"
                        fname = qfont.family().lower()
                        if "times" in fname: family = "ti"
                        elif "courier" in fname: family = "co"

                        if qfont.bold() and qfont.italic(): fontname = f"{family}bi"
                        elif qfont.bold(): fontname = f"{family}bo"
                        elif qfont.italic(): fontname = f"{family}it"
                        else: fontname = f"{family}ro" if family == "ti" else family

                        baseline_y = y + (fontsize * 0.8)
                        page.insert_text(fitz.Point(x, baseline_y), text, fontname=fontname, fontsize=fontsize, color=pdf_color)

                    elif isinstance(item, QGraphicsRectItem):
                        # Masking block
                        # The QGraphicsRectItem geometry includes its internal rect() offset PLUS its scene pos().
                        # We map the QRectF directly to scene coordinates, then scale down to PyMuPDF.
                        scene_rect = item.sceneBoundingRect()
                        f_rect = fitz.Rect(
                            scene_rect.x() / zoom_factor,
                            scene_rect.y() / zoom_factor,
                            (scene_rect.x() + scene_rect.width()) / zoom_factor,
                            (scene_rect.y() + scene_rect.height()) / zoom_factor
                        )
                        brush_color = item.brush().color()
                        if brush_color.isValid() and brush_color.alpha() > 0:
                            pdf_fill = (brush_color.red()/255.0, brush_color.green()/255.0, brush_color.blue()/255.0)
                            page.draw_rect(f_rect, color=pdf_fill, fill=pdf_fill)

            # Save strategy: to avoid incremental lock errors on existing files,
            # we save to a temporary file, close the original, and swap.
            import tempfile
            import os
            import shutil

            fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)

            self.doc.save(tmp_path, garbage=3, deflate=True)
            self.doc.close()

            shutil.move(tmp_path, self.original_filepath)

            # Reload to continue editing
            self.doc = fitz.open(self.original_filepath)
            self.cmd_manager.clear() # Edits are baked in

            # Re-render to clear the scene of floating editable items since they are now baked
            self.scene.clear()
            self._render_page(self.doc[0])

            self.statusbar.showMessage(f"Saved to {self.original_filepath}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save document: {str(e)}")

    def _render_page(self, page: fitz.Page):
        """Renders a single PyMuPDF page to the QGraphicsScene."""
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Scale up for better initial resolution
        # For simplicity in this foundational step, we'll just add the pixmap as a background item.
        # In the future, this will need to be parsed to recreate editable text boxes.

        # Needs QImage conversion
        from PyQt6.QtGui import QImage, QPixmap
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        qpix = QPixmap.fromImage(img)

        pixmap_item = self.scene.addPixmap(qpix)
        pixmap_item.setPos(0, 0)
        pixmap_item.setZValue(-1) # Keep it in the background

        # Set scene rect to match page
        self.scene.setSceneRect(0, 0, qpix.width(), qpix.height())

    def _on_text_item_added(self, text_item):
        from src.commands.command_manager import AddGraphicsItemCommand
        # Push the creation to the undo stack
        self.scene.removeItem(text_item)

        cmd = AddGraphicsItemCommand(self.scene, text_item, "Add Text")
        self.cmd_manager.push(cmd)

        # Restore focus so the user can begin typing immediately
        text_item.setFocus()

        # Turn off the Add Text toggle button
        self.addTextButton.setChecked(False)

    def _on_canvas_double_clicked(self, scene_pos):
        """Extract text from PyMuPDF under the double click and spawn an editor."""
        if not self.doc or len(self.doc) == 0:
            return

        page = self.doc[0]

        # Convert Scene pos back to PyMuPDF pos
        zoom_factor = 2.0
        pdf_x = scene_pos.x() / zoom_factor
        pdf_y = scene_pos.y() / zoom_factor

        click_point = fitz.Point(pdf_x, pdf_y)

        # Search for text blocks
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block: continue
            for line in block["lines"]:
                for span in line["spans"]:
                    bbox = fitz.Rect(span["bbox"])
                    if bbox.contains(click_point):
                        self._spawn_editor_for_span(span, bbox, zoom_factor)
                        return

    def _spawn_editor_for_span(self, span, bbox, zoom_factor):
        from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem
        from PyQt6.QtGui import QColor, QFont, QTextCursor, QTextCharFormat
        from PyQt6.QtCore import Qt, QRectF
        from src.commands.command_manager import AddMaskAndTextCommand

        # 1. Create a Masking Rectangle (white out the baked text)
        rect_f = QRectF(bbox.x0 * zoom_factor, bbox.y0 * zoom_factor, bbox.width * zoom_factor, bbox.height * zoom_factor)
        mask = QGraphicsRectItem(rect_f)
        mask.setBrush(QColor(255, 255, 255)) # White
        mask.setPen(QColor(255, 255, 255, 0)) # Transparent border
        mask.setZValue(1)

        # 2. Create the Editable Text Item
        text_item = QGraphicsTextItem(span["text"])

        # Attempt to map font
        font = QFont()
        font.setPointSize(int(span["size"] * zoom_factor)) # Font size scales with zoom

        flags = span.get("flags", 0)
        if flags & 2: font.setItalic(True)
        if flags & 16: font.setBold(True)

        fontname = span.get("font", "").lower()
        if "times" in fontname: font.setFamily("Times-Roman")
        elif "courier" in fontname: font.setFamily("Courier")
        else: font.setFamily("Helvetica")

        text_item.setFont(font)

        # Map Color (int format to RGB)
        color_int = span.get("color", 0)
        r = (color_int >> 16) & 255
        g = (color_int >> 8) & 255
        b = color_int & 255
        qcolor = QColor(r, g, b)
        text_item.setDefaultTextColor(qcolor)

        # Positioning: PyMuPDF bounding box top-left mapped to Qt top-left
        # QGraphicsTextItem has some internal padding, we adjust slightly.
        padding_offset = 4
        text_item.setPos((bbox.x0 * zoom_factor) - padding_offset, (bbox.y0 * zoom_factor) - padding_offset)
        text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        text_item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable)
        text_item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)
        text_item.setZValue(2)

        # 3. Push to Undo Stack
        cmd = AddMaskAndTextCommand(self.scene, mask, text_item, "Edit PDF Text")
        self.cmd_manager.push(cmd)

        # 4. Trigger selection UI sync and focus
        text_item.setSelected(True)
        text_item.setFocus()

    # --- Business Features ---

    def convert_txt_to_pdf(self):
        from fpdf import FPDF
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Text File", "", "Text Files (*.txt)")
        if not filepath: return
        with open(filepath, 'r', encoding='utf-8') as f: text_content = f.read()

        # Replace non-latin1 characters with '?' to prevent FPDF crash
        text_content = text_content.encode('latin-1', 'replace').decode('latin-1')

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", size=12)
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
        from fpdf import FPDF
        import csv
        filepath, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)")
        if not filepath: return
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", size=10)
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                line = " | ".join(row)
                line = line.encode('latin-1', 'replace').decode('latin-1')
                pdf.cell(0, 10, txt=line, ln=True)
        out_path = filepath + ".pdf"
        pdf.output(out_path)
        QMessageBox.information(self, "Success", f"Converted to {out_path}")

    def print_pdf(self):
        if not self.doc:
            QMessageBox.warning(self, "Warning", "No document to print.")
            return

        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt6.QtGui import QPainter, QImage
        from PyQt6.QtCore import Qt

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)

        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            painter = QPainter()
            if not painter.begin(printer):
                QMessageBox.warning(self, "Warning", "Failed to open printer.")
                return

            for page_num in range(len(self.doc)):
                if page_num > 0:
                    printer.newPage()

                page = self.doc[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3)) # High res
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)

                # Scale to fit printer page
                rect = painter.viewport()
                size = img.size()
                size.scale(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
                painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
                painter.setWindow(img.rect())

                painter.drawImage(0, 0, img)

            painter.end()

    def toggle_grid(self, checked):
        if checked:
            self.statusbar.showMessage("Grid overlay enabled (View only).")
            # Drawing a simple visual grid over the QGraphicsScene.
            from PyQt6.QtWidgets import QGraphicsLineItem
            from PyQt6.QtGui import QPen, QColor
            from PyQt6.QtCore import Qt

            self._grid_lines = []
            pen = QPen(QColor(200, 200, 200, 150))
            pen.setStyle(Qt.PenStyle.DashLine)

            # Simple 50px grid
            width = self.scene.sceneRect().width()
            height = self.scene.sceneRect().height()

            for x in range(0, int(width), 50):
                line = self.scene.addLine(x, 0, x, height, pen)
                line.setZValue(100) # Draw over everything
                self._grid_lines.append(line)
            for y in range(0, int(height), 50):
                line = self.scene.addLine(0, y, width, y, pen)
                line.setZValue(100)
                self._grid_lines.append(line)
        else:
            self.statusbar.showMessage("Grid overlay disabled.")
            if hasattr(self, '_grid_lines'):
                for line in self._grid_lines:
                    self.scene.removeItem(line)
                self._grid_lines = []

    def insert_table(self):
        from PyQt6.QtWidgets import QInputDialog
        rows, ok1 = QInputDialog.getInt(self, "Insert Table", "Rows:", 3, 1, 100)
        if not ok1: return
        cols, ok2 = QInputDialog.getInt(self, "Insert Table", "Columns:", 3, 1, 100)
        if not ok2: return

        # We define a quick TableContainer layout since it was part of the legacy UI
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QSizeGrip
        from PyQt6.QtWidgets import QGraphicsProxyWidget
        from PyQt6.QtCore import Qt

        class TableContainer(QWidget):
            def __init__(self, r, c, parent=None):
                super().__init__(parent)
                self.layout = QVBoxLayout(self)
                self.layout.setContentsMargins(0, 0, 0, 0)
                self.layout.setSpacing(0)

                self.handle = QLabel("    [:: Drag Table ::]")
                self.handle.setStyleSheet("background-color: lightgray; border: 1px solid black; font-size: 10px; padding: 2px;")
                self.handle.setFixedHeight(20)
                self.layout.addWidget(self.handle)

                self.table = QTableWidget(r, c)
                self.table.horizontalHeader().setVisible(False)
                self.table.verticalHeader().setVisible(False)
                self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                self.table.setStyleSheet("QTableWidget { background-color: white; } QTableWidget::item { border: 1px solid black; }")
                self.layout.addWidget(self.table)

                self.grip = QSizeGrip(self)
                self.grip.setFixedSize(15, 15)
                self.layout.addWidget(self.grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

            def resizeEvent(self, event):
                super().resizeEvent(event)
                available_width = self.width()
                available_height = self.height() - self.handle.height() - self.grip.height()
                if self.table.columnCount() > 0:
                    col_w = int(available_width / self.table.columnCount())
                    for c in range(self.table.columnCount()):
                        self.table.setColumnWidth(c, col_w)
                if self.table.rowCount() > 0:
                    row_h = int(available_height / self.table.rowCount())
                    for r in range(self.table.rowCount()):
                        self.table.setRowHeight(r, row_h)

        container = TableContainer(rows, cols)
        container.setFixedSize(cols * 100, rows * 30 + 35)

        # We need a proxy to put it in the scene
        proxy = QGraphicsProxyWidget()
        proxy.setWidget(container)
        proxy.setFlag(QGraphicsProxyWidget.GraphicsItemFlag.ItemIsMovable, True)
        proxy.setFlag(QGraphicsProxyWidget.GraphicsItemFlag.ItemIsSelectable, True)
        proxy.setPos(50, 50)

        # In a real scenario we push this to UndoStack, but for now just add to scene
        from src.commands.command_manager import AddGraphicsItemCommand
        cmd = AddGraphicsItemCommand(self.scene, proxy, "Insert Table")
        self.cmd_manager.push(cmd)
