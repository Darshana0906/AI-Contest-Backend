from flask import Flask, request, jsonify
import os
from flask_cors import CORS
import pytesseract
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image, ImageOps
import re

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return "Server is running 🚀"

# ----------- Text Cleaning -----------
def clean_text(text):
    # Remove private-use glyphs/icons
    text = re.sub(r'[\uE000-\uF8FF]', '', text)
    # Remove other non-ascii symbols but keep basic punctuation
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# ----------- Typed PDF Extraction -----------
def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

# ----------- OCR for Images -----------
def ocr_from_image(image):
    # Preprocess image
    img = ImageOps.grayscale(image)  # grayscale
    width, height = img.size
    if width < 1000:  # optional upscaling for small images
        img = img.resize((width*2, height*2))
    text = pytesseract.image_to_string(img)
    return text

# ----------- OCR for Scanned PDFs -----------
def ocr_from_pdf(pdf_path):
    text = ""
    images = convert_from_path(pdf_path)
    for img in images:
        text += ocr_from_image(img) + "\n"
    return text

# ----------- Upload Endpoint -----------
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')

    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    extracted_text = ""

    # ----------- Handle PDF -----------
    if file.filename.lower().endswith(".pdf"):
        # Try typed PDF first
        text = extract_text_from_pdf(filepath)
        if text.strip():
            extracted_text = text
        else:
            # scanned PDF → OCR
            extracted_text = ocr_from_pdf(filepath)
    else:
        # Image file
        try:
            img = Image.open(filepath)
            extracted_text = ocr_from_image(img)
        except Exception as e:
            return jsonify({"error": f"Failed to process image: {str(e)}"}), 500

    # Clean text
    extracted_text = clean_text(extracted_text)

    # Return JSON
    return jsonify({
        "extracted_text": extracted_text
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)