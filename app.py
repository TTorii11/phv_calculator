import streamlit as st
import datetime
import hashlib
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client, Client

# --- OLDAL BEÁLLÍTÁSAI ---
st.set_page_config(page_title="PHV Érési Kalkulátor", page_icon="⚽", layout="centered")

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
    """Közös megjelenítő függvény az eredményekhez és a grafikonhoz."""
    st.markdown("---")
    st.subheader(f"Eredmények: {res['player_name']}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kronológiai kor", f"{res['chronological_age']:.2f} év")
    c2.metric("Becsült biológiai kor", f"{res['estimated_bio_age']:.2f} év", f"{res['biological_diff']:+.2f} év")
    c3.metric("Maturity Offset", f"{res['offset_val']:+.2f} év")
    c4.metric("PHV életkor", f"{res['predicted_phv_age']:.2f} év")

    st.markdown(f"**Biológiai érési státusz:** :{res['status_color']}[**{res['timing_status']}**]")

    offset = res["offset_val"]
    if offset < -1.0:
        st.write(f"📌 A játékos **{abs(offset):.1f} évvel** van a növekedési csúcs előtt (Pre-PHV szakasz). Aerob állóképesség, alap koordináció és technika fejlesztése ideális.")
    elif -1.0 <= offset <= 1.0:
        st.write("⚡ **A játékos épp a legintenzívebb növekedési fázisban van (Circa-PHV)!** Fokozott sérülésveszély (túlterheléses panaszok, Osgood-Schlatter, átmeneti koordinációs visszaesés).")
    else:
        st.write(f"🚀 A játékos **{offset:.1f} évvel** már túljutott a csúcson (Post-PHV). Megkezdhető a specifikus erő- és hipertrófia-edzés.")

    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=offset,
        title={'text': f"{res['player_name']} – PHV Offset (év a növekedési csúcstól)"},
        gauge={
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
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
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
    st.title("⚽ Biológiai Érés & PHV Kalkulátor")
    st.info("Jelentkezz be vagy regisztrálj a mérések elvégzéséhez és mentéséhez!")

    tab_login, tab_reg = st.tabs(["Bejelentkezés", "Regisztráció"])

    with tab_login:
        with st.form("login_form"):
            login_user = st.text_input("Felhasználónév").strip()
            login_pw = st.text_input("Jelszó", type="password")
            submitted = st.form_submit_button("Belépés")
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
            reg_name = st.text_input("Teljes név / Klub neve").strip()
            reg_user = st.text_input("Választott felhasználónév").strip()
            reg_pw = st.text_input("Jelszó", type="password")
            reg_submit = st.form_submit_button("Fiók létrehozása")
            if reg_submit:
                if reg_name and reg_user and reg_pw:
                    if register_user(reg_user, reg_pw, reg_name):
                        st.success("Sikeres regisztráció! Most már bejelentkezhetsz a Bejelentkezés fülön.")
                    else:
                        st.error("Ez a felhasználónév már foglalt.")
                else:
                    st.warning("Kérjük, tölts ki minden mezőt!")
    st.stop()

# --- BEJELENTKEZETT FELÜLET ---
st.sidebar.markdown(f"👤 **{st.session_state.full_name}**")
st.sidebar.caption(f"Felhasználó: `{st.session_state.username}`")
if st.sidebar.button("Kijelentkezés"):
    st.session_state.logged_in = False
    st.session_state.last_result = None
    st.rerun()

st.title("Biológiai Érés & PHV Becslés")
st.caption("Mirwald et al. (2002) protokoll alapján – Felhős adatmentéssel")

tab_calc, tab_history = st.tabs(["📏 Új mérés", "🗂️ Korábbi mérések"])

with tab_calc:
    with st.form("phv_form"):
        col1, col2 = st.columns(2)
        with col1:
            player_name = st.text_input("Játékos neve", placeholder="Pl. Kiss Ádám")
            gender = st.selectbox("Neme", options=["Fiú", "Lány"])
            birth_date = st.date_input(
                "Születési dátum", 
                value=datetime.date(2013, 1, 1),
                min_value=datetime.date(2000, 1, 1),
                max_value=datetime.date.today()
            )
        with col2:
            standing_height = st.number_input("Álló testmagasság (cm)", min_value=100.0, max_value=230.0, value=152.0, step=0.1)
            sitting_height = st.number_input("Ülő magasság (cm)", min_value=50.0, max_value=130.0, value=78.0, step=0.1)
            weight = st.number_input("Testsúly (kg)", min_value=20.0, max_value=130.0, value=42.0, step=0.1)
        
        measure_date = st.date_input("Mérés dátuma", value=datetime.date.today())
        calc_button = st.form_submit_button("📊 Számítás és Mentés")

    if calc_button:
        if standing_height <= sitting_height:
            st.error("Az álló magasságnak nagyobbnak kell lennie, mint az ülő magasságnak!")
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
                status_color = "red"
            elif biological_diff < -0.5:
                timing_status = "Későn érő (Late)"
                status_color = "blue"
            else:
                timing_status = "Átlagos (On-Time)"
                status_color = "green"

            clean_name = player_name.strip() if player_name.strip() else "Névtelen játékos"

            # Mentés Supabase-be
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
            st.toast("✅ Mérés elmentve az adatbázisba!")

            # Eltároljuk a session_state-ben, hogy ne tűnjön el a grafikon!
            st.session_state.last_result = {
                **record,
                "estimated_bio_age": round(estimated_bio_age, 2),
                "biological_diff": round(biological_diff, 2),
                "status_color": status_color
            }

    # Ha van kiszámolt eredmény a munkamenetben, mindig megjelenítjük
    if st.session_state.last_result:
        render_phv_result(st.session_state.last_result)

with tab_history:
    st.subheader("Korábban rögzített játékosok")
    history = get_user_measurements(st.session_state.username)
    
    if history:
        df = pd.DataFrame(history)
        
        # Kiszámoljuk a biológiai életkort és az eltérést minden sorra (visszamenőleg is!)
        avg_phv_series = df["gender"].apply(lambda g: 13.8 if g == "Fiú" else 12.0)
        df["biological_diff"] = (avg_phv_series - df["predicted_phv_age"]).round(2)
        df["estimated_bio_age"] = (df["chronological_age"] + df["biological_diff"]).round(2)

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
        st.dataframe(df_filtered, use_container_width=True, hide_index=True)
        
        csv = df_filtered.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Letöltés Excel (CSV) formátumban",
            data=csv,
            file_name="phv_meresek.csv",
            mime="text/csv"
        )

        st.markdown("---")
        
        # --- KORÁBBI GRAFIKON ÚJRAMEGJELENÍTÉSE ---
        st.subheader("📈 Korábbi mérés grafikonjának megtekintése")
        record_options = {
            f"{row['player_name']} ({row['measure_date']}) – Bio kor: {row['estimated_bio_age']} év": row 
            for _, row in df.iterrows()
        }
        selected_label = st.selectbox("Válassz egy játékost a listából:", options=list(record_options.keys()))
        if selected_label:
            sel_row = record_options[selected_label]
            color = "red" if sel_row["biological_diff"] > 0.5 else ("blue" if sel_row["biological_diff"] < -0.5 else "green")
            render_phv_result({
                "player_name": sel_row["player_name"],
                "chronological_age": sel_row["chronological_age"],
                "estimated_bio_age": sel_row["estimated_bio_age"],
                "biological_diff": sel_row["biological_diff"],
                "offset_val": sel_row["offset_val"],
                "predicted_phv_age": sel_row["predicted_phv_age"],
                "timing_status": sel_row["timing_status"],
                "status_color": color
            })

        st.markdown("---")

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
        st.info("Még nincs elmentett mérésed.")
