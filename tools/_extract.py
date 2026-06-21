import json
import sys
src = sys.argv[1] if len(sys.argv) > 1 else r'data\simplify_diff\gamma_full_sub_1_input.json'
dst = sys.argv[2] if len(sys.argv) > 2 else r'data\simplify_diff\gamma_full_sub_1_compact.txt'
data = json.loads(open(src, encoding='utf-8').read())
out_lines = []
for i, c in enumerate(data['clusters']):
    out_lines.append(f"=== {i+1:3d} | {c['word']} | {c['pos']} | beta={c['current_score']:.3f} | {len(c['senses'])} senses ===")
    for s in c['senses']:
        out_lines.append(f"  def {s['def_idx']}: {s['text']}")
        for ex in s.get('examples', [])[:3]:
            out_lines.append(f"    ex: {ex[:120]}")
    out_lines.append('')
text = '\n'.join(out_lines)
with open(dst, 'w', encoding='utf-8') as f:
    f.write(text)
print(f'Wrote {len(text)} chars to {dst}')
