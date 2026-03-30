"""
Full Pipeline
--------------
Wires together:
  1. extraction_chain.py  — Qwen extracts drugs from OCR text
  2. matching.py          — finds generics in Jan Aushadhi DB

Usage:
    from pipeline import process_prescription
    results = process_prescription("Tab. Crocin 500mg BD x 5 days")
"""

import re
from extraction_chain import extract_drugs
from matching import find_generics, calculate_savings


# ── 1. Salt Composition Normalizer ───────────────────────────────────────────

def normalize_salt_composition(salt: str) -> str:
    """
    Normalize salt composition string for consistent matching.
    Handles different separators Qwen might return:
      "Amoxicillin 500mg + Clavulanic Acid 125mg"  → "Amoxicillin 500mg, Clavulanic Acid 125mg"
      "Amoxicillin 500mg and Clavulanic Acid 125mg" → "Amoxicillin 500mg, Clavulanic Acid 125mg"
    """
    salt = re.sub(r'\s*\+\s*', ', ', salt)        # + → ,
    salt = re.sub(r'\s+and\s+', ', ', salt, flags=re.IGNORECASE)  # and → ,
    return salt.strip()


# ── 2. Core Pipeline Function ─────────────────────────────────────────────────

def process_prescription(ocr_text: str) -> dict:
    """
    Full pipeline: OCR text → extracted drugs → generic alternatives

    Args:
        ocr_text: raw text from prescription OCR

    Returns:
        dict with all drugs and their generic alternatives
    """

    print(f"\n{'='*60}")
    print(f"🏥 Processing prescription...")
    print(f"{'='*60}")

    # ── Step 1: Extract drugs using Qwen ─────────────────────────────────────
    extraction = extract_drugs(ocr_text)

    if extraction["status"] != "SUCCESS" or not extraction["drugs"]:
        return {
            "status":  "ERROR",
            "message": "Could not extract drugs from prescription",
            "drugs":   []
        }

    # ── Step 2: Find generics for each drug ───────────────────────────────────
    results = []

    for drug in extraction["drugs"]:

        # Normalize salt composition (handle +, and, , separators)
        salt = normalize_salt_composition(drug["salt_composition"])

        print(f"\n💊 {drug['brand_name']} → {salt}")

        # Find generics in Jan Aushadhi DB
        match_result = find_generics(salt)

        # Build result for this drug
        drug_result = {
            "brand_name":       drug["brand_name"],
            "salt_composition": salt,
            "drug_class":       drug["drug_class"],
            "dosage_form":      drug["dosage_form"],
            "confidence":       drug["confidence"],
            "needs_fallback":   drug["needs_fallback"],
            "match_status":     match_result["status"],
            "match_level":      match_result.get("match_level", "NONE"),
            "generics":         []
        }

        if match_result["status"] == "SUCCESS":
            for generic in match_result["results"]:
                drug_result["generics"].append({
                    "generic_name":   generic["generic_name"],
                    "mrp":            generic["mrp"],
                    "unit_size":      generic["unit_size"],
                    "price_per_unit": generic["price_per_unit"],
                    "group":          generic["group"],
                    "match_score":    generic["match_score"],
                })

        results.append(drug_result)

    return {
        "status": "SUCCESS",
        "total_drugs": len(results),
        "drugs": results
    }


# ── 3. Pretty Printer ─────────────────────────────────────────────────────────

def print_results(pipeline_output: dict):
    """Print pipeline results in a readable format"""

    if pipeline_output["status"] != "SUCCESS":
        print(f"❌ Error: {pipeline_output['message']}")
        return

    print(f"\n{'='*60}")
    print(f"📋 PRESCRIPTION ANALYSIS RESULTS")
    print(f"{'='*60}")
    print(f"Total drugs found: {pipeline_output['total_drugs']}")

    for drug in pipeline_output["drugs"]:
        print(f"\n{'─'*50}")
        print(f"💊 Brand      : {drug['brand_name']}")
        print(f"   Salt       : {drug['salt_composition']}")
        print(f"   Class      : {drug['drug_class']}")
        print(f"   Form       : {drug['dosage_form']}")
        print(f"   Confidence : {drug['confidence']}")

        if drug["needs_fallback"]:
            print(f"   ⚠️  Low confidence — manual verification needed")

        if drug["match_status"] == "SUCCESS":
            print(f"\n   ✅ Generic alternatives ({drug['match_level']} match):")
            for i, g in enumerate(drug["generics"][:3], 1):
                print(f"   {i}. {g['generic_name']}")
                print(f"      ₹{g['mrp']} for {g['unit_size']} | ₹{g['price_per_unit']}/unit")
        else:
            print(f"\n   ❌ No generics found in Jan Aushadhi DB")
            print(f"      Consider checking CDSCO or pharmacy APIs")


# ── 4. Sanity Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":

    test_prescriptions = [
        # Real world multi-drug prescription
        "1. Tab. Dolo 650mg TDS x 3 days\n2. Cap. Moxclav 625mg BD x 7 days\n3. Tab. Cetzine 10mg OD x 5 days",

        # Messy OCR
        "Brufen 4OOmg 1-0-1 Mox 5OOmg 1-1-1",
    ]

    for prescription in test_prescriptions:
        result = process_prescription(prescription)
        print_results(result)