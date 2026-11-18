import ast
import hashlib

import pytest

from tests.preservation_cases import assert_preserved


def _hash(text: str, *, signature: bool = False) -> str:
    node = ast.parse(text).body[0]
    if signature:
        node.body = []
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


@pytest.mark.parametrize(
    "case",
    [
        "unchanged",
        "new-body",
        "new-node",
        "bad-stable",
        "bad-signature",
        "missing-stable",
        "bad-import",
    ],
)
def test_structural_freezes_keep_the_unaffected_role_and_public_signature(tmp_path, case) -> None:
    path = tmp_path / "synthetic.py"
    baseline = (
        "from math import ceil\ndef stable() -> int:\n    return 1\n\n"
        "def changed(value: int) -> int:\n    return value\n"
    )
    expected = {
        "imports": [["from", "math", "ceil", None]],
        "stable_nodes": {"stable": _hash("def stable() -> int:\n    return 1\n")},
        "mutable_signatures": {
            "changed": _hash("def changed(value: int) -> int:\n    return value\n", signature=True)
        },
    }
    variants = {
        "unchanged": baseline,
        "new-body": baseline.replace("return value", "return value + 1"),
        "new-node": baseline + "\ndef added() -> int:\n    return 3\n",
        "bad-stable": baseline.replace("return 1", "return 2"),
        "bad-signature": baseline.replace("value: int", "value: str"),
        "missing-stable": baseline.replace("def stable", "def removed"),
        "bad-import": baseline.replace("from math import ceil", "from math import floor as ceil"),
    }
    path.write_text(variants[case])
    if case in ("bad-stable", "bad-signature", "missing-stable", "bad-import"):
        with pytest.raises(AssertionError):
            assert_preserved(path, expected)
    else:
        assert_preserved(path, expected)


def test_byte_freezes_still_refuse_any_changed_byte(tmp_path) -> None:
    path = tmp_path / "synthetic.txt"
    path.write_bytes(b"synthetic")
    expected = "b3cc0475bb78a5026098858e9889acf666d31062d513d303314eca31d36e72f2"
    assert_preserved(path, expected)
    path.write_bytes(b"synthetic\n")
    with pytest.raises(AssertionError):
        assert_preserved(path, expected)


def test_unaffected_core_and_store_roles_keep_the_exact_feature_boundary() -> None:
    from tests.product_support_cases import MANIFEST, ROOT

    core = MANIFEST["frozen"]["src/docket/core.py"]
    store = MANIFEST["frozen"]["src/docket/store.py"]
    assert len(core["stable_nodes"]) == 38
    assert set(core["mutable_signatures"]) == {"change_state", "edit_task", "_insert_open_task"}
    assert len(store["stable_nodes"]) == 86
    assert set(store["mutable_signatures"]) == {"Store._apply_migration"}
    assert_preserved(ROOT / "src/docket/core.py", core)
    assert_preserved(ROOT / "src/docket/store.py", store)
