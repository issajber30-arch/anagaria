"""Wardrobe geometry, validation, cut list and pricing. Units: mm. x=width, y=depth (0=front), z=height."""
from dataclasses import dataclass

import pandas as pd


@dataclass
class Panel:
    name: str
    x: float
    y: float
    z: float
    dx: float
    dy: float
    dz: float
    material: str  # board | back | hardware
    kind: str  # carcass | shelf | drawer | door | rod | back


def column_width(cfg):
    n = len(cfg["columns"])
    return (cfg["width"] - 2 * cfg["t"] - (n - 1) * cfg["t"]) / n


def build_panels(cfg):
    W, H, D, t, bt, pl = (cfg[k] for k in ("width", "height", "depth", "t", "back_t", "plinth"))
    cols, cw, cd = cfg["columns"], column_width(cfg), cfg["depth"] - cfg["back_t"]
    z0, z1 = pl + t, H - t  # inner region of the carcass
    P = []

    def add(name, x, y, z, dx, dy, dz, kind, material="board"):
        P.append(Panel(name, x, y, z, dx, dy, dz, material, kind))

    add("דופן", 0, 0, 0, t, cd, H, "carcass")
    add("דופן", W - t, 0, 0, t, cd, H, "carcass")
    add("תקרה", t, 0, H - t, W - 2 * t, cd, t, "carcass")
    add("תחתית", t, 0, pl, W - 2 * t, cd, t, "carcass")
    if pl > 0:
        add("צוקל", t, 50, 0, W - 2 * t, t, pl, "carcass")
    add("גב", 0, cd, pl, W, bt, H - pl, "back", "back")

    for i, c in enumerate(cols):
        x0 = t + i * (cw + t)
        if i:
            add("מחיצה", x0 - t, 0, z0, t, cd, z1 - z0, "carcass")
        dh, dd = c["drawer_h"], cd - t - 20
        for j in range(c["drawers"]):
            z = z0 + j * dh + 2
            add("חזית מגירה", x0 + 2, 0, z, cw - 4, t, dh - 4, "drawer")
            add("דופן מגירה", x0 + 2, t, z, t, dd - t, dh - 4, "drawer")
            add("דופן מגירה", x0 + cw - 2 - t, t, z, t, dd - t, dh - 4, "drawer")
            add("גב מגירה", x0 + 2 + t, dd - t, z, cw - 4 - 2 * t, t, dh - 4, "drawer")
            add("תחתית מגירה", x0 + 2 + t, t, z, cw - 4 - 2 * t, dd - 2 * t, t, "drawer")
        base = z0 + c["drawers"] * dh
        if c["drawers"]:
            add("מדף", x0, 0, base, cw, cd, t, "shelf")  # separator above drawers
            base += t
        k = c["shelves"]
        gap = (z1 - base - k * t) / (k + 1)
        for s in range(k):
            add("מדף", x0, 0, base + gap * (s + 1) + t * s, cw, cd, t, "shelf")
        if c["rod"]:
            add("מוט תלייה", x0, cd / 2 - 12.5, z1 - 60 - 25, cw, 25, 25, "rod", "hardware")

    if cfg["doors"]:
        for i in range(len(cols)):
            x0 = t + i * (cw + t)
            add("דלת", x0 - t / 2 + 1.5, -t, pl + 1.5, cw + t - 3, t, H - pl - 3, "door")
    return P


def validate(cfg):
    errs = []
    for k, label in (("width", "רוחב"), ("height", "גובה"), ("depth", "עומק"), ("t", "עובי לוח"), ("back_t", "עובי גב")):
        if cfg[k] <= 0:
            errs.append(f"{label} חייב להיות חיובי")
    if cfg["plinth"] < 0:
        errs.append("גובה צוקל לא יכול להיות שלילי")
    elif 0 < cfg["plinth"] < cfg["t"]:
        errs.append("גובה צוקל חייב להיות 0 או לפחות עובי הלוח")
    if errs or not cfg["columns"]:
        return errs or ["חייבת להיות לפחות עמודה אחת"]
    if column_width(cfg) < 200:
        errs.append(f"רוחב עמודה {column_width(cfg):.0f} מ\"מ קטן מ-200 מ\"מ")
    inner = cfg["height"] - cfg["plinth"] - 2 * cfg["t"]
    for i, c in enumerate(cfg["columns"], 1):
        need = c["drawers"] * c["drawer_h"] + (cfg["t"] if c["drawers"] else 0) + c["shelves"] * (cfg["t"] + 150)
        if c["shelves"] or c["rod"]:
            need += 150  # k shelves make k+1 gaps; each gap (and the rod's space) needs >= 150
        if need > inner:
            errs.append(f"עמודה {i}: המגירות והמדפים לא נכנסים בגובה הפנימי ({need:.0f} > {inner:.0f} מ\"מ)")
    return errs


def cut_list(panels):
    rows = []
    for p in panels:
        if p.material in ("board", "back"):
            t, w, l = sorted((p.dx, p.dy, p.dz))
            rows.append((p.name, round(l), round(w), round(t)))
    df = pd.DataFrame(rows, columns=["חלק", "אורך", "רוחב", "עובי"])
    if df.empty:
        return df.assign(כמות=[])
    return df.groupby(list(df.columns)).size().reset_index(name="כמות")


def price(panels, cfg):
    def m2(material):
        return sum(max(p.dx, p.dy, p.dz) * sorted((p.dx, p.dy, p.dz))[1] for p in panels if p.material == material) / 1e6

    pr = cfg["prices"]
    board, back = m2("board"), m2("back")
    drawers = sum(p.name == "חזית מגירה" for p in panels)
    doors = sum(p.kind == "door" for p in panels)
    rods = sum(p.kind == "rod" for p in panels)
    r = {
        "board_m2": board, "back_m2": back, "drawers": drawers, "doors": doors, "rods": rods,
        "board_cost": board * pr["board_m2"], "back_cost": back * pr["back_m2"],
        "drawers_cost": drawers * pr["drawer"], "doors_cost": doors * pr["door"], "rods_cost": rods * pr["rod"],
    }
    r["total"] = sum(v for k, v in r.items() if k.endswith("_cost"))
    return r
