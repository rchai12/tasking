from docket.spotcheck import verdict


def test_trailing_spaces_on_an_error_line_are_cut() -> None:
    assert verdict("E   KeyError: 'l1'   \n1 failed\n", 1) == "fails: KeyError: 'l1'"
