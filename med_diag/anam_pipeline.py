"""
anam_pipeline.py — Pagina ANAM in TITUS Streamlit.

Flux:
  1. Selectie anamneza (exemple predefinite sau text liber)
  2. Procesare ANAM -> extractie entitati clinice
  3. Rulare TITUS -> ranking diagnostic
"""

import re
import json
import urllib.request

import streamlit as st

from .ui_common import panel_header
from .narrative_engine import extract as _local_extract


# ── Anamneze predefinite ───────────────────────────────────────────────────────
ANAMNEZE = {
    "Parkinson": {
        "icon": "Neurologie",
        "tema": "Sindrom parkinsonian",
        "text": (
            "Medic: Buna ziua. Ce va aduce astazi la consultatie?\n"
            "Pacient: De cateva luni ma misc tot mai greu. Parca nu mai pornesc la fel de repede.\n"
            "Medic: De cat timp exact?\n"
            "Pacient: Vreo 4-5 luni. La inceput am pus pe seama varstei, dar acum ma incurca la mers.\n"
            "Medic: Cum este mersul?\n"
            "Pacient: Merg mai incet, cu pasi mici. Uneori parcă imi tarsesc piciorul stang.\n"
            "Medic: Aveti rigiditate musculara?\n"
            "Pacient: Da, mai ales dimineata. Ma simt intepenit, parca ar trebui timp sa ma dezmortes.\n"
            "Medic: Tremuraturi?\n"
            "Pacient: Imi tremura mana dreapta cand stau linistit. Daca fac ceva cu mana, se mai linisteste.\n"
            "Medic: Ati cazut?\n"
            "Pacient: Nu am cazut, dar ma simt nesigur cand ma intorc brusc.\n"
            "Medic: Altceva observat de familie?\n"
            "Pacient: Sotia spune ca scriu tot mai mic. Vorbesc mai incet si par mereu serios, cand nu sunt suparatat.\n"
            "Medic: Probleme de somn?\n"
            "Pacient: Da, transpir noaptea destul de mult. Uneori am miscari in somn.\n"
            "Medic: Simtiti mirosurile bine?\n"
            "Pacient: De fapt, de vreo 2 ani nu mai simt bine mirosurile. Nu am legat-o de nimic."
        ),
    },
    "Angina": {
        "icon": "Cardiologie",
        "tema": "Durere toracica de efort",
        "text": (
            "Medic: Ce probleme va aduc astazi?\n"
            "Pacient: Am o presiune in piept de cateva saptamani, mai ales cand urc scarile sau merg repede.\n"
            "Medic: Descrieti mai exact aceasta senzatie.\n"
            "Pacient: E ca o strangere, in mijlocul pieptului. Uneori imi iradiaza in bratul stang.\n"
            "Medic: Trece cand va odihniti?\n"
            "Pacient: Da, dupa 5-10 minute de repaus cedeaza.\n"
            "Medic: Altceva?\n"
            "Pacient: Transpir cand apare durerea. Ma gafai repede la efort.\n"
            "Medic: Febra, tuse?\n"
            "Pacient: Nu am febra. Nu am tuse.\n"
            "Medic: Antecedente?\n"
            "Pacient: Fumez de 20 de ani. Am tensiune mare. Tatal meu a murit de infarct la 62 de ani."
        ),
    },
    "Pneumonie": {
        "icon": "Pneumologie",
        "tema": "Sindrom infectios respirator",
        "text": (
            "Medic: Ce simptome aveti?\n"
            "Pacient: Tusesc de doua saptamani si scot un mucus galben-verzui.\n"
            "Medic: Altceva?\n"
            "Pacient: Am febra de cateva zile, vreo 38.5. Ma doare pieptul cand respir adanc.\n"
            "Medic: Dificultate la respirat?\n"
            "Pacient: Da, respir mai greu. Nu am scuipat sange.\n"
            "Medic: Cum a inceput?\n"
            "Pacient: Brusc, acum doua saptamani, dupa ce am stat in frig.\n"
            "Medic: Fumati?\n"
            "Pacient: Da, de 15 ani. Nu am alte boli cronice.\n"
            "Medic: Frisoane?\n"
            "Pacient: Da, am avut frisoane puternice la debut."
        ),
    },
    "Hipertiroidism": {
        "icon": "Endocrinologie",
        "tema": "Sindrom hipertiroidian",
        "text": (
            "Medic: Ce va deranjeaza?\n"
            "Pacient: De cateva luni am inima care bate repede tot timpul. Si am slabit fara sa vreau.\n"
            "Medic: Cat ati slabit?\n"
            "Pacient: Vreo 6-7 kilograme in 3 luni, desi manânc mai mult ca inainte.\n"
            "Medic: Altceva?\n"
            "Pacient: Transpir mult, ma simt agitata, nervoasa. Mainile imi tremura usor.\n"
            "Medic: Aveti probleme cu somnul?\n"
            "Pacient: Da, nu pot adormi, ma trezesc des.\n"
            "Medic: Scaunele?\n"
            "Pacient: Merg mai des la baie, am diaree usoara.\n"
            "Medic: Ochii?\n"
            "Pacient: Mi s-a spus ca am ochii mai proeminenti. Ii simt usturimi.\n"
            "Medic: Antecedente familiale?\n"
            "Pacient: Mama a avut probleme cu tiroida."
        ),
    },
    "Text liber": {
        "icon": "Alta specialitate",
        "tema": "Anamnexa proprie",
        "text": "",
    },
}


# ── Parsare transcript ────────────────────────────────────────────────────────
_SPEAKER_MAP = {
    "doctor":"doctor","dr":"doctor","medic":"doctor","medicul":"doctor",
    "patient":"patient","pacient":"patient","pacienta":"patient",
    "bolnav":"patient","bolnavul":"patient",
}

def _parse(text):
    turns, sp, parts = [], None, []
    def flush():
        nonlocal sp, parts
        if sp and parts:
            t = " ".join(p.strip() for p in parts if p.strip()).strip()
            if t:
                turns.append({"speaker":sp,"text":t})
        sp,parts = None,[]
    for line in text.splitlines():
        line = line.strip()
        if not line: continue
        m = re.match(
            r"^(Doctor|Dr|Medic|Medicul|Patient|Pacient|Pacienta|Bolnav|Bolnavul)\s*:\s*(.*)$",
            line, flags=re.IGNORECASE)
        if m:
            flush()
            sp = _SPEAKER_MAP.get(m.group(1).lower(),"unknown")
            if m.group(2).strip(): parts.append(m.group(2).strip())
        elif sp:
            parts.append(line)
    flush()
    return turns


# ── Extractie ─────────────────────────────────────────────────────────────────
_SYS = """Esti medic specialist in semiologie clinica romaneasca.
Analizezi EXCLUSIV replicile pacientului. Extragi entitati clinice.

REGULI:
1. Extragi: Sympt, Signe, RiskF.
2. Negatia: \"nu am cazut\" -> polarity=negat, code=0067.
3. Lateralitate, temporalitate, severitate obligatoriu.
4. Expresii implicite:
   \"scriu mai mic/inghesuit\" = NS DYSGRAPHIA [Signe 1399]
   \"par serios fara motiv\" = FACE EXPRESSION FIXED [Signe 0600]
   \"imi tarsesc piciorul/pasi mici\" = WALKING DIFFICULTY [Sympt 0067]
   \"ma simt intepenit/rigiditate\" = NS EXTRAPYRAMIDAL [Signe 0073]
   \"vorbesc mai incet\" = VOICE ABNORMALITY [Sympt 0330]
   \"tremor linistit/cedeaza la miscare\" = TREMOR REST [Sympt 0097]
   \"ma misc greu/lentoare\" = NS BRADYKINESIA [Signe 0494]
   \"nu simt mirosurile\" = SMELL LOST [Sympt 0242]
   \"inima bate repede\" = PALPITATIONS [Sympt 0044]
   \"ochi proeminenti/exoftalmie\" = EXOPHTHALMOS [Signe 0308]

CODURI TITUS:
Sympt: 0005=SWEATING,0006=DYSPNEA,0013=WEIGHT LOSS,0014=FATIGUE,0019=COUGH,
0022=FEVER,0023=HEADACHE,0042=PAIN CHEST,0044=PALPITATIONS,0067=WALKING DIFFICULTY,
0071=CHILLS,0095=NUMBNESS,0097=TREMOR REST,0120=CONSTIPATION,0147=DEPRESSION,
0160=NOCTURNAL SWEATING,0202=THIRST,0242=SMELL LOST,0330=VOICE ABNORMALITY,
0358=DIARRHEA CHRONIC,0498=INSOMNIA
Signe: 0073=NS EXTRAPYRAMIDAL,0494=NS BRADYKINESIA,0600=FACE EXPRESSION FIXED,
1399=NS DYSGRAPHIA,0308=EXOPHTHALMOS,0132=EDEMA
RiskF: 0014=SMOKING,0029=HYPERTENSION,0003=DIABETES,0037=ALCOHOL,0004=OBESITY

JSON array — un obiect per entitate:
{"expression":"textul exact","element_std":"termen RO","nature":"Sympt|Signe|RiskF",
"code_titus":"0067","polarity":"prezent|negat|incert","negation_cue":"",
"temporality":"acut|cronic|recurent|","temporal_cue":"","severity":"usor|moderat|sever|",
"laterality":"stanga|dreapta|bilateral|","body_region":"","aggravating":"",
"relieving":"","qualifier":"","confidence":0.95}

ZERO text in afara JSON array."""


def _extract(turns, api_key):
    all_ents = []
    for i, turn in enumerate(turns):
        if turn["speaker"] != "patient":
            continue
        ctx = "\n".join(
            f"{'Medic' if t['speaker']=='doctor' else 'Pacient'}: {t['text']}"
            for t in turns[max(0,i-4):i]
        )
        text = turn["text"]
        if api_key.strip():
            try:
                user = (f"[CONTEXT]\n{ctx}\n\n" if ctx else "") + f"[PACIENT]\n{text}"
                payload = json.dumps({
                    "model":"claude-sonnet-4-20250514","max_tokens":1500,
                    "system":_SYS,"messages":[{"role":"user","content":user}]
                }).encode()
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages", data=payload,
                    headers={"Content-Type":"application/json",
                             "anthropic-version":"2023-06-01",
                             "x-api-key":api_key.strip()})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = json.loads(resp.read())["content"][0]["text"].strip()
                    raw = raw.replace("```json","").replace("```","").strip()
                    ents = json.loads(raw)
                    if isinstance(ents, list):
                        all_ents.extend(ents)
                        continue
            except Exception:
                pass
        for e in _local_extract(text):
            all_ents.append({
                "expression":  e.get("expression",""),
                "element_std": e.get("name_ro",""),
                "nature":      e.get("nature","Sympt"),
                "code_titus":  str(e.get("code","")),
                "polarity":    "prezent",
                "negation_cue":"","temporality":"","temporal_cue":"",
                "severity":"","laterality":"","body_region":"",
                "aggravating":"","relieving":"","qualifier":"","confidence":0.9,
            })
    return all_ents


def _to_titus(entities):
    present, denied = [], []
    seen_p, seen_d = set(), set()
    for e in entities:
        try: code = int(str(e.get("code_titus","")).strip())
        except ValueError: continue
        if not code: continue
        nat = e.get("nature","Sympt")
        pol = e.get("polarity","prezent")
        key = (code, nat)
        if pol == "prezent" and key not in seen_p:
            seen_p.add(key); present.append((code,nat,150))
        elif pol == "negat" and key not in seen_d:
            seen_d.add(key); denied.append(key)
    return present, denied


# ── Pagina principala ─────────────────────────────────────────────────────────
def page_anam(name_catalog, sympt_catalog, signe_catalog, riskf_catalog, engine, lang="ro"):

    panel_header("Anamnexa ANAM", "Transcript liber -> extractie semiologica -> ranking TITUS")

    ss = st.session_state
    ss.setdefault("anam_step",     1)
    ss.setdefault("anam_text",     "")
    ss.setdefault("anam_tema",     "")
    ss.setdefault("anam_turns",    [])
    ss.setdefault("anam_entities", [])
    ss.setdefault("anam_ranking",  None)
    ss.setdefault("anam_api_key",  "")
    ss.setdefault("anam_choice",   "Parkinson")

    step = ss["anam_step"]

    # Progress
    labels = ["1 · Selectie anamnexa", "2 · Procesare ANAM", "3 · Diagnostic TITUS"]
    cols = st.columns(3)
    for i,(lbl,col) in enumerate(zip(labels,cols),1):
        done   = step > i
        active = step == i
        mark = "OK" if done else (">" if active else "-")
        col.markdown(f"**{mark} {lbl}**" if active else (f"{mark} {lbl}"))

    st.divider()

    # ════════════════════════════════════════════════
    # PAS 1 — SELECTIE
    # ════════════════════════════════════════════════
    if step == 1:
        col_list, col_text = st.columns([1, 3])

        with col_list:
            st.markdown("**Anamneze disponibile**")
            for key, val in ANAMNEZE.items():
                label = f"{key}\n{val['icon']}"
                if st.button(key, use_container_width=True,
                             type="primary" if key==ss["anam_choice"] else "secondary",
                             key=f"pick_{key}"):
                    ss["anam_choice"] = key
                    ss["anam_text"]   = val["text"]
                    ss["anam_tema"]   = val["tema"]
                    st.rerun()

            st.divider()
            new_key = st.text_input(
                "Cheie API Claude (optional)",
                value=ss["anam_api_key"],
                type="password",
                key="anam_api_input",
            )
            ss["anam_api_key"] = new_key

        with col_text:
            choice = ss["anam_choice"]
            st.markdown(f"**{choice}** — *{ANAMNEZE[choice]['tema']}*")
            # Textarea fara key pentru a evita conflictul session_state/widget
            edited = st.text_area(
                "Transcript (Medic: ... / Pacient: ...)",
                value=ss["anam_text"],
                height=400,
                placeholder="Medic: Ce va aduce?\nPacient: De cateva luni...",
            )
            ss["anam_text"] = edited

        st.divider()
        if st.button("Proceseaza anamneza", type="primary", use_container_width=True):
            text = ss["anam_text"].strip()
            if not text:
                st.warning("Selectati o anamnexa sau introduceti text.")
                st.stop()
            turns = _parse(text)
            n_p = sum(1 for t in turns if t["speaker"]=="patient")
            if n_p == 0:
                st.error("Nu s-au gasit replici 'Pacient:' in transcript.")
                st.stop()
            ss["anam_turns"] = turns
            ss["anam_step"]  = 2
            ss["anam_entities"] = []
            st.rerun()

    # ════════════════════════════════════════════════
    # PAS 2 — PROCESARE ANAM
    # ════════════════════════════════════════════════
    elif step == 2:
        turns = ss.get("anam_turns", [])
        n_p   = sum(1 for t in turns if t["speaker"]=="patient")
        st.markdown(f"**{ss['anam_tema']}**  |  {n_p} replici pacient")

        if not ss["anam_entities"]:
            with st.spinner("Extragere entitati semiologice..."):
                ents = _extract(turns, ss["anam_api_key"])
            ss["anam_entities"] = ents
            st.rerun()

        entities = ss["anam_entities"]
        prez = [e for e in entities if e.get("polarity","prezent")=="prezent"]
        neg  = [e for e in entities if e.get("polarity","prezent")=="negat"]

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Turns pacient",  n_p)
        c2.metric("Entitati total", len(entities))
        c3.metric("Prezente",       len(prez))
        c4.metric("Negate",         len(neg))
        st.divider()

        NAT_ICON = {"Sympt":"Sym","Signe":"Sgn","RiskF":"RF"}
        for e in entities:
            pol  = e.get("polarity","prezent")
            nat  = e.get("nature","Sympt")
            code = e.get("code_titus","")
            expr = e.get("expression","")
            std  = e.get("element_std","")
            tags = []
            for k,label in [("laterality",""),("temporal_cue",""),
                            ("severity",""),("qualifier",""),
                            ("aggravating","UP:"),("relieving","DN:")]:
                v = e.get(k,"")
                if v: tags.append(f"{label}{v}")
            neg_str = "  [NEGAT]" if pol=="negat" else ""
            line_md = '[' + NAT_ICON.get(nat,nat) + '] **' + std + '**  '
            line_md += '- *' + expr + '*' + neg_str
            if tags: line_md += '  |  ' + '  '.join(tags)
            st.markdown(line_md)

        st.divider()
        cb, cf = st.columns([1,2])
        with cb:
            if st.button("Inapoi"):
                ss["anam_step"] = 1; st.rerun()
        with cf:
            if st.button("Ruleaza TITUS", type="primary", use_container_width=True):
                present, denied = _to_titus(entities)
                if not present:
                    st.warning("Nicio entitate prezenta identificata."); st.stop()
                cr  = st.session_state.get("cr_threshold", 0.20)
                top = st.session_state.get("top_k", 10)
                with st.spinner("Calcul CR pentru 2989 boli TITUS..."):
                    result = engine.diagnose(present, top_n=top, cr_threshold=cr)
                ss["anam_ranking"] = result
                ss["anam_present"] = present
                ss["anam_denied"]  = denied
                ss["anam_step"]    = 3
                st.rerun()

    # ════════════════════════════════════════════════
    # PAS 3 — RANKING TITUS
    # ════════════════════════════════════════════════
    elif step == 3:
        result   = ss["anam_ranking"]
        entities = ss["anam_entities"]
        present  = ss.get("anam_present", [])

        ranking = result.get("ranking", [])
        waiting = result.get("waiting_room", [])

        st.markdown(f"**{ss['anam_tema']}**")
        st.markdown(
            f"**{len(ranking)}** diagnostice peste prag  |  "
            f"**{len(waiting)}** in waiting room  |  "
            f"Prag CR = {st.session_state.get('cr_threshold', 0.20):.2f}"
        )
        st.divider()

        if not ranking:
            st.info("Niciun diagnostic peste prag. Reduceti pragul CR din sidebar.")
        else:
            for i, dis in enumerate(ranking):
                cr      = dis.get("cr", 0)
                name    = dis.get("name_en", str(dis.get("code","")))
                matched = dis.get("matched", [])
                bar = ">" * int(cr*10) + "-" * (10-int(cr*10))
                with st.expander(f"#{i+1}  {name}   CR={cr:.3f}  [{bar}]",
                                 expanded=(i<3)):
                    ca,cb = st.columns(2)
                    with ca:
                        st.caption("Elemente concordante")
                        for m in matched: st.markdown(f"- `{m}`")
                    with cb:
                        st.caption("Cod TITUS")
                        st.code(str(dis.get("code","")))

        if waiting:
            with st.expander(f"Waiting room ({len(waiting)} boli)"):
                for w in waiting[:20]:
                    st.caption(f"{w.get('name_en','')}  CR={w.get('cr',0):.3f}")

        st.divider()
        with st.expander("Vector clinic (coduri TITUS)"):
            sympt = [f"`{c}`" for c,n,_ in present if n=="Sympt"]
            signe = [f"`{c}`" for c,n,_ in present if n=="Signe"]
            riskf = [f"`{c}`" for c,n,_ in present if n=="RiskF"]
            neg_c = [f"`{e['code_titus']}`" for e in entities
                     if e.get("polarity")=="negat" and e.get("code_titus")]
            ca,cb = st.columns(2)
            with ca:
                st.caption("Prezente")
                if sympt: st.markdown("Sympt: " + "  ".join(sympt))
                if signe: st.markdown("Signe: " + "  ".join(signe))
                if riskf: st.markdown("RiskF: " + "  ".join(riskf))
            with cb:
                st.caption("Absente (negate)")
                st.markdown("  ".join(neg_c) if neg_c else "niciuna")

        st.divider()
        cb1,cb2 = st.columns(2)
        with cb1:
            if st.button("Modifica entitatile"):
                ss["anam_step"] = 2; st.rerun()
        with cb2:
            if st.button("Anamnexa noua", type="primary", use_container_width=True):
                for k in ["anam_step","anam_text","anam_tema","anam_turns",
                          "anam_entities","anam_ranking","anam_present","anam_denied"]:
                    ss.pop(k, None)
                st.rerun()