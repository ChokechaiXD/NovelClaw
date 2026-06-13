"""test_constants.py — Verify shared constants are sane.

Locks down the values that multiple tools depend on. If anyone changes
LENGTH_RATIO_OK or NAME_CHECKS, these tests force them to think about
the downstream impact.
"""
import constants


def test_length_ratio_ok_is_a_tuple():
    assert isinstance(constants.LENGTH_RATIO_OK, tuple)
    assert len(constants.LENGTH_RATIO_OK) == 2


def test_length_ratio_ok_bounds_are_floats_in_range():
    low, high = constants.LENGTH_RATIO_OK
    assert 0.5 <= low <= 2.0, f'low bound {low} seems wrong (should be 0.5-2.0)'
    assert 1.5 <= high <= 5.0, f'high bound {high} seems wrong (should be 1.5-5.0)'
    assert low < high, 'low must be less than high'


def test_name_checks_have_three_fields():
    for entry in constants.NAME_CHECKS:
        assert len(entry) == 3, f'NAME_CHECKS entry must have (cn, correct, wrong): {entry}'
        cn, correct, wrong = entry
        assert isinstance(cn, str) and cn, f'CN must be non-empty string: {entry}'
        assert isinstance(correct, str) and correct, f'correct must be non-empty: {entry}'
        assert isinstance(wrong, str) and wrong, f'wrong must be non-empty: {entry}'


def test_name_checks_correct_differs_from_wrong():
    """Entries where correct == wrong can never trigger auto-fix.
    See the deprecation note in constants.py — keep this guard so the
    bug class doesn't return.
    """
    for entry in constants.NAME_CHECKS:
        cn, correct, wrong = entry
        if correct == wrong:
            raise AssertionError(
                f'NAME_CHECKS entry has identical correct and wrong Thai: '
                f'{entry!r} — auto-fix can never trigger for this case'
            )


def test_novel_root_points_to_existing_dir():
    p = constants.NOVEL_ROOT
    assert p.exists(), f'NOVEL_ROOT does not exist: {p}'
    assert p.is_dir(), f'NOVEL_ROOT is not a directory: {p}'


def test_glossary_dir_under_novel_root():
    assert constants.GLOSSARY_DIR.parent == constants.NOVEL_ROOT


def test_chapters_dir_under_novel_root():
    assert constants.CHAPTERS_DIR.parent == constants.NOVEL_ROOT
    assert constants.SOURCE_DIR.parent == constants.CHAPTERS_DIR
