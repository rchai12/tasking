import pytest

from docket import core
from docket.store import Store, Task
from tests.reference_cases import BODY, LINK, NOW
from tests.support import fixed_times
from tests.support import path as path
from tests.support import store as store


def create(store: Store, path: str, fields: dict[str, object]) -> Task | core.Outcome:
    values = {
        "title": BODY["title"],
        "source": "email",
        "provider": "gmail",
        "message_id": "synthetic/1",
        "link": "https://mail.example/1",
        **fields,
    }
    if path == "plain":
        return core.create_task(store, **values)
    return core.create_task_once(store, client="email", key="k", request=BODY, **values)


@pytest.mark.parametrize("path", ["plain", "keyed", "link"])
@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("message_id", "x" * 513),
        ("link", "x" * 2049),
        ("message_id", "bad\x1b[2J"),
        ("link", "bad\nline"),
        ("message_id", "bad\u200dformat"),
        ("link", "bad\u2028line"),
        ("message_id", "bad\u2029paragraph"),
        ("link", "bad\x00tail"),
    ],
    ids=["id-long", "link-long", "escape", "newline", "format", "line", "paragraph", "nul"],
)
def test_invalid_references_never_write(
    store: Store, monkeypatch: pytest.MonkeyPatch, path: str, field: str, bad: str
) -> None:
    if path == "link":
        fixed_times(monkeypatch, NOW)
        core.create_task(store, title="Synthetic reference task", source="owner")
    fixed_times(monkeypatch)
    with pytest.raises(core.CoreError) as raised:
        if path == "link":
            core.add_link(
                store,
                "t1",
                client="email",
                key="k",
                request=LINK,
                provider="gmail",
                message_id=bad if field == "message_id" else "follow",
                link=bad if field == "link" else "https://mail.example/2",
            )
        else:
            create(store, path, {field: bad})
    assert (raised.value.code, str(raised.value)) == ("invalid_reference", "invalid_reference")
    assert store.links("t1") == []
    assert store.request_key("email", "k") is None
    assert len(store.audit("t1")) == (1 if path == "link" else 0)
    assert len(store.tasks()) == (1 if path == "link" else 0)


@pytest.mark.parametrize("path", ["plain", "keyed", "link"])
def test_boundaries_round_trip_without_rewriting(
    store: Store, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    fixed_times(monkeypatch, NOW, NOW)
    if path == "link":
        core.create_task(store, title="Synthetic reference task", source="owner")
        result = core.add_link(
            store,
            "t1",
            client="email",
            key="k",
            request=LINK,
            provider="gmail",
            message_id="é" * 512,
            link="x" * 2048,
        ).link
    else:
        result = create(store, path, {"message_id": "é" * 512, "link": "x" * 2048})
        if path == "keyed":
            result = result.task
    assert result.message_id == "é" * 512
    assert result.link == "x" * 2048


def test_rejected_key_can_be_used_by_a_corrected_request(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch)
    with pytest.raises(core.CoreError, match="^invalid_reference$"):
        create(store, "keyed", {"message_id": "bad\nline"})
    fixed_times(monkeypatch, NOW, NOW)
    assert create(store, "keyed", {}).task.id == "t1"
    assert create(store, "keyed", {}).changed is False
    assert len(store.audit("t1")) == 1
