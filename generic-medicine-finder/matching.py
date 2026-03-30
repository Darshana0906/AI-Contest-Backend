"""
Jan Aushadhi Matching Engine
------------------------------
Matches LLM-extracted salt compositions to Jan Aushadhi generic drugs.
Uses pandas string matching + fuzzy matching (thefuzz).
No vector search needed for 1700-2000 entries.

Usage:
    from matching import find_generics
    results = find_generics("Amoxicillin 500mg, Clavulanic Acid 125mg")
"""

import re
import pandas as pd
from thefuzz import fuzz


# ── 1. Load & Prepare DB (runs once on import) ────────────────────────────────

def load_db(csv_path: str = "Jan_Aushadhi.csv") -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Clean column names (handles BOM character in official CSV)
    df.columns = df.columns.str.strip().str.lstrip("\ufeff").str.strip('"')

    # Convert MRP to numeric
    df["MRP"] = pd.to_numeric(df["MRP"], errors="coerce").fillna(0)

    # Filter out surgical/consumable items (MRP = 0)
    df = df[df["MRP"] > 0].copy()

    # Normalize "X and Y" → "X, Y" for consistent splitting
    df["Generic Name"] = df["Generic Name"].str.replace(
        r"\s+and\s+", ", ", regex=True
    )

    # Compute per unit price
    def parse_unit_count(unit_size: str) -> int:
        match = re.search(r"(\d+)", str(unit_size))
        return int(match.group(1)) if match else 1

    df["unit_count"]     = df["Unit Size"].apply(parse_unit_count)
    df["price_per_unit"] = (df["MRP"] / df["unit_count"]).round(2)

    return df.reset_index(drop=True)


# Load DB once at module level
DB = load_db()
print(f"✅ Jan Aushadhi DB loaded: {len(DB)} drug entries")


# ── 2. Salt Extraction Helpers ────────────────────────────────────────────────

def extract_salt_names(salt_composition: str) -> list[str]:
    """
    Extract just the drug names from a salt composition string.
    
    "Amoxicillin 500mg, Clavulanic Acid 125mg"
    → ["Amoxicillin", "Clavulanic Acid"]
    
    Handles: mg, ml, mcg, %, IU, million spores, w/w, per 5ml etc.
    """
    salts = [s.strip() for s in salt_composition.split(",")]
    
    # Remove dosage numbers and units
    cleaned = []
    for salt in salts:
        # Remove patterns like: 500mg, 125 mg, 0.025%w/w, 60 Million Spore, 15,00,000 IU
        name = re.sub(
            r'\d[\d,.]*\s*(%\s*w/w|%|mg|ml|mcg|iu|million\s*spore[s]?|per\s*\d+\s*ml)',
            '', salt, flags=re.IGNORECASE
        )
        # Remove leftover standalone numbers
        name = re.sub(r'\b\d+\b', '', name)
        name = name.strip().strip(',').strip()
        if name:
            cleaned.append(name)
    
    return cleaned


def salt_in_generic(salt_name: str, generic_name: str) -> bool:
    """
    Check if a salt name is present in a generic drug name.
    Uses fuzzy matching to handle spelling variants:
    - Amoxicillin vs Amoxycillin
    - Paracetamol vs Paracetamol
    """
    # Direct substring match first (fast)
    if salt_name.lower() in generic_name.lower():
        return True
    
    # Fuzzy match for spelling variants (Amoxicillin vs Amoxycillin)
    # Check against each word chunk of similar length in generic name
    ratio = fuzz.partial_ratio(salt_name.lower(), generic_name.lower())
    return ratio >= 88  # 88% similarity threshold


# ── 3. Core Matching Function ─────────────────────────────────────────────────

def find_generics(salt_composition: str, top_n: int = 5) -> dict:
    """
    Find generic alternatives for a given salt composition.
    
    Args:
        salt_composition: LLM output e.g. "Amoxicillin 500mg, Clavulanic Acid 125mg"
        top_n: max results to return
    
    Returns:
        dict with match results and metadata
    
    Match levels:
        EXACT    - all salts + strength match
        GOOD     - all salts match, different strength
        PARTIAL  - some salts match (relaxed for edge cases)
        NO_MATCH - nothing found
    """

    salt_names = extract_salt_names(salt_composition)
    
    if not salt_names:
        return {"status": "ERROR", "message": "Could not parse salt composition", "results": []}

    print(f"\n🔍 Searching for: {salt_composition}")
    print(f"   Extracted salts: {salt_names}")

    # ── Score each DB entry ───────────────────────────────────────────────────
    def score_row(generic_name: str) -> float:
        matched = sum(
            1 for salt in salt_names
            if salt_in_generic(salt, generic_name)
        )
        return matched / len(salt_names)  # 0.0 to 1.0

    DB["match_score"] = DB["Generic Name"].apply(score_row)

    # ── Filter by match level ─────────────────────────────────────────────────

    # Perfect: all prescription salts found in generic name
    perfect_matches = DB[DB["match_score"] >= 1.0].copy()

    if len(perfect_matches) > 0:
        # Try to find exact strength match within perfect matches
        # Extract all strength numbers from query e.g. ["500", "125"]
        strengths = re.findall(r'(\d+)\s*mg', salt_composition, re.IGNORECASE)
        
        exact_strength = perfect_matches.copy()
        for strength in strengths:
            exact_strength = exact_strength[
                exact_strength["Generic Name"].str.contains(strength, na=False)
            ]
        
        if len(exact_strength) > 0:
            result_df = exact_strength
            match_level = "EXACT"
        else:
            result_df = perfect_matches
            match_level = "GOOD"
    else:
        # Partial match — at least 50% of salts found
        partial = DB[DB["match_score"] >= 0.5].copy()
        if len(partial) > 0:
            result_df = partial
            match_level = "PARTIAL"
        else:
            return {
                "status": "NO_MATCH",
                "message": f"No generics found for: {salt_composition}",
                "salts_searched": salt_names,
                "results": []
            }

    # ── Format results ────────────────────────────────────────────────────────
    # Sort by: fewest salts first (plain drug before combos), then best match, then cheapest
    result_df["salt_count"] = result_df["Generic Name"].str.count(",") + 1
    result_df = result_df.sort_values(
        ["salt_count", "match_score", "price_per_unit"],
        ascending=[True, False, True]
    ).head(top_n)

    results = []
    for _, row in result_df.iterrows():
        results.append({
            "generic_name":   row["Generic Name"],
            "drug_code":      str(row["Drug Code"]),
            "mrp":            row["MRP"],
            "unit_size":      row["Unit Size"],
            "price_per_unit": row["price_per_unit"],
            "group":          row["Group Name"],
            "match_score":    round(row["match_score"], 2),
        })

    return {
        "status":        "SUCCESS",
        "match_level":   match_level,
        "salts_searched": salt_names,
        "total_found":   len(result_df),
        "results":       results
    }


# ── 4. Savings Calculator ─────────────────────────────────────────────────────

def calculate_savings(branded_price: float, generic_price: float) -> dict:
    """
    Calculate savings between branded and generic drug.
    
    Args:
        branded_price: price per unit of branded drug
        generic_price: price per unit of generic drug
    
    Returns:
        dict with savings amount and percentage
    """
    if branded_price <= 0:
        return {"savings_amount": 0, "savings_percent": 0}
    
    savings_amount  = branded_price - generic_price
    savings_percent = round((savings_amount / branded_price) * 100, 1)
    
    return {
        "savings_amount":  round(savings_amount, 2),
        "savings_percent": savings_percent,
        "is_cheaper":      savings_amount > 0
    }


# ── 5. Sanity Tests ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    test_cases = [
        "Paracetamol 500mg",                           # Simple single salt
        "Amoxicillin 500mg, Clavulanic Acid 125mg",    # Combination — Moxclav
        "Ibuprofen 400mg",                             # Brufen
        "Cetirizine 10mg",                             # Cetzine
        "Amoxicillin 250mg",                           # Mox
    ]

    for salt in test_cases:
        result = find_generics(salt)
        print(f"\n{'='*60}")
        print(f"Query : {salt}")
        print(f"Status: {result['status']} | Level: {result.get('match_level')}")
        print(f"Found : {result.get('total_found')} results")
        for r in result["results"][:3]:
            print(f"  → {r['generic_name']}")
            print(f"     ₹{r['mrp']} for {r['unit_size']} | ₹{r['price_per_unit']}/unit")