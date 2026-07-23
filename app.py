from datetime import date
import random
import re
import sqlite3
import time
import unicodedata
import pandas as pd
import streamlit as st

# הגדרות עמוד (חייב להיות הקריאה הראשונה של Streamlit)
st.set_page_config(
    page_title="NBA Mystery Player", page_icon="🏀", layout="wide"
)

st.title("NBA Guess The Player")

# CSS מקיף לעיצוב Dark Mode
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    .main-title {
        text-align: center;
        font-size: 2.8rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin-bottom: 5px;
    }
    .main-title .gradient-text {
        background: linear-gradient(135deg, #ff7e5f, #feb47b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .main-title .icon {
        font-style: normal;
        display: inline-block;
    }
    .sub-title {
        text-align: center;
        color: #94a3b8;
        font-size: 1.1rem;
        font-weight: 500;
        margin-bottom: 25px;
    }
    .hint-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
    }
    .hint-title {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .hint-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: #38bdf8;
    }
    [data-testid="stDataFrame"] {
        background-color: #1e293b !important;
        border: 1px solid #334155;
        border-radius: 12px;
        box-shadow: 0 8px 16px rgba(0,0,0,0.4);
    }
    .stSelectbox label p {
        color: #f8fafc !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #1e293b !important;
        border: 1px solid #475569 !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="select"] div[role="combobox"], 
    div[data-baseweb="select"] input {
        color: #ffffff !important;
        font-weight: 600 !important;
    }
    ul[data-baseweb="menu"] {
        background-color: #1e293b !important;
    }
    li[data-baseweb="option"] {
        background-color: #1e293b !important;
        color: #f8fafc !important;
    }
    li[data-baseweb="option"]:hover {
        background-color: #334155 !important;
    }
    div[data-testid="stButton"] button:not([kind="primary"]) {
        background-color: #1e293b;
        color: #f8fafc;
        border: 1px solid #475569;
        border-radius: 10px;
        font-weight: 700;
        height: 3rem;
        transition: all 0.2s ease-in-out;
    }
    div[data-testid="stButton"] button:not([kind="primary"]):hover:not(:disabled) {
        background-color: #dc2626 !important;
        color: #ffffff !important;
        border-color: #ef4444 !important;
        box-shadow: 0 0 12px rgba(239, 68, 68, 0.4);
        transform: translateY(-2px);
    }
    div[data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(135deg, #10b981, #059669);
        color: #ffffff !important;
        border: none;
        border-radius: 10px;
        font-weight: 700;
        height: 3rem;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        transition: all 0.2s ease-in-out;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover:not(:disabled) {
        background: linear-gradient(135deg, #34d399, #10b981);
        box-shadow: 0 0 16px rgba(16, 185, 129, 0.5);
        transform: translateY(-2px);
    }
    .stButton > button:disabled {
        background-color: #0f172a !important;
        color: #475569 !important;
        border: 1px solid #1e293b !important;
        cursor: not-allowed;
        opacity: 0.5;
        box-shadow: none !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# --- חיבור ל-SQLite ---
def get_db_connection():
    conn = sqlite3.connect("nba_data.db", check_same_thread=False)
    return conn


def get_remote_ip():
    """שליפת כתובת ה-IP של הלקוח"""
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers

        headers = _get_websocket_headers()
        if headers:
            return headers.get(
                "X-Forwarded-For", headers.get("Host", "127.0.0.1")
            ).split(",")[0]
    except Exception:
        pass
    return "127.0.0.1"


def clean_string(text):
    if not text:
        return ""
    normalized = unicodedata.normalize("NFD", text)
    ascii_text = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    cleaned = re.sub(r"['`’\-]", "", ascii_text.lower())
    return " ".join(cleaned.split())


def format_achievements(ach_text):
    if not ach_text or pd.isna(ach_text):
        return "-"

    text_cleaned = str(ach_text).replace("_", " ")
    parts = [p.strip() for p in text_cleaned.split(",") if p.strip()]
    formatted_parts = []

    for part in parts:
        lower_p = part.lower()
        if "all-star" in lower_p or "all star" in lower_p:
            formatted_parts.append(f"⭐ {part}")
        else:
            formatted_parts.append(part)

    return " | ".join(formatted_parts) if formatted_parts else "-"


@st.cache_data(ttl=600)
def get_db_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT player FROM View_PlayerStats_Formatted WHERE player IS NOT NULL;")
    all_players = [row[0] for row in cursor.fetchall()]

    eligible_query = """
    SELECT v.player 
    FROM View_PlayerStats_Formatted v
    LEFT JOIN Awards a ON v.player = a.player
    LEFT JOIN AllStars al ON v.player = al.player
    GROUP BY v.player 
    HAVING MAX(CAST(v.PPG AS FLOAT)) >= 12.0 
       AND MAX(CAST(v.season AS INT)) >= 1995
       AND (COUNT(a.award) > 0 OR COUNT(al.season) > 0);
    """
    cursor.execute(eligible_query)
    quiz_players = [row[0] for row in cursor.fetchall() if row[0]]

    cursor.close()
    conn.close()
    return all_players, quiz_players


def get_player_stats(player_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT 
        season AS Season, Teams AS Team, Age, GP, GS, MP, 
        PPG, RPG, APG, TOV, STL, BLK, PF, 
        FG_Perc AS [FG%], ThreeP_Perc AS [3P%], FT_Perc AS [FT%], 
        Achievements AS [Awards & Honors]
    FROM View_PlayerStats_Formatted 
    WHERE player = ? 
    ORDER BY season ASC;
    """
    cursor.execute(query, (player_name,))
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    data = [dict(zip(columns, row)) for row in rows]
    cursor.close()
    conn.close()
    return data


# --- פונקציות ניהול האתגר היומי ב-DB ---

def get_daily_players(quiz_players):
    today_seed = int(date.today().strftime("%Y%m%d"))
    rng = random.Random(today_seed)
    return rng.sample(quiz_players, min(3, len(quiz_players)))


def has_device_played_today(user_ip):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT 1 FROM DailyLeaderboard WHERE user_ip = ? AND date_played = DATE('now');"
    cursor.execute(query, (user_ip,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row is not None


def has_user_played_today(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT 1 FROM DailyLeaderboard WHERE username = ? AND date_played = DATE('now');"
    cursor.execute(query, (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row is not None


def save_daily_score(username, time_sec, penalties, total_sec, user_ip):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    INSERT INTO DailyLeaderboard (username, completion_time_seconds, penalties, total_score_seconds, date_played, user_ip)
    VALUES (?, ?, ?, ?, DATE('now'), ?);
    """
    cursor.execute(query, (username, time_sec, penalties, total_sec, user_ip))
    conn.commit()
    cursor.close()
    conn.close()


def get_today_leaderboard():
    conn = get_db_connection()
    query = """
    SELECT 
        username AS [Player], 
        ROUND(total_score_seconds, 2) AS [Total Score (Sec)], 
        ROUND(completion_time_seconds, 2) AS [Pure Time (Sec)], 
        penalties AS [Penalty Seconds]
    FROM DailyLeaderboard 
    WHERE date_played = DATE('now')
    ORDER BY total_score_seconds ASC
    LIMIT 10;
    """
    df_lb = pd.read_sql(query, conn)
    conn.close()
    return df_lb


# טעינת נתונים
all_players, quiz_players = get_db_data()

# סרגל צד
st.sidebar.image(
    "https://img.icons8.com/emoji/96/000000/basketball-emoji.png", width=60
)
st.sidebar.title("🎮 Game Modes")
game_mode = st.sidebar.radio(
    "Choose Mode:",
    ["🎮 Practice Mode (Free Play)", "🏆 Daily Challenge (Speedrun)"],
    index=0,
)

st.sidebar.divider()
st.sidebar.info(
    "💡 **Daily Rules:**\n- One attempt per day per device!\n- Solve 3"
    " players as fast as possible.\n- Wrong guess: **+10s** penalty.\n- Give Up:"
    " **+60s** penalty."
)

# הגדרת רוחב מיוחד לעמודת ההישגים
df_column_config = {
    "Awards & Honors": st.column_config.TextColumn(
        "Awards & Honors",
        width="large",
    )
}

# -----------------------------------------------------------------------------
# MODE 1: PRACTICE MODE
# -----------------------------------------------------------------------------
if game_mode == "🎮 Practice Mode (Free Play)":

    def reset_for_next_player():
        st.session_state.target_player = random.choice(quiz_players)
        st.session_state.game_over = False
        st.session_state.guess_input = ""

    if "target_player" not in st.session_state:
        st.session_state.target_player = random.choice(quiz_players)
        st.session_state.game_over = False

    st.markdown(
        '<div class="main-title"><span class="icon">🏀</span> <span'
        ' class="gradient-text">PRACTICE MODE</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-title">Train your skills! Unlimited mystery players'
        " with no time limit.</div>",
        unsafe_allow_html=True,
    )

    player_stats = get_player_stats(st.session_state.target_player)
    df = pd.DataFrame(player_stats)

    if "Awards & Honors" in df.columns:
        df["Awards & Honors"] = df["Awards & Honors"].apply(format_achievements)

    numeric_one_decimal = ["MP", "PPG", "RPG", "APG", "TOV", "STL", "BLK", "PF"]
    numeric_three_decimals = ["FG%", "3P%", "FT%"]
    integer_cols = ["Season", "Age", "GP", "GS"]

    for col in numeric_one_decimal + numeric_three_decimals + integer_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            '<div class="hint-card"><div class="hint-title">Seasons'
            f' Played</div><div class="hint-value">{len(df)}</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        max_ppg = (
            df["PPG"].max()
            if "PPG" in df.columns and not df["PPG"].empty
            else 0.0
        )
        st.markdown(
            '<div class="hint-card"><div class="hint-title">Peak'
            f' PPG</div><div class="hint-value">{max_ppg:.1f}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        last_team = df["Team"].iloc[-1] if not df["Team"].empty else "-"
        st.markdown(
            '<div class="hint-card"><div class="hint-title">Last'
            f' Team</div><div class="hint-value">{last_team}</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    format_dict = {
        col: "{:.1f}" for col in numeric_one_decimal if col in df.columns
    }
    format_dict.update(
        {col: "{:.3f}" for col in numeric_three_decimals if col in df.columns}
    )
    format_dict.update(
        {col: "{:.0f}" for col in integer_cols if col in df.columns}
    )

    def style_dark_rows(row):
        bg_color = "#1e293b" if row.name % 2 == 0 else "#0f172a"
        return [f"background-color: {bg_color}; color: #f8fafc;" for _ in row]

    styled_df = df.style.apply(style_dark_rows, axis=1).format(
        format_dict, na_rep="-"
    )
    calculated_height = (len(df) + 1) * 35 + 38

    st.dataframe(
        styled_df,
        use_container_width=True,
        column_config=df_column_config,
        hide_index=True,
        height=calculated_height,
    )

    st.write("")

    with st.container(border=True):
        st.markdown("### 🎯 Make Your Move")
        col1, col2, col3 = st.columns([3.8, 1.2, 1.2], vertical_alignment="bottom")

        with col1:
            selected_guess = st.selectbox(
                "Type or select player name:",
                options=[""] + sorted(all_players),
                key="guess_input",
                disabled=st.session_state.game_over,
                placeholder="Search for an NBA player...",
            )

        with col2:
            if st.button(
                "🏳️ Give Up",
                use_container_width=True,
                disabled=st.session_state.game_over,
            ):
                st.session_state.game_over = True
                st.rerun()

        with col3:
            if st.session_state.game_over:
                st.button(
                    "🔄 Next Player",
                    type="primary",
                    use_container_width=True,
                    on_click=reset_for_next_player,
                )
            else:
                st.button("🔄 Next Player", disabled=True, use_container_width=True)

    if st.session_state.game_over:
        if selected_guess and clean_string(selected_guess) == clean_string(
            st.session_state.target_player
        ):
            st.balloons()
            st.success(
                "🔥 **BOOM! YOU GOT IT!** The player is indeed"
                f" **{st.session_state.target_player}**!"
            )
        else:
            st.error(
                "❌ Game Over! The mystery player was"
                f" **{st.session_state.target_player}**."
            )
    elif selected_guess:
        if clean_string(selected_guess) == clean_string(
            st.session_state.target_player
        ):
            st.session_state.game_over = True
            st.rerun()
        else:
            st.toast(f"Incorrect: '{selected_guess}'", icon="❌")


# -----------------------------------------------------------------------------
# MODE 2: DAILY CHALLENGE
# -----------------------------------------------------------------------------
else:
    st.markdown(
        '<div class="main-title"><span class="icon">🏆</span> <span'
        ' class="gradient-text">DAILY CHALLENGE</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class=\"sub-title\">One shot per day! Solve today's 3 mystery"
        " players as fast as you can.</div>",
        unsafe_allow_html=True,
    )

    user_ip = get_remote_ip()

    if "daily_status" not in st.session_state:
        st.session_state.daily_status = "not_started"
        st.session_state.daily_step = 0
        st.session_state.daily_penalties = 0
        st.session_state.daily_start_time = None
        st.session_state.daily_players = get_daily_players(quiz_players)
        st.session_state.daily_username = ""

    if (
        has_device_played_today(user_ip)
        and st.session_state.daily_status != "completed"
    ):
        st.warning(
            "⛔ You have already completed today's challenge on this device! Come"
            " back tomorrow for a new set of players."
        )
        st.divider()
        st.subheader("📊 Today's Leaderboard")
        st.dataframe(
            get_today_leaderboard(), use_container_width=True, hide_index=True
        )

    elif st.session_state.daily_status == "not_started":
        col_a, col_b, col_c = st.columns([1, 2, 1])
        with col_b:
            with st.container(border=True):
                st.subheader("⚡ Start Today's Run")
                username_input = st.text_input("Enter your Nickname:", max_chars=20)

                if st.button(
                    "🚀 Start Challenge", type="primary", use_container_width=True
                ):
                    clean_user = username_input.strip()
                    if not clean_user:
                        st.warning("Please enter a nickname!")
                    elif has_user_played_today(clean_user):
                        st.error(
                            f"⛔ Nickname '{clean_user}' has already completed today's"
                            " challenge! Choose another name or wait for tomorrow."
                        )
                    else:
                        st.session_state.daily_username = clean_user
                        st.session_state.daily_status = "in_progress"
                        st.session_state.daily_start_time = time.time()
                        st.session_state.daily_step = 0
                        st.session_state.daily_penalties = 0
                        st.rerun()

        st.divider()
        st.subheader("📊 Today's Leaderboard")
        try:
            lb_df = get_today_leaderboard()
            if not lb_df.empty:
                st.dataframe(lb_df, use_container_width=True, hide_index=True)
            else:
                st.info("No entries yet today. Be the first!")
        except Exception:
            st.error("Error loading daily leaderboard.")

    elif st.session_state.daily_status == "in_progress":
        current_step = st.session_state.daily_step
        target_p = st.session_state.daily_players[current_step]

        elapsed_so_far = int(time.time() - st.session_state.daily_start_time)
        st.progress(
            (current_step) / 3.0,
            text=(
                f"Player {current_step + 1} of 3 | Elapsed: {elapsed_so_far}s |"
                f" Penalty Secs: +{st.session_state.daily_penalties}s"
            ),
        )

        player_stats = get_player_stats(target_p)
        df = pd.DataFrame(player_stats)

        if "Awards & Honors" in df.columns:
            df["Awards & Honors"] = df["Awards & Honors"].apply(format_achievements)

        numeric_one_decimal = ["MP", "PPG", "RPG", "APG", "TOV", "STL", "BLK", "PF"]
        numeric_three_decimals = ["FG%", "3P%", "FT%"]
        integer_cols = ["Season", "Age", "GP", "GS"]

        for col in numeric_one_decimal + numeric_three_decimals + integer_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                '<div class="hint-card"><div class="hint-title">Seasons'
                f' Played</div><div class="hint-value">{len(df)}</div></div>',
                unsafe_allow_html=True,
            )
        with c2:
            max_ppg = (
                df["PPG"].max()
                if "PPG" in df.columns and not df["PPG"].empty
                else 0.0
            )
            st.markdown(
                '<div class="hint-card"><div class="hint-title">Peak'
                f' PPG</div><div class="hint-value">{max_ppg:.1f}</div></div>',
                unsafe_allow_html=True,
            )
        with c3:
            last_team = df["Team"].iloc[-1] if not df["Team"].empty else "-"
            st.markdown(
                '<div class="hint-card"><div class="hint-title">Last'
                f' Team</div><div class="hint-value">{last_team}</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")

        format_dict = {
            col: "{:.1f}" for col in numeric_one_decimal if col in df.columns
        }
        format_dict.update(
            {col: "{:.3f}" for col in numeric_three_decimals if col in df.columns}
        )
        format_dict.update(
            {col: "{:.0f}" for col in integer_cols if col in df.columns}
        )

        def style_dark_rows(row):
            bg_color = "#1e293b" if row.name % 2 == 0 else "#0f172a"
            return [f"background-color: {bg_color}; color: #f8fafc;" for _ in row]

        styled_df = df.style.apply(style_dark_rows, axis=1).format(
            format_dict, na_rep="-"
        )
        calculated_height = (len(df) + 1) * 35 + 38

        st.dataframe(
            styled_df,
            use_container_width=True,
            column_config=df_column_config,
            hide_index=True,
            height=calculated_height,
        )

        st.write("")

        with st.container(border=True):
            st.markdown(f"### 🎯 Guess Player #{current_step + 1}")
            col1, col2 = st.columns([4, 1], vertical_alignment="bottom")

            with col1:
                guess = st.selectbox(
                    "Type or select player name:",
                    options=[""] + sorted(all_players),
                    key=f"daily_guess_{current_step}",
                    placeholder="Search player name...",
                )

            with col2:
                give_up = st.button("🏳️ Give Up (+60s)", use_container_width=True)

        if give_up:
            st.session_state.daily_penalties += 60
            st.toast(
                f"Skipped! Mystery player was {target_p}. (+60s Penalty)", icon="⚠️"
            )

            if current_step + 1 >= 3:
                end_time = time.time()
                pure_time = end_time - st.session_state.daily_start_time
                total_score = pure_time + st.session_state.daily_penalties
                save_daily_score(
                    st.session_state.daily_username,
                    pure_time,
                    st.session_state.daily_penalties,
                    total_score,
                    user_ip,
                )

                st.session_state.daily_status = "completed"
                st.session_state.last_total_score = total_score
                st.session_state.last_pure_time = pure_time
            else:
                st.session_state.daily_step += 1
            st.rerun()

        elif guess:
            if clean_string(guess) == clean_string(target_p):
                st.toast(f"Correct! That was {target_p}!", icon="✅")
                if current_step + 1 >= 3:
                    end_time = time.time()
                    pure_time = end_time - st.session_state.daily_start_time
                    total_score = pure_time + st.session_state.daily_penalties
                    save_daily_score(
                        st.session_state.daily_username,
                        pure_time,
                        st.session_state.daily_penalties,
                        total_score,
                        user_ip,
                    )

                    st.session_state.daily_status = "completed"
                    st.session_state.last_total_score = total_score
                    st.session_state.last_pure_time = pure_time
                else:
                    st.session_state.daily_step += 1
                st.rerun()
            else:
                st.session_state.daily_penalties += 10
                st.toast("Incorrect guess! (+10s Penalty)", icon="❌")

    elif st.session_state.daily_status == "completed":
        st.balloons()
        st.success(
            f"🎉 **CHALLENGE COMPLETED, {st.session_state.daily_username}!**"
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(
                "Total Score (Lower is better)",
                f"{st.session_state.last_total_score:.2f}s",
            )
        with c2:
            st.metric("Pure Time", f"{st.session_state.last_pure_time:.2f}s")
        with c3:
            st.metric("Penalty Time", f"+{st.session_state.daily_penalties}s")

        st.divider()
        st.subheader("🏆 Today's Leaderboard")
        st.dataframe(
            get_today_leaderboard(), use_container_width=True, hide_index=True
        )

        if st.button("🎮 Practice Mode", type="primary"):
            st.session_state.daily_status = "not_started"
            st.rerun()