"""
OCR using Groq Vision Model via LangChain
------------------------------------------
Sends prescription image directly to Llama Vision model.
No separate OCR library needed!

Usage:
    from ocr import extract_text_from_image
    text = extract_text_from_image("prescription.jpg")
"""

import base64
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

load_dotenv()


# ── 1. Vision LLM Setup ───────────────────────────────────────────────────────

vision_llm = ChatGroq(
    model="meta-llama/llama-4-scout-17b-16e-instruct",
    temperature=0,
)


# ── 2. Image to Base64 ────────────────────────────────────────────────────────

def image_to_base64(image_path: str) -> tuple[str, str]:
    """
    Convert image file to base64 string.
    Returns (base64_string, media_type)
    """
    # Detect media type from extension
    ext = image_path.lower().split(".")[-1]
    media_types = {
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
        "png":  "image/png",
        "webp": "image/webp",
    }
    media_type = media_types.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    return image_data, media_type


# ── 3. Core OCR Function ──────────────────────────────────────────────────────

def extract_text_from_image(image_path: str) -> dict:
    """
    Extract all text from a prescription image using Groq Vision.

    Args:
        image_path: path to prescription image (jpg, png, webp)

    Returns:
        dict with extracted text and status
    """

    print(f"\n📸 Reading prescription image: {image_path}")

    try:
        # Convert image to base64
        image_data, media_type = image_to_base64(image_path)

        # Build vision message
        message = HumanMessage(content=[
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{image_data}"
                }
            },
            {
                "type": "text",
                "text": """You are reading a medical prescription from India.

Extract ALL text from this prescription image exactly as written.
Include:
- Doctor name and details
- Patient name and details  
- All medicines with dosage and frequency
- Any other instructions

Return the raw extracted text only. Do not interpret or summarize."""
            }
        ])

        # Call vision model
        response = vision_llm.invoke([message])
        extracted_text = response.content

        print(f"✅ Text extracted successfully!")
        print(f"\n--- Extracted Text ---")
        print(extracted_text)
        print(f"----------------------")

        return {
            "status": "SUCCESS",
            "text":   extracted_text,
            "image":  image_path
        }

    except Exception as e:
        return {
            "status":  "ERROR",
            "message": str(e),
            "text":    ""
        }


# ── 4. Full Pipeline Function ─────────────────────────────────────────────────

def process_prescription_image(image_path: str) -> dict:
    """
    Complete pipeline from image to generic alternatives.
    Image → OCR → Drug extraction → Generic matching

    Args:
        image_path: path to prescription image

    Returns:
        dict with all drugs and their generic alternatives
    """
    # Import here to avoid circular imports
    from pipeline import process_prescription

    # Step 1 — Extract text from image
    ocr_result = extract_text_from_image(image_path)

    if ocr_result["status"] != "SUCCESS":
        return {
            "status":  "ERROR",
            "message": f"OCR failed: {ocr_result['message']}",
            "drugs":   []
        }

    # Step 2 — Process extracted text through pipeline
    return process_prescription(ocr_result["text"])


# ── 5. Sanity Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pipeline import print_results

    # Test with image path from command line
    # Usage: python ocr.py prescription.jpg
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"\n🏥 Processing prescription image: {image_path}")
        result = process_prescription_image(image_path)
        print_results(result)
    else:
        print("Usage: python ocr.py <path_to_prescription_image>")
        print("Example: python ocr.py prescription.jpg")
        print("\nTo test, add a prescription image to your project folder and run:")
        print("python ocr.py prescription.jpg")