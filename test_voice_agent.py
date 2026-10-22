import json
from types import SimpleNamespace as NS

from streamlit.testing.v1 import AppTest

from voice_agent import apply_changes, run_agent


def test_clamp_and_int():
    s = {}
    notes = apply_changes(s, {"width": 99999.7, "depth": "450", "t": 1, "n": 4})
    assert s == {"width": 6000, "depth": 450, "t": 10, "n": 4} and len(notes) == 2


def test_unknown_and_bad_values_ignored():
    s = {"n": 3}
    notes = apply_changes(s, {"evil": 1, "height": "abc", "doors": "yes", "prices": {}})
    assert s == {"n": 3} and len(notes) == 4


def test_doors_bool():
    s = {}
    apply_changes(s, {"doors": False})
    assert s["doors"] is False


def test_columns():
    s = {"n": 2}
    notes = apply_changes(s, {"columns": [{"index": 1, "drawers": 99, "rod": True, "x": 1}, {"index": 3, "shelves": 1},
                                          {"index": 0}, {"shelves": 1}]})
    assert s == {"n": 2, "drawers0": 10, "rod0": True} and len(notes) == 5


def test_increase_n_allows_new_columns():
    s = {"n": 3}
    apply_changes(s, {"n": 5, "columns": [{"index": 5, "shelves": 4}]})
    assert s == {"n": 5, "shelves4": 4}


def msg(content=None, args=()):
    calls = [NS(id=f"c{i}", function=NS(name="update_design", arguments=a)) for i, a in enumerate(args)]
    return NS(choices=[NS(message=NS(content=content, tool_calls=calls or None))])


class Fake:
    def __init__(self, *resp):
        self.resp, self.calls = list(resp), []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        self.calls.append(kw)
        return self.resp.pop(0)


def test_run_agent_merges_calls_and_confirms():
    f = Fake(msg(None, [json.dumps({"width": 3000, "columns": [{"index": 1, "drawers": 2}]}),
                        json.dumps({"n": 4, "columns": [{"index": 2, "rod": True}]})]), msg("בוצע, רוחב 3 מטר"))
    changes, reply = run_agent(f, "שנה", {}, "")
    assert changes == {"width": 3000, "n": 4, "columns": [{"index": 1, "drawers": 2}, {"index": 2, "rod": True}]}
    assert reply == "בוצע, רוחב 3 מטר" and len(f.calls) == 2


def test_run_agent_text_only_single_call():
    f = Fake(msg("זה עולה 5000"))
    assert run_agent(f, "כמה זה עולה?", {}, "סה\"כ 5000") == ({}, "זה עולה 5000") and len(f.calls) == 1


def test_run_agent_bad_json_is_no_changes():
    f = Fake(msg("סליחה", ["{not json"]))
    assert run_agent(f, "x", {}, "") == ({}, "סליחה")


def test_app_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    at = AppTest.from_file("app.py").run()
    assert not at.exception and at.sidebar.info
