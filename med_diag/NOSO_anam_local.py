# NOSO_anam_local.py
# Motor de conversație pentru anamneză — fără cheie API
#
# Logică:
#   1. narrative_engine extrage entitățile din răspunsul pacientului
#   2. Pe baza entităților detectate + sistem curent, alege întrebarea următoare
#   3. Parcurge sistematic: acuza → caracterizare → sisteme → antecedente → RF

import re
from .narrative_engine import extract as _extract

# ── Sisteme de parcurs în ordine ──────────────────────────────────────────────
_SYSTEMS = [
    "acuza",
    "durere",
    "cardio",
    "respirator",
    "digestiv",
    "neurologic",
    "urinar",
    "psihic",
    "cutanat",
    "antecedente_personale",
    "antecedente_familiale",
    "factori_risc",
    "final",
]

# ── Întrebări per sistem ───────────────────────────────────────────────────────
_Q = {
    "acuza": [
        "Care este motivul principal al consultației de astăzi?",
        "De cât timp aveți aceste simptome?",
        "Cum au apărut — brusc sau treptat?",
    ],
    "durere": [
        "Aveți dureri? Dacă da, unde exact?",
        "Cum descrieți durerea — ascuțită, surdă, arsură, presiune?",
        "Durerea iradiază undeva?",
        "Ce agravează sau ameliorează durerea?",
    ],
    "cardio": [
        "Aveți palpitații sau senzația că inima bate neregulat?",
        "Aveți dureri sau presiune în piept?",
        "Vă lipsește aerul la efort sau în repaus?",
        "Aveți glezne sau picioare umflate?",
    ],
    "respirator": [
        "Aveți tuse? Dacă da, cu sau fără expectorație?",
        "Aveți dificultăți la respirat?",
        "Ați observat șuierături la respirat?",
        "Ați tușit vreodată cu sânge?",
    ],
    "digestiv": [
        "Aveți greață sau vărsături?",
        "Cum sunt scaunele — normale, diareice, cu sânge?",
        "Aveți dureri abdominale?",
        "Ați observat îngălbenirea pielii sau a ochilor?",
    ],
    "neurologic": [
        "Aveți dureri de cap frecvente?",
        "Aveți amețeli sau tulburări de echilibru?",
        "Aveți amorțeli sau furnicături?",
        "Aveți tremurături sau dificultăți de mișcare?",
    ],
    "urinar": [
        "Urinați mai des decât de obicei, inclusiv noaptea?",
        "Aveți dureri sau arsuri la urinat?",
        "Ați observat sânge în urină?",
    ],
    "psihic": [
        "Vă simțiți deprimat sau anxios în ultimul timp?",
        "Aveți probleme cu somnul?",
        "Aveți dificultăți de concentrare sau de memorie?",
    ],
    "cutanat": [
        "Aveți erupții, mâncărimi sau modificări ale pielii?",
        "Ați observat pierdere de păr neobișnuită?",
    ],
    "antecedente_personale": [
        "Aveți boli cronice cunoscute — diabet, tensiune, boli de inimă, altele?",
        "Ați avut internări sau operații în trecut?",
        "Luați medicamente în mod regulat? Care anume?",
        "Aveți alergii cunoscute?",
    ],
    "antecedente_familiale": [
        "Există boli care se repetă în familie — cancer, boli de inimă, diabet, boli neurologice?",
    ],
    "factori_risc": [
        "Fumați sau ați fumat? De cât timp și câte țigarete pe zi?",
        "Consumați alcool? Cât de des?",
        "Ce ocupație aveți? Lucrați cu substanțe chimice sau în condiții speciale?",
        "Faceți activitate fizică regulată?",
    ],
    "final": [],
}

# ── Urmărire suplimentară pe entități detectate ───────────────────────────────
# Dacă detectăm codul X → punem întrebarea Y imediat
_FOLLOWUP = {
    97:  "Tremorul apare când stați liniștit sau când faceți mișcări?",      # TREMOR REST
    67:  "Ați căzut? Vă simțiți nesigur la mers?",                           # WALKING DIFFICULTY
    73:  "Simțiți rigiditate musculară, mai ales dimineața?",                  # EXTRAPYRAMIDAL
    494: "Gesturile dumneavoastră sunt mai lente decât înainte?",              # BRADYKINESIA
    42:  "Durerea toracică iradiază în brațul stâng sau în maxilar?",          # CHEST PAIN
    6:   "Lipsa de aer apare la efort sau și în repaus?",                      # DYSPNEA
    22:  "De cât timp aveți febra? A depășit 38.5 grade?",                     # FEVER
    19:  "Tusea este productivă? Ce culoare are expectorația?",                # COUGH
    18:  "Durerea abdominală este continuă sau în crize? Iradiază undeva?",    # ABD PAIN
    109: "Urinați cantități mari? Aveți și sete intensă?",                     # POLYURIA
    95:  "Amorțeala este la mâini, picioare sau altundeva? Când apare?",       # NUMBNESS
    147: "De cât timp vă simțiți deprimat? Afectează activitatea zilnică?",   # DEPRESSION
    44:  "Palpitațiile apar brusc? Inima bate rapid sau neregulat?",           # PALPITATIONS
    83:  "Ați tușit cu sânge de mai multe ori? Câtă cantitate?",               # HEMOPTYSIS
    38:  "Urina roșie apare constant sau episodic? Aveți și dureri?",          # HEMATURIA
    13:  "Cât ați slăbit și în ce perioadă? Ați modificat dieta?",             # WEIGHT LOSS
}


class LocalAnamEngine:
    """Motor local de conversație pentru anamneză."""

    def __init__(self):
        self.entities:    list[dict] = []
        self.system_idx:  int        = 0
        self.q_idx:       int        = 0
        self.asked:       set        = set()
        self.followup_q:  list[str]  = []
        self.done:        bool       = False

    def process(self, patient_text: str) -> tuple[str, list[dict]]:
        """
        Procesează un răspuns al pacientului.
        Returnează (next_question, new_entities).
        """
        # Extrage entități
        new_ents = _extract(patient_text)
        self.entities.extend(new_ents)

        # Adaugă follow-up specifice pentru entitățile noi
        for e in new_ents:
            code = int(e.get("code", 0))
            if code in _FOLLOWUP:
                q = _FOLLOWUP[code]
                if q not in self.asked:
                    self.followup_q.append(q)

        next_q = self._next_question()
        return next_q, new_ents

    def first_question(self) -> str:
        return _Q["acuza"][0]

    def _next_question(self) -> str:
        # Prioritate: follow-up specific > întrebare curentă din sistem
        while self.followup_q:
            q = self.followup_q.pop(0)
            if q not in self.asked:
                self.asked.add(q)
                return q

        # Avansează în sistemul curent
        while self.system_idx < len(_SYSTEMS):
            system = _SYSTEMS[self.system_idx]

            if system == "final":
                self.done = True
                return ""

            questions = _Q.get(system, [])
            if self.q_idx < len(questions):
                q = questions[self.q_idx]
                self.q_idx += 1
                if q not in self.asked:
                    self.asked.add(q)
                    return q
            else:
                # Trece la sistemul următor
                self.system_idx += 1
                self.q_idx = 0

        self.done = True
        return ""

    def is_done(self) -> bool:
        return self.done

    def summary(self) -> str:
        """Rezumat text al entităților colectate."""
        prez = [e for e in self.entities if e.get("polarity","prezent") == "prezent"]
        neg  = [e for e in self.entities if e.get("polarity","prezent") == "negat"]
        parts = [f"{e.get('name_ro','')} [{e.get('nature','')} {e.get('code','')}]"
                 for e in prez]
        s = f"{len(prez)} entități prezente"
        if neg:
            s += f", {len(neg)} negate"
        if parts:
            s += ": " + ", ".join(parts[:8])
        return s
