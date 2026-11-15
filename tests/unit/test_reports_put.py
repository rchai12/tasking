from dataclasses import replace
from datetime import date

import pytest

from docket.reports import ENTRY_MESSAGE, ProgressEntry, format_entry, parse_progress, put_entry

ENTRY = ProgressEntry(
    phase="2e",
    title="Phase tooling",
    date=date(2026, 11, 15),
    tests_before=732,
    tests_after=790,
    given=40,
    new_names="`docket.spotcheck`: `mutate`, `verdict`",
    changed_files=9,
    deviations=(),
    follow_ups=("Stopped: G3 | 1 failed | a fix to the probe", "Check the log folder"),
    line=0,
)
TEXT = (
    "## Phase 2e: Phase tooling (2026-11-15)\n"
    "- Tests: 732 -> 790 (given 40)\n"
    "- New public names: `docket.spotcheck`: `mutate`, `verdict`\n"
    "- Changed files: 9\n"
    "- Deviations:\n"
    "  - None\n"
    "- Follow-ups:\n"
    "  - Stopped: G3 | 1 failed | a fix to the probe\n"
    "  - Check the log folder\n"
)
HEAD = "# Progress\n\nOne entry per phase.\n"
EARLIER = (
    "## Phase 2d: Serve (2026-11-14)\n"
    "- Tests: 703 -> 732 (given 24)\n"
    "- New public names: None\n"
    "- Changed files: 7\n"
    "- Deviations:\n"
    "  - None\n"
    "- Follow-ups:\n"
    "  - None\n"
)
OLD = TEXT.replace("790", "760").replace("9\n", "8\n")


def test_an_entry_is_written_in_the_progress_form() -> None:
    assert format_entry(ENTRY) == TEXT
    assert format_entry(replace(ENTRY, deviations=("One handler",), follow_ups=())) == (
        TEXT.replace("Deviations:\n  - None", "Deviations:\n  - One handler").replace(
            "  - Stopped: G3 | 1 failed | a fix to the probe\n  - Check the log folder\n",
            "  - None\n",
        )
    )


def test_a_new_phase_is_appended_after_one_empty_line() -> None:
    assert put_entry(HEAD + "\n" + EARLIER, ENTRY) == HEAD + "\n" + EARLIER + "\n" + TEXT
    assert put_entry(HEAD + "\n" + EARLIER + "\n\n", ENTRY) == HEAD + "\n" + EARLIER + "\n" + TEXT


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (HEAD + "\n" + EARLIER + "\n" + OLD, HEAD + "\n" + EARLIER + "\n" + TEXT),
        (HEAD + "\n" + OLD + "\n" + EARLIER, HEAD + "\n" + TEXT + "\n" + EARLIER),
    ],
    ids=["last", "middle"],
)
def test_the_phase_entry_is_replaced_in_place(before: str, after: str) -> None:
    assert put_entry(before, ENTRY) == after


def test_the_written_entry_reads_back() -> None:
    entries, problems = parse_progress(put_entry(HEAD + "\n" + EARLIER, ENTRY))
    assert problems == []
    assert replace(entries[-1], line=0) == replace(ENTRY, deviations=("None",))


@pytest.mark.parametrize(
    "changed",
    [
        {"title": ""},
        {"deviations": ("one\ntwo",)},
        {"follow_ups": ("",)},
        {"new_names": ""},
    ],
    ids=["no-title", "line-break", "empty-item", "no-names"],
)
def test_an_entry_out_of_form_is_refused(changed: dict[str, object]) -> None:
    with pytest.raises(ValueError) as raised:
        put_entry(HEAD + "\n" + EARLIER, replace(ENTRY, **changed))  # type: ignore[arg-type]
    assert str(raised.value) == ENTRY_MESSAGE == "the entry does not match the progress form"
