import pytesseract
from PIL import Image

# Set path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text(image_path):
    img = Image.open(image_path)

    text = pytesseract.image_to_string(img, config='--psm 6')
    return text