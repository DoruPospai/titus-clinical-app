"""
question_tree.py — TITUS
Arborele de întrebări pentru modulul Consultație.
Structura: fiecare nod are întrebare, cod simptom asociat,
filtre demografice, și copii pentru Da/Nu.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

# ── Structura unui nod ────────────────────────────────────────────────────────

@dataclass
class QNode:
    id:        str
    q:         dict                       # {ro, fr, en}
    code:      Optional[int]  = None     # codul simptomului/semnului adăugat dacă Da
    nature:    str            = "Sympt"  # Sympt | Signe | RiskF
    score:     int            = 150
    sex:       Optional[str]  = None     # None=orice | "F"=femei | "M"=bărbați
    min_age:   Optional[int]  = None     # vârstă minimă în luni
    max_age:   Optional[int]  = None     # vârstă maximă în luni
    pregnant:  Optional[bool] = None     # None=orice | True=gravide | False=negravide
    yes:       list           = field(default_factory=list)  # noduri copil dacă Da
    no:        list           = field(default_factory=list)  # noduri copil dacă Nu (rar)

    def visible(self, profile: dict) -> bool:
        """Verifică dacă nodul e vizibil pentru profilul pacientului."""
        sex = profile.get("gender", "")
        age = int(profile.get("age_in_months", 0) or 0)
        is_pregnant = (sex == "Female" and
                       str(profile.get("pregnancy", "No")) == "Yes")
        if self.sex == "F" and sex != "Female":
            return False
        if self.sex == "M" and sex != "Male":
            return False
        if self.min_age is not None and age < self.min_age:
            return False
        if self.max_age is not None and age > self.max_age:
            return False
        if self.pregnant is True and not is_pregnant:
            return False
        if self.pregnant is False and is_pregnant:
            return False
        return True


# ── Arborele principal ────────────────────────────────────────────────────────

def build_tree() -> list[QNode]:
    """Construiește și returnează lista de noduri rădăcină."""

    # ── DEBUT ─────────────────────────────────────────────────────────────────
    debut_acut = QNode(
        id="debut_acut", code=153, nature="Sympt",
        q={"ro":"Simptomele au apărut brusc, în mai puțin de 3 zile?",
           "fr":"Les symptômes sont-ils apparus brusquement, en moins de 3 jours?",
           "en":"Did symptoms appear suddenly, within less than 3 days?"},
    )
    debut_insidios = QNode(
        id="debut_insidios", code=51, nature="Sympt",
        q={"ro":"Simptomele s-au instalat treptat, în mai mult de 3 zile?",
           "fr":"Les symptômes se sont-ils installés progressivement, en plus de 3 jours?",
           "en":"Did symptoms develop gradually over more than 3 days?"},
    )

    # ── FEBRĂ ─────────────────────────────────────────────────────────────────
    febra_inalta = QNode(
        id="febra_inalta",
        q={"ro":"Temperatura depășește 38.5°C?",
           "fr":"La température dépasse-t-elle 38,5°C?",
           "en":"Is the temperature above 38.5°C?"},
    )
    febra_frisoane = QNode(
        id="febra_frisoane", code=71, nature="Sympt",
        q={"ro":"Febra este însoțită de frisoane?",
           "fr":"La fièvre est-elle accompagnée de frissons?",
           "en":"Is the fever accompanied by chills?"},
    )
    febra_nocturna = QNode(
        id="febra_nocturna",
        q={"ro":"Febra apare mai ales noaptea (transpirații nocturne)?",
           "fr":"La fièvre survient-elle surtout la nuit (sueurs nocturnes)?",
           "en":"Does the fever occur mainly at night with night sweats?"},
    )
    febra_periodica = QNode(
        id="febra_periodica", code=84, nature="Sympt",
        q={"ro":"Febra apare în crize periodice, cu intervale fără febră?",
           "fr":"La fièvre survient-elle par épisodes périodiques avec intervalles libres?",
           "en":"Does the fever occur in periodic episodes with fever-free intervals?"},
    )
    febra_inalta.yes = [febra_frisoane, febra_nocturna, febra_periodica]
    febra = QNode(
        id="febra", code=22, nature="Sympt",
        q={"ro":"Are febră (temperatura peste 37.5°C)?",
           "fr":"A-t-il de la fièvre (température supérieure à 37,5°C)?",
           "en":"Does the patient have fever (temperature above 37.5°C)?"},
        yes=[febra_inalta, febra_frisoane, febra_nocturna, febra_periodica],
    )

    # ── DURERE ────────────────────────────────────────────────────────────────
    # Durere cap
    cefalee_brusca = QNode(
        id="cefalee_brusca",
        q={"ro":"Durerea de cap a apărut brusc, ca o lovitură de tunet?",
           "fr":"La céphalée est-elle apparue brutalement, comme un coup de tonnerre?",
           "en":"Did the headache appear suddenly, like a thunderclap?"},
    )
    cefalee_greata = QNode(
        id="cefalee_greata", code=17, nature="Sympt",
        q={"ro":"Durerea de cap este însoțită de greață sau vărsături?",
           "fr":"La céphalée est-elle accompagnée de nausées ou vomissements?",
           "en":"Is the headache accompanied by nausea or vomiting?"},
    )
    cefalee_vedere = QNode(
        id="cefalee_vedere", code=2, nature="Sympt",
        q={"ro":"Durerea de cap este însoțită de tulburări de vedere?",
           "fr":"La céphalée est-elle accompagnée de troubles visuels?",
           "en":"Is the headache accompanied by visual disturbances?"},
    )
    cefalee_lumina = QNode(
        id="cefalee_lumina", code=102, nature="Sympt",
        q={"ro":"Are sensibilitate la lumină sau la zgomot?",
           "fr":"A-t-il une sensibilité à la lumière ou au bruit?",
           "en":"Does the patient have sensitivity to light or noise?"},
    )
    durere_cap = QNode(
        id="durere_cap", code=23, nature="Sympt",
        q={"ro":"Are dureri de cap?",
           "fr":"A-t-il mal à la tête?",
           "en":"Does the patient have headache?"},
        yes=[cefalee_brusca, cefalee_greata, cefalee_vedere, cefalee_lumina],
    )

    # Durere toracică
    durere_tor_stanga = QNode(
        id="durere_tor_stanga", code=42, nature="Sympt",
        q={"ro":"Durerea toracică este pe stânga sau difuză?",
           "fr":"La douleur thoracique est-elle à gauche ou diffuse?",
           "en":"Is the chest pain on the left side or diffuse?"},
    )
    durere_tor_efort = QNode(
        id="durere_tor_efort", code=47, nature="Sympt",
        q={"ro":"Durerea apare sau se agravează la efort fizic?",
           "fr":"La douleur apparaît-elle ou s'aggrave-t-elle à l'effort?",
           "en":"Does the pain appear or worsen with exertion?"},
    )
    durere_tor_respiratie = QNode(
        id="durere_tor_respiratie", code=177, nature="Sympt",
        q={"ro":"Durerea se agravează la respirație, tuse sau mișcare?",
           "fr":"La douleur s'aggrave-t-elle à la respiration, la toux ou les mouvements?",
           "en":"Does the pain worsen with breathing, coughing, or movement?"},
    )
    durere_tor_iradiere = QNode(
        id="durere_tor_iradiere",
        q={"ro":"Durerea iradiază în braț stâng, maxilar sau spate?",
           "fr":"La douleur irradie-t-elle vers le bras gauche, la mâchoire ou le dos?",
           "en":"Does the pain radiate to the left arm, jaw, or back?"},
    )
    durere_toracica = QNode(
        id="durere_toracica",
        q={"ro":"Are dureri în piept?",
           "fr":"A-t-il des douleurs dans la poitrine?",
           "en":"Does the patient have chest pain?"},
        yes=[durere_tor_stanga, durere_tor_efort, durere_tor_respiratie, durere_tor_iradiere],
    )

    # Durere abdominală
    durere_abd_dupa_masa = QNode(
        id="durere_abd_dupa_masa", code=268, nature="Sympt",
        q={"ro":"Durerea abdominală apare sau se agravează după masă?",
           "fr":"La douleur abdominale apparaît-elle ou s'aggrave-t-elle après les repas?",
           "en":"Does the abdominal pain appear or worsen after eating?"},
    )
    durere_abd_varsaturi = QNode(
        id="durere_abd_varsaturi", code=17, nature="Sympt",
        q={"ro":"Durerea este însoțită de greață sau vărsături?",
           "fr":"La douleur est-elle accompagnée de nausées ou de vomissements?",
           "en":"Is the pain accompanied by nausea or vomiting?"},
    )
    durere_abd_icter = QNode(
        id="durere_abd_icter",
        q={"ro":"Are îngălbenirea pielii sau a ochilor (icter)?",
           "fr":"A-t-il un jaunissement de la peau ou des yeux (ictère)?",
           "en":"Does the patient have yellowing of skin or eyes (jaundice)?"},
    )
    durere_abd_hipocondru = QNode(
        id="durere_abd_hipocondru", code=388, nature="Sympt",
        q={"ro":"Durerea este localizată sub coaste pe dreapta (hipocondru drept)?",
           "fr":"La douleur est-elle localisée sous les côtes à droite (hypocondre droit)?",
           "en":"Is the pain localized in the right upper quadrant?"},
    )
    durere_abd_epigastru = QNode(
        id="durere_abd_epigastru", code=394, nature="Sympt",
        q={"ro":"Durerea este în epigastru (zona centrală superioară)?",
           "fr":"La douleur est-elle en épigastre (région centrale supérieure)?",
           "en":"Is the pain in the epigastrium (upper central area)?"},
    )
    durere_abdominala = QNode(
        id="durere_abdominala", code=18, nature="Sympt",
        q={"ro":"Are dureri abdominale?",
           "fr":"A-t-il des douleurs abdominales?",
           "en":"Does the patient have abdominal pain?"},
        yes=[durere_abd_dupa_masa, durere_abd_varsaturi, durere_abd_icter,
             durere_abd_hipocondru, durere_abd_epigastru],
    )

    # Durere articulară
    art_multiple = QNode(
        id="art_multiple", code=55, nature="Sympt",
        q={"ro":"Durerea afectează mai multe articulații simultan?",
           "fr":"La douleur affecte-t-elle plusieurs articulations simultanément?",
           "en":"Does the pain affect multiple joints simultaneously?"},
    )
    art_redoare = QNode(
        id="art_redoare",
        q={"ro":"Există redoare matinală (rigiditate dimineața care cedează în peste 30 minute)?",
           "fr":"Y a-t-il une raideur matinale (rigidité le matin pendant plus de 30 minutes)?",
           "en":"Is there morning stiffness lasting more than 30 minutes?"},
    )
    art_umflate = QNode(
        id="art_umflate",
        q={"ro":"Articulațiile sunt vizibil umflate sau calde la palpare?",
           "fr":"Les articulations sont-elles visiblement gonflées ou chaudes à la palpation?",
           "en":"Are the joints visibly swollen or warm to touch?"},
    )
    durere_articulara = QNode(
        id="durere_articulara",
        q={"ro":"Are dureri articulare?",
           "fr":"A-t-il des douleurs articulaires?",
           "en":"Does the patient have joint pain?"},
        yes=[art_multiple, art_redoare, art_umflate],
    )

    # Durere lombară
    durere_lombar_iradiere = QNode(
        id="durere_lombar_iradiere",
        q={"ro":"Durerea iradiază pe picior, până sub genunchi (sciatalgie)?",
           "fr":"La douleur irradie-t-elle dans la jambe, jusqu'en dessous du genou (sciatalgie)?",
           "en":"Does the pain radiate down the leg below the knee (sciatica)?"},
    )
    durere_lombar_miscare = QNode(
        id="durere_lombar_miscare", code=177, nature="Sympt",
        q={"ro":"Durerea se agravează la mișcare sau efort?",
           "fr":"La douleur s'aggrave-t-elle aux mouvements ou à l'effort?",
           "en":"Does the pain worsen with movement or exertion?"},
    )
    durere_lombar = QNode(
        id="durere_lombar", code=40, nature="Sympt",
        q={"ro":"Are dureri în zona lombară (spate jos)?",
           "fr":"A-t-il des douleurs dans le bas du dos (région lombaire)?",
           "en":"Does the patient have lower back pain?"},
        yes=[durere_lombar_iradiere, durere_lombar_miscare],
    )

    # ── RESPIRATOR ────────────────────────────────────────────────────────────
    dispnee_efort = QNode(
        id="dispnee_efort", code=47, nature="Sympt",
        q={"ro":"Dificultatea de respirație apare la efort fizic?",
           "fr":"La difficulté à respirer survient-elle à l'effort physique?",
           "en":"Does the breathing difficulty occur with physical exertion?"},
    )
    dispnee_repaus = QNode(
        id="dispnee_repaus",
        q={"ro":"Are dificultăți de respirație și în repaus?",
           "fr":"A-t-il des difficultés à respirer même au repos?",
           "en":"Does the patient have breathing difficulty even at rest?"},
    )
    dispnee_noapte = QNode(
        id="dispnee_noapte",
        q={"ro":"Se trezește noaptea cu senzație de sufocare?",
           "fr":"Se réveille-t-il la nuit avec une sensation d'étouffement?",
           "en":"Does the patient wake up at night with a sensation of suffocation?"},
    )
    dispnee = QNode(
        id="dispnee", code=6, nature="Sympt",
        q={"ro":"Are dificultăți de respirație sau senzație de lipsă de aer?",
           "fr":"A-t-il des difficultés à respirer ou une sensation de manque d'air?",
           "en":"Does the patient have difficulty breathing or a feeling of breathlessness?"},
        yes=[dispnee_efort, dispnee_repaus, dispnee_noapte],
    )
    tuse_sange = QNode(
        id="tuse_sange", code=83, nature="Sympt",
        q={"ro":"Tusea este însoțită de sânge (hemoptizie)?",
           "fr":"La toux est-elle accompagnée de sang (hémoptysie)?",
           "en":"Is the cough accompanied by blood (hemoptysis)?"},
    )
    tuse_expectoratie = QNode(
        id="tuse_expectoratie", code=82, nature="Sympt",
        q={"ro":"Tusea produce secreții (expectorație, mucus)?",
           "fr":"La toux produit-elle des sécrétions (expectoration, mucus)?",
           "en":"Does the cough produce sputum or mucus?"},
    )
    tuse_nocturna = QNode(
        id="tuse_nocturna", code=160, nature="Sympt",
        q={"ro":"Tusea este mai intensă noaptea?",
           "fr":"La toux est-elle plus intense la nuit?",
           "en":"Is the cough more intense at night?"},
    )
    tuse = QNode(
        id="tuse", code=19, nature="Sympt",
        q={"ro":"Are tuse?",
           "fr":"A-t-il de la toux?",
           "en":"Does the patient have a cough?"},
        yes=[tuse_sange, tuse_expectoratie, tuse_nocturna],
    )
    palpitatii_neregulate = QNode(
        id="palpitatii_neregulate",
        q={"ro":"Bătăile inimii sunt neregulate, sar sau se opresc?",
           "fr":"Les battements du cœur sont-ils irréguliers, sautent-ils ou s'arrêtent-ils?",
           "en":"Are the heartbeats irregular, skipping, or pausing?"},
    )
    palpitatii_sincopa = QNode(
        id="palpitatii_sincopa", code=1, nature="Sympt",
        q={"ro":"Palpitațiile sunt însoțite de leșin sau amețeală severă?",
           "fr":"Les palpitations sont-elles accompagnées de malaises ou vertiges sévères?",
           "en":"Are the palpitations accompanied by fainting or severe dizziness?"},
    )
    palpitatii = QNode(
        id="palpitatii", code=44, nature="Sympt",
        q={"ro":"Simte palpitații sau bătăi neregulate ale inimii?",
           "fr":"Ressent-il des palpitations ou des battements irréguliers du cœur?",
           "en":"Does the patient feel palpitations or irregular heartbeats?"},
        yes=[palpitatii_neregulate, palpitatii_sincopa],
    )

    # ── NEUROLOGIC ────────────────────────────────────────────────────────────
    conv_febra = QNode(
        id="conv_febra",
        q={"ro":"Convulsiile apar în context febril?",
           "fr":"Les convulsions surviennent-elles dans un contexte fébrile?",
           "en":"Do the seizures occur in a febrile context?"},
    )
    conv_pierdere = QNode(
        id="conv_pierdere",
        q={"ro":"Sunt însoțite de pierderea cunoștinței?",
           "fr":"Sont-elles accompagnées d'une perte de connaissance?",
           "en":"Are they accompanied by loss of consciousness?"},
    )
    convulsii = QNode(
        id="convulsii", code=35, nature="Sympt",
        q={"ro":"A avut convulsii sau crize de epilepsie?",
           "fr":"A-t-il eu des convulsions ou des crises d'épilepsie?",
           "en":"Has the patient had seizures or epileptic episodes?"},
        yes=[conv_febra, conv_pierdere],
    )
    amorteli_generalizate = QNode(
        id="amorteli_generalizate",
        q={"ro":"Amorțeala afectează mai multe zone simultan?",
           "fr":"L'engourdissement affecte-t-il plusieurs zones simultanément?",
           "en":"Does the numbness affect multiple areas simultaneously?"},
    )
    amorteli_membre = QNode(
        id="amorteli_membre",
        q={"ro":"Amorțeala este predominantă la mâini și picioare (mănuși-șosete)?",
           "fr":"L'engourdissement prédomine-t-il aux mains et aux pieds (en gants et chaussettes)?",
           "en":"Is the numbness predominantly in hands and feet (glove-stocking pattern)?"},
    )
    amorteli = QNode(
        id="amorteli", code=95, nature="Sympt",
        q={"ro":"Are senzații de amorțeală sau furnicături?",
           "fr":"A-t-il des sensations d'engourdissement ou de fourmillements?",
           "en":"Does the patient have numbness or tingling sensations?"},
        yes=[amorteli_generalizate, amorteli_membre],
    )
    confuzie_brusca = QNode(
        id="confuzie_brusca",
        q={"ro":"Confuzia a apărut brusc (în ore)?",
           "fr":"La confusion est-elle apparue brutalement (en quelques heures)?",
           "en":"Did the confusion appear suddenly (within hours)?"},
    )
    confuzie_progresiva = QNode(
        id="confuzie_progresiva",
        q={"ro":"Confuzia s-a instalat progresiv, în săptămâni sau luni?",
           "fr":"La confusion s'est-elle installée progressivement, en semaines ou mois?",
           "en":"Did the confusion develop progressively over weeks or months?"},
    )
    confuzie = QNode(
        id="confuzie", code=53, nature="Sympt",
        q={"ro":"Prezintă stări de confuzie sau dezorientare?",
           "fr":"Présente-t-il des états confusionnels ou de la désorientation?",
           "en":"Does the patient show confusion or disorientation?"},
        yes=[confuzie_brusca, confuzie_progresiva],
    )
    mers_dificil_echilibru = QNode(
        id="mers_dificil_echilibru",
        q={"ro":"Are probleme de echilibru sau se clatină la mers?",
           "fr":"A-t-il des problèmes d'équilibre ou trébuche-t-il en marchant?",
           "en":"Does the patient have balance problems or stumble while walking?"},
    )
    mers_dificil_slabiciune = QNode(
        id="mers_dificil_slabiciune", code=66, nature="Sympt",
        q={"ro":"Dificultatea de mers este din cauza slăbiciunii musculare?",
           "fr":"La difficulté à marcher est-elle due à une faiblesse musculaire?",
           "en":"Is the difficulty walking due to muscle weakness?"},
    )
    mers_dificil = QNode(
        id="mers_dificil", code=67, nature="Sympt",
        q={"ro":"Are dificultăți la mers?",
           "fr":"A-t-il des difficultăți à marcher?",
           "en":"Does the patient have difficulty walking?"},
        yes=[mers_dificil_echilibru, mers_dificil_slabiciune],
    )
    vedere_dubla = QNode(
        id="vedere_dubla", code=124, nature="Sympt",
        q={"ro":"Vede dublu?",
           "fr":"Voit-il en double?",
           "en":"Does the patient see double?"},
    )
    vedere_ingustata = QNode(
        id="vedere_ingustata", code=155, nature="Sympt",
        q={"ro":"Câmpul vizual este îngustat (vede doar în față)?",
           "fr":"Le champ visuel est-il rétréci (ne voit-il que droit devant)?",
           "en":"Is the visual field narrowed?"},
    )
    vedere_incetosata = QNode(
        id="vedere_incetosata", code=2, nature="Sympt",
        q={"ro":"Vederea este încetoșată sau neclară?",
           "fr":"La vision est-elle trouble ou floue?",
           "en":"Is the patient's vision blurred or unclear?"},
        yes=[vedere_dubla, vedere_ingustata],
    )
    tremor_repaus = QNode(
        id="tremor_repaus", code=97, nature="Sympt",
        q={"ro":"Tremurăturile apar în repaus (nu la mișcare)?",
           "fr":"Les tremblements surviennent-ils au repos (pas lors des mouvements)?",
           "en":"Do the tremors occur at rest (not during movement)?"},
    )
    tremor_intentional = QNode(
        id="tremor_intentional", code=219, nature="Sympt",
        q={"ro":"Tremurăturile apar la mișcările voluntare (la intenția de a apuca ceva)?",
           "fr":"Les tremblements surviennent-ils lors des mouvements volontaires?",
           "en":"Do the tremors occur during voluntary movements?"},
    )
    extrapiramidal = QNode(
        id="extrapiramidal", code=73, nature="Signe",
        q={"ro":"Prezintă rigiditate musculară, mișcări lente sau dificultate de inițiere a mișcării?",
           "fr":"Présente-t-il une rigidité musculaire, des mouvements lents ou une difficulté à initier les mouvements?",
           "en":"Does the patient have muscle rigidity, slow movements, or difficulty initiating movement?"},
        yes=[tremor_repaus, tremor_intentional],
    )
    tremor = QNode(
        id="tremor",
        q={"ro":"Are tremurături?",
           "fr":"A-t-il des tremblements?",
           "en":"Does the patient have tremors?"},
        yes=[tremor_repaus, tremor_intentional],
    )

    # ── DIGESTIV ──────────────────────────────────────────────────────────────
    diaree_cronica = QNode(
        id="diaree_cronica", code=358, nature="Sympt",
        q={"ro":"Diareea durează de mai mult de o lună sau revine periodic?",
           "fr":"La diarrhée dure-t-elle depuis plus d'un mois ou revient-elle périodiquement?",
           "en":"Has the diarrhea lasted more than a month or does it recur periodically?"},
    )
    diaree_sange = QNode(
        id="diaree_sange", code=39, nature="Sympt",
        q={"ro":"Scaunele conțin sânge sau mucus?",
           "fr":"Les selles contiennent-elles du sang ou du mucus?",
           "en":"Do the stools contain blood or mucus?"},
    )
    diaree_grase = QNode(
        id="diaree_grase", code=11, nature="Sympt",
        q={"ro":"Scaunele sunt grase, lucioase, greu de spălat (steatoree)?",
           "fr":"Les selles sont-elles grasses, brillantes et difficiles à éliminer (stéatorrhée)?",
           "en":"Are the stools fatty, greasy, difficult to flush (steatorrhea)?"},
    )
    diaree = QNode(
        id="diaree", code=10, nature="Sympt",
        q={"ro":"Are diaree (mai mult de 3 scaune pe zi)?",
           "fr":"A-t-il de la diarrhée (plus de 3 selles par jour)?",
           "en":"Does the patient have diarrhea (more than 3 stools per day)?"},
        yes=[diaree_cronica, diaree_sange, diaree_grase],
    )
    varsaturi_sange = QNode(
        id="varsaturi_sange", code=143, nature="Sympt",
        q={"ro":"Vomismentele conțin sânge sau material de culoare cafenie (zaț de cafea)?",
           "fr":"Les vomissements contiennent-ils du sang ou une matière brune (marc de café)?",
           "en":"Do the vomits contain blood or coffee-ground material?"},
    )
    varsaturi_persistente = QNode(
        id="varsaturi_persistente",
        q={"ro":"Vărsăturile sunt frecvente și persistente (de mai mult de 24 ore)?",
           "fr":"Les vomissements sont-ils fréquents et persistants (depuis plus de 24 heures)?",
           "en":"Are the vomits frequent and persistent (lasting more than 24 hours)?"},
    )
    varsaturi = QNode(
        id="varsaturi", code=17, nature="Sympt",
        q={"ro":"Are greață sau varsă?",
           "fr":"A-t-il des nausées ou vomit-il?",
           "en":"Does the patient have nausea or vomiting?"},
        yes=[varsaturi_sange, varsaturi_persistente],
    )
    icter_urini = QNode(
        id="icter_urini", code=139, nature="Sympt",
        q={"ro":"Urina este de culoare închisă (brună sau portocalie)?",
           "fr":"Les urines sont-elles de couleur foncée (brune ou orangée)?",
           "en":"Is the urine dark-colored (brown or orange)?"},
    )
    icter_scaune = QNode(
        id="icter_scaune",
        q={"ro":"Scaunele sunt de culoare deschisă sau albicioasă?",
           "fr":"Les selles sont-elles de couleur claire ou blanchâtre?",
           "en":"Are the stools light-colored or whitish?"},
    )

    # ── URINAR ────────────────────────────────────────────────────────────────
    poliurie_sete = QNode(
        id="poliurie_sete",
        q={"ro":"Este însoțită de sete exagerată (bea mult)?",
           "fr":"Est-elle accompagnée d'une soif exagérée (boit-il beaucoup)?",
           "en":"Is it accompanied by excessive thirst (drinking a lot)?"},
    )
    poliurie_nocturna = QNode(
        id="poliurie_nocturna", code=110, nature="Sympt",
        q={"ro":"Se trezește de mai mult de 2 ori noaptea să urineze?",
           "fr":"Se lève-t-il plus de 2 fois par nuit pour uriner?",
           "en":"Does the patient get up more than 2 times at night to urinate?"},
    )
    poliurie = QNode(
        id="poliurie", code=109, nature="Sympt",
        q={"ro":"Urinează des și în cantități mari?",
           "fr":"Urine-t-il souvent et en grande quantité?",
           "en":"Does the patient urinate frequently and in large quantities?"},
        yes=[poliurie_sete, poliurie_nocturna],
    )
    hematurie_durere = QNode(
        id="hematurie_durere", code=64, nature="Sympt",
        q={"ro":"Hematuria este însoțită de durere la urinare sau în flanc?",
           "fr":"L'hématurie est-elle accompagnée de douleurs à la miction ou dans les flancs?",
           "en":"Is the hematuria accompanied by pain when urinating or flank pain?"},
    )
    hematurie = QNode(
        id="hematurie", code=38, nature="Sympt",
        q={"ro":"Are sânge în urină?",
           "fr":"A-t-il du sang dans les urines?",
           "en":"Does the patient have blood in the urine?"},
        yes=[hematurie_durere],
    )

    # ── GENERAL ───────────────────────────────────────────────────────────────
    scadere_ponderala_rapida = QNode(
        id="scadere_ponderala_rapida",
        q={"ro":"Slăbiciunea s-a instalat rapid (mai mult de 5 kg în ultima lună)?",
           "fr":"La perte de poids s-est-elle installée rapidement (plus de 5 kg en un mois)?",
           "en":"Has the weight loss been rapid (more than 5 kg in the last month)?"},
    )
    scadere_ponderala_apetit = QNode(
        id="scadere_ponderala_apetit", code=74, nature="Sympt",
        q={"ro":"Scăderea în greutate este însoțită de pierderea poftei de mâncare?",
           "fr":"La perte de poids est-elle accompagnée d'une perte d'appétit?",
           "en":"Is the weight loss accompanied by loss of appetite?"},
    )
    scadere_ponderala = QNode(
        id="scadere_ponderala", code=13, nature="Sympt",
        q={"ro":"A slăbit recent fără o cauză evidentă?",
           "fr":"A-t-il maigri récemment sans raison évidente?",
           "en":"Has the patient lost weight recently without obvious cause?"},
        yes=[scadere_ponderala_rapida, scadere_ponderala_apetit],
    )
    oboseala_la_efort = QNode(
        id="oboseala_la_efort", code=47, nature="Sympt",
        q={"ro":"Oboseala apare sau se agravează la efort fizic mic?",
           "fr":"La fatigue apparaît-elle ou s'aggrave-t-elle à un effort physique minime?",
           "en":"Does the fatigue appear or worsen with minimal physical exertion?"},
    )
    oboseala_membre = QNode(
        id="oboseala_membre", code=66, nature="Sympt",
        q={"ro":"Oboseala este mai accentuată la nivelul membrelor?",
           "fr":"La fatigue est-elle plus marquée au niveau des membres?",
           "en":"Is the fatigue more pronounced in the limbs?"},
    )
    oboseala = QNode(
        id="oboseala", code=14, nature="Sympt",
        q={"ro":"Se simte extrem de obosit sau lipsit de energie?",
           "fr":"Se sent-il extrêmement fatigué ou sans énergie?",
           "en":"Does the patient feel extremely tired or lacking energy?"},
        yes=[oboseala_la_efort, oboseala_membre],
    )
    paloare_lesin = QNode(
        id="paloare_lesin", code=1, nature="Sympt",
        q={"ro":"Paloarea este însoțită de leșin sau amețeli?",
           "fr":"La pâleur est-elle accompagnée de malaises ou vertiges?",
           "en":"Is the pallor accompanied by fainting or dizziness?"},
    )
    paloare = QNode(
        id="paloare", code=4, nature="Sympt",
        q={"ro":"Are un aspect palid, lipsit de culoare?",
           "fr":"A-t-il un teint pâle?",
           "en":"Does the patient look pale?"},
        yes=[paloare_lesin],
    )

    # ── SPECIFIC FEMININ ──────────────────────────────────────────────────────
    meno_amenoree = QNode(
        id="meno_amenoree", code=174, nature="Sympt", sex="F",
        q={"ro":"Menstruația a încetat fără o cauză aparentă (amenoree)?",
           "fr":"Les règles ont-elles cessé sans raison apparente (aménorrhée)?",
           "en":"Has menstruation stopped without apparent cause (amenorrhea)?"},
    )
    meno_sangerari_anormale = QNode(
        id="meno_sangerari_anormale", code=27, nature="Sympt", sex="F",
        q={"ro":"Are sângerări uterine în afara menstruației?",
           "fr":"A-t-elle des saignements utérins en dehors des règles?",
           "en":"Does the patient have uterine bleeding outside of menstruation?"},
    )
    meno_durere = QNode(
        id="meno_durere", code=37, nature="Sympt", sex="F",
        q={"ro":"Are dureri în timpul menstruației sau actului sexual?",
           "fr":"A-t-elle des douleurs pendant les règles ou les rapports sexuels?",
           "en":"Does the patient have pain during menstruation or sexual intercourse?"},
    )
    durere_pelvina = QNode(
        id="durere_pelvina", code=151, nature="Sympt", sex="F",
        q={"ro":"Are dureri în zona pelviană sau abdomenul inferior?",
           "fr":"A-t-elle des douleurs dans la région pelvienne ou le bas-ventre?",
           "en":"Does the patient have pelvic or lower abdominal pain?"},
        yes=[meno_amenoree, meno_sangerari_anormale, meno_durere],
    )
    sangerare_vaginala = QNode(
        id="sangerare_vaginala", code=150, nature="Sympt", sex="F",
        q={"ro":"Are sângerări vaginale anormale (nu menstruație)?",
           "fr":"A-t-elle des saignements vaginaux anormaux (en dehors des règles)?",
           "en":"Does the patient have abnormal vaginal bleeding?"},
    )
    scurgeri_vaginale = QNode(
        id="scurgeri_vaginale", code=25, nature="Sympt", sex="F",
        q={"ro":"Are scurgeri vaginale anormale (cu miros, culoare sau cantitate neobișnuită)?",
           "fr":"A-t-elle des pertes vaginales anormales (odeur, couleur ou quantité inhabituelle)?",
           "en":"Does the patient have abnormal vaginal discharge?"},
    )
    sterilitate = QNode(
        id="sterilitate", code=171, nature="Sympt", sex="F",
        q={"ro":"Are dificultăți să conceapă (sterilitate, >12 luni fără contracepție)?",
           "fr":"A-t-elle du mal à concevoir (stérilité, > 12 mois sans contraception)?",
           "en":"Does the patient have difficulty conceiving (infertility, >12 months without contraception)?"},
    )

    # ── SPECIFIC GRAVIDĂ ──────────────────────────────────────────────────────
    gravida_tensiune = QNode(
        id="gravida_tensiune", sex="F", pregnant=True,
        q={"ro":"Tensiunea arterială este crescută în sarcină?",
           "fr":"La pression artérielle est-elle élevée pendant la grossesse?",
           "en":"Is blood pressure elevated during pregnancy?"},
    )
    gravida_edeme = QNode(
        id="gravida_edeme", sex="F", pregnant=True,
        q={"ro":"Are edeme (umflături) la față sau mâini, brusc apărute?",
           "fr":"A-t-elle des œdèmes (gonflements) du visage ou des mains, apparus brusquement?",
           "en":"Does the patient have sudden swelling of face or hands?"},
    )
    gravida_miscari = QNode(
        id="gravida_miscari", sex="F", pregnant=True,
        q={"ro":"Mișcările fetale au scăzut sau au încetat?",
           "fr":"Les mouvements fœtaux ont-ils diminué ou cessé?",
           "en":"Have fetal movements decreased or stopped?"},
    )
    gravida_sangerare = QNode(
        id="gravida_sangerare", code=150, nature="Sympt", sex="F", pregnant=True,
        q={"ro":"Are sângerări vaginale în sarcină?",
           "fr":"A-t-elle des saignements vaginaux pendant la grossesse?",
           "en":"Does the patient have vaginal bleeding during pregnancy?"},
    )

    # ── PEDIATRIC ─────────────────────────────────────────────────────────────
    retard_crestere = QNode(
        id="retard_crestere", code=229, nature="Sympt", max_age=216,
        q={"ro":"Copilul crește mai lent decât ceilalți de aceeași vârstă?",
           "fr":"L'enfant grandit-il plus lentement que les autres enfants du même âge?",
           "en":"Is the child growing more slowly than peers of the same age?"},
    )
    conv_febrile = QNode(
        id="conv_febrile", max_age=72,
        q={"ro":"A avut convulsii febrile în trecut?",
           "fr":"A-t-il eu des convulsions fébriles dans le passé?",
           "en":"Has the child had febrile seizures in the past?"},
    )

    # ── PSIHIATRIC / COMPORTAMENTAL ───────────────────────────────────────────
    depresie_dispozitie = QNode(
        id="depresie_dispozitie",
        q={"ro":"Dispoziția este persistent tristă sau fără speranță?",
           "fr":"L'humeur est-elle persistamment triste ou sans espoir?",
           "en":"Is the mood persistently sad or hopeless?"},
    )
    depresie_somn = QNode(
        id="depresie_somn", code=138, nature="Sympt",
        q={"ro":"Are tulburări de somn (insomnie sau hipersomnie)?",
           "fr":"A-t-il des troubles du sommeil (insomnie ou hypersomnie)?",
           "en":"Does the patient have sleep disturbances (insomnia or hypersomnia)?"},
    )
    depresie = QNode(
        id="depresie", code=147, nature="Sympt",
        q={"ro":"Prezintă semne de depresie (tristețe persistentă, pierderea interesului)?",
           "fr":"Présente-t-il des signes de dépression (tristesse persistante, perte d'intérêt)?",
           "en":"Does the patient show signs of depression?"},
        yes=[depresie_dispozitie, depresie_somn],
    )
    anxietate = QNode(
        id="anxietate", code=45, nature="Sympt",
        q={"ro":"Are stări de anxietate, neliniște sau atacuri de panică?",
           "fr":"A-t-il de l'anxiété, de l'agitation ou des attaques de panique?",
           "en":"Does the patient have anxiety, restlessness, or panic attacks?"},
    )
    schimbari_personalitate = QNode(
        id="schimbari_personalitate", code=287, nature="Sympt",
        q={"ro":"Au apărut schimbări de comportament sau personalitate observate de cei din jur?",
           "fr":"Y a-t-il eu des changements de comportement ou de personnalité remarqués par l'entourage?",
           "en":"Have behavioral or personality changes been noticed by those around the patient?"},
    )
    memoria = QNode(
        id="memoria", code=62, nature="Sympt",
        q={"ro":"Are probleme de memorie sau uită lucruri recente?",
           "fr":"A-t-il des problèmes de mémoire ou oublie-t-il des événements récents?",
           "en":"Does the patient have memory problems or forget recent events?"},
    )

    # ── CUTANAT ───────────────────────────────────────────────────────────────
    prurit_generalizat = QNode(
        id="prurit_generalizat", code=24, nature="Sympt",
        q={"ro":"Mâncărimile sunt generalizate (pe tot corpul)?",
           "fr":"Les démangeaisons sont-elles généralisées (sur tout le corps)?",
           "en":"Is the itching generalized (all over the body)?"},
    )
    prurit_nocturn = QNode(
        id="prurit_nocturn",
        q={"ro":"Mâncărimile sunt mai intense noaptea?",
           "fr":"Les démangeaisons sont-elles plus intenses la nuit?",
           "en":"Is the itching more intense at night?"},
    )
    prurit = QNode(
        id="prurit",
        q={"ro":"Are mâncărimi (prurit)?",
           "fr":"A-t-il des démangeaisons (prurit)?",
           "en":"Does the patient have itching (pruritus)?"},
        yes=[prurit_generalizat, prurit_nocturn],
    )
    eruptie_distributie = QNode(
        id="eruptie_distributie",
        q={"ro":"Erupția este localizată sau difuză (pe tot corpul)?",
           "fr":"L'éruption est-elle localisée ou diffuse (sur tout le corps)?",
           "en":"Is the rash localized or diffuse (all over the body)?"},
    )
    eruptie_evolutie = QNode(
        id="eruptie_evolutie",
        q={"ro":"Erupția apare brusc sau evoluează progresiv?",
           "fr":"L'éruption apparaît-elle brusquement ou évolue-t-elle progressivement?",
           "en":"Does the rash appear suddenly or evolve progressively?"},
    )
    eruptie = QNode(
        id="eruptie",
        q={"ro":"Are erupții sau leziuni cutanate (pete, papule, vezicule)?",
           "fr":"A-t-il des éruptions ou lésions cutanées (taches, papules, vésicules)?",
           "en":"Does the patient have skin rashes or lesions (spots, papules, blisters)?"},
        yes=[eruptie_distributie, eruptie_evolutie],
    )

    # ── ASAMBLARE RĂDĂCINI ────────────────────────────────────────────────────
    # Organizate pe sisteme — prima întrebare deschide întregul sistem
    roots = [
        # 1. Semne generale (febră, oboseală, slăbire)
        QNode(id="sistem_general",
              q={"ro":"Prezintă simptome generale: febră, oboseală marcată sau scădere în greutate?",
                 "fr":"Présente-t-il des symptômes généraux: fièvre, fatigue marquée ou perte de poids?",
                 "en":"Does the patient have general symptoms: fever, marked fatigue or weight loss?"},
              yes=[febra, oboseala, scadere_ponderala, paloare]),

        # 2. Durere (oriunde)
        QNode(id="sistem_durere",
              q={"ro":"Acuză dureri (oriunde în corp)?",
                 "fr":"Souffre-t-il de douleurs (n'importe où dans le corps)?",
                 "en":"Does the patient complain of pain (anywhere in the body)?"},
              yes=[durere_cap, durere_toracica, durere_abdominala,
                   durere_articulara, durere_lombar]),

        # 3. Cardio-respirator
        QNode(id="sistem_cardio",
              q={"ro":"Are simptome cardiace sau respiratorii (dificultăți de respirație, palpitații, tuse)?",
                 "fr":"A-t-il des symptômes cardiaques ou respiratoires (essoufflement, palpitations, toux)?",
                 "en":"Does the patient have cardiac or respiratory symptoms?"},
              yes=[dispnee, palpitatii, tuse]),

        # 4. Neurologic
        QNode(id="sistem_neuro",
              q={"ro":"Are simptome neurologice (convulsii, amorțeală, confuzie, tulburări de mers sau vedere)?",
                 "fr":"A-t-il des symptômes neurologiques (convulsions, engourdissements, confusion)?",
                 "en":"Does the patient have neurological symptoms?"},
              yes=[convulsii, amorteli, confuzie, tremor,
                   extrapiramidal, mers_dificil, vedere_incetosata]),

        # 5. Digestiv
        QNode(id="sistem_digestiv",
              q={"ro":"Are simptome digestive (greață, vărsături, diaree, dureri abdominale, sângerare)?",
                 "fr":"A-t-il des symptômes digestifs (nausées, vomissements, diarrhée, douleurs)?",
                 "en":"Does the patient have digestive symptoms?"},
              yes=[varsaturi, diaree]),

        # 6. Urinar
        QNode(id="sistem_urinar",
              q={"ro":"Are simptome urinare (urinări frecvente, durere la urinare, sânge în urină)?",
                 "fr":"A-t-il des symptômes urinaires (mictions fréquentes, douleurs, sang dans les urines)?",
                 "en":"Does the patient have urinary symptoms?"},
              yes=[poliurie, hematurie]),

        # 7. Psihiatric / comportamental
        QNode(id="sistem_psih",
              q={"ro":"Prezintă simptome psihice: depresie, anxietate, schimbări de personalitate sau memorie?",
                 "fr":"Présente-t-il des symptômes psychiques: dépression, anxiété, changements de personnalité?",
                 "en":"Does the patient have psychiatric symptoms: depression, anxiety, personality changes?"},
              yes=[depresie, anxietate, schimbari_personalitate, memoria]),

        # 8. Cutanat
        QNode(id="sistem_cutanat",
              q={"ro":"Are probleme cutanate: erupții, mâncărimi sau leziuni ale pielii?",
                 "fr":"A-t-il des problèmes cutanés: éruptions, démangeaisons ou lésions de la peau?",
                 "en":"Does the patient have skin problems: rashes, itching, or skin lesions?"},
              yes=[prurit, eruptie]),

        # 9. Specific feminin
        QNode(id="sectiune_gineco", sex="F",
              q={"ro":"Pacienta are simptome ginecologice: dureri pelvine, sângerări sau scurgeri anormale?",
                 "fr":"La patiente a-t-elle des symptômes gynécologiques: douleurs pelviennes, saignements, pertes?",
                 "en":"Does the patient have gynecological symptoms: pelvic pain, bleeding, or discharge?"},
              yes=[durere_pelvina, sangerare_vaginala, scurgeri_vaginale, sterilitate]),

        # 10. Specific gravidă
        QNode(id="sectiune_gravida", sex="F", pregnant=True,
              q={"ro":"Prezintă simptome specifice sarcinii: tensiune crescută, edeme bruște sau sângerare?",
                 "fr":"Présente-t-elle des symptômes spécifiques de la grossesse: HTA, œdèmes, saignements?",
                 "en":"Does the patient have pregnancy-specific symptoms: hypertension, edema, bleeding?"},
              yes=[gravida_tensiune, gravida_edeme, gravida_miscari, gravida_sangerare]),

        # 11. Pediatric
        QNode(id="sectiune_pediatric", max_age=216,
              q={"ro":"Copilul prezintă retard de creștere sau convulsii febrile?",
                 "fr":"L'enfant présente-t-il un retard de croissance ou des convulsions fébriles?",
                 "en":"Does the child have growth retardation or febrile seizures?"},
              yes=[retard_crestere, conv_febrile]),

        # 12. Debut (la final, ca context)
        QNode(id="sistem_debut",
              q={"ro":"Simptomele au apărut brusc (în mai puțin de 3 zile)?",
                 "fr":"Les symptômes sont-ils apparus brusquement (en moins de 3 jours)?",
                 "en":"Did the symptoms appear suddenly (within less than 3 days)?"},
              yes=[debut_acut],
              no=[debut_insidios]),
    ]

    return roots


# ── Navigator ─────────────────────────────────────────────────────────────────

class TreeNavigator:
    """
    Navighează arborele de întrebări cu suport pentru înapoi.
    Istoricul permite revenirea la întrebarea precedentă.
    """

    def __init__(self, roots: list[QNode], profile: dict):
        self.profile  = profile
        self._queue: list[QNode] = [n for n in roots if n.visible(profile)]
        self._answered: set[str] = set()
        # Istoric: fiecare intrare = (node, answer, queue_snapshot, answered_snapshot, elems_added)
        self._history: list[tuple] = []

    def current(self) -> Optional[QNode]:
        while self._queue:
            node = self._queue[0]
            if node.id in self._answered:
                self._queue.pop(0)
                continue
            return node
        return None

    def answer(self, answer: str) -> None:
        """
        Procesează răspunsul ('yes' | 'no' | 'skip').
        Salvează starea în istoric înainte de modificare.
        """
        node = self._queue[0]

        # Salvează snapshot înainte de răspuns
        self._history.append({
            "node"     : node,
            "answer"   : answer,
            "queue"    : list(self._queue),
            "answered" : set(self._answered),
            "elems"    : self.elements_to_add(node, answer),
        })

        self._queue.pop(0)
        self._answered.add(node.id)

        if answer == "yes" and node.yes:
            visible = [c for c in node.yes
                       if c.visible(self.profile) and c.id not in self._answered]
            self._queue = visible + self._queue
        elif answer == "no" and node.no:
            visible = [c for c in node.no
                       if c.visible(self.profile) and c.id not in self._answered]
            self._queue = visible + self._queue

    def back(self) -> Optional[list[tuple]]:
        """
        Revine la întrebarea precedentă.
        Returnează lista de elemente care trebuie ELIMINATE din profilul pacientului,
        sau None dacă nu există istoric.
        """
        if not self._history:
            return None
        snap = self._history.pop()
        self._queue    = list(snap["queue"])
        self._answered = set(snap["answered"])
        return snap["elems"]  # caller trebuie să le elimine din cons_elements

    def can_go_back(self) -> bool:
        return len(self._history) > 0

    def progress(self) -> tuple[int, int]:
        done  = len(self._answered)
        total = done + len(self._queue)
        return done, max(total, 1)

    def elements_to_add(self, node: QNode, answer: str) -> list[tuple]:
        if answer == "yes" and node.code is not None:
            return [(node.code, node.nature, node.score)]
        return []
