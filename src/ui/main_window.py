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

        # Initial states
        self.actionUndo.setEnabled(False)
        self.actionRedo.setEnabled(False)

        self.statusbar.showMessage("Ready")

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
                        # Default insertion, ignoring complex formatting for now
                        page.insert_text(fitz.Point(x, y), text, fontname="helv", fontsize=12, color=(0,0,0))

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
