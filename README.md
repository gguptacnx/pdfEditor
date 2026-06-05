# pdfEditor

A local application to edit PDF text in a WYSIWYG manner. This app is designed to run on Windows, offering native UI via PyQt6. It allows you to select text blocks in a PDF, edit the text, prompt for font replacements (if the exact font isn't embedded or available), and push subsequent elements down if the text expands.

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

- **WYSIWYG Editing:** Click directly on text blocks in the PDF canvas to edit them.
- **Font Replacement:** If the PDF uses subsetted or proprietary fonts, the app allows you to select a local `.ttf` or `.otf` font file from your system to ensure correct rendering.
- **Text Reflowing:** If the newly added text expands the paragraph's height, the application will calculate the difference and alert you. Note that automatically pushing subsequent PDF elements (text, images, paths) down the page is highly complex due to the absolute positioning nature of PDFs, and the current implementation warns of structural shifts.
