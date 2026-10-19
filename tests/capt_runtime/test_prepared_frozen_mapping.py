import json

import pytest

from capt_runtime.prepared_execution import FrozenDict, freeze


def test_approved_mapping_rejects_in_place_union():
    bound=freeze({"model": "approved", "nested": {"scope": "read"}})
    with pytest.raises(TypeError,match="immutable"):
        bound |= {"model":"substituted"}
    with pytest.raises(TypeError,match="immutable"):
        bound["nested"] |= {"scope":"write"}
    assert bound["model"]=="approved"
    assert bound["nested"]["scope"]=="read"


def test_mapping_still_canonical_json_serializable():
    bound=freeze({"model":"approved","arguments":[1,{"path":"notes/a.md"}]})
    assert isinstance(bound,FrozenDict)
    assert json.loads(json.dumps(bound))=={"model":"approved","arguments":[1,{"path":"notes/a.md"}]}


@pytest.mark.parametrize("method",["update","pop","setdefault","clear"])
def test_mutators_still_fail(method):
    bound=freeze({"model":"approved"})
    with pytest.raises(TypeError,match="immutable"):
        if method=="update":bound.update({"model":"other"})
        elif method=="pop":bound.pop("model")
        elif method=="setdefault":bound.setdefault("other","x")
        else:bound.clear()
