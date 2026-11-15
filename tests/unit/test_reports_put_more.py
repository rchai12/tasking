from docket.reports import format_entry, parse_progress, put_entry
from tests.unit.test_reports_put import EARLIER, ENTRY, HEAD, TEXT


def test_an_entry_follows_one_empty_line_without_a_trailing_break() -> None:
    text = (HEAD + "\n" + EARLIER).rstrip("\n")
    assert text.endswith("None")
    assert put_entry(text, ENTRY) == HEAD + "\n" + EARLIER + "\n" + TEXT


def test_an_empty_log_is_the_entry_alone() -> None:
    assert put_entry("", ENTRY) == format_entry(ENTRY)
    entries, problems = parse_progress(put_entry("", ENTRY))
    assert problems == []
    assert len(entries) == 1


def test_one_empty_line_is_kept_before_the_next_entry() -> None:
    old = TEXT.replace("790", "760")
    earlier = HEAD + "\n" + old
    assert put_entry(earlier + EARLIER, ENTRY) == HEAD + "\n" + TEXT + "\n" + EARLIER
    assert put_entry(earlier + "\n\n\n" + EARLIER, ENTRY) == HEAD + "\n" + TEXT + "\n" + EARLIER
