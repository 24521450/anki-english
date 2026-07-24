from __future__ import annotations

from src.scraper.cambridge import parse_cambridge


def test_each_entry_body_pos_owns_only_its_own_senses():
    parsed = parse_cambridge(
        b"""
        <html><body>
          <div class="pr entry-body__el">
            <div class="cid" id="cald4-1"></div>
            <div class="pos-header dpos-h">
              <span class="headword"><span class="hw dhw">extract</span></span>
              <div class="posgram dpos-g">
                <span class="pos dpos">verb</span>
              </div>
            </div>
            <div class="dsense_b">
              <div class="ddef_d">to remove something</div>
            </div>
          </div>
          <div class="pr entry-body__el">
            <div class="cid" id="cald4-2"></div>
            <div class="pos-header dpos-h">
              <span class="headword"><span class="hw dhw">extract</span></span>
              <div class="posgram dpos-g">
                <span class="pos dpos">noun</span>
              </div>
            </div>
            <div class="dsense_b">
              <div class="ddef_d">a substance taken from something</div>
            </div>
          </div>
        </body></html>
        """
    )

    definitions_by_pos = {
        entry["pos"]: [definition["text"] for definition in entry["definitions"]]
        for entry in parsed["pos_data"]
    }
    assert definitions_by_pos == {
        "verb": ["to remove something"],
        "noun": ["a substance taken from something"],
    }
