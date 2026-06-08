from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsTextItem
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont

class PDFGraphicsScene(QGraphicsScene):
    """Custom QGraphicsScene to handle PDF rendering and interaction."""
    # Signal emitted when a new text item has finished being edited for the first time
    # Signal emitted when an item (text or rect) has finished being edited for the first time
    text_item_added = pyqtSignal(object) # Changed from QGraphicsTextItem to object to allow QGraphicsRectItem
    # Signal emitted when double clicking on the canvas
    canvas_double_clicked = pyqtSignal(object) # passes QPointF scene_pos

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
        self.current_tool = "select" # can be 'select', 'add_text', or 'whiteout'
        self._is_drawing_rect = False
        self._current_rect_item = None
        self._rect_start_pos = None

    def set_tool(self, tool_name: str):
        self.current_tool = tool_name
        if tool_name == "add_text":
            self.setCursor(Qt.CursorShape.IBeamCursor)
        elif tool_name == "whiteout":
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.current_tool == "select":
            scene_pos = self.mapToScene(event.pos())
            if isinstance(self.scene(), PDFGraphicsScene):
                self.scene().canvas_double_clicked.emit(scene_pos)
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if self.current_tool == "whiteout" and self._is_drawing_rect and self._current_rect_item:
            scene_pos = self.mapToScene(event.pos())
            from PyQt6.QtCore import QRectF
            rect = QRectF(self._rect_start_pos, scene_pos).normalized()
            self._current_rect_item.setRect(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.current_tool == "whiteout" and self._is_drawing_rect and self._current_rect_item:
            self._is_drawing_rect = False
            # Emit signal to register to undo stack
            if isinstance(self.scene(), PDFGraphicsScene):
                self.scene().text_item_added.emit(self._current_rect_item) # Reuse signal for simplicity
            self._current_rect_item = None
        else:
            super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        if self.current_tool == "whiteout" and event.button() == Qt.MouseButton.LeftButton:
            self._is_drawing_rect = True
            self._rect_start_pos = self.mapToScene(event.pos())
            from PyQt6.QtWidgets import QGraphicsRectItem
            from PyQt6.QtGui import QColor, QPen
            from PyQt6.QtCore import QRectF

            self._current_rect_item = QGraphicsRectItem(QRectF(self._rect_start_pos, self._rect_start_pos))
            self._current_rect_item.setBrush(QColor(255, 255, 255)) # Solid white
            pen = QPen(QColor(150, 150, 150))
            pen.setStyle(Qt.PenStyle.DashLine)
            self._current_rect_item.setPen(pen)
            self._current_rect_item.setZValue(100) # Draw over text

            self.scene().addItem(self._current_rect_item)

        elif self.current_tool == "add_text" and event.button() == Qt.MouseButton.LeftButton:
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
