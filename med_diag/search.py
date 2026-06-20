import pandas as pd

from .utils import normalize_text, split_synonyms, token_set

def score_catalog_match(user_text: str, row: pd.Series) -> float:
    txt = normalize_text(user_text)
    if not txt:
        return 0.0

    score = 0.0
    display = normalize_text(row["DisplayName"])
    searchable = normalize_text(" ".join([
        str(row.get("DisplayName", "")),
        str(row.get("Synonyms", "")),
        str(row.get("DescriptionRO", "")),
        str(row.get("DescriptionEN", "")),
    ]))

    # direct contains both directions
    if display and display in txt:
        score += 6.0
    if display and txt in display and len(txt) >= 2:
        score += 4.5

    for syn in split_synonyms(str(row.get("Synonyms", ""))):
        syn_n = normalize_text(syn)
        if syn_n and syn_n in txt:
            score += 5.0
        elif syn_n and txt in syn_n and len(txt) >= 2:
            score += 4.0

    # token overlap
    display_tokens = token_set(display)
    txt_tokens = token_set(txt)
    if display_tokens:
        overlap = len(display_tokens & txt_tokens) / max(len(display_tokens), 1)
        score += 2.5 * overlap

    searchable_tokens = token_set(searchable)
    if searchable_tokens:
        overlap_all = len(searchable_tokens & txt_tokens) / max(min(len(searchable_tokens), 12), 1)
        score += 1.5 * overlap_all

    # prefix / partial token boost for short fragments like "nec" -> "neck"
    if txt:
        searchable_parts = searchable.split()
        for tok in searchable_parts:
            if tok.startswith(txt) and len(txt) >= 2:
                score += 2.0
                break
            if txt in tok and len(txt) >= 2:
                score += 1.5
                break

    return float(score)

def extract_candidates_from_text(
    user_text: str,
    catalog_df: pd.DataFrame,
    top_k: int = 25,
    min_score: float = 2.0,
) -> pd.DataFrame:
    if not user_text.strip():
        return pd.DataFrame(columns=["Key", "Nature", "Code", "DisplayName", "MatchScore", "Synonyms", "CategoryLabel"])

    scored_rows = []
    for _, row in catalog_df.iterrows():
        s = score_catalog_match(user_text, row)
        if s >= min_score:
            scored_rows.append(
                {
                    "Key": row["Key"],
                    "Nature": row["Nature"],
                    "Code": int(row["Code"]),
                    "DisplayName": row["DisplayName"],
                    "Synonyms": row.get("Synonyms", ""),
                    "CategoryLabel": row.get("CategoryLabel", "Uncategorized"),
                    "MatchScore": round(float(s), 4),
                }
            )

    if not scored_rows:
        return pd.DataFrame(columns=["Key", "Nature", "Code", "DisplayName", "MatchScore", "Synonyms", "CategoryLabel"])

    out = pd.DataFrame(scored_rows).sort_values(
        ["MatchScore", "Nature", "Code"],
        ascending=[False, True, True]
    ).head(top_k)
    return out.reset_index(drop=True)
