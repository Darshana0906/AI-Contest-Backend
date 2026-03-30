"""
Jan Aushadhi DB Embedding Pipeline
------------------------------------
Run this ONCE to build and save the FAISS index.
Flask will load the saved index on startup — no re-embedding needed.

Usage:
    python embed_jan_aushadhi.py
"""

import pandas as pd
import re
import pickle
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document


# ── 1. Load CSV ──────────────────────────────────────────────────────────────

df = pd.read_csv("Jan_Aushadhi.csv")

# Strip BOM and whitespace from column names (CSV has a BOM character)
df.columns = df.columns.str.strip().str.lstrip("\ufeff").str.strip('"')

print(f"✅ Loaded {len(df)} entries")
print(f"   Columns: {list(df.columns)}")


# ── 2. Clean & Filter ─────────────────────────────────────────────────────────

# Convert MRP to numeric
df["MRP"] = pd.to_numeric(df["MRP"], errors="coerce").fillna(0)

# Filter out surgical/consumable items with MRP = 0 (not medicines)
df_drugs = df[df["MRP"] > 0].copy()
print(f"✅ Filtered to {len(df_drugs)} drug entries (removed zero-MRP surgical items)")

# Normalize multi-salt separators: "X and Y" → "X, Y"
df_drugs["Generic Name"] = df_drugs["Generic Name"].str.replace(
    r"\s+and\s+", ", ", regex=True
)

# Parse unit count from Unit Size column for per-unit price
def parse_unit_count(unit_size: str) -> int:
    """Extract numeric count from unit size strings like "10's", "14's", "6's" """
    match = re.search(r"(\d+)", str(unit_size))
    return int(match.group(1)) if match else 1

df_drugs["unit_count"] = df_drugs["Unit Size"].apply(parse_unit_count)
df_drugs["price_per_unit"] = (df_drugs["MRP"] / df_drugs["unit_count"]).round(2)

print(f"✅ Cleaned Generic Names and computed per-unit prices")


# ── 3. Build LangChain Documents ─────────────────────────────────────────────

"""
page_content = Generic Name only → this is what gets embedded & vector searched
metadata     = everything else   → returned alongside search results
"""

docs = [
    Document(
        page_content=row["Generic Name"],
        metadata={
            "drug_code":      str(row["Drug Code"]),
            "generic_name":   row["Generic Name"],
            "unit_size":      row["Unit Size"],
            "mrp":            row["MRP"],
            "unit_count":     row["unit_count"],
            "price_per_unit": row["price_per_unit"],
            "group":          row["Group Name"],
        }
    )
    for _, row in df_drugs.iterrows()
]

print(f"✅ Built {len(docs)} LangChain Documents")
print(f"\n   Sample document:")
print(f"   content  : {docs[0].page_content}")
print(f"   metadata : {docs[0].metadata}")


# ── 4. Embed & Build FAISS Index ──────────────────────────────────────────────

print(f"\n⏳ Embedding documents using Qwen 2.5 via Ollama...")
print(f"   This will take a few minutes — runs only once!\n")

embeddings = OllamaEmbeddings(model="mxbai-embed-large:latest")

vectorstore = FAISS.from_documents(docs, embeddings)

print(f"✅ FAISS index built successfully!")


# ── 5. Save Index to Disk ─────────────────────────────────────────────────────

vectorstore.save_local("faiss_jan_aushadhi")
print(f"✅ FAISS index saved to ./faiss_jan_aushadhi/")
print(f"\n🎉 Done! Your vector store is ready.")
print(f"   Load it in Flask with:")
print(f"   vectorstore = FAISS.load_local('faiss_jan_aushadhi', embeddings)")


# ── 6. Quick Sanity Test ──────────────────────────────────────────────────────

print(f"\n🧪 Running sanity test — searching for 'Paracetamol 500mg'...\n")

results = vectorstore.similarity_search("Paracetamol", k=3)

for i, r in enumerate(results, 1):
    m = r.metadata
    print(f"  {i}. {m['generic_name']}")
    print(f"     MRP: ₹{m['mrp']} for {m['unit_size']} | ₹{m['price_per_unit']} per unit")
    print(f"     Group: {m['group']}")
    print()