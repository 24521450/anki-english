import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# We will import these from our tool to be implemented
from tools._apply_txt_escaped_pipe_p3a import process_line, process_txt_lines


def test_compact_pipe_behavior():
    # Test line with escaped pipe
    line = 'GUID\tModel\tDeck\tword\tpos\tIPA\ta \\| b\texample\t\t\t\t\t\t\tCEFR'
    new_line, modified = process_line(line)
    assert modified is True
    fields = new_line.split('\t')
    assert fields[6] == 'a|b'
    assert fields[3] == 'word'
    assert fields[14] == 'CEFR'

    # Test line with spacing and escaped pipe
    line2 = 'GUID\tModel\tDeck\tword\tpos\tIPA\ta  \\|  b\texample\t\t\t\t\t\t\tCEFR'
    new_line2, modified2 = process_line(line2)
    assert modified2 is True
    assert new_line2.split('\t')[6] == 'a|b'

    # Test line with normal pipe and spaces (should NOT be modified because no literal escaped pipe is present)
    line3 = 'GUID\tModel\tDeck\tword\tpos\tIPA\ta | b\texample\t\t\t\t\t\t\tCEFR'
    new_line3, modified3 = process_line(line3)
    assert modified3 is False
    assert new_line3 == line3

    # Test line with normal clean pipe
    line4 = 'GUID\tModel\tDeck\tword\tpos\tIPA\ta|b\texample\t\t\t\t\t\t\tCEFR'
    new_line4, modified4 = process_line(line4)
    assert modified4 is False
    assert new_line4 == line4


def test_process_line_metadata_and_headers():
    # Header starts with #
    header = '#separator:tab'
    new_line, modified = process_line(header)
    assert modified is False
    assert new_line == header

    # Empty line
    empty = '  '
    new_line, modified = process_line(empty)
    assert modified is False
    assert new_line == empty

    # Short line
    short = 'a\tb\tc'
    new_line, modified = process_line(short)
    assert modified is False
    assert new_line == short


def test_process_txt_lines_success():
    lines = [
        '#separator:tab',
        'G1\tM\tD\tw1\tpos\tIPA\ta \\| b\tex',
        'G2\tM\tD\tw2\tpos\tIPA\ta|b\tex',
        'G3\tM\tD\tw3\tpos\tIPA\tx | y\tex',
    ]
    # Expected modified count = 1 (only row 1 has escaped pipe)
    new_lines, count = process_txt_lines(lines, expected_count=1)
    assert count == 1
    assert new_lines[1].split('\t')[6] == 'a|b'
    assert new_lines[2].split('\t')[6] == 'a|b'
    assert new_lines[3].split('\t')[6] == 'x | y'


def test_process_txt_lines_abort_on_mismatch():
    lines = [
        '#separator:tab',
        'G1\tM\tD\tw1\tpos\tIPA\ta \\| b\tex',
    ]
    # We expect 2 but only get 1
    with pytest.raises(ValueError, match="Expected exactly 2 touched rows, but got 1"):
        process_txt_lines(lines, expected_count=2)
