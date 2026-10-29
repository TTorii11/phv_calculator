import streamlit as st
import datetime
import math
import sqlite3
import hashlib
import plotly.graph_objects as go

# --- ADATBÁZIS ÉS FELHASZNÁLÓKEZELÉS (SQLite) ---
def get_db():
    conn = sqlite3.connect("users_phv.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT,
            full_name TEXT
        )
    """)
    conn.commit()
    return conn

db = get_db()

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password, full_name):
    c = db.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?)", (username, hash_pw(password), full_name))
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def check_login(username, password):
    c = db.cursor()
    c.execute("SELECT full_name FROM users WHERE username = ? AND password_hash = ?", (username, hash_pw(password)))
    return c.fetchone()

# --- OLDAL BEÁLLÍTÁSAI ---
st.set_page_config(page_title="PHV Érési Kalkulátor", page_icon="⚽", layout="centered")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""

# --- HITELOSÍTÁSI FELÜLET ---
if not st.session_state.logged_in:
    st.title("⚽ Biológiai Érés & PHV Kalkulátor")
    st.info("Kérjük, jelentkezz be vagy regisztrálj a kalkulátor használatához!")

    tab_login, tab_reg = st.tabs(["Bejelentkezés", "Regisztráció"])

    with tab_login:
        with st.form("login_form"):
            login_user = st.text_input("Felhasználónév")
            login_pw = st.text_input("Jelszó", type="password")
            submitted = st.form_submit_button("Belépés")
            if submitted:
                user_match = check_login(login_user, login_pw)
                if user_match:
                    st.session_state.logged_in = True
                    st.session_state.user_name = user_match[0]
                    st.rerun()
                else:
                    st.error("Hibás felhasználónév vagy jelszó!")

    with tab_reg:
        with st.form("reg_form"):
            reg_name = st.text_input("Teljes név / Klub neve")
            reg_user = st.text_input("Választott felhasználónév")
            reg_pw = st.text_input("Jelszó", type="password")
            reg_submit = st.form_submit_button("Fiók létrehozása")
            if reg_submit:
                if reg_name and reg_user and reg_pw:
                    if register_user(reg_user, reg_pw, reg_name):
                        st.success("Sikeres regisztráció! Most már bejelentkezhetsz a bal oldali fülön.")
                    else:
                        st.error("Ez a felhasználónév már foglalt.")
                else:
                    st.warning("Kérjük, tölts ki minden mezőt!")
    st.stop()

# --- BEJELENTKEZETT FELÜLET ---
st.sidebar.markdown(f"**Bejelentkezve:** {st.session_state.user_name}")
if st.sidebar.button("Kijelentkezés"):
    st.session_state.logged_in = False
    st.rerun()

st.title("Biológiai Érés & PHV Becslés")
st.caption("Mirwald et al. (2002) algoritmus alapján")

# --- ADATBEVITEL ---
with st.form("phv_form"):
    col1, col2 = st.columns(2)
    with col1:
        player_name = st.text_input("Játékos neve", placeholder="Pl. Kiss Ádám")
        gender = st.selectbox("Neme", options=["Fiú", "Lány"])
        birth_date = st.date_input(
            "Születési dátum", 
            value=datetime.date(2012, 1, 1),
            min_value=datetime.date(2000, 1, 1),
            max_value=datetime.date.today()
        )
    with col2:
        standing_height = st.number_input("Álló testmagasság (cm)", min_value=100.0, max_value=230.0, value=152.0, step=0.1)
        sitting_height = st.number_input("Ülő magasság (cm)", min_value=50.0, max_value=130.0, value=78.0, step=0.1)
        weight = st.number_input("Testsúly (kg)", min_value=20.0, max_value=130.0, value=42.0, step=0.1)
    
    measure_date = st.date_input("Mérés dátuma", value=datetime.date.today())
    calc_button = st.form_submit_button("📊 Eredmény Kiszámítása")

# --- SZÁMÍTÁSI MOTOR ---
if calc_button:
    # 1. Életkor években
    age_days = (measure_date - birth_date).days
    chronological_age = age_days / 365.25

    if chronological_age < 8.0 or chronological_age > 18.0:
        st.warning("⚠️ Figyelem: A Mirwald-egyenlet megbízhatósága fiúknál 8–18 év, lányoknál 8–16 év között optimális.")

    # 2. Lábhossz és arány
    leg_length = standing_height - sitting_height
    ratio = sitting_height / leg_length

    # 3. Mirwald-formula (Maturity Offset becslés években)
    if gender == "Fiú":
        offset = (
            -9.236
            + (0.0002708 * (leg_length * sitting_height))
            + (-0.001663 * (chronological_age * leg_length))
            + (0.007216 * (chronological_age * sitting_height))
            + (0.02292 * ((weight / standing_height) * 100))
        )
        avg_phv_age = 13.8  # Átlagos PHV életkor fiúknál
    else:
        offset = (
            -9.376
            + (0.0001882 * (leg_length * sitting_height))
            + (0.0022 * (chronological_age * leg_length))
            + (0.005841 * (chronological_age * sitting_height))
            + (-0.002658 * (chronological_age * weight))
            + (0.07693 * ((weight / standing_height) * 100))
        )
        avg_phv_age = 12.0  # Átlagos PHV életkor lányoknál

    # 4. Becsült PHV kor és Biológiai kor eltérés
    predicted_phv_age = chronological_age - offset
    biological_diff = avg_phv_age - predicted_phv_age

    # Besorolás
    if biological_diff > 0.5:
        timing_status = "Korán érő (Early Maturing)"
        status_color = "red"
    elif biological_diff < -0.5:
        timing_status = "Későn érő (Late Maturing)"
        status_color = "blue"
    else:
        timing_status = "Átlagos ütemben érő (On-Time)"
        status_color = "green"

    st.markdown("---")
    st.subheader(f"Eredmények: {player_name if player_name else 'Játékos'}")

    res_col1, res_col2, res_col3 = st.columns(3)
    res_col1.metric("Kronológiai kor", f"{chronological_age:.2f} év")
    res_col2.metric("Maturity Offset (PHV-tól)", f"{offset:+.2f} év")
    res_col3.metric("Becsült PHV életkor", f"{predicted_phv_age:.2f} év")

    # Értelmező szöveg
    st.markdown(f"**Biológiai érési státusz:** :{status_color}[**{timing_status}**]")
    if offset < -1.0:
        st.write(f"📌 A játékos **{abs(offset):.1f} évvel** van a növekedési csúcs előtt (Pre-PHV szakasz). Aerob állóképesség, alap koordináció és technika fejlesztése ideális.")
    elif -1.0 <= offset <= 1.0:
        st.write(f"⚡ **A játékos épp a legintenzívebb növekedési fázisban van (Circa-PHV)!** Fokozott sérülésveszély (túlterheléses apophysitis, Osgood-Schlatter, koordinációs visszaesés).")
    else:
        st.write(f"🚀 A játékos **{offset:.1f} évvel** már túljutott a csúcson (Post-PHV). Megkezdhető a specifikus erő- és hipertrófia-edzés.")

    # Plotly Vizuális Skála
    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode = "gauge+number",
        value = offset,
        title = {'text': "PHV Offset (év: negatív = előtte, pozitív = utána)"},
        gauge = {
            'axis': {'range': [-3, 3]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [-3, -1], 'color': "lightblue"},
                {'range': [-1, 1], 'color': "orange"},
                {'range': [1, 3], 'color': "lightgreen"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': offset
            }
        }
    ))
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)
