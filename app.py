import streamlit as st
import pandas as pd
import requests
import os
import zipfile
import io
import re
import time
from urllib.parse import urlparse

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Gallica Image Downloader",
    page_icon="📚",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&display=swap');

:root {
    --ink: #1a1410;
    --paper: #f5f0e8;
    --sepia: #8b6914;
    --rust: #c0392b;
    --sage: #2d6a4f;
    --gold: #d4a017;
    --light-paper: #faf7f0;
    --border: #d4c4a0;
}

html, body, [class*="css"] {
    font-family: 'DM Mono', monospace;
    background-color: var(--paper);
    color: var(--ink);
}

.stApp {
    background: var(--paper);
}

h1, h2, h3 {
    font-family: 'DM Serif Display', serif !important;
    color: var(--ink) !important;
}

.main-title {
    font-family: 'DM Serif Display', serif;
    font-size: 2.8rem;
    color: var(--ink);
    border-bottom: 3px double var(--sepia);
    padding-bottom: 0.5rem;
    margin-bottom: 0.2rem;
    letter-spacing: -0.5px;
}

.subtitle {
    font-family: 'DM Mono', monospace;
    font-size: 0.8rem;
    color: var(--sepia);
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 2rem;
}

.section-label {
    font-family: 'DM Serif Display', serif;
    font-size: 1.2rem;
    color: var(--sepia);
    border-left: 4px solid var(--gold);
    padding-left: 0.7rem;
    margin: 1.5rem 0 0.5rem 0;
}

.url-card {
    background: var(--light-paper);
    border: 1px solid var(--border);
    border-left: 4px solid var(--sepia);
    border-radius: 2px;
    padding: 0.6rem 0.8rem;
    margin: 0.4rem 0;
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
}

.url-index {
    color: var(--sepia);
    font-weight: 500;
}

.url-text {
    color: #555;
    word-break: break-all;
    font-size: 0.7rem;
}

.name-preview {
    color: var(--sage);
    font-weight: 500;
    font-size: 0.8rem;
}

.badge-ok { background:#e8f5e9; color:#2d6a4f; padding:2px 8px; border-radius:2px; font-size:0.7rem; }
.badge-err { background:#fce4e4; color:#c0392b; padding:2px 8px; border-radius:2px; font-size:0.7rem; }
.badge-wait { background:#fff8e1; color:#8b6914; padding:2px 8px; border-radius:2px; font-size:0.7rem; }

div.stButton > button {
    background: var(--ink);
    color: var(--paper);
    border: none;
    border-radius: 2px;
    font-family: 'DM Mono', monospace;
    font-size: 0.8rem;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 0.5rem 1.5rem;
    transition: background 0.2s;
}
div.stButton > button:hover {
    background: var(--sepia);
    color: white;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    font-family: 'DM Mono', monospace;
    font-size: 0.8rem;
    background: var(--light-paper);
    border: 1px solid var(--border);
    border-radius: 2px;
    color: var(--ink);
}

.stDataFrame {
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
}

.progress-bar-custom {
    background: var(--border);
    border-radius: 2px;
    height: 6px;
    width: 100%;
    margin: 0.3rem 0;
}

hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 1.5rem 0;
}

.info-box {
    background: #fffbf0;
    border: 1px solid var(--gold);
    padding: 0.7rem 1rem;
    border-radius: 2px;
    font-size: 0.78rem;
    color: #5a4a00;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def gallica_url_to_highres(url: str) -> str:
    """
    Convert a Gallica notice/viewer URL to a direct high-res JPEG download URL.
    Handles common patterns:
      https://gallica.bnf.fr/ark:/12148/btv1b...          → add /f1.highres
      https://gallica.bnf.fr/ark:/12148/btv1b.../f3.item  → replace with .highres
      https://gallica.bnf.fr/ark:/12148/btv1b.../f3.highres → keep as-is
    """
    url = url.strip()
    # Already a highres link
    if url.endswith(".highres"):
        return url
    # Replace .item or .thumbnail etc. with .highres
    url = re.sub(r'/f(\d+)\.\w+$', r'/f\1.highres', url)
    if re.search(r'/f\d+\.highres$', url):
        return url
    # Viewer URL with ?id= pattern
    m = re.search(r'ark:/12148/([^/?#]+)', url)
    if m:
        ark_id = m.group(1)
        return f"https://gallica.bnf.fr/ark:/12148/{ark_id}/f1.highres"
    # Fallback: return as-is
    return url


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = name.strip()
    return name or "image"


def build_name(template: str, index: int, variant: str) -> str:
    """
    Replace {n} with index+1 (1-based), append variant if given.
    """
    name = template.replace("{n}", str(index + 1))
    name = name.replace("{N}", str(index + 1).zfill(3))
    if variant.strip():
        name = f"{name}_{variant.strip()}"
    return sanitize_filename(name)


def download_image(url: str, dest_path: str) -> tuple[bool, str]:
    try:
        dl_url = gallica_url_to_highres(url)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; GallicaDownloader/1.0; "
                "+https://github.com/gallica)"
            )
        }
        r = requests.get(dl_url, headers=headers, timeout=30, stream=True)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "png" in content_type:
            ext = ".png"
        elif "tiff" in content_type or "tif" in content_type:
            ext = ".tif"
        else:
            ext = ".jpg"  # Gallica default
        final_path = dest_path + ext
        with open(final_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True, final_path
    except Exception as e:
        return False, str(e)


# ── Session state init ────────────────────────────────────────────────────────
for key, val in [
    ("urls", []),
    ("names", []),
    ("variants", []),
    ("download_results", []),
    ("step", 1),
]:
    if key not in st.session_state:
        st.session_state[key] = val


# ── UI ────────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">📚 Gallica Downloader</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">BnF · Bibliothèque nationale de France — outil de téléchargement en lot</div>', unsafe_allow_html=True)

# ── ÉTAPE 1 : Upload ──────────────────────────────────────────────────────────
st.markdown('<div class="section-label">① Importer le fichier Excel</div>', unsafe_allow_html=True)

uploaded = st.file_uploader(
    "Déposez votre fichier .xlsx (URLs en colonne A)",
    type=["xlsx"],
    label_visibility="collapsed",
)

if uploaded:
    df = pd.read_excel(uploaded, header=None)
    raw_urls = df.iloc[:, 0].dropna().astype(str).tolist()
    urls = [u.strip() for u in raw_urls if u.strip().startswith("http")]
    st.session_state["urls"] = urls
    st.session_state["variants"] = [""] * len(urls)
    if len(urls) < len(raw_urls):
        st.warning(f"{len(raw_urls) - len(urls)} ligne(s) ignorée(s) (non-URL).")
    st.success(f"✓ {len(urls)} URL(s) détectée(s) en colonne A")
    st.session_state["step"] = 2

# ── ÉTAPE 2 : Nomenclature ────────────────────────────────────────────────────
if st.session_state["step"] >= 2 and st.session_state["urls"]:
    st.markdown('<div class="section-label">② Définir la nomenclature</div>', unsafe_allow_html=True)

    st.markdown("""
<div class="info-box">
Utilisez <code>{n}</code> pour le numéro séquentiel (1, 2, 3…) ou <code>{N}</code> pour le numéro zéro-padé (001, 002…).<br>
<b>Exemples :</b> <code>DEL-45_{N}</code> → <code>DEL-45_001</code> &nbsp;|&nbsp; <code>Mazarin_{n}_photo</code> → <code>Mazarin_1_photo</code>
</div>
""", unsafe_allow_html=True)

    col_tpl, col_prev = st.columns([2, 1])
    with col_tpl:
        template = st.text_input(
            "Modèle de nom (commun à tous les fichiers)",
            value="image_{N}",
            key="template_input",
        )
    with col_prev:
        st.markdown("**Aperçu (ligne 1)**")
        preview = build_name(template, 0, "")
        st.code(preview + ".jpg", language=None)

    st.markdown("---")
    st.markdown('<div class="section-label">③ Variantes individuelles (optionnel)</div>', unsafe_allow_html=True)
    st.caption("Ajoutez un suffixe spécifique à chaque URL, par ex. `[DEL-45][345-6]`")

    if len(st.session_state["variants"]) != len(st.session_state["urls"]):
        st.session_state["variants"] = [""] * len(st.session_state["urls"])

    urls = st.session_state["urls"]

    # Show editable rows
    for i, url in enumerate(urls):
        cols = st.columns([0.3, 3, 2, 2])
        with cols[0]:
            st.markdown(f"<span class='url-index'>#{i+1}</span>", unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f"<span class='url-text'>{url[:70]}{'…' if len(url)>70 else ''}</span>", unsafe_allow_html=True)
        with cols[2]:
            variant = st.text_input(
                "Variante",
                value=st.session_state["variants"][i],
                key=f"variant_{i}",
                label_visibility="collapsed",
                placeholder="ex: DEL-45_345-6",
            )
            st.session_state["variants"][i] = variant
        with cols[3]:
            final = build_name(template, i, variant)
            st.markdown(f"<span class='name-preview'>→ {final}.jpg</span>", unsafe_allow_html=True)

    # Build final names list
    st.session_state["names"] = [
        build_name(template, i, st.session_state["variants"][i])
        for i in range(len(urls))
    ]

    st.markdown("---")

    # ── ÉTAPE 4 : Téléchargement ──────────────────────────────────────────────
    st.markdown('<div class="section-label">④ Télécharger les images</div>', unsafe_allow_html=True)

    if st.button("🚀  Lancer le téléchargement"):
        urls = st.session_state["urls"]
        names = st.session_state["names"]
        results = []
        zip_buffer = io.BytesIO()

        progress_bar = st.progress(0)
        status_text = st.empty()
        log_area = st.empty()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            log_lines = []
            for i, (url, name) in enumerate(zip(urls, names)):
                status_text.markdown(f"⏳ Téléchargement `{name}` ({i+1}/{len(urls)})…")
                tmp_path = f"/tmp/gallica_{i}"
                ok, info = download_image(url, tmp_path)
                if ok:
                    ext = os.path.splitext(info)[1]
                    zf.write(info, f"{name}{ext}")
                    os.remove(info)
                    results.append({"#": i+1, "Fichier": f"{name}{ext}", "Statut": "✓ OK", "URL": url})
                    log_lines.append(f"✓  {name}{ext}")
                else:
                    results.append({"#": i+1, "Fichier": f"{name}", "Statut": f"✗ Erreur: {info[:60]}", "URL": url})
                    log_lines.append(f"✗  {name} — {info[:60]}")
                progress_bar.progress((i + 1) / len(urls))
                log_area.code("\n".join(log_lines[-15:]), language=None)

        st.session_state["download_results"] = results
        status_text.markdown("✅ **Téléchargement terminé !**")

        # Offer ZIP download
        ok_count = sum(1 for r in results if r["Statut"].startswith("✓"))
        err_count = len(results) - ok_count
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Images téléchargées", ok_count, delta=None)
        with col_b:
            st.metric("Erreurs", err_count, delta=None)

        zip_buffer.seek(0)
        st.download_button(
            label="📦  Télécharger le ZIP",
            data=zip_buffer,
            file_name="gallica_images.zip",
            mime="application/zip",
        )

        # Summary table
        st.markdown("**Récapitulatif**")
        df_res = pd.DataFrame(results)[["#", "Fichier", "Statut"]]
        st.dataframe(df_res, use_container_width=True, hide_index=True)
