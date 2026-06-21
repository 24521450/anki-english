"""Debug: find empty-string fields in failing records."""
import json

TARGET_WORDS = {"AIDS", "April", "CD", "DVD", "December", "February", "Friday", "OK"}

with open(r"C:\Users\admin\Downloads\ankideck\data\oxford_merged.jsonl") as f:
    for line in f:
        rec = json.loads(line)
        if rec.get("word") not in TARGET_WORDS:
            continue
        print(f"--- {rec['word']} ---")
        # Top-level
        for k, v in rec.items():
            if v == "":
                print(f"  TOP.{k} = '' (type={type(v).__name__})")
        # pos_data
        for pi, pd in enumerate(rec.get("pos_data", [])):
            for k, v in pd.items():
                if v == "":
                    print(f"  pos_data[{pi}].{k} = ''")
            for di, d in enumerate(pd.get("definitions", [])):
                for k, v in d.items():
                    if v == "":
                        print(f"  pos_data[{pi}].def[{di}].{k} = ''")
        # idioms
        for ii, i in enumerate(rec.get("idioms", [])):
            for k, v in i.items():
                if v == "":
                    print(f"  idioms[{ii}].{k} = ''")
        # break after first hit
        break
