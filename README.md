# pdfEditor

A local application to edit PDF text in a WYSIWYG manner. This app is designed to run on Windows, offering native UI via PyQt6. It allows you to select text blocks in a PDF, edit the text, and apply formatting.

## Prerequisites

- Python 3.8 or higher installed on your system.

## Setup Instructions (Windows)

1. **Clone the repository** (or download the files):
   ```cmd
   git clone <repository_url>
   cd pdfEditor
   ```

2. **Create a virtual environment (Optional but recommended)**:
   ```cmd
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install the required dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```

## Running the Application

To start the PDF editor, simply run:
```cmd
python pdf_editor.py
```

## Features

- **In-Place WYSIWYG Editing:** Click directly on text lines in the PDF canvas to edit them in-place with a floating text box perfectly aligned over the original text.
- **Advanced Text Formatting:** Apply Bold, Italic, Underline, Strikethrough, Text Color, Background Color, and Font Size natively.
- **Drag and Drop:** Move text elements around the page using the mouse.
- **Form Filling:** Automatically detects and overlays interactive PDF forms (text fields, checkboxes) for easy filling.
- **Signatures:** Insert image-based signatures directly onto the PDF canvas.
- **Tabular Tools:** Draw tables from scratch and toggle visual alignment gridlines.
- **Font Handling:** Extracts and preserves original embedded PDF fonts where possible, safely routing unknown styling to default PyMuPDF Base-14 internal equivalents to ensure robust rendering.