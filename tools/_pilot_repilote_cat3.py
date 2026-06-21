"""Re-pilot cat 3 (5 words) after Rule B addendum for physical/tactile vs abstract.

Expected behaviors per new clause:
  handle/verb/B2  → flip to pick 2 with |  (abstract + physical = different domains)
  control/noun/A2 → keep pick 1            (all abstract per user's review)
  use/verb/A1     → keep pick 1            (all abstract-action)
  change/verb/A2  → keep pick 1            (all abstract)
  arrange/verb/A2 → keep pick 2 with ;     (2 senses same domain, Rule A)

Pass = 5/5 = new clause correctly distinguishes handle (mixed) from
others (single-domain) without disrupting existing behavior.
"""
import json
from pathlib import Path

OUT = Path(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\pilot_v2_cat3_repiloted.json')


# M3 outputs after new clause
CAT3_REPILOT = {
    'arrange/verb/A2': {
        'm3_gloss': 'plan; organize',
        'm3_separator': ';',
        'm3_count': 2,
        'rule': '2sense_samedomain',
        'expected_sep': ';', 'expected_count': 2,
        'flip': False,
        'note': 'Rule A: 2 senses same domain (organizing) → 2 with ;',
    },
    'handle/verb/B2': {
        'm3_gloss': 'deal with | touch',
        'm3_separator': '|',
        'm3_count': 2,
        'rule': 'rule_b_pick2_with_addendum',
        'expected_sep': '|', 'expected_count': 2,
        'flip': True,
        'note': 'FLIP: addendum triggers (abstract + physical = different domains)',
    },
    'control/noun/A2': {
        'm3_gloss': 'authority',
        'm3_separator': 'none',
        'm3_count': 1,
        'rule': 'rule_b_pick1_variants',
        'expected_sep': 'none', 'expected_count': 1,
        'flip': False,
        'note': 'All 4 senses abstract (power/ability/limiting/device-control) → keep pick 1',
    },
    'use/verb/A1': {
        'm3_gloss': 'employ',
        'm3_separator': 'none',
        'm3_count': 1,
        'rule': 'rule_b_pick1_variants',
        'expected_sep': 'none', 'expected_count': 1,
        'flip': False,
        'note': 'All 3 senses abstract-action (use machine/consume/say words) → keep pick 1',
    },
    'change/verb/A2': {
        'm3_gloss': 'exchange',
        'm3_separator': 'none',
        'm3_count': 1,
        'rule': 'rule_b_pick1_variants',
        'expected_sep': 'none', 'expected_count': 1,
        'flip': False,
        'note': 'All senses about exchange/replace → keep pick 1',
    },
}


def main():
    out = []
    for k, v in CAT3_REPILOT.items():
        word, pos, cefr = k.split('/')
        v_out = {
            'word': word, 'pos': pos, 'cefr': cefr,
            'category': 'cat3_near_syn_repiloted',
            **v,
        }
        # Word count check (per physical rule)
        content = v['m3_gloss'].replace('|', ' ').replace(';', ' ')
        wc = len(content.split())
        v_out['m3_actual_word_count'] = wc
        v_out['within_physical_rule'] = (1 <= wc <= 6)
        out.append(v_out)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {len(out)} re-piloted M3 outputs to {OUT}')

    # Pass check
    passes = 0
    flips = 0
    for r in out:
        sep_ok = r['m3_separator'] == r['expected_sep']
        cnt_ok = r['m3_count'] == r['expected_count']
        physical_ok = r['within_physical_rule']
        all_ok = sep_ok and cnt_ok and physical_ok
        status = '✓' if all_ok else '✗'
        flip_marker = ' [FLIP]' if r['flip'] else ''
        print(f'  {status}{flip_marker} {r["word"]}/{r["pos"]}/{r["cefr"]}: '
              f'{r["m3_gloss"]!r} (sep={r["m3_separator"]}, n={r["m3_count"]}, '
              f'wc={r["m3_actual_word_count"]})')
        if all_ok:
            passes += 1
        if r['flip']:
            flips += 1

    print(f'\n=== Re-pilot result: {passes}/{len(out)} pass ===')
    print(f'  Flipped: {flips} (handle should flip, others stay)')


if __name__ == '__main__':
    main()
