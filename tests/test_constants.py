"""test_constants.py — Verify shared constants are sane.

Locks down the values that multiple tools depend on. If anyone changes
LENGTH_RATIO_OK or NAME_CHECKS, these tests force them to think about
the downstream impact.
"""
from schema import (
    CHAPTERS_DIR, GLOSSARY_DIR, LENGTH_RATIO_OK, NAME_CHECKS, NOVEL_ROOT, SOURCE_DIR
)


def test_length_ratio_ok_is_a_tuple():
    assert isinstance(LENGTH_RATIO_OK, tuple)
    assert len(LENGTH_RATIO_OK) == 2


def test_length_ratio_ok_bounds_are_floats_in_range():
    low, high = LENGTH_RATIO_OK
    assert 0.5 <= low <= 2.0, f'low bound {low} seems wrong (should be 0.5-2.0)'
    assert 1.5 <= high <= 5.0, f'high bound {high} seems wrong (should be 1.5-5.0)'
    assert low < high, 'low must be less than high'


def test_name_checks_have_three_fields():
    for entry in NAME_CHECKS:
        assert len(entry) == 3, f'NAME_CHECKS entry must have (cn, correct, wrong): {entry}'
        cn, correct, wrong = entry
        assert isinstance(cn, str) and cn, f'CN must be non-empty string: {entry}'
        assert isinstance(correct, str) and correct, f'correct must be non-empty: {entry}'
        assert isinstance(wrong, str) and wrong, f'wrong must be non-empty: {entry}'


def test_name_checks_correct_differs_from_wrong():
    for entry in NAME_CHECKS:
        cn, correct, wrong = entry
        if correct == wrong:
            raise AssertionError(
                f'NAME_CHECKS entry has identical correct and wrong Thai: '
                f'{entry!r} — auto-fix can never trigger for this case'
            )


def test_novel_root_points_to_existing_dir():
    assert NOVEL_ROOT.exists(), f'NOVEL_ROOT does not exist: {NOVEL_ROOT}'
    assert NOVEL_ROOT.is_dir(), f'NOVEL_ROOT is not a directory: {NOVEL_ROOT}'


def test_glossary_dir_under_novel_root():
    assert GLOSSARY_DIR.parent == NOVEL_ROOT


def test_chapters_dir_under_novel_root():
    assert CHAPTERS_DIR.parent == NOVEL_ROOT
    assert SOURCE_DIR.parent == CHAPTERS_DIR
