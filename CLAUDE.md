# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Streamlit app (Hebrew UI) for a carpentry shop: design a wardrobe (columns with shelves, drawers, hanging rod, doors), view it in 3D, get a cut list and a price estimate.

## Commands

- Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest`
- Run: `.venv/bin/streamlit run app.py` (http://localhost:8501)
- Tests: `.venv/bin/pytest -q`; single test: `.venv/bin/pytest -q test_wardrobe.py::test_validate`
- Dependency audit: `.venv/bin/pip-audit -r requirements.txt`

## Architecture

- `wardrobe.py` holds all logic and must not import streamlit. It works on a plain `cfg` dict built in `app.py`. The dict has these keys:
  - Dimensions in mm: `width`, `height`, `depth`, `t`, `back_t`, `plinth`.
  - `columns`: a list of `{shelves, drawers, drawer_h, rod}`.
  - `doors`
  - `prices`
- `build_panels(cfg)` returns a flat list of `Panel` boxes. Each box has a min corner `x,y,z`, sizes `dx,dy,dz`, a `material` (`board` | `back` | `hardware`) and a `kind`, which picks the 3D color. Everything else derives from this list:
  - `cut_list` uses `board`/`back` panels only. The smallest dimension is the thickness and the largest is the length, and identical rows are grouped into a quantity.
  - `price`: area in m² by material, plus a per-unit cost. Drawers are counted by the panel name `"חזית מגירה"`, doors by kind and rods by kind.
  - The 3D view in `app.py` draws one Plotly `Mesh3d` cube per panel. Corner index bits are 0=x, 1=y, 2=z, and the `I, J, K` triangle lists depend on that ordering.
- Coordinates:
  - x is width.
  - y is depth, with **y=0 at the front**. Doors sit at y=-t, and the back panel sits behind the sides at y=depth-back_t.
  - z is height. The inner region of each column runs from `plinth+t` to `height-t`.
  - The camera is set to look from the front.
- `validate(cfg)` must guarantee that `build_panels` output has no overlaps: shelf gaps of at least 150 mm, the rod clear of shelves, and the plinth either 0 or at least `t`. `app.py` shows the errors and calls `st.stop()` before drawing. If you change the geometry, keep `test_valid_configs_have_no_overlaps` passing.
- Panel names are Hebrew strings and are used as keys (in counting and in tests), so renaming one breaks those references.
- `test_wardrobe.py` also runs the whole UI headless through `streamlit.testing.v1.AppTest`. Widgets have keys like `shelves0` and `drawers0`.

## Voice agent

- `voice_agent.py` (no streamlit import) holds the model constants at the top (`STT_MODEL`, `LLM_MODEL`, `TTS_MODEL`, `TTS_VOICE`, `TTS_INSTRUCTIONS`), `LIMITS`, the `update_design` function tool, and `transcribe`/`run_agent`/`speak`, which take an OpenAI `client` so tests pass a fake.
- `apply_changes(state, changes)` is the trust boundary: the LLM output is untrusted, so it clamps to `LIMITS`, coerces to int, ignores unknown keys and out-of-range columns, and returns Hebrew notes. It writes to the widget keys (`width,height,depth,t,back_t,plinth,n,doors`, `shelves{i}` etc.).
- In `app.py` the voice processing runs at the top, before the other widgets (Streamlit forbids setting a widget key after its widget exists in the same run). It uses `session_state["cfg"]`/`["summary"]` stored by the previous run, handles each recording once (hash in `last_audio`), then `st.rerun()`.
- Requires `OPENAI_API_KEY` (env or `.streamlit/secrets.toml`, which is gitignored). Without it the voice section is disabled and the rest of the app works.

## Workflow

- Plan with Opus 5.5 (`claude-opus-5-5`); execute with Sonnet 5.5 (`claude-sonnet-5-5`, pass `model: "sonnet"` when delegating to a subagent).
- After every execution: run `.venv/bin/pytest -q`, exercise the changed flow in the running app, and re-check features that worked before (regressions). Report actual results, including failures.
- Run the `/security-review` skill on the updated code before reporting done.
