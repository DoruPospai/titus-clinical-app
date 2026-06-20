import os
from pathlib import Path

root = Path(r"D:\MULTIMI_VAGI1\Test11\Test11_Final_OK")

files = [
    root / "ClinicalPipeline_RO_SINGLE_v14_RUNTIME_AUDIT.xlsx",
    root / "data_clean" / "Tabel2_Titus.xlsx",
    root / "data_clean" / "Maladies.xlsx",
    root / "data_clean" / "Signe.xlsx",
    root / "data_clean" / "Symptomes.xlsx",
    root / "data_clean" / "Riskf.xlsx",
    root / "data_clean" / "catriskf.xlsx",
    root / "data_clean" / "Order_AgeMetadata_FINAL.xlsx",
]

total = 0
for p in files:
    if p.exists():
        size_mb = p.stat().st_size / (1024 * 1024)
        print(f"{p.name}: {size_mb:.2f} MB")
        total += size_mb
    else:
        print(f"{p.name}: NU EXISTĂ la {p}")

print(f"\nTOTAL workbook-uri: {total:.2f} MB")

# Bonus: cât din cele 0.99 GB e modelul semantic (cache + model HuggingFace)
print("\n--- Verificare model semantic ---")
cache_candidates = [
    root / "ClinicalPipeline_RO_SINGLE_v14_RUNTIME_AUDIT.semantic_cache.pkl",
]
for p in cache_candidates:
    if p.exists():
        size_mb = p.stat().st_size / (1024 * 1024)
        print(f"{p.name}: {size_mb:.2f} MB")
    else:
        print(f"{p.name}: NU EXISTĂ la {p}")