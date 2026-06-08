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
        from PyQt6.QtWidgets import QToolButton, QMenu, QWidgetAction, QWidget, QVBoxLayout, QLabel, QPushButton, QGridLayout, QHBoxLayout
        from PyQt6.QtCore import Qt

        self.toolBar.setMovable(False)
        self.toolBar.setStyleSheet("QToolBar { background-color: white; border-bottom: 1px solid #ccc; } QToolButton { padding: 5px 10px; border: 1px solid transparent; border-radius: 4px; } QToolButton:hover { border: 1px solid #0078D4; background-color: #E5F1FB; } QToolButton:checked { border: 1px solid #0078D4; background-color: #CCE4F7; }")

        # 1. Text Tool & Search
        self.btn_text = QToolButton()
        self.btn_text.setText("Text")
        self.btn_text.setToolTip("Add text. Change or delete existing text.")
        self.btn_text.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.btn_text.setCheckable(True)
        menu_text = QMenu(self)
        action_find = menu_text.addAction("Find & Replace")
        self.btn_text.setMenu(menu_text)
        self.btn_text.toggled.connect(self._on_add_text_toggled)
        self.toolBar.addWidget(self.btn_text)

        # 2. Links Tool
        self.btn_links = QToolButton()
        self.btn_links.setText("Links")
        self.btn_links.setToolTip("Add links. Change existing links.")
        self.btn_links.setCheckable(True)
        self.toolBar.addWidget(self.btn_links)

        # 3. Interactive Forms Tool
        self.btn_forms = QToolButton()
        self.btn_forms.setText("Forms")
        self.btn_forms.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_forms = QMenu(self)
        menu_forms.setStyleSheet("QMenu::item { padding: 5px 20px; }")

        # Form Sections (Using custom QWidgetActions to get layout headers)
        w_forms = QWidget()
        l_forms = QVBoxLayout(w_forms)
        l_forms.setContentsMargins(5, 5, 5, 5)

        lbl1 = QLabel("ADD TEXT AND SYMBOLS")
        lbl1.setStyleSheet("color: gray; font-size: 10px; font-weight: bold;")
        l_forms.addWidget(lbl1)

        # Symbols row
        row1 = QHBoxLayout()
        row1.addWidget(QPushButton("IA"))
        row1.addWidget(QPushButton("X"))
        row1.addWidget(QPushButton("✓"))
        row1.addWidget(QPushButton("●"))
        l_forms.addLayout(row1)

        lbl2 = QLabel("ADD NEW FORM FIELDS")
        lbl2.setStyleSheet("color: gray; font-size: 10px; font-weight: bold; margin-top: 10px;")
        l_forms.addWidget(lbl2)

        grid = QGridLayout()
        grid.addWidget(QPushButton("Text"), 0, 0)
        grid.addWidget(QPushButton("Radio button"), 0, 1)
        grid.addWidget(QPushButton("Text multiline"), 1, 0)
        grid.addWidget(QPushButton("Checkbox"), 1, 1)
        grid.addWidget(QPushButton("Drop-down list"), 2, 0)
        grid.addWidget(QPushButton("Signature box"), 2, 1)
        l_forms.addLayout(grid)

        lbl3 = QLabel("CHANGE EXISTING FORM FIELDS")
        lbl3.setStyleSheet("color: gray; font-size: 10px; font-weight: bold; margin-top: 10px;")
        l_forms.addWidget(lbl3)
        l_forms.addWidget(QPushButton("Form Edit mode"))
        l_forms.addWidget(QPushButton("Change tab order"))

        wa_forms = QWidgetAction(self)
        wa_forms.setDefaultWidget(w_forms)
        menu_forms.addAction(wa_forms)
        self.btn_forms.setMenu(menu_forms)
        self.toolBar.addWidget(self.btn_forms)

        # 4. Images & Stamps Tool
        self.btn_images = QToolButton()
        self.btn_images.setText("Images")
        self.btn_images.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_images = QMenu(self)
        w_images = QWidget()
        l_images = QVBoxLayout(w_images)
        lbl_img = QLabel("[ PREVIEW BOX: DRAFT X ]")
        lbl_img.setStyleSheet("color: red; border: 1px solid red; padding: 10px; text-align: center;")
        l_images.addWidget(lbl_img)
        l_images.addWidget(QPushButton("+ New Image"))
        l_images.addWidget(QPushButton("Delete existing image"))
        l_images.addWidget(QPushButton("+ New Stamp"))
        wa_images = QWidgetAction(self)
        wa_images.setDefaultWidget(w_images)
        menu_images.addAction(wa_images)
        self.btn_images.setMenu(menu_images)
        self.toolBar.addWidget(self.btn_images)

        # 5. Sign Tool
        self.btn_sign = QToolButton()
        self.btn_sign.setText("Sign")
        self.btn_sign.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_sign = QMenu(self)
        w_sign = QWidget()
        l_sign = QVBoxLayout(w_sign)
        lbl_sign = QLabel("[ SIGNATURE PREVIEW: Govind ]")
        l_sign.addWidget(lbl_sign)
        l_sign.addWidget(QPushButton("+ New Signature"))
        wa_sign = QWidgetAction(self)
        wa_sign.setDefaultWidget(w_sign)
        menu_sign.addAction(wa_sign)
        self.btn_sign.setMenu(menu_sign)
        self.toolBar.addWidget(self.btn_sign)

        # 6. Whiteout Tool
        self.btn_whiteout = QToolButton()
        self.btn_whiteout.setText("Whiteout")
        self.btn_whiteout.setToolTip("Whiteout")
        self.btn_whiteout.setCheckable(True)
        self.toolBar.addWidget(self.btn_whiteout)

        # 7. Annotate Tool
        self.btn_annotate = QToolButton()
        self.btn_annotate.setText("Annotate")
        self.btn_annotate.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_annotate = QMenu(self)
        w_ann = QWidget()
        l_ann = QVBoxLayout(w_ann)
        l_ann.addWidget(QPushButton("Show annotations (Toggle)"))
        l_ann.addWidget(QLabel("TEXT"))
        l_ann.addWidget(QPushButton("Strike out [Colors]"))
        l_ann.addWidget(QPushButton("Highlight [Colors]"))
        l_ann.addWidget(QPushButton("Underline [Colors]"))
        l_ann.addWidget(QLabel("FREEHAND"))
        l_ann.addWidget(QPushButton("Highlight [Colors]"))
        l_ann.addWidget(QPushButton("Draw [Colors]"))
        wa_ann = QWidgetAction(self)
        wa_ann.setDefaultWidget(w_ann)
        menu_annotate.addAction(wa_ann)
        self.btn_annotate.setMenu(menu_annotate)
        self.toolBar.addWidget(self.btn_annotate)

        # 8. Shapes Tool
        self.btn_shapes = QToolButton()
        self.btn_shapes.setText("Shapes")
        self.btn_shapes.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_shapes = QMenu(self)
        menu_shapes.addAction("Ellipse")
        menu_shapes.addAction("Rectangle")
        menu_shapes.addAction("Line")
        menu_shapes.addAction("Arrow")
        self.btn_shapes.setMenu(menu_shapes)
        self.toolBar.addWidget(self.btn_shapes)

        # 9. Undo Manager Dialog Tool
        self.btn_undo_dialog = QToolButton()
        self.btn_undo_dialog.setText("Undo")
        self.btn_undo_dialog.clicked.connect(self._show_undo_dialog)
        self.toolBar.addWidget(self.btn_undo_dialog)
        self.btn_text.toggled.connect(self._on_add_text_toggled)
        self.btn_whiteout.toggled.connect(self._on_whiteout_toggled)

    def _show_undo_dialog(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QLabel
        d = QDialog(self)
        d.setWindowTitle("Undo changes")
        d.resize(400, 300)
        l = QVBoxLayout(d)

        if self.cmd_manager.undo_stack.count() == 0:
            l.addWidget(QLabel("No changes found"))
        else:
            lst = QListWidget()
            for i in range(self.cmd_manager.undo_stack.count()):
                cmd = self.cmd_manager.undo_stack.command(i)
                lst.addItem(f"Action {i+1}: {cmd.actionText()}")
            l.addWidget(lst)
            btn = QPushButton("Revert selected")
            def _revert():
                selected = lst.currentRow()
                if selected >= 0:
                    # QUndoStack index works backwards when undoing
                    self.cmd_manager.undo_stack.setIndex(selected)
                    d.accept()

            btn.clicked.connect(_revert)
            l.addWidget(btn)

        d.exec()

    def _on_add_text_toggled(self, checked):
        if checked:
            self.view.set_tool("add_text")
            self.statusbar.showMessage("Add Text Mode: Click anywhere on the canvas to add text.")
            # Uncheck conflicting modes
            if getattr(self, 'btn_whiteout', None):
                self.btn_whiteout.setChecked(False)
        else:
            self.view.set_tool("select")
            self.statusbar.showMessage("Select Mode.")

    def _on_selection_changed(self):
        """Syncs the toolbar to the currently selected item. (Disabled until Formatting Toolbar is rebuilt)"""
        pass

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
        pass

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

            # Map QGraphicsItems to PyMuPDF in a Two-Pass System
            from PyQt6.QtWidgets import QGraphicsTextItem, QGraphicsPixmapItem, QGraphicsRectItem
            zoom_factor = 2.0

            # Pass 1: Destructive Redactions (Masks & Whiteouts)
            has_redactions = False
            for item in self.scene.items():
                if item.zValue() >= 0 and isinstance(item, QGraphicsRectItem):
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
                        page.add_redact_annot(f_rect, fill=pdf_fill)
                        has_redactions = True

            if has_redactions:
                page.apply_redactions()

            # Pass 2: Additive Layering (Text, Signatures, Drawn shapes)
            for item in self.scene.items():
                if item.zValue() >= 0:
                    x = item.x() / zoom_factor
                    y = item.y() / zoom_factor

                    if isinstance(item, QGraphicsTextItem):
                        text = item.toPlainText()

                        cursor = item.textCursor()
                        fmt = cursor.charFormat()
                        qfont = fmt.font() if fmt.font().family() else item.font()
                        qcolor = fmt.foreground().color() if fmt.foreground().color().isValid() else item.defaultTextColor()

                        fontsize = qfont.pointSizeF()
                        if fontsize <= 0: fontsize = qfont.pointSize()
                        if fontsize <= 0: fontsize = 12 * zoom_factor
                        fontsize = fontsize / zoom_factor

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
        self.btn_text.setChecked(False)

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
        # QGraphicsTextItem has a document margin of 4px by default. We must counteract this.
        text_item.document().setDocumentMargin(0)

        # PyMuPDF bbox includes font descent. We align closely to top-left.
        text_item.setPos((bbox.x0 * zoom_factor), (bbox.y0 * zoom_factor))
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

    def _on_whiteout_toggled(self, checked):
        if checked:
            self.view.set_tool("whiteout")
            self.statusbar.showMessage("Whiteout Mode: Click and drag to create redaction blocks.")
            if getattr(self, 'btn_text', None): self.btn_text.setChecked(False)
        else:
            self.view.set_tool("select")
            self.statusbar.showMessage("Select Mode.")
