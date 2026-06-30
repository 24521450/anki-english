import json
d = json.loads(open(r'data\simplify_diff\gamma_full_sub_1_input.json', encoding='utf-8').read())
print(f"Total: {d['total_clusters']}")
