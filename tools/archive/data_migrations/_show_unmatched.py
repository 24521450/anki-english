"""Show 8 non-UNCLASSIFIED unmatched."""
import csv

with open(r"C:\Users\admin\Downloads\ankideck\data\simplify_diff\sense_unmatched_232.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print("Unmatched cases KHONG phai UNCLASSIFIED:")
print(f"{'word':<18} {'pos':<14} {'cefr':<6} {'badge':<6} reason")
print("-" * 100)
for r in rows:
    if r["audit_cefr"] != "UNCLASSIFIED":
        print(f"{r['word']:<18} {r['pos']:<14} {r['audit_cefr']:<6} "
              f"{r['oxford_badge']:<6} {r['reason']}")
