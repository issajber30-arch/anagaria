import json

STT_MODEL = "gpt-transcribe"  # recommended for recorded files; gpt-realtime-whisper is for live streams only
LLM_MODEL = "gpt-4.1-mini"
TTS_MODEL = "gpt-4o-mini-tts"  # shortcut: deprecated, shuts down 2027-01-06; migrate to the Realtime API (gpt-realtime-2.1-mini) before then
TTS_VOICE = "marin"
TTS_INSTRUCTIONS = "דבר בעברית, בטון ידידותי ותמציתי, כמו עוזר של נגר מנוסה."

LIMITS = dict(width=(300, 6000), height=(600, 3000), depth=(300, 900), t=(10, 40), back_t=(3, 20),
              plinth=(0, 200), n=(1, 10), shelves=(0, 20), drawers=(0, 10), drawer_h=(100, 400))
_num = lambda d: {"type": "integer", "description": d}
TOOLS = [{"type": "function", "function": {
    "name": "update_design",
    "description": "עדכון תכנון הארון. מידות במ\"מ. שדות שלא צוינו לא ישתנו.",
    "parameters": {"type": "object", "properties": {
        "width": _num("רוחב"), "height": _num("גובה"), "depth": _num("עומק"), "t": _num("עובי לוח"),
        "back_t": _num("עובי גב"), "plinth": _num("גובה צוקל"), "n": _num("מספר עמודות"),
        "doors": {"type": "boolean"},
        "columns": {"type": "array", "description": "שינויים בעמודות (אינדקס מ-1)", "items": {
            "type": "object", "required": ["index"], "properties": {
                "index": _num("מספר עמודה מ-1"), "shelves": _num("מדפים"), "drawers": _num("מגירות"),
                "drawer_h": _num("גובה מגירה"), "rod": {"type": "boolean"}}}}}}}}]


def _int(v):
    if isinstance(v, bool):
        raise ValueError
    return int(float(v))


def _set(state, key, v, lim, notes, label):
    try:
        x = _int(v)
    except (TypeError, ValueError, OverflowError):
        notes.append(f"{label}: ערך לא תקין, הושמט")
        return
    lo, hi = LIMITS[lim]
    c = min(max(x, lo), hi)
    if c != x:
        notes.append(f"{label}: {x} מחוץ לטווח, הוגדר ל-{c}")
    state[key] = c


def apply_changes(state, changes):
    """Trust boundary: the LLM output is untrusted. Mutates widget-keyed state, returns Hebrew notes."""
    notes = []
    if not isinstance(changes, dict):
        return ["שינויים לא תקינים, הושמטו"]
    for k, v in changes.items():
        if k in ("width", "height", "depth", "t", "back_t", "plinth", "n"):
            _set(state, k, v, k, notes, k)
        elif k == "doors":
            if isinstance(v, bool):
                state[k] = v
            else:
                notes.append("doors: ערך לא תקין, הושמט")
        elif k != "columns":
            notes.append(f"שדה לא מוכר '{k}' התעלמות")
    cols = changes.get("columns", [])
    for c in cols if isinstance(cols, list) else []:
        try:
            i = _int(c["index"]) - 1
        except (TypeError, KeyError, ValueError, OverflowError):
            notes.append("עמודה ללא אינדקס תקין, הושמטה")
            continue
        if not 0 <= i < state.get("n", 3):
            notes.append(f"עמודה {i + 1} לא קיימת, הושמטה")
            continue
        for k, v in c.items():
            if k in ("shelves", "drawers", "drawer_h"):
                _set(state, f"{k}{i}", v, k, notes, f"{k} בעמודה {i + 1}")
            elif k == "rod" and isinstance(v, bool):
                state[f"rod{i}"] = v
            elif k != "index":
                notes.append(f"שדה '{k}' בעמודה {i + 1} הושמט")
    return notes


def transcribe(client, audio_bytes):
    return client.audio.transcriptions.create(
        model=STT_MODEL, file=("audio.wav", audio_bytes), language="he").text


def run_agent(client, text, cfg, summary):
    system = ("אתה עוזר קולי לנגר שמתכנן ארון. עדכן את התכנון באמצעות הפונקציה update_design כשמבקשים שינוי. "
              "ענה בעברית בקצרה (משפט או שניים), בלי רשימות. מידות במ\"מ.\n"
              f"התכנון הנוכחי: {json.dumps(cfg, ensure_ascii=False)}\nסיכום מחיר וחיתוך: {summary}")
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": text}]
    msg = client.chat.completions.create(model=LLM_MODEL, messages=msgs, tools=TOOLS).choices[0].message
    calls = msg.tool_calls or []
    changes = {}
    for call in calls:
        try:
            args = json.loads(call.function.arguments)
        except (TypeError, ValueError):
            continue
        if not isinstance(args, dict):
            continue
        cols = args.pop("columns", [])
        changes.update(args)
        if isinstance(cols, list):
            changes.setdefault("columns", []).extend(cols)
    reply = msg.content or ""
    if calls and not reply:
        msgs.append({"role": "assistant", "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in calls]})
        msgs += [{"role": "tool", "tool_call_id": c.id, "content": "בוצע"} for c in calls]
        reply = client.chat.completions.create(model=LLM_MODEL, messages=msgs).choices[0].message.content or ""
    return changes, reply or ("בוצע" if changes else "לא הבנתי, אפשר לחזור על זה?")


def speak(client, text):
    return client.audio.speech.create(model=TTS_MODEL, voice=TTS_VOICE, input=text,
                                      instructions=TTS_INSTRUCTIONS, response_format="mp3").read()
