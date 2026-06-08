from PyQt6.QtGui import QUndoCommand, QUndoStack
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene

class AddGraphicsItemCommand(QUndoCommand):
    """Command to add an item to the QGraphicsScene."""
    def __init__(self, scene: QGraphicsScene, item: QGraphicsItem, description: str = "Add Item"):
        super().__init__(description)
        self.scene = scene
        self.item = item

    def redo(self):
        if self.item not in self.scene.items():
            self.scene.addItem(self.item)

    def undo(self):
        if self.item in self.scene.items():
            self.scene.removeItem(self.item)


class RemoveGraphicsItemCommand(QUndoCommand):
    """Command to remove an item from the QGraphicsScene."""
    def __init__(self, scene: QGraphicsScene, item: QGraphicsItem, description: str = "Remove Item"):
        super().__init__(description)
        self.scene = scene
        self.item = item

    def redo(self):
        if self.item in self.scene.items():
            self.scene.removeItem(self.item)

    def undo(self):
        if self.item not in self.scene.items():
            self.scene.addItem(self.item)


class CommandManager:
    """Manages the application's QUndoStack."""
    def __init__(self):
        self.undo_stack = QUndoStack()

    def push(self, command: QUndoCommand):
        """Pushes a command onto the stack, executing its redo() method."""
        self.undo_stack.push(command)

    def undo(self):
        self.undo_stack.undo()

    def redo(self):
        self.undo_stack.redo()

    def clear(self):
        self.undo_stack.clear()
