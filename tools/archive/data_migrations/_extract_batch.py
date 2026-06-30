"""Extract a compact view of batch 2 clusters for M3 reasoning."""
import json
data = json.loads(open(r'data\simplify_diff\gamma_batch_2_input.json', encoding='utf-8').read())
out_lines = []
for i, c in enumerate(data['clusters']):
    out_lines.append(f"=== {i+1:3d} | {c['word']} | {c['pos']} | β={c['current_score']:.3f} | {len(c['senses'])} senses ===")
    for s in c['senses']:
        out_lines.append(f"  def {s['def_idx']}: {s['text']}")
        for ex in s.get('examples', [])[:3]:
            out_lines.append(f"    ex: {ex[:120]}")
    out_lines.append('')
text = '\n'.join(out_lines)
with open(r'data\simplify_diff\gamma_batch_2_compact.txt', 'w', encoding='utf-8') as f:
    f.write(text)
print(f'Wrote {len(out_lines)} lines ({len(text)} chars)')
