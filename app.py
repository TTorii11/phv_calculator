import streamlit as st
import datetime
import hashlib
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client, Client

# --- OLDAL BEÁLLÍTÁSAI (Szélesebb, dashboard jellegű elrendezés) ---
st.set_page_config(page_title="PHV & Bio-Banding Dashboard", page_icon="⚽", layout="wide")

# --- EGYEDI CSS STÍLUSOK ---
st.markdown("""
<style>
    /* Fő fejléc banner */
    .hero-banner {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
        padding: 1.8rem 2rem;
        border-radius: 14px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .hero-banner h1 {
        color: white !important;
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
    }
    .hero-banner p {
        color: #cbd5e1;
        margin: 0.3rem 0 0 0;
        font-size: 1rem;
    }
    
    /* Metrika kártyák dobozolása */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    
    /* Sötét mód támogatása a kártyákhoz */
    @media (prefers-color-scheme: dark) {
        div[data-testid="stMetric"] {
            background-color: #1e293b;
            border-color: #334155;
        }
    }

    /* Státusz jelvény (Badge) */
    .status-badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 10px;
    }
    .badge-early { background-color: #fee2e2; color: #991b1b; border: 1px solid #f87171; }
    .badge-ontime { background-color: #dcfce7; color: #166534; border: 1px solid #4ade80; }
    .badge-late { background-color: #dbeafe; color: #1e40af; border: 1px solid #60a5fa; }
</style>
""", unsafe_allow_html=True)

# --- SUPABASE KAPCSOLAT INICIALIZÁLÁSA ---
@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception:
    st.error("⚠️ Hiányzó Supabase beállítások! Kérlek, állítsd be a SUPABASE_URL és SUPABASE_KEY értékeket a Streamlit Secrets-ben.")
    st.stop()

# --- SEGÉDFÜGGVÉNYEK ---
def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username: str, password: str, full_name: str) -> bool:
    existing = supabase.table("users").select("username").eq("username", username).execute()
    if existing.data:
        return False
    
    supabase.table("users").insert({
        "username": username,
        "password_hash": hash_pw(password),
        "full_name": full_name
    }).execute()
    return True

def check_login(username: str, password: str):
    res = supabase.table("users").select("full_name").eq("username", username).eq("password_hash", hash_pw(password)).execute()
    if res.data:
        return res.data[0]["full_name"]
    return None

def save_measurement(data: dict):
    supabase.table("measurements").insert(data).execute()

def get_user_measurements(username: str):
    res = supabase.table("measurements").select("*").eq("username", username).order("created_at", desc=True).execute()
    return res.data

def delete_measurements(ids: list):
    for record_id in ids:
        supabase.table("measurements").delete().eq("id", record_id).execute()

def render_phv_result(res: dict):
    """Közös, dizájnos megjelenítő függvény az eredményekhez és a grafikonhoz."""
    st.markdown("### 📊 Kiértékelés: **" + res['player_name'] + "**")

    # 4 fő metrika kártya
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📅 Kronológiai kor", f"{res['chronological_age']:.2f} év")
    c2.metric("🧬 Becsült biológiai kor", f"{res['estimated_bio_age']:.2f} év", f"{res['biological_diff']:+.2f} év eltérés")
    c3.metric("📈 Maturity Offset", f"{res['offset_val']:+.2f} év", help="Távolság a növekedési csúcstól (PHV) években")
    c4.metric("🎯 Várható PHV életkor", f"{res['predicted_phv_age']:.2f} év")

    st.write("") 

    # Kétoszlopos elrendezés: Bal oldalt szakmai elemzés, jobb oldalt a műszerfal
    left_col, right_col = st.columns([1.1, 1])

    with left_col:
        # Státusz jelvény
        badge_class = "badge-early" if res["biological_diff"] > 0.5 else ("badge-late" if res["biological_diff"] < -0.5 else "badge-ontime")
        st.markdown(f'<div>Érési ütem: <span class="status-badge {badge_class}">{res["timing_status"]}</span></div>', unsafe_allow_html=True)

        offset = res["offset_val"]
        if offset < -1.0:
            st.info(
                f"🌱 **Pre-PHV szakasz ({abs(offset):.1f} évvel a csúcs előtt)**\n\n"
                "**Edzésmódszertani fókusz (Neurális adaptáció & Mozgásműveltség):** "
                "Ebben a korban az idegrendszer rendkívül fogékony! Az alapvető motoros kontroll kulcsa az **erőfejlesztés korai elkezdése** "
                "(saját testsúlyos alapmozgások, medicinlabda, kézisúlyzók, helyes guggolás/kitörés/húzás-tolás minták megtanulása). "
                "Nem az izomtömeg-növelés (hipertrófia), hanem az **ideg-izom koordináció, a robbanékonyság, a sebesség és a csontozat felkészítése** a cél, "
                "rövid, minőségi (10-20 perces) blokkokban, korai túl-specializáció helyett sokoldalú mozgással."
            )
        elif -1.0 <= offset <= 1.0:
            st.warning(
                f"⚡ **Circa-PHV szakasz – Intenzív növekedési zóna ({offset:+.2f} év)**\n\n"
                "**Edzésmódszertani fókusz (Mechanikai terhelés kontrollja):** "
                "A csontváz gyorsabban nő, mint az izomzat, ami átmeneti koordinációs visszaesést és növekedési zóna érzékenységet okozhat. "
                "**Fontos:** Ilyenkor nem az erőedzést kell elhagyni, hanem a feleslegesen magas futó-/ütközéses volument (*weightbearing load*) érdemes mérsékelni, "
                "miközben a **kontrollált erőedzés és törzsstabilitás (core, excentrikus kontroll)** kifejezetten védi az ízületeket és csökkenti a sérülésveszélyt!"
            )
        else:
            st.success(
                f"🚀 **Post-PHV szakasz ({offset:.1f} évvel a csúcson túl)**\n\n"
                "**Edzésmódszertani fókusz (Strukturális és hormonális adaptáció):** "
                "A hossznövekedés lelassult, a hormonális háttér (tesztoszteron, GH) most már a valódi izomkeresztmetszet-növekedést (hipertrófiát) is támogatja. "
                "A korábban felépített mozgásmintákra (technikai alapokra) ráépíthető a komolyabb **rúddal végzett (barbell) maximális erő- és robbanékonyság-fejlesztés**, "
                "valamint a magasabb edzésvolumen és intenzitástűrő képesség kialakítása."
            )

        # Testarányok kis táblázata
        leg_len = round(res['standing_height'] - res['sitting_height'], 1)
        sitting_ratio = round((res['sitting_height'] / res['standing_height']) * 100, 1)
        st.caption(f"📐 **Antropometriai részletek:** Álló: `{res['standing_height']} cm` | Ülő: `{res['sitting_height']} cm` | Lábhossz: `{leg_len} cm` | Törzs-arány: `{sitting_ratio}%` | Súly: `{res['weight']} kg`")

    with right_col:
        fig = go.Figure()
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=offset,
            number={'suffix': " év", 'font': {'size': 28}},
            title={'text': "Maturity Offset Skála (PHV = 0.0)", 'font': {'size': 15}},
            gauge={
                'axis': {'range': [-3.5, 3.5], 'tickwidth': 1},
                'bar': {'color': "#1e293b", 'thickness': 0.3},
                'steps': [
                    {'range': [-3.5, -1.0], 'color': "#93c5fd"}, # Pre-PHV (kék)
                    {'range': [-1.0, 1.0], 'color': "#fde047"},  # Circa-PHV (sárga)
                    {'range': [1.0, 3.5], 'color': "#86efac"}    # Post-PHV (zöld)
                ],
                'threshold': {
                    'line': {'color': "#dc2626", 'width': 5},
                    'thickness': 0.8,
                    'value': offset
                }
            }
        ))
        fig.update_layout(height=260, margin=dict(l=25, r=25, t=45, b=15), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

# --- SESSION STATE ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.full_name = ""

if "last_result" not in st.session_state:
    st.session_state.last_result = None

# --- HITELOSÍTÁSI FELÜLET (HA NINCS BELÉPVE) ---
if not st.session_state.logged_in:
    st.markdown("""
    <div class="hero-banner">
        <h1>⚽ Biológiai Érés & PHV Analitika</h1>
        <p>Sporttudományi kalkulátor és játékos-nyilvántartó rendszer (Mirwald-protokoll)</p>
    </div>
    """, unsafe_allow_html=True)

    col_spacer1, col_auth, col_spacer2 = st.columns([1, 1.5, 1])
    with col_auth:
        tab_login, tab_reg = st.tabs(["🔑 Bejelentkezés", "📝 Regisztráció"])

        with tab_login:
            with st.form("login_form"):
                login_user = st.text_input("Felhasználónév").strip()
                login_pw = st.text_input("Jelszó", type="password")
                submitted = st.form_submit_button("Belépés a rendszerbe", use_container_width=True, type="primary")
                if submitted:
                    full_name = check_login(login_user, login_pw)
                    if full_name:
                        st.session_state.logged_in = True
                        st.session_state.username = login_user
                        st.session_state.full_name = full_name
                        st.rerun()
                    else:
                        st.error("Hibás felhasználónév vagy jelszó!")

        with tab_reg:
            with st.form("reg_form"):
                reg_name = st.text_input("Teljes név / Klub vagy Akadémia neve").strip()
                reg_user = st.text_input("Választott felhasználónév").strip()
                reg_pw = st.text_input("Jelszó", type="password")
                reg_submit = st.form_submit_button("Ingyenes fiók létrehozása", use_container_width=True)
                if reg_submit:
                    if reg_name and reg_user and reg_pw:
                        if register_user(reg_user, reg_pw, reg_name):
                            st.success("Sikeres regisztráció! Most már beléphetsz a Bejelentkezés fülön.")
                        else:
                            st.error("Ez a felhasználónév már foglalt.")
                    else:
                        st.warning("Kérjük, tölts ki minden mezőt!")
    st.stop()

# --- OLDALSÁV (SIDEBAR) ---
with st.sidebar:
    st.markdown("### 👤 Profil")
    st.markdown(f"**{st.session_state.full_name}**")
    st.caption(f"Azonosító: `{st.session_state.username}`")
    st.markdown("---")
    st.markdown("### 💡 Gyors útmutató")
    st.caption(
        "**Maturity Offset:** Megmutatja, hány évre van a játékos a leggyorsabb növekedési fázistól (PHV).\n\n"
        "• **-1.0 alatt:** Pre-PHV (Előtte)\n"
        "• **-1.0 és +1.0 között:** Circa-PHV (Növekedési lökés alatt)\n"
        "• **+1.0 felett:** Post-PHV (Utána)"
    )
    st.markdown("---")
    if st.button("🚪 Kijelentkezés", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.last_result = None
        st.rerun()

# --- FŐ FEJLÉC ---
st.markdown("""
<div class="hero-banner">
    <h1>⚽ Biológiai Érés & PHV Dashboard</h1>
    <p>Antropometriai mérések, biológiai életkor becslés és csapat-szintű Bio-Banding áttekintés</p>
</div>
""", unsafe_allow_html=True)

tab_calc, tab_history = st.tabs(["📏 Új mérés rögzítése", "🗂️ Játékosok & Csapat Áttekintés"])

# --- 1. FÜL: ÚJ MÉRÉS ---
with tab_calc:
    with st.container(border=True):
        st.subheader("Adatbevitel")
        with st.form("phv_form", border=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                player_name = st.text_input("🏃 Játékos neve", placeholder="Pl. Kiss Ádám")
                gender = st.selectbox("🚻 Neme", options=["Fiú", "Lány"])
            with col2:
                birth_date = st.date_input(
                    "🎂 Születési dátum", 
                    value=datetime.date(2013, 1, 1),
                    min_value=datetime.date(2000, 1, 1),
                    max_value=datetime.date.today()
                )
                measure_date = st.date_input("📅 Mérés dátuma", value=datetime.date.today())
            with col3:
                standing_height = st.number_input("📏 Álló testmagasság (cm)", min_value=100.0, max_value=230.0, value=152.0, step=0.1)
                sitting_height = st.number_input("🪑 Ülő magasság (cm)", min_value=50.0, max_value=130.0, value=78.0, step=0.1)
                weight = st.number_input("⚖️ Testsúly (kg)", min_value=20.0, max_value=130.0, value=42.0, step=0.1)
            
            calc_button = st.form_submit_button("📊 Számítás és Mentés az adatbázisba", type="primary", use_container_width=True)

    if calc_button:
        if standing_height <= sitting_height:
            st.error("Hiba: Az álló magasságnak nagyobbnak kell lennie, mint az ülő magasságnak!")
        else:
            age_days = (measure_date - birth_date).days
            chronological_age = age_days / 365.25

            if chronological_age < 8.0 or chronological_age > 18.0:
                st.warning("⚠️ Figyelem: A Mirwald-egyenlet megbízhatósága 8 és 18 éves kor között optimális.")

            leg_length = standing_height - sitting_height

            if gender == "Fiú":
                offset = (
                    -9.236
                    + (0.0002708 * (leg_length * sitting_height))
                    + (-0.001663 * (chronological_age * leg_length))
                    + (0.007216 * (chronological_age * sitting_height))
                    + (0.02292 * ((weight / standing_height) * 100))
                )
                avg_phv_age = 13.8
            else:
                offset = (
                    -9.376
                    + (0.0001882 * (leg_length * sitting_height))
                    + (0.0022 * (chronological_age * leg_length))
                    + (0.005841 * (chronological_age * sitting_height))
                    + (-0.002658 * (chronological_age * weight))
                    + (0.07693 * ((weight / standing_height) * 100))
                )
                avg_phv_age = 12.0

            predicted_phv_age = chronological_age - offset
            biological_diff = avg_phv_age - predicted_phv_age
            estimated_bio_age = chronological_age + biological_diff

            if biological_diff > 0.5:
                timing_status = "Korán érő (Early)"
            elif biological_diff < -0.5:
                timing_status = "Későn érő (Late)"
            else:
                timing_status = "Átlagos (On-Time)"

            clean_name = player_name.strip() if player_name.strip() else "Névtelen játékos"

            record = {
                "username": st.session_state.username,
                "player_name": clean_name,
                "gender": gender,
                "birth_date": str(birth_date),
                "measure_date": str(measure_date),
                "standing_height": round(standing_height, 1),
                "sitting_height": round(sitting_height, 1),
                "weight": round(weight, 1),
                "chronological_age": round(chronological_age, 2),
                "offset_val": round(offset, 2),
                "predicted_phv_age": round(predicted_phv_age, 2),
                "timing_status": timing_status
            }
            save_measurement(record)
            st.toast("✅ Mérés sikeresen elmentve!")

            st.session_state.last_result = {
                **record,
                "estimated_bio_age": round(estimated_bio_age, 2),
                "biological_diff": round(biological_diff, 2)
            }

    if st.session_state.last_result:
        st.write("")
        with st.container(border=True):
            render_phv_result(st.session_state.last_result)

# --- 2. FÜL: KORÁBBI MÉRÉSEK & CSAPAT ÁTTEKINTÉS ---
with tab_history:
    history = get_user_measurements(st.session_state.username)
    
    if history:
        df = pd.DataFrame(history)
        
        avg_phv_series = df["gender"].apply(lambda g: 13.8 if g == "Fiú" else 12.0)
        df["biological_diff"] = (avg_phv_series - df["predicted_phv_age"]).round(2)
        df["estimated_bio_age"] = (df["chronological_age"] + df["biological_diff"]).round(2)

        # --- CSAPAT BIO-BANDING GRAFIKON ---
        with st.container(border=True):
            st.subheader("📊 Csapat PHV Eloszlás (Maturity Offset áttekintés)")
            st.caption("A sárga sáv (-1.0 és +1.0 év között) jelöli a növekedési lökésben lévő, fokozott figyelmet igénylő játékosokat.")
            
            fig_team = go.Figure()
            fig_team.add_vrect(x0=-1.0, x1=1.0, fillcolor="orange", opacity=0.15, line_width=0, annotation_text="Circa-PHV zóna", annotation_position="top left")
            fig_team.add_vline(x=0, line_dash="dash", line_color="red")

            bar_colors = ["#ef4444" if d > 0.5 else ("#3b82f6" if d < -0.5 else "#22c55e") for d in df["biological_diff"]]
            
            fig_team.add_trace(go.Bar(
                x=df["offset_val"],
                y=df["player_name"] + " (" + df["measure_date"] + ")",
                orientation='h',
                marker_color=bar_colors,
                text=df["offset_val"].apply(lambda x: f"{x:+.2f} év"),
                textposition="outside"
            ))
            fig_team.update_layout(
                xaxis_title="Maturity Offset (év a PHV-tól)",
                yaxis=dict(autorange="reversed"),
                height=max(250, len(df) * 38),
                margin=dict(l=20, r=40, t=20, b=20)
            )
            st.plotly_chart(fig_team, use_container_width=True)

        # --- ADATTÁBLA ÉS EXPORT ---
        with st.container(border=True):
            col_title, col_dl = st.columns([3, 1])
            col_title.subheader("📋 Rögzített mérések táblázata")
            
            display_cols = {
                "player_name": "Játékos",
                "measure_date": "Mérés dátuma",
                "gender": "Nem",
                "chronological_age": "Kronológiai kor (év)",
                "estimated_bio_age": "Biológiai kor (év)",
                "biological_diff": "Eltérés (év)",
                "offset_val": "PHV Offset (év)",
                "predicted_phv_age": "Becsült PHV kor",
                "timing_status": "Érési státusz",
                "standing_height": "Magasság (cm)",
                "sitting_height": "Ülőmagasság (cm)",
                "weight": "Súly (kg)"
            }
            
            df_filtered = df[list(display_cols.keys())].rename(columns=display_cols)
            
            csv = df_filtered.to_csv(index=False).encode('utf-8-sig')
            col_dl.download_button(
                label="📥 Excel (CSV) letöltése",
                data=csv,
                file_name="phv_meresek_export.csv",
                mime="text/csv",
                use_container_width=True,
                type="primary"
            )

            st.dataframe(df_filtered, use_container_width=True, hide_index=True)

        # --- EGYÉNI JÁTÉKOS KÁRTYA ÚJRAMEGJELENÍTÉSE ---
        with st.container(border=True):
            st.subheader("🔍 Egyéni játékos profil megtekintése")
            record_options = {
                f"{row['player_name']} ({row['measure_date']}) – Bio kor: {row['estimated_bio_age']} év ({row['timing_status']})": row 
                for _, row in df.iterrows()
            }
            selected_label = st.selectbox("Válassz egy mérést a részletes adatlap megnyitásához:", options=list(record_options.keys()))
            if selected_label:
                sel_row = record_options[selected_label]
                st.markdown("---")
                render_phv_result({
                    "player_name": sel_row["player_name"],
                    "chronological_age": sel_row["chronological_age"],
                    "estimated_bio_age": sel_row["estimated_bio_age"],
                    "biological_diff": sel_row["biological_diff"],
                    "offset_val": sel_row["offset_val"],
                    "predicted_phv_age": sel_row["predicted_phv_age"],
                    "timing_status": sel_row["timing_status"],
                    "standing_height": sel_row["standing_height"],
                    "sitting_height": sel_row["sitting_height"],
                    "weight": sel_row["weight"]
                })

        # --- MÉRÉSEK TÖRLÉSE ---
        with st.expander("🗑️ Hibás vagy felesleges mérések törlése"):
            delete_options = {
                f"#{row['id']} - {row['player_name']} ({row['measure_date']})": row['id'] 
                for _, row in df.iterrows()
            }
            selected_to_delete = st.multiselect(
                "Válaszd ki a törölni kívánt méréseket:",
                options=list(delete_options.keys())
            )
            if st.button("Kijelölt mérések végleges törlése", type="primary"):
                if selected_to_delete:
                    ids_to_remove = [delete_options[label] for label in selected_to_delete]
                    delete_measurements(ids_to_remove)
                    st.success("A kijelölt méréseket sikeresen töröltük!")
                    st.rerun()
                else:
                    st.warning("Először válassz ki legalább egy mérést a listából!")
    else:
        st.info("Még nincs elmentett mérésed. Rögzíts egyet az 'Új mérés rögzítése' fülön!")
