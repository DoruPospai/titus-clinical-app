"""
consultation.py — TITUS
Modul Consultație: arbore de întrebări ghidat demografic.
"""
from __future__ import annotations
import json as _json
import os as _os
import datetime
import pandas as pd
import streamlit as st

from .titus_engine import get_engine, patient_map_to_titus, titus_to_patient_dict
from .ui_common import note, panel_header, kpi_card
from .ui_filters import apply_ui_filters
from .config import DEFAULT_TABEL2, DEFAULT_W_MATRIX, DEFAULT_RARITATE
from .question_tree import build_tree, TreeNavigator
from .i18n import t as _t

_TRANS_PATH = _os.path.join(_os.path.dirname(__file__), 'translations.json')
try:
    with open(_TRANS_PATH, 'r', encoding='utf-8') as _f:
        _TRANS = _json.load(_f)
except Exception:
    _TRANS = {}

def T(key, **kw):
    lang = st.session_state.get("lang", "ro")
    _BACK = {"ro":"Înapoi","fr":"Retour","en":"Back"}
    if key == "btn_back": return _BACK.get(lang,"Înapoi")
    return _t(key, lang, **kw)

def term_name(code, nature, lang="ro"):
    key = {"Sympt":"sympt","Signe":"signe","RiskF":"riskf"}.get(nature,"sympt")
    v = _TRANS.get(key,{}).get(str(code),{})
    return v.get(lang) or v.get("ro") or v.get("en", f"{nature}:{code}")

def rf_question_for(code, lang="ro"):
    q = _TRANS.get("rf_questions",{}).get(str(code),{})
    if q: return q.get(lang) or q.get("ro","")
    nm = term_name(code,"RiskF",lang)
    return {"ro":f"Are {nm.lower()}?","fr":f"A-t-il {nm.lower()}?",
            "en":f"Does the patient have {nm.lower()}?"}.get(lang,"")

def disease_display_name(code, name_en, lang="ro"):
    v = _TRANS.get("disease",{}).get(str(code),{})
    tr = v.get(lang) or v.get("ro")
    return tr if (tr and tr.lower()!=name_en.lower()) else name_en

def get_disease_desc(code, lang="ro"):
    v = _TRANS.get("disease_desc",{}).get(str(code),{})
    desc = v.get(lang) or v.get("ro") or ""
    return (desc[:150]+"...") if len(desc)>150 else desc

def _run_ranking(engine, elements, denied, profile, cr_threshold=0.35, top_n=10):
    if not elements:
        return {"ranking":[], "waiting_room":[], "waiting_room_rf":[]}
    denied_set = {(int(c_),n_) for c_,n_ in denied}
    # Prag redus in consultatie — profilul e incomplet față de un caz real
    effective_threshold = min(cr_threshold, 0.20)
    output = engine.diagnose(list(elements), top_n=top_n, cr_threshold=effective_threshold)
    if not isinstance(output, dict):
        return {"ranking":[], "waiting_room":[], "waiting_room_rf":[]}
    if denied_set:
        DENY = 0.25
        for r in output.get("ranking",[]):
            prof = engine.profiles.get(r["code"],{})
            cr = r["cr"]
            for key in denied_set:
                ds = prof.get(key,0)
                if ds >= 150:
                    cr = max(0.0, cr - DENY*(ds/150.0)*cr)
            r["cr"] = round(cr,4)
        output["ranking"].sort(key=lambda r:-r["cr"])
        for i,r in enumerate(output["ranking"],1): r["rank"]=i
    is_female   = profile.get("gender")=="Female"
    is_pregnant = is_female and str(profile.get("pregnancy","No"))=="Yes"
    def _ok(code):
        sx=engine.sex_constraint.get(code,"")
        pr=engine.preg_constraint.get(code,"")
        if sx=="W" and not is_female: return False
        if sx=="M" and is_female:     return False
        if pr=="P" and not is_pregnant: return False
        if pr=="S" and is_pregnant:     return False
        return True
    if hasattr(engine,"sex_constraint"):
        output["ranking"]=[r for r in output.get("ranking",[]) if _ok(r["code"])]
        for i,r in enumerate(output["ranking"],1): r["rank"]=i
    return output

def _mini_ranking(ranking, n=5):
    lang = st.session_state.get("lang","ro")
    if not ranking:
        st.caption("Niciun diagnostic cu scor suficient.")
        return
    for r in ranking[:n]:
        dname = disease_display_name(r["code"], r["name"], lang)
        col1, col2 = st.columns([4,1])
        with col1:
            st.markdown(f"**{r['rank']}. {dname}**")
            st.progress(min(r["cr"],1.0))
            desc = get_disease_desc(r["code"], lang)
            if desc:
                with st.expander("ℹ️", expanded=False):
                    st.caption(desc)
        with col2:
            st.markdown(f"**{r['cr']:.3f}**")

def _update_ranking(ss, profile):
    try:
        engine = get_engine(str(DEFAULT_TABEL2),str(DEFAULT_W_MATRIX),str(DEFAULT_RARITATE))
        output = _run_ranking(engine, ss["cons_elements"], ss["cons_denied"], profile)
        ss["cons_ranking"] = output.get("ranking",[])
        ss["cons_output"]  = output
    except Exception:
        pass

def _add_journal(ss):
    ranking = ss["cons_ranking"]
    n_conf = len([e for e in ss["cons_elements"] if e[1] in ("Sympt","Signe","RiskF")])
    ss["cons_journal"].append({
        "Pas"  : ss["cons_step_n"],
        "Top 1": ranking[0]["name"] if ranking else "—",
        "CR"   : round(ranking[0]["cr"],3) if ranking else 0,
        "Top 2": ranking[1]["name"] if len(ranking)>1 else "—",
        "Top 3": ranking[2]["name"] if len(ranking)>2 else "—",
        "Elem.": n_conf,
    })

def _calc_age_months(dob: datetime.date) -> int:
    today = datetime.date.today()
    months = (today.year - dob.year)*12 + (today.month - dob.month)
    if today.day < dob.day: months -= 1
    return max(0, months)

# ── RF ghidat ────────────────────────────────────────────────────────────────
RF_CODES_ORDERED = [
    3,29,4,14,37,45,50,31,1,75,9,794,
    47,64,448,139,349,124,309,163,274,440,383,
    5,13,38,182,314,330,12,210,211,265,540,532,
    155,35,62,11,201,129,97,132,195,229,230,
    54,40,489,267,546,266,185,
]


# ── Extragere semiologică din narațiune ───────────────────────────────────────

from med_diag.narrative_engine import extract as _narrative_extract

# ── STUB păstrat pentru compatibilitate (nu mai e folosit direct) ──────────
_LAY_DICT = [
    # Mers / locomoție
    ("mers greoi",          67,"Sympt","dificultate la mers","sigur"),
    ("merg greu",           67,"Sympt","dificultate la mers","sigur"),
    ("dificultate la mers", 67,"Sympt","dificultate la mers","sigur"),
    ("nu pot merge",        67,"Sympt","dificultate la mers","sigur"),
    ("difficulté à marcher",67,"Sympt","dificultate la mers","sigur"),
    ("walking difficulty",  67,"Sympt","dificultate la mers","sigur"),
    # Tremor
    ("tremură",             97,"Sympt","tremor","sigur"),
    ("tremor",              97,"Sympt","tremor","sigur"),
    ("tremuratură",         97,"Sympt","tremor","sigur"),
    ("tremurături",         97,"Sympt","tremor","sigur"),
    ("tremblement",         97,"Sympt","tremor","sigur"),
    ("trembling",           97,"Sympt","tremor","sigur"),
    # Rigiditate / sindrom extrapiramidal / bradykinezie
    # Signe 73 = NS EXTRAPYRAMIDAL DYSFUNCTION
    # Signe 494 = NS BRADYKINESIA (element cardinal Parkinson!)
    ("rigiditate",           73,"Signe","sindrom extrapiramidal","sigur"),
    ("rigid",                73,"Signe","sindrom extrapiramidal","sigur"),
    ("rigiditate musculară",  73,"Signe","sindrom extrapiramidal","sigur"),
    ("extrapiramidal",        73,"Signe","sindrom extrapiramidal","sigur"),
    ("mișcări sacadate",      73,"Signe","sindrom extrapiramidal","sigur"),
    # Bradikinezie — Signe 494 (toate variantele de exprimare a încetinelii)
    ("bradikinezie",         494,"Signe","bradikinezie","sigur"),
    ("bradykinésie",         494,"Signe","bradikinezie","sigur"),
    ("bradykinesia",         494,"Signe","bradikinezie","sigur"),
    ("încetineală",          494,"Signe","bradikinezie","sigur"),
    ("încetineal",           494,"Signe","bradikinezie","sigur"),
    ("lentoare",             494,"Signe","bradikinezie","sigur"),
    ("lent în mișcări",      494,"Signe","bradikinezie","sigur"),
    ("mișcări lente",        494,"Signe","bradikinezie","sigur"),
    ("mișcare înceată",      494,"Signe","bradikinezie","sigur"),
    ("mișcări îngreunate",   494,"Signe","bradikinezie","sigur"),
    ("mișcări încetinite",   494,"Signe","bradikinezie","sigur"),
    ("gesturi lente",        494,"Signe","bradikinezie","sigur"),
    ("mă misc greu",         494,"Signe","bradikinezie","sigur"),
    ("mă mișc greu",         494,"Signe","bradikinezie","sigur"),
    ("mișcările sunt grele", 494,"Signe","bradikinezie","sigur"),
    ("kinésie lente",        494,"Signe","bradikinezie","sigur"),
    ("mouvements lents",     494,"Signe","bradikinezie","sigur"),
    ("slowness of movement", 494,"Signe","bradikinezie","sigur"),
    # Mers dificil — variante expresive
    ("mers greoi",            67,"Sympt","dificultate la mers","sigur"),
    ("mersul greoi",          67,"Sympt","dificultate la mers","sigur"),
    ("mers obositor",         67,"Sympt","dificultate la mers","sigur"),
    ("mersul este obositor",  67,"Sympt","dificultate la mers","sigur"),
    ("mersul obositor",       67,"Sympt","dificultate la mers","sigur"),
    ("merg greu",             67,"Sympt","dificultate la mers","sigur"),
    ("dificultate la mers",   67,"Sympt","dificultate la mers","sigur"),
    ("nu pot merge",          67,"Sympt","dificultate la mers","sigur"),
    ("mers dificil",          67,"Sympt","dificultate la mers","sigur"),
    ("pași mici",             67,"Sympt","dificultate la mers","sigur"),
    ("pași mici și șovăielnici",67,"Sympt","dificultate la mers","sigur"),
    ("difficulté à marcher",  67,"Sympt","dificultate la mers","sigur"),
    ("walking difficulty",    67,"Sympt","dificultate la mers","sigur"),
    # Transpirații — variante fără "noaptea" explicit
    ("transpir",               5,"Sympt","transpirații excesive","sigur"),
    ("transpir mult",        160,"Sympt","transpirații nocturne","probabil"),
    ("transpir noaptea",     160,"Sympt","transpirații nocturne","sigur"),
    ("transpirații nocturne",160,"Sympt","transpirații nocturne","sigur"),
    ("noapte transpir",      160,"Sympt","transpirații nocturne","sigur"),
    ("noaptea transpir",     160,"Sympt","transpirații nocturne","sigur"),
    ("sueurs nocturnes",     160,"Sympt","transpirații nocturne","sigur"),
    ("tremor de repaus",      97,"Sympt","tremor de repaus","sigur"),
    ("hipotensiune ortostatică",237,"Signe","hipotensiune ortostatică","probabil"),
    ("amețeli la ridicare",  237,"Signe","hipotensiune ortostatică","probabil"),
    # Transpirații
    ("transpir",             5,"Sympt","transpirații excesive","sigur"),
    ("transpirație",         5,"Sympt","transpirații excesive","sigur"),
    ("transpirații",         5,"Sympt","transpirații excesive","sigur"),
    ("sudorație",            5,"Sympt","transpirații excesive","sigur"),
    ("transpir noaptea",   160,"Sympt","transpirații nocturne","sigur"),
    ("transpirații nocturne",160,"Sympt","transpirații nocturne","sigur"),
    ("noapte transpir",    160,"Sympt","transpirații nocturne","sigur"),
    ("sueurs nocturnes",   160,"Sympt","transpirații nocturne","sigur"),
    # Durere
    ("durere",              18,"Sympt","durere","sigur"),
    ("mă doare",            18,"Sympt","durere","sigur"),
    ("dureri",              18,"Sympt","durere","sigur"),
    ("douleur",             18,"Sympt","durere","sigur"),
    ("dolor",               18,"Sympt","durere","sigur"),
    # Durere specifică
    ("durere de cap",       23,"Sympt","cefalee","sigur"),
    ("cap mă doare",        23,"Sympt","cefalee","sigur"),
    ("migrenă",             23,"Sympt","cefalee/migrenă","sigur"),
    ("cefalee",             23,"Sympt","cefalee","sigur"),
    ("durere toracic",      42,"Sympt","durere toracică","sigur"),
    ("piept mă doare",      42,"Sympt","durere toracică","sigur"),
    ("durere abdominal",    18,"Sympt","durere abdominală","sigur"),
    ("stomac mă doare",     18,"Sympt","durere abdominală","sigur"),
    ("durere spate",        40,"Sympt","durere lombară","sigur"),
    ("spate mă doare",      40,"Sympt","durere lombară","sigur"),
    ("durere articular",    55,"Sympt","dureri articulare","sigur"),
    ("articulații dureroase",55,"Sympt","dureri articulare","sigur"),
    # Oboseală
    ("obosit",              14,"Sympt","oboseală","sigur"),
    ("oboseală",            14,"Sympt","oboseală","sigur"),
    ("epuizat",             14,"Sympt","oboseală","sigur"),
    ("fără energie",        14,"Sympt","oboseală","sigur"),
    ("slăbiciune",          14,"Sympt","slăbiciune/oboseală","sigur"),
    ("fatigué",             14,"Sympt","oboseală","sigur"),
    ("fatigue",             14,"Sympt","oboseală","sigur"),
    # Respirator
    ("respir greu",          6,"Sympt","dispnee","sigur"),
    ("greu de respirat",     6,"Sympt","dispnee","sigur"),
    ("lipsă de aer",         6,"Sympt","dispnee","sigur"),
    ("dispnee",              6,"Sympt","dispnee","sigur"),
    ("tuse",                19,"Sympt","tuse","sigur"),
    ("tusesc",              19,"Sympt","tuse","sigur"),
    ("toux",                19,"Sympt","tuse","sigur"),
    ("răgușit",             20,"Sympt","răgușeală","sigur"),
    ("voce răgușită",       20,"Sympt","răgușeală","sigur"),
    # Digestiv
    ("greață",              17,"Sympt","greață/vărsături","sigur"),
    ("vomit",               17,"Sympt","greață/vărsături","sigur"),
    ("vărsături",           17,"Sympt","greață/vărsături","sigur"),
    ("diaree",              10,"Sympt","diaree","sigur"),
    ("scaune moale",        10,"Sympt","diaree","sigur"),
    ("constipat",          120,"Sympt","constipație","sigur"),
    ("nu merge la baie",   120,"Sympt","constipație","sigur"),
    ("nu am poftă",         74,"Sympt","anorexie","sigur"),
    ("fără poftă",          74,"Sympt","anorexie","sigur"),
    ("slăbit",              13,"Sympt","scădere în greutate","sigur"),
    ("slăbire",             13,"Sympt","scădere în greutate","sigur"),
    ("am slăbit",           13,"Sympt","scădere în greutate","sigur"),
    ("pierdere în greutate",13,"Sympt","scădere în greutate","sigur"),
    ("perte de poids",      13,"Sympt","scădere în greutate","sigur"),
    # Urinar
    ("urinez des",          65,"Sympt","urinări frecvente","sigur"),
    ("urinări frecvente",   65,"Sympt","urinări frecvente","sigur"),
    ("sânge în urină",      38,"Sympt","hematurie","sigur"),
    ("urini roșii",         38,"Sympt","hematurie","sigur"),
    ("arsuri la urinat",    64,"Sympt","disurie","sigur"),
    ("durere la urinat",    64,"Sympt","disurie","sigur"),
    ("noaptea mă trezesc să urineze",110,"Sympt","nicturie","sigur"),
    ("nicturie",           110,"Sympt","nicturie","sigur"),
    # Neurologic
    ("amețeli",              1,"Sympt","amețeli/sincope","sigur"),
    ("amețit",               1,"Sympt","amețeli","sigur"),
    ("am leșinat",           1,"Sympt","sincope","sigur"),
    ("leșin",                1,"Sympt","sincope","sigur"),
    ("convulsii",           35,"Sympt","convulsii","sigur"),
    ("epilepsie",           35,"Sympt","convulsii/epilepsie","sigur"),
    ("amorțeală",           95,"Sympt","amorțeală","sigur"),
    ("furnicături",         95,"Sympt","furnicături/amorțeală","sigur"),
    ("confuz",              53,"Sympt","confuzie","sigur"),
    ("confuzie",            53,"Sympt","confuzie","sigur"),
    ("nu mai țin minte",    62,"Sympt","tulburare de memorie","sigur"),
    ("memorie slabă",       62,"Sympt","tulburare de memorie","sigur"),
    ("pierdere de memorie", 62,"Sympt","tulburare de memorie","sigur"),
    ("vorbesc greu",        68,"Sympt","dificultate de vorbire","sigur"),
    ("vorbire dificilă",    68,"Sympt","dificultate de vorbire","sigur"),
    ("vedere încețoșată",    2,"Sympt","vedere încetoșată","sigur"),
    ("văd prost",            2,"Sympt","vedere încetoșată","sigur"),
    ("vedere dublă",       124,"Sympt","diplopie","sigur"),
    ("tinitus",              3,"Sympt","tinitus","sigur"),
    ("țiuit în urechi",      3,"Sympt","tinitus","sigur"),
    # Febră
    ("am temperatură",      22,"Sympt","febră","sigur"),
    ("febră",               22,"Sympt","febră","sigur"),
    ("frisoane",            71,"Sympt","frisoane","sigur"),
    # Cardiac
    ("palpitații",          44,"Sympt","palpitații","sigur"),
    ("inimă bate repede",   44,"Sympt","palpitații/tahicardie","sigur"),
    ("inimă neregulată",    44,"Sympt","palpitații neregulate","sigur"),
    # Cutanat
    ("mâncărimi",           24,"Sympt","prurit","sigur"),
    ("mă mănâncă",          24,"Sympt","prurit","sigur"),
    ("prurit",              24,"Sympt","prurit","sigur"),
    ("erupție",             24,"Sympt","erupție cutanată","probabil"),
    ("pete pe piele",       24,"Sympt","leziuni cutanate","probabil"),
    # Psihic
    ("deprimat",           147,"Sympt","depresie","sigur"),
    ("depresie",           147,"Sympt","depresie","sigur"),
    ("anxios",              45,"Sympt","anxietate","sigur"),
    ("anxietate",           45,"Sympt","anxietate","sigur"),
    ("insomnie",           138,"Sympt","insomnie","sigur"),
    ("nu dorm",            138,"Sympt","insomnie","sigur"),
    # Ginecologic
    ("durere pelvian",     151,"Sympt","durere pelvină","sigur"),
    ("sângerare vaginală", 150,"Sympt","sângerare vaginală","sigur"),
    ("menstruație absentă",174,"Sympt","amenoree","sigur"),
    ("amenoree",           174,"Sympt","amenoree","sigur"),
]

# Reguli de combinare: prezența simultană a mai multor expresii → element superior
# Format: ([listă_de_fraze_obligatorii], code, nature, name_ro, certainty)
_COMBO_RULES = [
    # Rigiditate + lentoare/încetineală → bradikinezie (Signe 494, cardinal Parkinson)
    (["rigiditate", "încetineal"],      494, "Signe", "bradikinezie (rigiditate + lentoare mișcări)", "sigur"),
    (["rigiditate", "lentoare"],        494, "Signe", "bradikinezie (rigiditate + lentoare mișcări)", "sigur"),
    (["rigiditate", "mișcări lente"],   494, "Signe", "bradikinezie (rigiditate + lentoare mișcări)", "sigur"),
    (["rigiditate", "mă misc greu"],    494, "Signe", "bradikinezie (rigiditate + lentoare mișcări)", "sigur"),
    (["rigid",      "lentoare"],        494, "Signe", "bradikinezie (rigiditate + lentoare mișcări)", "sigur"),
    (["rigid",      "încetineal"],      494, "Signe", "bradikinezie (rigiditate + lentoare mișcări)", "sigur"),
    # Tremor + rigiditate → sindrom parkinsonian (Signe 73)
    (["tremur", "rigiditate"],           73, "Signe", "sindrom extrapiramidal (tremor + rigiditate)", "sigur"),
    (["tremor", "rigid"],                73, "Signe", "sindrom extrapiramidal (tremor + rigiditate)", "sigur"),
    # Durere + iradiere în picior → sciatalgie → Pain Back Low (40) + Numbness (95)
    (["durere", "picior", "iradiaz"],    95, "Sympt", "durere cu iradiere în membrul inferior", "probabil"),
    # Tuse + sânge → hemoptizie (83)
    (["tuse", "sânge"],                  83, "Sympt", "hemoptizie (tuse cu sânge)", "sigur"),
    (["tusesc", "sânge"],                83, "Sympt", "hemoptizie (tuse cu sânge)", "sigur"),
    # Dispnee + efort → dispnee de efort (47)
    (["respir greu", "efort"],           47, "Sympt", "dispnee de efort", "sigur"),
    (["lipsă de aer", "efort"],          47, "Sympt", "dispnee de efort", "sigur"),
    # Durere toracică + iradiere braț/maxilar → angină/infarct
    (["durere", "piept", "braț"],        42, "Sympt", "durere toracică cu iradiere (posibil anginos)", "probabil"),
    (["durere", "piept", "stâng"],       42, "Sympt", "durere toracică stângă", "sigur"),
    # Poliurie + sete → diabet zaharat semn
    (["urineze des", "sete"],           109, "Sympt", "poliurie cu polidipsie", "sigur"),
    (["urinez des", "sete"],            109, "Sympt", "poliurie cu polidipsie", "sigur"),
    # Confuzie + febră → encefalopatie febrilă
    (["confuz", "febr"],                 53, "Sympt", "confuzie în context febril", "sigur"),
    # Pierdere memorie + schimbări personalitate → demență
    (["memorie", "personalitat"],        62, "Sympt", "tulburare de memorie cu schimbări de personalitate", "sigur"),
]

def _apply_combo_rules(text_l: str, seen_codes: set) -> list[dict]:
    """Aplică regulile de combinare pe text."""
    results = []
    for phrases, code, nature, name_ro, cert in _COMBO_RULES:
        if code in seen_codes:
            continue
        if all(p in text_l for p in phrases):
            seen_codes.add(code)
            results.append({
                "code"    : code,
                "nature"  : nature,
                "name_ro" : name_ro,
                "name_en" : "",
                "certainty": cert,
            })
    return results

def _extract_from_narrative(text: str, lang: str = "ro",
                             api_key: str = "") -> list[dict]:
    """
    Extrage elementele semiologice dintr-o narațiune liberă.
    1. Claude API dacă există cheie
    2. Motor regex morfologic (narrative_engine.py)
    """
    import urllib.request, json as _j

    if api_key.strip():
        try:
            prompt = (
                f"Ești un medic care extrage simptome și semne clinice.\n"
                f"Narațiune: \"{text}\"\n\n"
                f"Returnează DOAR JSON array:\n"
                f'[{{"name_ro":"...","name_en":"...","nature":"Sympt|Signe",'
                f'"certainty":"sigur|probabil|posibil"}}]\n'
                f"Termeni medicali scurți. Dacă nimic → []."
            )
            payload = _j.dumps({
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 800,
                "messages": [{"role":"user","content": prompt}]
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages", data=payload,
                headers={"Content-Type":"application/json",
                         "anthropic-version":"2023-06-01",
                         "x-api-key": api_key.strip()}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = _j.loads(resp.read())
                raw  = data["content"][0]["text"].strip()
                raw  = raw.replace("```json","").replace("```","").strip()
                extracted = _j.loads(raw)
                cat_s = {v.get("ro","").lower(): (int(k),"Sympt",v.get("ro",""),v.get("en",""))
                         for k,v in _TRANS.get("sympt",{}).items() if v.get("ro","")}
                cat_g = {v.get("ro","").lower(): (int(k),"Signe",v.get("ro",""),v.get("en",""))
                         for k,v in _TRANS.get("signe",{}).items() if v.get("ro","")}
                results, seen_api = [], set()
                for item in extracted:
                    nm  = item.get("name_ro","").lower()
                    nat = item.get("nature","Sympt")
                    cat = cat_s if nat=="Sympt" else cat_g
                    match = cat.get(nm) or next(
                        (v for k,v in cat.items() if nm in k or k in nm), None)
                    if match and match[0] not in seen_api:
                        seen_api.add(match[0])
                        results.append({"code":match[0],"nature":match[1],
                                        "name_ro":match[2],"name_en":match[3],
                                        "certainty":item.get("certainty","probabil")})
                if results:
                    return results
        except Exception:
            pass

    raw = _narrative_extract(text)
    return [{"code": r["code"], "nature": r["nature"],
             "name_ro": r["name_ro"], "name_en": "",
             "certainty": r["certainty"]} for r in raw]

def page_consultation(name_catalog, sympt_catalog, signe_catalog, riskf_catalog):
    panel_header("Consultație TITUS",
                 "Motorul ghidează. Medicul confirmă. Diagnosticul evoluează pas cu pas.")
    ss = st.session_state
    ss.setdefault("cons_phase",    "profil")
    ss.setdefault("cons_profile",  {})
    ss.setdefault("cons_elements", [])
    ss.setdefault("cons_denied",   [])
    ss.setdefault("cons_navigator",None)
    ss.setdefault("cons_ranking",  [])
    ss.setdefault("cons_output",   None)
    ss.setdefault("cons_journal",  [])
    ss.setdefault("cons_step_n",   0)
    ss.setdefault("cons_rf_q_idx",  0)
    ss.setdefault("cons_prev_phase","screening")
    ss.setdefault("cons_narrative",  "")
    ss.setdefault("cons_narr_result",None)

    if st.button("🔄 " + T("cons_new"), key="cons_reset"):
        for k in [k for k in ss if k.startswith("cons_")]: del ss[k]
        st.rerun()
    st.divider()

    # ════════════════════════════════════════════════════════════════════
    # PROFIL
    # ════════════════════════════════════════════════════════════════════
    if ss["cons_phase"] == "profil":
        st.markdown("## 👤 Profilul pacientului")

        col1, col2 = st.columns(2)
        with col1:
            dob = st.date_input(
                "Data nașterii",
                value=datetime.date(1980,1,1),
                min_value=datetime.date(1900,1,1),
                max_value=datetime.date.today(),
                key="cons_dob",
                format="DD/MM/YYYY",
            )
            age_months = _calc_age_months(dob)
            age_years  = age_months // 12
            age_rem    = age_months % 12
            if age_years == 0:
                st.caption(f"Vârstă: **{age_months} luni**")
            elif age_rem == 0:
                st.caption(f"Vârstă: **{age_years} ani**")
            else:
                st.caption(f"Vârstă: **{age_years} ani și {age_rem} luni** ({age_months} luni)")
        with col2:
            sex_ro = st.selectbox(T("cons_sex"),
                                  [T("cons_male"), T("cons_female")], key="cons_sex")

        is_female = (sex_ro == T("cons_female"))
        pregnant = False; weeks = 0
        if is_female:
            col_p, col_w = st.columns(2)
            with col_p:
                p_ro = st.radio(T("cons_pregnant"),
                                [T("cons_no"), T("cons_yes")],
                                horizontal=True, key="cons_preg")
                pregnant = (p_ro == T("cons_yes"))
            with col_w:
                if pregnant:
                    weeks = st.number_input(T("cons_weeks"), 1, 42, 20, key="cons_weeks")

        if age_months == 0:
            st.warning("Vârsta calculată este 0 luni. Verifică data nașterii.")

        if st.button(T("cons_start"), type="primary",
                     use_container_width=True, key="cons_start_btn"):
            profile = {
                "gender"        : "Female" if is_female else "Male",
                "age_in_months" : age_months,
                "pregnancy"     : "Yes" if pregnant else "No",
                "weeks_pregnant": weeks if pregnant else None,
            }
            ss["cons_profile"]   = profile
            ss["cons_navigator"] = TreeNavigator(build_tree(), profile)
            ss["cons_phase"]     = "screening"
            ss["cons_prev_phase"]= "screening"
            st.rerun()

    # ════════════════════════════════════════════════════════════════════
    # ARBORE ÎNTREBĂRI
    # ════════════════════════════════════════════════════════════════════
    elif ss["cons_phase"] == "screening":
        lang    = st.session_state.get("lang","ro")
        profile = ss["cons_profile"]

        if ss["cons_navigator"] is None:
            ss["cons_navigator"] = TreeNavigator(build_tree(), profile)

        nav  = ss["cons_navigator"]
        node = nav.current()

        if node is None:
            ss["cons_phase"]    = "riskf"
            ss["cons_rf_q_idx"] = 0
            st.rerun()

        done, total = nav.progress()
        st.markdown("### 🩺 Evaluare clinică")
        st.progress(done/total, text=f"Întrebarea {done+1} / ~{total}")

        if ss["cons_ranking"]:
            with st.expander("📊 " + T("cons_ranking_now"), expanded=False):
                _mini_ranking(ss["cons_ranking"])

        question = node.q.get(lang) or node.q.get("ro","?")
        st.markdown(f"## {question}")

        col_da, col_nu, col_ns = st.columns(3)
        with col_da:
            if st.button(T("btn_da"), type="primary",
                         use_container_width=True, key=f"tree_da_{node.id}"):
                elems = nav.elements_to_add(node,"yes")
                for e in elems:
                    if e not in ss["cons_elements"]:
                        ss["cons_elements"].append(e)
                nav.answer("yes")
                _update_ranking(ss, profile)
                ss["cons_step_n"] += 1
                _add_journal(ss)
                st.rerun()
        with col_nu:
            if st.button(T("btn_nu"), use_container_width=True,
                         key=f"tree_nu_{node.id}"):
                if node.code and node.nature in ("Sympt","Signe"):
                    key_dn = (node.code, node.nature)
                    if key_dn not in ss["cons_denied"]:
                        ss["cons_denied"].append(key_dn)
                nav.answer("no")
                _update_ranking(ss, profile)
                st.rerun()
        with col_ns:
            if st.button(T("btn_ns"), use_container_width=True,
                         key=f"tree_ns_{node.id}"):
                nav.answer("skip")
                st.rerun()

        # Buton înapoi
        if nav.can_go_back():
            if st.button("← " + T("btn_back"), use_container_width=True,
                         key=f"tree_back_{node.id}"):
                elems_to_remove = nav.back()
                if elems_to_remove:
                    for e in elems_to_remove:
                        if e in ss["cons_elements"]:
                            ss["cons_elements"].remove(e)
                # Elimina si din denied ultimul element adaugat
                if ss["cons_denied"]:
                    ss["cons_denied"].pop()
                _update_ranking(ss, profile)
                st.rerun()

        st.divider()
        col_rf, col_result = st.columns(2)
        with col_rf:
            if st.button("⚠️ " + T("cons_to_rf").replace("⚠️ ",""),
                         use_container_width=True, key="tree_to_rf"):
                ss["cons_phase"]    = "riskf"
                ss["cons_rf_q_idx"] = 0
                st.rerun()
        with col_result:
            if st.button("📊 " + T("cons_to_result").replace("📊 ",""),
                         use_container_width=True, key="tree_to_result"):
                ss["cons_prev_phase"] = "screening"
                ss["cons_phase"] = "result"
                st.rerun()

    # ════════════════════════════════════════════════════════════════════
    # FACTORI DE RISC — GHIDAT
    # ════════════════════════════════════════════════════════════════════
    elif ss["cons_phase"] == "riskf":
        lang    = st.session_state.get("lang","ro")
        profile = ss["cons_profile"]
        cat_filt = apply_ui_filters(riskf_catalog, "RiskF", profile)

        st.markdown("### ⚠️ Factori de risc și antecedente")

        # Filtrează codurile RF vizibile în catalog
        valid_rf = []
        for code in RF_CODES_ORDERED:
            row = cat_filt[cat_filt["Code"] == code]
            if not row.empty:
                valid_rf.append(code)

        rf_idx = ss["cons_rf_q_idx"]
        if rf_idx >= len(valid_rf):
            # RF epuizat → narațiune liberă
            ss["cons_prev_phase"] = "riskf"
            ss["cons_phase"] = "narrative"
            st.rerun()

        code_rf  = valid_rf[rf_idx]
        question = rf_question_for(code_rf, lang)

        st.progress((rf_idx+1)/max(len(valid_rf),1),
                    text=f"Factorul {rf_idx+1} din {len(valid_rf)}")

        st.markdown(f"## {question}")

        col_da, col_nu, col_ns = st.columns(3)
        with col_da:
            if st.button(T("btn_da"), type="primary",
                         use_container_width=True, key=f"rfda_{code_rf}_{rf_idx}"):
                ss["cons_elements"].append((code_rf,"RiskF",150))
                ss["cons_rf_q_idx"] += 1
                _update_ranking(ss, profile)
                st.rerun()
        with col_nu:
            if st.button(T("btn_nu"), use_container_width=True,
                         key=f"rfnu_{code_rf}_{rf_idx}"):
                ss["cons_rf_q_idx"] += 1
                st.rerun()
        with col_ns:
            if st.button(T("btn_ns"), use_container_width=True,
                         key=f"rfns_{code_rf}_{rf_idx}"):
                ss["cons_rf_q_idx"] += 1
                st.rerun()

        # Buton înapoi RF
        if rf_idx > 0:
            if st.button("← " + T("btn_back"), use_container_width=True,
                         key=f"rfback_{rf_idx}"):
                ss["cons_rf_q_idx"] -= 1
                # Elimina RF-ul precedent din elemente dacă fusese confirmat
                prev_code = valid_rf[rf_idx - 1]
                ss["cons_elements"] = [
                    e for e in ss["cons_elements"]
                    if not (e[0]==prev_code and e[1]=="RiskF")
                ]
                _update_ranking(ss, profile)
                st.rerun()

        # RF confirmați
        rf_done = [(ce,nl,sc) for ce,nl,sc in ss["cons_elements"] if nl=="RiskF"]
        if rf_done:
            st.markdown(f"**Factori confirmați ({len(rf_done)}):**")
            for ce,_,_ in rf_done:
                st.markdown(f"• {term_name(ce,'RiskF',lang)}")

        if st.button("📝 Descriere liberă & diagnostic",
                     type="primary", use_container_width=True, key="rf_to_narr"):
            ss["cons_prev_phase"] = "riskf"
            ss["cons_phase"] = "narrative"
            st.rerun()
        if st.button("📊 " + T("cons_to_result").replace("📊 ",""),
                     use_container_width=True, key="rf_to_result"):
            ss["cons_prev_phase"] = "riskf"
            ss["cons_phase"] = "result"
            st.rerun()

    # ════════════════════════════════════════════════════════════════════
    # NARAȚIUNE LIBERĂ
    # ════════════════════════════════════════════════════════════════════
    elif ss["cons_phase"] == "narrative":
        lang = st.session_state.get("lang","ro")
        st.markdown("### 📝 Descriere liberă")
        note("Lăsați pacientul să descrie în cuvinte proprii ce simte. "
             "Motorul va extrage elementele clinice complementare.")

        txt = st.text_area(
            "Descrieți în câteva propoziții simptomele și evoluția lor:",
            value=ss.get("cons_narrative",""),
            height=160,
            placeholder=("De exemplu: «De trei zile am o durere surdă în piept care "
                         "iradiază spre umărul stâng. Noaptea transpir mult și tusesc "
                         "uneori cu secreții gălbui. Mă simt obosit și lipsit de aer "
                         "la cel mai mic efort.»"),
            key="cons_narr_input",
        )
        ss["cons_narrative"] = txt

        api_key = st.text_input(
            "Cheie API Claude (opțional — pentru extracție îmbunătățită):",
            value=ss.get("cons_api_key",""), type="password",
            key="narr_api_key_input",
            help="Fără cheie, extracția funcționează prin dicționar local."
        )
        ss["cons_api_key"] = api_key

        col_ext, col_skip = st.columns(2)
        with col_ext:
            if st.button("🔍 Extrage simptome din text", type="primary",
                         use_container_width=True, key="narr_extract"):
                if txt.strip():
                    with st.spinner("Analizare narațiune..."):
                        ss["cons_narr_result"] = _extract_from_narrative(
                            txt, lang, api_key=ss.get("cons_api_key","")
                        )
                    st.rerun()
                else:
                    st.warning("Introduceți mai întâi descrierea.")
        with col_skip:
            if st.button("📊 " + T("cons_to_result").replace("📊 ",""),
                         use_container_width=True, key="narr_skip"):
                ss["cons_prev_phase"] = "narrative"
                ss["cons_phase"] = "result"
                st.rerun()

        # Afișare rezultate extracție
        narr_res = ss.get("cons_narr_result")
        if narr_res is not None:
            if not narr_res:
                st.info("Nu s-au identificat elemente semiologice noi în text.")
            else:
                st.markdown(f"**{len(narr_res)} elemente identificate — confirmați ce se aplică:**")
                to_add = []
                for i, item in enumerate(narr_res):
                    cert_icon = {"sigur":"🟢","probabil":"🟡","posibil":"🔵"}.get(
                        item["certainty"],"🟡")
                    label = f"{cert_icon} **{item['name_ro']}**"
                    if item["name_en"] and item["name_en"].lower() != item["name_ro"].lower():
                        label += f" *({item['name_en']})*"
                    already = any(ce==item["code"] and nl==item["nature"]
                                  for ce,nl,_ in ss["cons_elements"])
                    checked = st.checkbox(label, value=not already,
                                          key=f"narr_ck_{item['code']}_{i}")
                    if checked and not already:
                        to_add.append((item["code"], item["nature"], 150))

                if st.button("✅ Adaugă elementele selectate și vezi diagnosticul",
                             type="primary", use_container_width=True, key="narr_confirm"):
                    for e in to_add:
                        if e not in ss["cons_elements"]:
                            ss["cons_elements"].append(e)
                    ss["cons_prev_phase"] = "narrative"
                    ss["cons_phase"] = "result"
                    st.rerun()

    # ════════════════════════════════════════════════════════════════════
    # REZULTAT FINAL
    # ════════════════════════════════════════════════════════════════════
    elif ss["cons_phase"] == "result":
        lang    = st.session_state.get("lang","ro")
        profile = ss["cons_profile"]
        st.markdown("## 📊 Diagnostic final")
        try:
            engine = get_engine(str(DEFAULT_TABEL2),str(DEFAULT_W_MATRIX),str(DEFAULT_RARITATE))
            output = _run_ranking(engine, ss["cons_elements"], ss["cons_denied"],
                                  profile, top_n=10)
            ss["cons_ranking"] = output.get("ranking",[])
            ss["cons_output"]  = output
        except Exception as ex:
            st.error(f"Eroare: {ex}"); return

        ranking = ss["cons_ranking"]
        wr_rf   = ss["cons_output"].get("waiting_room_rf",[]) if ss["cons_output"] else []
        p       = ss["cons_profile"]
        age_m   = p.get("age_in_months",0) or 0
        age_y   = age_m // 12
        age_r   = age_m % 12
        sex_ro  = "Feminin" if p.get("gender")=="Female" else "Masculin"
        preg    = (", gravidă" if lang=="ro" else
                   ", enceinte" if lang=="fr" else ", pregnant") \
                   if p.get("pregnancy")=="Yes" else ""
        if age_y == 0:
            age_str = f"{age_m} luni" if lang=="ro" else f"{age_m} mois" if lang=="fr" else f"{age_m} months"
        else:
            age_str = f"{age_y} ani" if lang=="ro" else f"{age_y} ans" if lang=="fr" else f"{age_y} years"

        n_da = len([e for e in ss["cons_elements"] if e[1] in ("Sympt","Signe")])
        n_nu = len(ss["cons_denied"])
        n_rf = len([e for e in ss["cons_elements"] if e[1]=="RiskF"])

        c1,c2,c3,c4 = st.columns(4)
        with c1: kpi_card(T("cons_patient_label"), f"{sex_ro}, {age_str}{preg}")
        with c2: kpi_card(T("cons_confirmed_label"), str(n_da))
        with c3: kpi_card(T("cons_denied_label"), str(n_nu))
        with c4: kpi_card("RF", str(n_rf))
        st.divider()

        if ranking:
            st.markdown("### " + T("cons_main_diag").replace("### ",""))
            _mini_ranking(ranking, n=10)
        else:
            st.warning(T("cons_no_diag"))

        if wr_rf:
            st.markdown(f"### ⏳ {T('cons_wr_rf').replace('### ⏳ ','')} ({len(wr_rf)})")
            for w in wr_rf[:5]:
                dn = disease_display_name(w['code'], w['name'], lang)
                st.markdown(f"- **{dn}** (CR={w['cr_semio']:.3f})")

        if ss["cons_journal"]:
            st.divider()
            st.markdown("### " + T("cons_journal_title").replace("### ",""))
            st.dataframe(pd.DataFrame(ss["cons_journal"]),
                         hide_index=True, use_container_width=True)

        prev = ss.get("cons_prev_phase", "screening")
        if st.button("← " + T("cons_back").replace("← ",""),
                     use_container_width=True, key="back_to_tree"):
            ss["cons_phase"] = prev
            st.rerun()
