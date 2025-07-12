# streamlit_book_recommender.py —  Nool Sakā “book-buddy”
# ---------------------------------------------------------------------------
# pastel wallpaper · interactive placeholders · enlarged QR listing all recos 1-N
# ranking: same-author → Indian-genre → Tamil-genre → Foreign-genre
# ---------------------------------------------------------------------------

from pathlib import Path
from typing import List
import difflib, io, pandas as pd, streamlit as st
from streamlit_searchbox import st_searchbox      # autosuggest component
import qrcode                                     # QR generator
from PIL import Image                             # for resizing

# ───────────────────────── 1 • PAGE STYLE ─────────────────────────
st.set_page_config("📚 Nool Sakā — Your Book Buddy", "📖", layout="wide")
st.markdown("""
<style>
html,body,.stApp {
  background: #FFF9C4;
  color: #111;
  font-family: 'Segoe UI', sans-serif;
}
body:before {
  content: '';
  position: fixed;
  inset: 0;
  background: url("data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0iI0ZGRUIwMCIgZD0iTTcgMkgyMXYxOC03SDBaIi8+PC9zdmc+") repeat;
  opacity: .25;
  pointer-events: none;
  z-index: -2;
}
body:after {
  content: '';
  position: fixed;
  inset: 0;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='60' height='60'><text x='50%' y='50%' text-anchor='middle' dominant-baseline='middle' font-size='48'>📚</text></svg>") repeat;
  background-size: 120px 120px;
  opacity: .12;
  pointer-events: none;
  z-index: -1;
}
.hero-main {
  position: relative;
  background: #FFC400;
  color: #000;
  font-size: 2.4rem;
  font-weight: 800;
  text-align: center;
  padding: 1rem 0;
  margin: -2rem -2rem 0;
}
.hero-main:after {
  content: '';
  position: absolute;
  inset: 0;
  opacity: .15;
  pointer-events: none;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80'><text x='50%' y='50%' text-anchor='middle' dominant-baseline='middle' font-size='64'>📚</text></svg>") repeat;
  background-size: 80px 80px;
}
.hero-sub {
  background: #FFFDE7;
  color: #000;
  font-size: 1.3rem;
  font-weight: 600;
  text-align: center;
  padding: .6rem 0;
  margin: 0 -2rem;
}
.footer-credit {
  text-align: right;
  font-size: .95rem;
  font-weight: 600;
  color: #333;
  margin: .4rem 0 3rem;
}
section[data-testid="stSidebar"] > div:first-child {
  background: #ECEFF1;
}
.section-header {
  background: #A9A9A9;
  color: #000000;
  padding: .8rem 1rem;
  font-weight: 600;
  border-radius: 10px;
}
.stDataFrame {
  background: #fff!important;
  border: 3px solid #FFC400;
  border-radius: 12px;
}
button[kind="primary"] {
  border-radius: 12px;
  font-weight: 800;
  background: #FFC400;
  border: none;
  color: #000;
  padding: .45rem 1.2rem;
}
button[kind="primary"]:hover {
  filter: brightness(110%);
  transform: translateY(-2px);
}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="hero-main">📚 BOOK RECOMMENDER</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Nool Sakā — Your Pudhaga Buddy!</div>', unsafe_allow_html=True)
st.markdown('<p class="footer-credit">Powered by Black Board Learning</p>', unsafe_allow_html=True)
celebrate = lambda: st.balloons()

# ───────────────────────── 2 • DATA LOADER ───────────────────────
DEFAULT_PATH = Path("Book List1.csv")

@st.cache_data(show_spinner=False)
def load_dataset(path: Path) -> pd.DataFrame:
    def canonical(df: pd.DataFrame) -> pd.DataFrame:
        clean = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}
        alias = lambda *alts: next((clean[a] for a in alts if a in clean), None)
        rename = {}
        for canon, alts in {
            "Book Name": ("bookname","book","title"),
            "Author":    ("author","authors"),
            "Genre":     ("genre","category")
        }.items():
            key = alias(*alts)
            if not key:
                raise ValueError(f"Missing {canon} column")
            rename[key] = canon

        rating = alias("averageratings","averagerating","avg")
        count  = alias("totalratings","numberofratings","ratingscount")
        nat    = alias("nationality","country","origin")

        if rating:
            rename[rating] = "Average Rating"
            df[rating] = pd.to_numeric(df[rating], errors="coerce").fillna(0).round(2)
        else:
            df["Average Rating"] = 0.0

        if count:
            rename[count] = "Number of Ratings"
            df[count] = pd.to_numeric(df[count], errors="coerce").fillna(0).astype(int)
        else:
            df["Number of Ratings"] = 0

        if nat:
            rename[nat] = "Nationality"

        # preserve any extra columns like Stall Number and Publisher
        return df.rename(columns=rename)

    raw = pd.read_excel(path) if path.suffix.lower()==".xlsx" else pd.read_csv(path, encoding="latin1")
    df  = canonical(raw).fillna("")
    df["_title_lc"]  = df["Book Name"].str.lower().str.strip()
    df["_author_lc"] = df["Author"].str.lower().str.strip()
    return df

# ───────────────────────── 3 • MATCH & RESOLVE ───────────────────
def resolve(df: pd.DataFrame, text: str) -> pd.Series:
    frag      = text.lower().strip()
    by_author = df[df["_author_lc"].str.contains(frag)]
    if len(by_author):
        return by_author.iloc[0]
    by_title = df[df["_title_lc"].str.contains(frag)]
    if len(by_title):
        return by_title.iloc[0]
    combos = (df["_title_lc"]+"|"+df["_author_lc"]).tolist()
    best   = difflib.get_close_matches(frag, combos, 1, 0.3)
    if not best:
        st.error(f"No close match for '{text}'."); st.stop()
    return df[(df["_title_lc"]+"|"+df["_author_lc"])==best[0]].iloc[0]

# ───────────────────────── 4 • RECOMMENDER ───────────────────────
def recommend(df: pd.DataFrame, favs: List[pd.Series], top: int = 10) -> pd.DataFrame:
    df = df.copy()
    df["Is Indian"] = df["Author"].str.lower().str.contains("|".join([
        "tagore","narayan","desai","nair","mistry","gosh","bhagat","murthy","rao","sahni"
    ]))
    df["Is Tamil"]  = df["Author"].str.lower().str.contains("|".join([
        "kalki","jeyamohan","vaasan","vairamuthu","sivashankari","sujatha",
        "imbam","charu","nivedita","imayam","magan","ananth","pandian"
    ]))

    fav_idx = {r.name for r in favs}
    authors = {r["Author"] for r in favs}
    genres  = {r["Genre"] for r in favs if r.get("Genre")}

    same_author = pd.concat([
        df[(df["Author"]==a)&(~df.index.isin(fav_idx))]
          .nlargest(3, ["Average Rating","Number of Ratings"])
        for a in authors
    ], ignore_index=False) if authors else pd.DataFrame()

    pool    = df[(df["Genre"].isin(genres)) & (~df.index.isin(fav_idx|set(same_author.index)))]
    indian  = pool[(pool["Is Indian"]) & (~pool["Is Tamil"])]
    tamil   = pool[pool["Is Tamil"]]
    foreign = pool[~pool["Is Indian"]]

    ranked = pd.concat([
        same_author,
        indian.nlargest(top,   ["Average Rating","Number of Ratings"]),
        tamil.nlargest(top,    ["Average Rating","Number of Ratings"]),
        foreign.nlargest(top,  ["Average Rating","Number of Ratings"]),
    ], ignore_index=False)

    if len(ranked) < top:
        rest = df[~df.index.isin(ranked.index)]
        ranked = pd.concat([
            ranked,
            rest[(rest["Is Indian"]) & (~rest["Is Tamil"])].nlargest(top, ["Average Rating","Number of Ratings"]),
            rest[rest["Is Tamil"]].nlargest(top, ["Average Rating","Number of Ratings"]),
            rest[~rest["Is Indian"]].nlargest(top, ["Average Rating","Number of Ratings"]),
        ], ignore_index=False)

    return ranked.drop_duplicates("Book Name").head(top)

# ───────────────────────── 5 • SIDEBAR & UPLOAD ─────────────────
st.sidebar.header("🛠 Settings")
st.sidebar.write("📂 **Upload CSV/XLSX — drop it here!**")
uploaded   = st.sidebar.file_uploader("", type=["csv","xlsx"])
data_path  = DEFAULT_PATH if uploaded is None else Path(uploaded.name)
if uploaded:
    data_path.write_bytes(uploaded.getbuffer())

rec_n   = st.sidebar.slider("🔢 **How many recos?**", 5, 25, 10, 1)
ratings = st.sidebar.checkbox("⭐ Show rating columns", True)

df      = load_dataset(data_path)
options = sorted(set(df["Book Name"]) | set(df["Author"]))

# ───────────────────────── 6 • INTERACTIVE INPUTS ───────────────
st.markdown('<div class="section-header">🤗 Hey buddy! Pick up to 3 books/authors you love:</div>', unsafe_allow_html=True)

def sugg(term: str) -> list[str]:
    if not term:
        return []
    term = term.lower()
    return [o for o in options if term in o.lower()][:30]

favs  = []
pick1 = st_searchbox(sugg, placeholder="🤔 What's got you hooked right now?", key="pick1")
if pick1:
    favs.append(pick1)
    pick2 = st_searchbox(sugg, placeholder="🔍 Got another fav? Share it!", key="pick2")
else:
    pick2 = None
if pick2:
    favs.append(pick2)
    pick3 = st_searchbox(sugg, placeholder="🎯 One last pick to seal the deal?", key="pick3")
else:
    pick3 = None
if pick3:
    favs.append(pick3)

st.markdown(
    '<p style="font-size:0.9rem;color:#555;margin-top:0.5rem;">'
    'The more you share, the sharper your recos become! 😉'
    '</p>',
    unsafe_allow_html=True
)

# ───────────────────────── 7 • ACTION & OUTPUTS ──────────────────
def build_qr_payload(df_out: pd.DataFrame) -> str:
    lines = [f"{i}. {r['Book Name']} — {r['Author']}"
             for i, (_, r) in enumerate(df_out.iterrows(), start=1)]
    return "\n".join(lines)[:4200]

if st.button("🚀 Get my recos!", use_container_width=True):
    if not favs:
        st.warning("Buddy, gimme at least ONE favourite first!"); st.stop()

    fav_rows = [resolve(df, x) for x in favs]
    recs     = recommend(df, fav_rows, rec_n)
    cols     = ["Book Name","Author","Genre","Publisher","Stall Number"] + (["Average Rating","Number of Ratings"] if ratings else [])

    st.markdown('<div class="section-header">✨ Your custom picks are here!</div>', unsafe_allow_html=True)
    st.dataframe(recs[cols], hide_index=True)
    celebrate()

    left, mid, right = st.columns(3)
    with left:
        st.download_button("⬇️ Download CSV",
            recs[cols].to_csv(index=False).encode("utf-8"),
            "noolsaka_recs.csv","text/csv"
        )
    with mid:
        st.download_button("⬇️ Download JSON",
            recs[cols].to_json(orient="records",indent=2).encode("utf-8"),
            "noolsaka_recs.json","application/json"
        )
    with right:
        qr_text = build_qr_payload(recs[cols])
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=4)
        qr.add_data(qr_text); qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((260,260), resample=Image.NEAREST)
        buf = io.BytesIO(); img.save(buf, format="PNG")
        st.image(buf.getvalue(), caption="📱 Scan to grab your picks", width=260)
        st.download_button("⬇️ QR PNG", buf.getvalue(), "noolsaka_recs.png", "image/png")
