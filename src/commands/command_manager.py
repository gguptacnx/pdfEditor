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
        # PyQt QUndoStack.push() sometimes doesn't execute redo() immediately in certain Qt versions
        # unless triggered via macro or event loop. Let's force it if it didn't run.
        # Actually, QUndoStack.push DOES run redo. Let's just print a debug.

    def undo(self):
        self.undo_stack.undo()

    def redo(self):
        self.undo_stack.redo()

    def clear(self):
        self.undo_stack.clear()

class ChangeFormatCommand(QUndoCommand):
    """Command to change the formatting (font, color) of a QGraphicsTextItem."""
    def __init__(self, item: QGraphicsItem, old_format: dict, new_format: dict, description: str = "Change Format"):
        super().__init__(description)
        self.item = item
        self.old_format = old_format
        self.new_format = new_format

    def _apply_format(self, fmt: dict):
        # We must use QTextCursor to override the rich-text HTML properties
        # generated when the user types inside the QGraphicsTextItem.
        from PyQt6.QtGui import QTextCursor, QTextCharFormat
        from PyQt6.QtWidgets import QGraphicsTextItem

        if isinstance(self.item, QGraphicsTextItem):
            cursor = self.item.textCursor()
            char_format = QTextCharFormat()

            if 'font' in fmt:
                char_format.setFont(fmt['font'])
                self.item.setFont(fmt['font']) # Update base font too
            if 'color' in fmt:
                char_format.setForeground(fmt['color'])
                self.item.setDefaultTextColor(fmt['color'])

            # Apply to entire text
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.mergeCharFormat(char_format)
            self.item.setTextCursor(cursor)

    def redo(self):
        self._apply_format(self.new_format)

    def undo(self):
        self._apply_format(self.old_format)

class AddMaskAndTextCommand(QUndoCommand):
    """Command to add a redaction mask and an editable text block simultaneously."""
    def __init__(self, scene: QGraphicsScene, mask_item: QGraphicsItem, text_item: QGraphicsItem, description: str = "Edit Existing Text"):
        super().__init__(description)
        self.scene = scene
        self.mask_item = mask_item
        self.text_item = text_item

    def redo(self):
        if self.mask_item not in self.scene.items():
            self.scene.addItem(self.mask_item)
        if self.text_item not in self.scene.items():
            self.scene.addItem(self.text_item)

    def undo(self):
        if self.mask_item in self.scene.items():
            self.scene.removeItem(self.mask_item)
        if self.text_item in self.scene.items():
            self.scene.removeItem(self.text_item)
