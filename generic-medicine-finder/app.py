"""
Flask API
----------
Wraps the full pipeline as HTTP endpoints for React frontend.

Endpoints:
    POST /api/scan          — upload prescription image
    POST /api/scan/text     — send raw text (for testing)
    GET  /api/health        — health check

Usage:
    python app.py
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from ocr import process_prescription_image
from pipeline import process_prescription

load_dotenv()

# ── App Setup ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)  # allow React frontend to call this API

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload


# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def format_response(pipeline_output: dict) -> dict:
    """Format pipeline output for React frontend."""
    if pipeline_output["status"] != "SUCCESS":
        return {
            "success": False,
            "error":   pipeline_output.get("message", "Unknown error"),
            "drugs":   []
        }

    drugs = []
    for drug in pipeline_output["drugs"]:
        drugs.append({
            "brand_name":       drug["brand_name"],
            "salt_composition": drug["salt_composition"],
            "drug_class":       drug["drug_class"],
            "dosage_form":      drug["dosage_form"],
            "confidence":       drug["confidence"],
            "needs_fallback":   drug["needs_fallback"],
            "match_level":      drug["match_level"],
            "generics":         drug["generics"][:5],
        })

    return {
        "success":     True,
        "total_drugs": pipeline_output["total_drugs"],
        "drugs":       drugs
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status":  "ok",
        "message": "Generic medicine finder API is running"
    })


@app.route("/api/scan", methods=["POST"])
def scan_prescription():
    """
    Upload prescription image and get generic alternatives.
    Request : multipart/form-data with 'file' field (jpg, jpeg, png, webp)
    Response: JSON with extracted drugs and generic alternatives
    """

    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded. Send file in 'file' field."}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"success": False, "error": "Empty filename"}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": f"File type not allowed. Allowed: {ALLOWED_EXTENSIONS}"}), 400

    # Save uploaded file
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)
    print(f"\n📁 File saved: {filepath}")

    try:
        result = process_prescription_image(filepath)
        os.remove(filepath)  # clean up after processing
        return jsonify(format_response(result))

    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/scan/text", methods=["POST"])
def scan_text():
    """
    Send raw prescription text and get generic alternatives.
    Useful for testing without an image.
    Request : JSON with 'text' field
    Response: JSON with extracted drugs and generic alternatives
    """

    data = request.get_json()

    if not data or "text" not in data:
        return jsonify({"success": False, "error": "Send JSON with 'text' field"}), 400

    text = data["text"].strip()

    if not text:
        return jsonify({"success": False, "error": "Empty text"}), 400

    try:
        result = process_prescription(text)
        return jsonify(format_response(result))

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n🚀 Starting Generic Medicine Finder API...")
    print("   Health check : http://localhost:5000/api/health")
    print("   Scan image   : POST http://localhost:5000/api/scan")
    print("   Scan text    : POST http://localhost:5000/api/scan/text")
    app.run(debug=True, host="0.0.0.0", port=5000)