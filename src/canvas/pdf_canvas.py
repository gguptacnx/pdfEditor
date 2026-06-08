from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor

class PDFGraphicsScene(QGraphicsScene):
    """Custom QGraphicsScene to handle PDF rendering and interaction."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QColor(240, 240, 240)) # Light gray background for the canvas area


class PDFGraphicsView(QGraphicsView):
    """Custom QGraphicsView with zoom and pan capabilities."""
    def __init__(self, scene=None, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.zoom_factor = 1.0
        self.zoom_step = 0.1

    def wheelEvent(self, event):
        """Handle zooming with Ctrl + Mouse Wheel."""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            super().wheelEvent(event)

    def zoom_in(self):
        self.zoom_factor += self.zoom_step
        self.apply_zoom()

    def zoom_out(self):
        self.zoom_factor -= self.zoom_step
        if self.zoom_factor < 0.1:
            self.zoom_factor = 0.1
        self.apply_zoom()

    def apply_zoom(self):
        self.resetTransform()
        self.scale(self.zoom_factor, self.zoom_factor)
