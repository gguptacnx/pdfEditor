from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsTextItem
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont

class PDFGraphicsScene(QGraphicsScene):
    """Custom QGraphicsScene to handle PDF rendering and interaction."""
    # Signal emitted when a new text item has finished being edited for the first time
    text_item_added = pyqtSignal(QGraphicsTextItem)

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

        # Tools state
        self.current_tool = "select" # can be 'select' or 'add_text'

    def set_tool(self, tool_name: str):
        self.current_tool = tool_name
        if tool_name == "add_text":
            self.setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if self.current_tool == "add_text" and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())

            # Create a new text item
            text_item = QGraphicsTextItem()
            text_item.setPos(scene_pos)
            text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
            text_item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable)
            text_item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)

            # Default Font
            font = QFont("Helvetica", 12)
            text_item.setFont(font)

            self.scene().addItem(text_item)

            # Give it focus immediately
            text_item.setFocus()

            # We don't push to undo stack here yet. We wait until they finish typing.
            # We'll hook into focus out event via a custom class or signal in the future.
            # For this MVP, we push it immediately but it might be empty if they don't type.
            # Let's emit it to the main window to handle the Undo command.
            if isinstance(self.scene(), PDFGraphicsScene):
                self.scene().text_item_added.emit(text_item)

            # Reset tool
            self.set_tool("select")
            # We need to signal the UI that the tool reset, but for now we'll just handle it internally.

        else:
            super().mousePressEvent(event)

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
