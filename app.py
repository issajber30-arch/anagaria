import hashlib
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from openai import OpenAI, OpenAIError

import voice_agent
from wardrobe import build_panels, cut_list, price, validate

st.set_page_config(layout="wide", page_title="תכנון ארון")
st.title("תכנון ארון")

sb = st.sidebar
# Voice agent runs first: Streamlit forbids setting a widget's state after the widget is created in the same run.
try:
    api_key = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
except Exception:  # no secrets.toml
    api_key = None
sb.subheader("סוכן קולי")
if not api_key:
    sb.info("להפעלת הסוכן הקולי הגדר OPENAI_API_KEY במשתנה סביבה או ב-.streamlit/secrets.toml")
audio = sb.audio_input("דבר אל הסוכן", disabled=not api_key)
if audio and api_key:
    data = audio.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    if digest != st.session_state.get("last_audio"):
        st.session_state["last_audio"] = digest
        try:
            client = OpenAI(api_key=api_key)
            said = voice_agent.transcribe(client, data)
            changes, reply = voice_agent.run_agent(client, said, st.session_state.get("cfg", {}), st.session_state.get("summary", ""))
            notes = voice_agent.apply_changes(st.session_state, changes)
            st.session_state.update(said=said, reply=reply, notes=notes, mp3=voice_agent.speak(client, reply))
            st.rerun()
        except OpenAIError as e:
            sb.error(str(e))
if "said" in st.session_state:
    sb.text(f"אמרת: {st.session_state['said']}")  # text, not markdown: model/transcript output is untrusted
    sb.text(st.session_state["reply"])
    for note in st.session_state["notes"]:
        sb.text(note)
if "mp3" in st.session_state:
    sb.audio(st.session_state.pop("mp3"), autoplay=True)  # popped: plays once

width = sb.number_input("רוחב (מ\"מ)", 300, 6000, 2400, key="width")
height = sb.number_input("גובה (מ\"מ)", 600, 3000, 2400, key="height")
depth = sb.number_input("עומק (מ\"מ)", 300, 900, 600, key="depth")
t = sb.number_input("עובי לוח (מ\"מ)", 10, 40, 18, key="t")
back_t = sb.number_input("עובי גב (מ\"מ)", 3, 20, 5, key="back_t")
plinth = sb.number_input("גובה צוקל (מ\"מ)", 0, 200, 80, key="plinth")
n = sb.number_input("מספר עמודות", 1, 10, 3, key="n")
doors = sb.checkbox("דלתות", True, key="doors")
sb.subheader("מחירים (₪)")
prices = {
    "board_m2": sb.number_input("לוח למ\"ר", 0.0, value=120.0),
    "back_m2": sb.number_input("גב למ\"ר", 0.0, value=40.0),
    "drawer": sb.number_input("מגירה (פרזול)", 0.0, value=80.0),
    "door": sb.number_input("דלת (פרזול)", 0.0, value=60.0),
    "rod": sb.number_input("מוט תלייה", 0.0, value=30.0),
}

columns = []
for i, box in enumerate(st.columns(n)):
    with box.expander(f"עמודה {i + 1}", expanded=True):
        columns.append({
            "shelves": st.number_input("מדפים", 0, 20, 2, key=f"shelves{i}"),
            "drawers": st.number_input("מגירות", 0, 10, 0, key=f"drawers{i}"),
            "drawer_h": st.number_input("גובה מגירה", 100, 400, 200, key=f"drawer_h{i}"),
            "rod": st.checkbox("מוט תלייה", key=f"rod{i}"),
        })
show_doors = st.checkbox("הצג דלתות בתצוגה", True)

cfg = dict(width=width, height=height, depth=depth, t=t, back_t=back_t, plinth=plinth,
           columns=columns, doors=doors, prices=prices)
st.session_state["cfg"] = cfg  # read by the voice agent on the next run
errors = validate(cfg)
for e in errors:
    st.error(e)
if errors:
    st.stop()

panels = build_panels(cfg)
r = price(panels, cfg)
df = cut_list(panels)
st.session_state["summary"] = f"סה\"כ מחיר {r['total']:.0f} ₪, {r['drawers']} מגירות, {r['doors']} דלתות, {r['rods']} מוטות, {len(df)} שורות ברשימת חיתוך"
COLORS = {"carcass": "#c8a27a", "shelf": "#a97c50", "drawer": "#6b8e9b", "door": "#8a6a4f", "rod": "#555555", "back": "#e0d2bd"}
# cube corners (bit 0=x, 1=y, 2=z) and 12 triangles
I, J, K = [0, 0, 4, 4, 0, 0, 2, 2, 0, 0, 1, 1], [1, 3, 5, 7, 1, 5, 3, 7, 2, 6, 3, 7], [3, 2, 7, 6, 5, 4, 7, 6, 6, 4, 7, 5]

tab3d, tabcut, tabprice = st.tabs(["תלת־ממד", "רשימת חיתוך", "מחיר"])
with tab3d:
    fig = go.Figure()
    for p in panels:
        if p.kind == "door" and not show_doors:
            continue
        v = [(p.x + (c & 1) * p.dx, p.y + (c >> 1 & 1) * p.dy, p.z + (c >> 2 & 1) * p.dz) for c in range(8)]
        fig.add_trace(go.Mesh3d(
            x=[a[0] for a in v], y=[a[1] for a in v], z=[a[2] for a in v], i=I, j=J, k=K,
            color=COLORS[p.kind], opacity=0.35 if p.kind == "door" else 1, flatshading=True,
            name=p.name, hovertemplate=f"{p.name}<br>{p.dx:.0f}×{p.dy:.0f}×{p.dz:.0f}<extra></extra>"))
    fig.update_layout(scene=dict(aspectmode="data", camera=dict(eye=dict(x=0.8, y=-1.6, z=0.6))),  # front view (y=0 is front)
                      height=700, showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch")
with tabcut:
    st.dataframe(df, width="stretch")
    st.download_button("הורד CSV", df.to_csv(index=False).encode("utf-8-sig"), "cutlist.csv", "text/csv")
with tabprice:
    st.table(pd.DataFrame([
        ("לוחות", f"{r['board_m2']:.2f} מ\"ר", f"{r['board_cost']:.2f}"),
        ("גב", f"{r['back_m2']:.2f} מ\"ר", f"{r['back_cost']:.2f}"),
        ("מגירות", r["drawers"], f"{r['drawers_cost']:.2f}"),
        ("דלתות", r["doors"], f"{r['doors_cost']:.2f}"),
        ("מוטות", r["rods"], f"{r['rods_cost']:.2f}"),
    ], columns=["פריט", "כמות", "עלות ₪"]).astype(str))
    st.metric("סה\"כ ₪", f"{r['total']:.2f}")
