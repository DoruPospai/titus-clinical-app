import streamlit as st
from .config import APP_NAME, APP_SUBTITLE

def inject_css() -> None:
    st.markdown(
        """
        <style>
        .main > div { padding-top: 1rem; }
        [data-testid="stSidebar"] { background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%); }
        .dor-hero {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #2563eb 100%);
            border-radius: 28px; padding: 28px 32px; color: white;
            box-shadow: 0 18px 40px rgba(15,23,42,0.18); margin-bottom: 1rem;
        }
        .dor-hero-row { display:flex; gap:18px; align-items:center; }
        .dor-logo {
            width:74px; height:74px; border-radius:20px; display:flex; align-items:center;
            justify-content:center; background: rgba(255,255,255,0.12); font-size:2rem;
        }
        .dor-hero h1 { margin:0 0 0.25rem 0; font-size:2.3rem; font-weight:800; letter-spacing:-0.03em; }
        .dor-hero p { margin:0; font-size:1.02rem; line-height:1.55; opacity:0.94; max-width:980px; }
        .dor-panel {
            background:#fff; border:1px solid rgba(15,23,42,0.08); border-radius:22px;
            padding:18px 20px; box-shadow:0 10px 24px rgba(15,23,42,0.05); margin-bottom:0.9rem;
        }
        .dor-panel-title { color:#0f172a; font-size:1.15rem; font-weight:800; margin-bottom:0.25rem; }
        .dor-panel-subtitle { color:#64748b; font-size:0.96rem; line-height:1.5; }
        .dor-note {
            background: linear-gradient(180deg,#ffffff 0%,#f8fbff 100%);
            border:1px solid #dbeafe; border-left:5px solid #2563eb; padding:12px 14px;
            border-radius:14px; color:#334155; margin:0.5rem 0 0.8rem 0;
        }
        .dor-kpi {
            background: linear-gradient(180deg,#ffffff 0%,#f8fafc 100%);
            border:1px solid rgba(15,23,42,0.08); border-radius:18px; padding:16px 18px;
            box-shadow:0 10px 24px rgba(15,23,42,0.05); height:100%;
        }
        .dor-kpi-label { color:#64748b; font-size:0.9rem; margin-bottom:0.35rem; }
        .dor-kpi-value { color:#0f172a; font-size:1.45rem; font-weight:800; letter-spacing:-0.02em; }
        div[data-testid="stDataEditor"], div[data-testid="stDataFrame"] { border-radius:18px; overflow:hidden; }
        .dor-footer-note {
            color:#475569; font-size:0.94rem; line-height:1.55; background:#f8fafc;
            border:1px solid rgba(15,23,42,0.07); border-radius:16px; padding:14px 16px;
        }
        .dor-mini-muted { color:#64748b; font-size:0.9rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def hero() -> None:
    st.markdown(
        f"""
        <div class="dor-hero">
            <div class="dor-hero-row">
                <div class="dor-logo">🩺</div>
                <div>
                    <h1>{APP_NAME}</h1>
                    <p>{APP_SUBTITLE}</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def panel_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="dor-panel">
            <div class="dor-panel-title">{title}</div>
            <div class="dor-panel-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def kpi_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="dor-kpi">
            <div class="dor-kpi-label">{label}</div>
            <div class="dor-kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def note(text: str) -> None:
    st.markdown(f'<div class="dor-note">{text}</div>', unsafe_allow_html=True)
