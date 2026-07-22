from src.deck_builder.text_integrity import has_suspected_lossy_unicode


def test_rejects_replacement_and_embedded_lossy_question_marks():
    assert has_suspected_lossy_unicode("ho?n to?n")
    assert has_suspected_lossy_unicode("x� lạ")


def test_rejects_high_confidence_utf8_mojibake():
    assert has_suspected_lossy_unicode("hoÃ n toÃ n")
    assert has_suspected_lossy_unicode("khÃ³e máº¡nh")
    assert has_suspected_lossy_unicode("â€™s")


def test_accepts_valid_vietnamese_and_terminal_question_mark():
    assert not has_suspected_lossy_unicode("hoàn toàn khỏe mạnh")
    assert not has_suspected_lossy_unicode("Tại sao?")
    assert not has_suspected_lossy_unicode("question? answer")
