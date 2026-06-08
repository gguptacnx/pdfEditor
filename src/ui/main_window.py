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
        self.actionUndo.triggered.connect(self.cmd_manager.undo)
        self.actionRedo.triggered.connect(self.cmd_manager.redo)

        # Connect Stack state to UI (enable/disable based on stack)
        self.cmd_manager.undo_stack.canUndoChanged.connect(self.actionUndo.setEnabled)
        self.cmd_manager.undo_stack.canRedoChanged.connect(self.actionRedo.setEnabled)

        # Connect Canvas Signals
        self.scene.text_item_added.connect(self._on_text_item_added)

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

        # Connect Signals
        self.fontFamilyComboBox.currentTextChanged.connect(self._on_format_changed)
        self.fontSizeSpinBox.valueChanged.connect(self._on_format_changed)
        self.boldButton.toggled.connect(self._on_format_changed)
        self.italicButton.toggled.connect(self._on_format_changed)
        self.underlineButton.toggled.connect(self._on_format_changed)
        self.colorButton.clicked.connect(self._on_color_clicked)
        self.opacitySpinBox.valueChanged.connect(self._on_format_changed)
        self.formatPainterButton.toggled.connect(self._on_format_painter_toggled)

    def _on_add_text_toggled(self, checked):
        if checked:
            self.view.set_tool("add_text")
            self.statusbar.showMessage("Add Text Mode: Click anywhere on the canvas to add text.")
            # Uncheck if format painter is on
            self.formatPainterButton.setChecked(False)
        else:
            self.view.set_tool("select")
            self.statusbar.showMessage("Select Mode.")

    def _on_format_changed(self, *args):
        # Stub for when a formatting property is updated
        # This will later be hooked up to the currently selected QGraphicsItem via QUndoCommand
        pass

    def _on_color_clicked(self):
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor()
        if color.isValid():
            # Update the button visual or store the color state
            # Stub for now
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
            self.statusbar.showMessage(f"Opened {os.path.basename(filepath)}")

    def save_pdf(self):
        """Compiles the canvas objects back onto the fitz document and saves it."""
        if not self.doc:
            QMessageBox.warning(self, "Warning", "No document to save.")
            return

        filepath, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if not filepath:
            return

        try:
            # We are assuming a single page for now as per the New PDF workflow.
            page = self.doc[0]

            # The background image is added with Z=-1. Real objects have Z>=0.
            for item in self.scene.items():
                if item.zValue() >= 0:
                    from PyQt6.QtWidgets import QGraphicsTextItem, QGraphicsPixmapItem, QGraphicsRectItem

                    # Convert View Coordinates to PDF Coordinates.
                    # In our New PDF, we scaled the pixmap by a matrix(2,2).
                    # If an item is placed at (x,y) on the scene, its actual PDF coordinate is (x/2, y/2).
                    zoom_factor = 2.0

                    x = item.x() / zoom_factor
                    y = item.y() / zoom_factor

                    if isinstance(item, QGraphicsTextItem):
                        text = item.toPlainText()
                        # PyMuPDF insert_text expects the bottom-left baseline coordinate, not the top-left bounding box.
                        # We approximate the baseline descent offset (roughly 80% of font size).
                        fontsize = 12
                        baseline_y = y + (fontsize * 0.8)
                        # Default insertion, ignoring complex formatting for now
                        page.insert_text(fitz.Point(x, baseline_y), text, fontname="helv", fontsize=fontsize, color=(0,0,0))

                    elif isinstance(item, QGraphicsRectItem):
                        rect = item.rect()
                        # Map QRectF to fitz.Rect
                        f_rect = fitz.Rect(x, y, x + (rect.width() / zoom_factor), y + (rect.height() / zoom_factor))
                        page.draw_rect(f_rect, color=(1,0,0), width=1) # Draw a red box for debugging/test

                    elif isinstance(item, QGraphicsPixmapItem):
                        pass # To be implemented in the Object Manipulation Module

            self.doc.save(filepath)
            self.statusbar.showMessage(f"Saved to {filepath}")
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
