from streamlit.testing.v1 import AppTest

from wardrobe import build_panels, column_width, cut_list, price, validate


def col(**k):
    return {"shelves": 2, "drawers": 0, "drawer_h": 200, "rod": False, **k}


def cfg(n=3, **k):
    c = dict(width=2400, height=2400, depth=600, t=18, back_t=5, plinth=80, columns=[col() for _ in range(n)],
             doors=True, prices=dict(board_m2=100, back_m2=40, drawer=80, door=60, rod=30))
    c.update(k)
    return c


def count(panels, name):
    return sum(p.name == name for p in panels)


def test_counts():
    c = cfg(columns=[col(drawers=2), col(), col(rod=True)])
    p = build_panels(c)
    assert count(p, "דופן") == 2 and count(p, "מחיצה") == 2 and count(p, "דלת") == 3
    assert count(p, "מדף") == 2 * 3 + 1  # separator above the drawers
    assert count(p, "חזית מגירה") == 2 and count(p, "דופן מגירה") == 4
    assert count(p, "גב מגירה") == 2 and count(p, "תחתית מגירה") == 2
    assert count(p, "מוט תלייה") == 1
    assert count(build_panels(cfg(doors=False)), "דלת") == 0


def test_widths():
    c = cfg(n=4)
    assert 4 * column_width(c) + 3 * 18 + 2 * 18 == c["width"]


def test_cut_list():
    df = cut_list(build_panels(cfg()))
    sides = df[df["חלק"] == "דופן"]
    assert len(sides) == 1 and sides.iloc[0]["כמות"] == 2 and sides.iloc[0]["אורך"] == 2400
    assert sides.iloc[0]["עובי"] == 18 and sides.iloc[0]["רוחב"] == 595


def test_price():
    c = cfg(n=1, width=1000, height=1000, depth=500, plinth=0, columns=[col(shelves=0, rod=True)], doors=True)
    r = price(build_panels(c), c)
    assert r["doors"] == 1 and r["rods"] == 1 and r["drawers"] == 0
    assert abs(r["back_m2"] - 1.0 * 1.0) < 1e-9 and abs(r["back_cost"] - 40) < 1e-6
    assert abs(r["total"] - (r["board_cost"] + 40 + 60 + 30)) < 1e-6


def test_validate():
    assert validate(cfg()) == []
    assert validate(cfg(n=1, columns=[col(shelves=0)])) == []
    assert validate(cfg(n=1, columns=[col(shelves=0, drawers=0)])) == []
    assert any("עמודה 1" in e for e in validate(cfg(n=1, columns=[col(drawers=10)])))
    assert validate(cfg(n=10, width=300))
    assert validate(cfg(n=10, width=6000)) == []
    assert validate(cfg(depth=0))


def test_app_runs():
    at = AppTest.from_file("app.py", default_timeout=30).run()
    assert not at.exception


def test_valid_configs_have_no_overlaps():
    # any config that passes validation must give shelf gaps >= 150 and a rod clear of shelves
    for shelves in range(0, 12):
        for drawers in range(0, 6):
            for rod in (False, True):
                c = cfg(n=1, width=1000, height=1620, depth=500, t=10, back_t=10, plinth=0,
                        columns=[col(shelves=shelves, drawers=drawers, drawer_h=100, rod=rod)])
                if validate(c):
                    continue
                P = build_panels(c)
                boards = sorted(p.z for p in P if p.name in ("מדף", "תקרה"))
                assert all(b - a - c["t"] >= 150 - 1e-6 for a, b in zip(boards, boards[1:]))
                for r in (p for p in P if p.kind == "rod"):
                    assert not any(s.z < r.z + r.dz and r.z < s.z + s.dz for s in P if s.name == "מדף")


def test_plinth_thinner_than_board_rejected():
    assert validate(cfg(plinth=10))
    assert validate(cfg(plinth=0)) == []
