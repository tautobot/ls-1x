import time
import base64
import requests
import pandas as pd
import streamlit as st
from livescore import utils
from livescore.config import logger
from schedule import clear
from operator import itemgetter
from livescore.json_server import JsonServerProcessor
from livescore.enums import MatchStatus
from livescore.json_sync.embedded import ensure_sync_running
from livescore.json_sync.settings import settings
from livescore.providers.onexbet_events import (
    parse_game_events,
    prioritize_markets,
    MARKET_GROUP_NAMES,
    _interval_width,
    _outcome_label,
)
from livescore.betting.sync_client import (
    fetch_game_events_sync,
    build_coupon_events,
)
from streamlit_autorefresh import st_autorefresh

# Set page config as the first Streamlit command
st.set_page_config(
    page_title="Livescore App",
    page_icon=":soccer:",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Populate the store from within the Streamlit process. On Streamlit Community
# Cloud only `streamlit run` executes (no separate sync service), so start the
# live-match sync loops in a background thread here — once per server process.
# Set EMBEDDED_SYNC=0 to disable (e.g. when running sync_matches.py separately).
ensure_sync_running()

# Auto-rerun every 15s so live data written by the background sync shows up
# without a manual browser refresh. Keyed so it doesn't clash with widgets;
# session_state (selected_ids etc.) persists across these reruns.
st_autorefresh(interval=15000, key="livescore_autorefresh")

# Initialize global variables
filters = None
column_config = None
page_num = 1
page_size = 50
data = []

# Begin streamlit UI Region
def page_load():
    global filters
    global page_num
    global page_size
    global column_config
    global data

    col1, col2, _, _ = st.columns([2, 1, 1, 1])
    with col1:
        option2 = st.radio(
            "Filters:",
            ["All", "H1", "H2", "NS", "HT", "FT", "Unknown"],
            horizontal=True
        )
    with col2:
        option1 = st.radio(
            "Filters:",
            ["All", "Potential Match", "Good Potential Match"],
            horizontal=True
        )
        if option1 == "All":
            filters = ''
        elif option1 == "Potential Match":
            filters = "?risk=0&risk=-1&risk=-2"
        elif option1 == "Good Potential Match":
            filters = "?risk=-1&risk=-2"

    pagination_cols = st.columns([1, 1, 2, 2, 2])
    with pagination_cols[0]:
        page_num = st.number_input("Page Number", min_value=1, value=1)
    with pagination_cols[1]:
        page_size = st.selectbox("Page Size", options=[10, 25, 50, 100], index=2)

    # # Initialize page_num and page_size as they'll be set below the table
    # if 'page_num' not in st.session_state:
    #     st.session_state.page_num = 1
    # if 'page_size' not in st.session_state:
    #     st.session_state.page_size = 50

    # Create text input boxes for "TOK" and "UID" in the sidebar
    tok = st.sidebar.text_input("TOK", "")
    uid = st.sidebar.text_input("UID", "")

    # --- 1xBet betting session inputs -------------------------------------
    # Runtime-only credentials for the "Bet" tab. Persisted in st.session_state
    # for the life of the browser session ONLY — never written to disk, never
    # logged. (Phase 1 uses these for read + coupon PREVIEW; no bet is placed.)
    st.sidebar.markdown("---")
    st.sidebar.subheader("1xBet Session (for betting)")
    st.session_state["bet_cookies"] = st.sidebar.text_area(
        "COOKIES (raw Cookie header)",
        value=st.session_state.get("bet_cookies", ""),
        height=100,
        key="bet_cookies_input",
        help="Paste the full 'cookie' request header from a logged-in 1xbet session. "
             "Session-only, never committed or logged.",
    )
    st.session_state["bet_x_hd"] = st.sidebar.text_input(
        "x-hd header",
        value=st.session_state.get("bet_x_hd", ""),
        key="bet_x_hd_input",
        type="password",
        help="Paste the 'x-hd' request header value. Session-only, never committed or logged.",
    )
    st.session_state["bet_user_id"] = st.sidebar.text_input(
        "UserId",
        value=st.session_state.get("bet_user_id", ""),
        key="bet_user_id_input",
        help="Numeric 1xBet account UserId (needed for live placement in a later phase).",
    )
    st.session_state["bet_dry_run"] = st.sidebar.checkbox(
        "DRY RUN (build coupon, do NOT place bet)",
        value=st.session_state.get("bet_dry_run", True),
        key="bet_dry_run_input",
    )

    # Remove page controls from here as they'll be moved below the table

    if option2 == "All":
        st.header("All", divider="rainbow")
    elif option2 == "H1":
        filters = filters + f"&status={MatchStatus.ON_GOING_H1}&status={MatchStatus.EXTRA_TIME_H1}" if filters else f"?status={MatchStatus.ON_GOING_H1}&status={MatchStatus.EXTRA_TIME_H1}"
        st.header("1st Half", divider="rainbow")
    elif option2 == "H2":
        filters = filters + f"&status={MatchStatus.ON_GOING_H2}&status={MatchStatus.EXTRA_TIME_H2}" if filters else f"?status={MatchStatus.ON_GOING_H2}&status={MatchStatus.EXTRA_TIME_H2}"
        st.header("2nd Half", divider="rainbow")
    elif option2 == "NS":
        filters = filters + f"&status={MatchStatus.NOT_STARTED}" if filters else f"?status={MatchStatus.NOT_STARTED}"
        st.header("Matches Not Started", divider="rainbow")
    elif option2 == "HT":
        filters = filters + f"&status={MatchStatus.HALF_TIME}" if filters else f"?status={MatchStatus.HALF_TIME}"
        st.header("Half Time", divider="rainbow")
    elif option2 == "FT":
        filters = filters + f"&status={MatchStatus.ENDED}" if filters else f"?status={MatchStatus.ENDED}"
        st.header("Full Time", divider="rainbow")
    elif option2 == "Unknown":
        filters = filters + f"&status={MatchStatus.UNKNOWN}" if filters else f"?status={MatchStatus.UNKNOWN}"
        st.header("Unknown", divider="rainbow")

    if filters:
        clear()

    column_config = {
        "selected": st.column_config.CheckboxColumn(
            "Select",
            help="Select to track this match",
            width="small",
            default=False
        ),
        "id": st.column_config.Column(
            label="ID",
            width=50
        ),
        "league": st.column_config.Column(
            label="League",
            width="small"
        ),
        "team1": st.column_config.Column(
            label="T1",
            width="small"
        ),
        "team2": st.column_config.Column(
            label="T2",
            width="small"
        ),
        "half": st.column_config.Column(
            label="Half",
            width=40
        ),
        "h1_score": st.column_config.TextColumn(
            label="H1 Score",
            width=50
        ),
        "rc1": st.column_config.ImageColumn(
            label="",
            width=28
        ),
        "score": st.column_config.TextColumn(
            label="Score",
            width=50
        ),
        "rc2": st.column_config.ImageColumn(
            label="",
            width=28
        ),
        # Raw "X - Y" score kept for highlight_rows' colour logic; hidden from view.
        "score_val": None,
        "time_match": st.column_config.Column(
            label="Time",
            width=70
        ),
        "goal_up_to_min": st.column_config.Column(
            label="G",
            help="Match offers the 'Goal will be scored up to a minute' market (bettable)",
            width=30
        ),
        "quick_events_url": st.column_config.LinkColumn(
            label="QE Link",
            display_text="QE Link",
            width=30
        ),
        "prediction": st.column_config.NumberColumn(
            label="Pre",
            format="%.1f",
            width=50
        ),
        "h2_prediction": st.column_config.NumberColumn(
            label="H2 Pre",
            format="%.1f",
            width=50
        ),
        "cur_prediction": st.column_config.NumberColumn(
            label="Cur Pre",
            format="%.1f",
            width=50
        ),
        "team1_possession": st.column_config.ProgressColumn(
            label="T1 Possession",
            min_value=0,
            max_value=100,
            format="%d%%",
            width=80
        ),
        "team2_possession": st.column_config.ProgressColumn(
            label="T2 Possession",
            min_value=0,
            max_value=100,
            format="%d%%",
            width=80
        ),
        "team1_shots": st.column_config.TextColumn(
            label="T1 Shots",
            width=50
        ),
        "team2_shots": st.column_config.TextColumn(
            label="T2 Shots",
            width=50
        ),
        "team1_attacks": st.column_config.NumberColumn(
            label="T1 Attacks",
            width=50
        ),
        "team1_d_attacks": st.column_config.NumberColumn(
            label="T1 DAttacks",
            width=50
        ),
        "team2_attacks": st.column_config.NumberColumn(
            label="T2 Attacks",
            width=50
        ),
        "team2_d_attacks": st.column_config.NumberColumn(
            label="T2 DAttacks",
            width=50
        ),
        "scores": st.column_config.Column(
            label="Scored",
            width=80
        ),
        "rc_times": st.column_config.Column(
            label="RCs",
            width=80
        ),
        "url": st.column_config.LinkColumn(
            label="Link",
            display_text="Link",
            width="small"
        ),
        "h1_url": st.column_config.LinkColumn(
            label="H1 Link",
            display_text="H1 Link",
            width="small"
        ),
        "h2_scores": st.column_config.Column(
            label="H2 Scored",
            width=70
        ),
        "h1_scores": st.column_config.Column(
            label="H1 Scored",
            width=70
        ),
        
    }
# End Region

def paginate_dataframe(dataframe, page_size, page_num):
    page_size = page_size
    if page_size is None:
        return None

    offset = page_size * (page_num - 1)
    return dataframe[offset:offset + page_size]


def _redcards_count(value) -> int:
    """Coerce a stored red-card value (str/int/NaN/None) to a non-negative int."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 0
    return n if n > 0 else 0


def _redcard_dots_uri(value) -> str:
    """Small red dots as a data-URI SVG — one dot per red card, '' when none.
    Shown in a narrow ImageColumn beside the score; a tall-ish viewBox keeps each
    dot small once ImageColumn scales the image up to the row height."""
    n = _redcards_count(value)
    if n <= 0:
        return ""
    H = 22.0
    cy = H / 2
    r = 4.5            # small dot radius (relative to the 22-tall viewBox)
    gap = 2.5
    pad = 2.0
    d = 2 * r
    W = pad * 2 + n * d + (n - 1) * gap
    dots = "".join(
        f'<circle cx="{pad + r + i * (d + gap):.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#d40000"/>'
        for i in range(n)
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
        f'viewBox="0 0 {W:.0f} {H:.0f}">{dots}</svg>'
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def covert_json_to_dataframe(j_data):
    df = pd.DataFrame(
        data=j_data,
        columns=(
            "id",
            "league",
            "team1",
            "team2",
            "half",
            "h1_score",
            "score",
            "time_match",
            "goal_up_to_min",
            "quick_events_url",
            "prediction",
            "h2_prediction",
            "cur_prediction",
            "team1_possession",
            "team2_possession",
            "team1_shots",
            "team2_shots",
            "team1_attacks",
            "team1_d_attacks",
            "team2_attacks",
            "team2_d_attacks",
            "scores",
            "rc_times",
            "status",
            "url",
            "h1_url",
            "video",
            "freeze_time",
            "h1_scores",
            "h2_scores",
            "risk",
            # Red-card counts — used only to decorate the score columns below,
            # then dropped so they never render as their own columns.
            "team1_redcard",
            "team2_redcard",
        )
    )
    # Missing H1 scores (pre-halftime) render blank, not the literal "None".
    df["h1_score"] = df["h1_score"].fillna("")
    # "G" column: a check when the goal-up-to-minute market is on offer, else blank.
    if "goal_up_to_min" in df.columns:
        df["goal_up_to_min"] = df["goal_up_to_min"].map(
            lambda v: "✓" if str(v) == "1" else ""
        )
    # Score stays plain text (so it keeps its row colour and is selectable). Red
    # cards render as small red dots in narrow image columns flanking Score —
    # team1 (rc1) on the left, team2 (rc2) on the right. `score_val` mirrors the
    # raw score for highlight_rows.
    if not df.empty:
        df["score_val"] = df["score"]
        df["rc1"] = df["team1_redcard"].apply(_redcard_dots_uri)
        df["rc2"] = df["team2_redcard"].apply(_redcard_dots_uri)
    else:
        df["score_val"] = pd.Series(dtype=object)
        df["rc1"] = pd.Series(dtype=object)
        df["rc2"] = pd.Series(dtype=object)
    df = df.drop(columns=["team1_redcard", "team2_redcard"])
    # Place the red-card dot columns immediately left/right of Score.
    cols = df.columns.tolist()
    for c in ("rc1", "rc2"):
        cols.remove(c)
    si = cols.index("score")
    cols.insert(si, "rc1")
    cols.insert(si + 2, "rc2")
    df = df[cols]
    # Add selected column and put it first.
    df['selected'] = False
    cols = ['selected'] + [c for c in df.columns.tolist() if c != 'selected']
    df = df[cols]
    return df


# Function to simulate loading new data into the DataFrame
def load_data():
    try:
        # Get the current selected_ids before loading new data
        selected_ids = st.session_state.get('selected_ids', set())
        
        JsonServer = JsonServerProcessor(source='1x', params={'skip_convert_data_types': True})
        if filters is not None:
            res = JsonServer.get_all_matches(filters)
        else:
            res = JsonServer.get_all_matches()
        if res.get('success'):
            data = res.get('data') or []
            data = utils.sort_json(data, keys=itemgetter('half', 'time_match'))

            df = covert_json_to_dataframe(data)
            df = paginate_dataframe(df, page_size, page_num)
            
            # Get the set of current IDs in the loaded data
            current_ids = set(df['id'].unique())
            
            # Find any selected IDs that are no longer in the current data
            removed_ids = selected_ids - current_ids
            
            # Update selected_ids to only keep those that exist in the current data
            if removed_ids:
                st.session_state.selected_ids = selected_ids - removed_ids
            
            # Update selected_matches with the latest data for the selected matches
            if st.session_state.get('selected_ids'):
                # Get the latest data for all selected matches
                selected_matches = df[df['id'].isin(st.session_state.selected_ids)].copy()
                if not selected_matches.empty:
                    # Remove the 'selected' column if it exists to avoid confusion
                    if 'selected' in selected_matches.columns:
                        selected_matches = selected_matches.drop(columns=['selected'])
                    st.session_state.selected_matches = selected_matches
                else:
                    st.session_state.selected_matches = pd.DataFrame()
            else:
                st.session_state.selected_matches = pd.DataFrame()
            
            # Restore the selected state in the main DataFrame
            df['selected'] = False
            if st.session_state.get('selected_ids'):
                df.loc[df['id'].isin(st.session_state.selected_ids), 'selected'] = True
                
            return df
    except requests.exceptions.RequestException as e:
        logger.error(f'RequestException: {e}')
    except ConnectionResetError:
        logger.error('ConnectionResetError')
    return None


def handle_selection():
    """Handle checkbox selection changes"""
    try:
        # Get the edited data from session state
        edited_data = st.session_state.live_matches
        original_df = st.session_state.df_data
        
        # Get edited rows from the data structure
        edited_rows = edited_data.get('edited_rows', {})
        
        # Initialize selected_ids if not exists
        if 'selected_ids' not in st.session_state:
            st.session_state.selected_ids = set()
        
        # Update selected_ids based on changes
        for idx, changes in edited_rows.items():
            row_idx = int(idx)
            match_id = original_df.iloc[row_idx]['id']
            if changes.get('selected', False):
                st.session_state.selected_ids.add(match_id)
            else:
                st.session_state.selected_ids.discard(match_id)
        
        # Update selected column in the main DataFrame
        original_df.loc[:, 'selected'] = False  # Reset all to False
        original_df.loc[original_df['id'].isin(st.session_state.selected_ids), 'selected'] = True
        st.session_state.df_data = original_df  # Update the DataFrame in session state
        
        # Update selected matches
        if st.session_state.selected_ids:
            # Get all rows where id is in selected_ids
            selected_rows = original_df[original_df['id'].isin(st.session_state.selected_ids)].copy()
            if 'selected' in selected_rows.columns:
                selected_rows = selected_rows.drop(columns=['selected'])
            st.session_state.selected_matches = selected_rows
        else:
            st.session_state.selected_matches = pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error updating selections: {str(e)}")


def main():
    # Initialize UI components first
    page_load()
    
    # Initialize selected matches if not exists
    if 'selected_matches' not in st.session_state:
        st.session_state.selected_matches = pd.DataFrame()
    
    # Load data
    df = load_data()
    if df is not None:
        # Store the dataframe in session state
        st.session_state.df_data = df
        
        # Add selected column if not exists
        if 'selected' not in df.columns:
            df['selected'] = False
        
        # Configure the checkbox column
        column_config['selected'] = st.column_config.CheckboxColumn(
            'Select',
            help='Select this match',
            default=False
        )
        
        def highlight_rows(row):
            if pd.isna(row.team1_shots) and pd.isna(row.team2_shots):
                return ['color: red; opacity: 0.5'] * len(row)

            team1_shots = str(row.team1_shots) if pd.notna(row.team1_shots) else '0'
            team2_shots = str(row.team2_shots) if pd.notna(row.team2_shots) else '0'

            team1_shots_total = sum(int(x.strip()) for x in team1_shots.split('+') if x.strip().isdigit())
            team2_shots_total = sum(int(x.strip()) for x in team2_shots.split('+') if x.strip().isdigit())
            total_shots = team1_shots_total + team2_shots_total

            if row.half == '1':
                # Check for red color condition in first half
                if total_shots >= 11:
                    return ['color: red; opacity: 0.5'] * len(row)
            else:
                # Check for red color condition in second half
                if total_shots >= 22:
                    return ['color: red; opacity: 0.5'] * len(row)
    
            if row.risk == '-1':
                return ['color: pink; opacity: 0.5'] * len(row)
            if row.risk == '-2':
                return ['color: cyan; opacity: 0.5'] * len(row)
            if row.prediction:
                if float(row.cur_prediction) > 3.5 or row.half not in ('1', '2'):
                    return ['color: '] * len(row)  # white

                if row.half == '1':
                    if (
                            (
                                float(row.prediction) <= 2.5 and
                                row.score_val in ('0 - 0', '0 - 1', '1 - 0', '1 - 1')
                            ) or 
                            (
                                float(row.prediction) <= 3 and
                                row.score_val in ('0 - 0', '0 - 1', '1 - 0', '1 - 1', '0 - 2', '2 - 0')
                            )
                        ):
                        if (
                            ':' in str(row.h1_scores) and
                            ':' in str(row.time_match) and
                            0 < utils.convert_timematch_to_seconds(row.time_match) - utils.convert_timematch_to_seconds(row.h1_scores.split(',')[0]) <= 720
                        ):
                            return ['color: #FFA500; opacity: 0.5'] * len(row)  # orange
                        else:
                            return ['color: #00FF00; opacity: 0.5'] * len(row)  # green
                elif row.half == '2':
                    if (
                        float(row.prediction) <= 3 and
                        row.score_val in ('0 - 0', '0 - 1', '1 - 0', '1 - 1', '2 - 1', '1 - 2', '2 - 0', '0 - 2')
                    ):
                        if (
                            ':' in str(row.h2_scores) and
                            ':' in str(row.time_match) and
                            0 < utils.convert_timematch_to_seconds(row.time_match) - utils.convert_timematch_to_seconds(row.h2_scores.split(',')[0]) <= 600
                        ):
                            return ['color: #FFA500; opacity: 0.5'] * len(row)  # orange
                        else:
                            return ['color: #00FF00; opacity: 0.5'] * len(row)  # green
            return ['color: '] * len(row)  # white
        
        # Create tabs for Matches table and Details
        tab1, tab2, tab3, tab4 = st.tabs(["Matches", "Details", "MfB", "Bet"])
        
        # Tab 1: Main Matches table
        with tab1:
            # Create a copy of the dataframe without the 'selected' column for display
            summary_df = df.drop(columns=['selected']) if 'selected' in df.columns else df.copy()
            
            # Display the summary table with a fixed height
            st.dataframe(
                summary_df.style.apply(highlight_rows, axis=1),
                use_container_width=True,
                height=(len(df) + 1) * 35 + 3,
                column_config={k: v for k, v in column_config.items() if k != 'selected'},
                key='df_live_matches'
            )
        
        # Tab 2: Selected and All Matches (previously in expander)
        with tab2:
            # Selected Matches section
            st.markdown("##### Selected Matches")
            if not st.session_state.selected_matches.empty:
                seletced_matches = st.session_state.selected_matches
                st.dataframe(
                    st.session_state.selected_matches.style.apply(highlight_rows, axis=1),
                    use_container_width=True,
                    hide_index=True,
                    height=(len(seletced_matches) + 1) * 35 + 3,
                    column_config={k: v for k, v in column_config.items() if k != 'selected'},
                    key='selected_matches_display'
                )
            else:
                # Create an empty DataFrame with the same columns
                empty_df = pd.DataFrame(columns=[col for col in column_config.keys() if col != 'selected'])
                st.dataframe(
                    empty_df,
                    use_container_width=True,
                    hide_index=True,
                    height=5 * 35 + 3,
                    column_config={k: v for k, v in column_config.items() if k != 'selected'},
                    key='selected_matches_display'
                )
            
            # Add Clear button below Selected Matches
            if st.button('Clear Selected Matches'):
                # Clear selected matches
                st.session_state.selected_matches = pd.DataFrame()
                st.session_state.selected_ids = set()
                # Update selected column in main DataFrame
                st.session_state.df_data.loc[:, 'selected'] = False
                st.rerun()
            
            # Add a divider between sections
            st.markdown("---")
            
            # All Matches section
            st.markdown("##### All Matches")
            
            # Configure which columns are editable
            disabled_columns = [col for col in df.columns if col != 'selected']
            
            # Calculate height to fit all rows plus header
            all_rows_height = (len(df) + 1) * 35 + 3  # Cap height at 500px
            
            st.data_editor(
                df.style.apply(highlight_rows, axis=1),
                use_container_width=True,
                height=all_rows_height,
                column_config=column_config,
                key='live_matches',
                num_rows="fixed",  # Prevent adding rows
                on_change=handle_selection,
                disabled=disabled_columns
            )

        # Tab 3: MfB - Auto-select orange matches
        with tab3:
            # Initialize MfB selected matches if not exists
            if 'mfb_selected_matches' not in st.session_state:
                st.session_state.mfb_selected_matches = pd.DataFrame()
            
            # Function to check if a row should be orange (auto-selected)
            def is_orange_row(row):
                if pd.isna(row.team1_shots) and pd.isna(row.team2_shots):
                    return False

                team1_shots = str(row.team1_shots) if pd.notna(row.team1_shots) else '0'
                team2_shots = str(row.team2_shots) if pd.notna(row.team2_shots) else '0'

                team1_shots_total = sum(int(x.strip()) for x in team1_shots.split('+') if x.strip().isdigit())
                team2_shots_total = sum(int(x.strip()) for x in team2_shots.split('+') if x.strip().isdigit())
                total_shots = team1_shots_total + team2_shots_total

                if row.half == '1':
                    if total_shots >= 11:
                        return False
                else:
                    if total_shots >= 22:
                        return False
        
                if row.prediction:
                    if float(row.cur_prediction) > 3.5 or row.half not in ('1', '2'):
                        return False

                    if row.half == '1':
                        if (
                                (
                                    float(row.prediction) <= 2.5 and
                                    row.score_val in ('0 - 0', '0 - 1', '1 - 0', '1 - 1')
                                ) or 
                                (
                                    float(row.prediction) <= 3 and
                                    row.score_val in ('0 - 0', '0 - 1', '1 - 0', '1 - 1', '0 - 2', '2 - 0')
                                )
                            ):
                            if (
                                ':' in str(row.h1_scores) and
                                ':' in str(row.time_match) and
                                0 < utils.convert_timematch_to_seconds(row.time_match) - utils.convert_timematch_to_seconds(row.h1_scores.split(',')[0]) <= 350
                            ):
                                return True  # This would be orange
                    elif row.half == '2':
                        if (
                            float(row.prediction) <= 3 and
                            row.score_val in ('0 - 0', '0 - 1', '1 - 0', '1 - 1', '2 - 1', '1 - 2', '2 - 0', '0 - 2')
                        ):
                            if (
                                ':' in str(row.h2_scores) and
                                ':' in str(row.time_match) and
                                0 < utils.convert_timematch_to_seconds(row.time_match) - utils.convert_timematch_to_seconds(row.h2_scores.split(',')[0]) <= 350
                            ):
                                return True  # This would be orange
                return False
            
            # Auto-select orange rows
            orange_rows = df[df.apply(is_orange_row, axis=1)]
            
            # Always update mfb_selected_matches to sync with current data
            if not orange_rows.empty:
                # Remove 'selected' column if it exists for the MfB selected matches
                orange_rows_clean = orange_rows.drop(columns=['selected']) if 'selected' in orange_rows.columns else orange_rows.copy()
                st.session_state.mfb_selected_matches = orange_rows_clean
            else:
                # Clear selected matches if no orange rows exist
                st.session_state.mfb_selected_matches = pd.DataFrame()
            
            # Selected Matches section
            st.markdown("##### Selected MfB")
            if not st.session_state.mfb_selected_matches.empty:
                # Calculate height to fit all selected rows plus header
                selected_rows_height = (len(st.session_state.mfb_selected_matches) + 1) * 35 + 3
                st.dataframe(
                    st.session_state.mfb_selected_matches.style.apply(highlight_rows, axis=1),
                    use_container_width=True,
                    hide_index=True,
                    height=selected_rows_height,
                    column_config={k: v for k, v in column_config.items() if k != 'selected'},
                    key='mfb_selected_matches_display'
                )
            else:
                # Create an empty DataFrame with the same columns
                empty_df = pd.DataFrame(columns=[col for col in column_config.keys() if col != 'selected'])
                st.dataframe(
                    empty_df,
                    use_container_width=True,
                    hide_index=True,
                    height=5 * 35 + 3,
                    column_config={k: v for k, v in column_config.items() if k != 'selected'},
                    key='mfb_selected_matches_display'
                )
            
            # Add Clear button below Selected Matches
            if st.button('Clear MfB Selected Matches'):
                # Clear MfB selected matches
                st.session_state.mfb_selected_matches = pd.DataFrame()
                st.rerun()
            
            # Add a divider between sections
            st.markdown("---")
            
            # All Matches section
            st.markdown("##### All Matches")
            
            # Create a copy of the dataframe without the 'selected' column for display
            all_matches_df = df.drop(columns=['selected']) if 'selected' in df.columns else df.copy()
            
            # Calculate height to fit all rows plus header
            all_rows_height = (len(all_matches_df) + 1) * 35 + 3
            
            st.dataframe(
                all_matches_df.style.apply(highlight_rows, axis=1),
                use_container_width=True,
                height=all_rows_height,
                column_config={k: v for k, v in column_config.items() if k != 'selected'},
                key='mfb_all_matches'
            )

        # Tab 4: Bet - per-match markets (current-half priority) + coupon PREVIEW.
        # PHASE 1: read + display + multi-select bet-slip + dry-run coupon preview.
        # NO network WRITE call is made anywhere here; placement is a disabled stub.
        with tab4:
            st.markdown("##### Per-Match Markets (current-half priority)")
            selected_ids = st.session_state.get('selected_ids', set())
            if not selected_ids:
                st.info("Select one or more matches in the Matches/Details tab first.")
            else:
                match_choice = st.selectbox(
                    "Match", options=sorted(selected_ids), key="bet_match_choice"
                )

                if st.button("Fetch markets", key="bet_fetch_events"):
                    with st.spinner("Fetching markets..."):
                        raw = fetch_game_events_sync(
                            settings.x1_base_url,
                            str(match_choice),
                            proxy=settings.http_proxy,
                        )
                    if raw is None:
                        st.error(
                            "Fetch failed (network/block). "
                            "Check SYNC_HTTP_PROXY if on Cloud."
                        )
                    else:
                        st.session_state["bet_events_cache"] = parse_game_events(raw)
                        # New fetch => drop any stale bet-slip from a prior match.
                        st.session_state.pop("bet_slip", None)

                events = st.session_state.get("bet_events_cache")
                if events is not None and events.match_id == str(match_choice):
                    st.caption(
                        f"Current half: {events.current_period_name}  |  "
                        f"Score: {events.full_score}"
                    )
                    groups = prioritize_markets(events)
                    if not groups:
                        st.warning(
                            "None of the target markets are currently live for this match."
                        )

                    bet_slip = st.session_state.setdefault("bet_slip", [])
                    slip_keys = {
                        (s["group_id"], s["type"], s["parameter"], s["game_id"])
                        for s in bet_slip
                    }

                    for group in groups:
                        label = MARKET_GROUP_NAMES.get(group.group_id, str(group.group_id))
                        if group.group_id == 2750:
                            width = _interval_width(group)
                            if width:
                                label = f"{label} ({width:g}m)"
                        header = f"{label}  [{group.subgame_name or 'match'}]"
                        with st.expander(header, expanded=True):
                            bettable = [o for o in group.outcomes if not o.blocked]
                            if not bettable:
                                st.caption("All outcomes currently blocked.")
                            for outcome in bettable:
                                param_key = outcome.parameter if outcome.parameter is not None else 0
                                key4 = (
                                    group.group_id,
                                    outcome.type,
                                    param_key,
                                    group.subgame_id or int(match_choice),
                                )
                                label_txt = _outcome_label(group.group_id, outcome)
                                cols = st.columns([4, 1])
                                cols[0].write(f"{label_txt}  —  **{outcome.cf_view}**")
                                checked = cols[1].checkbox(
                                    "Add",
                                    value=key4 in slip_keys,
                                    key=(
                                        f"pick_{group.group_id}_{outcome.type}_"
                                        f"{param_key}_{group.subgame_id}"
                                    ),
                                )
                                if checked and key4 not in slip_keys:
                                    bet_slip.append({
                                        "group_id": group.group_id,
                                        "group_name": label,
                                        "type": outcome.type,
                                        "parameter": param_key,
                                        "cf": outcome.cf,
                                        "cf_view": outcome.cf_view,
                                        "game_id": group.subgame_id or int(match_choice),
                                        "label": label_txt,
                                    })
                                    slip_keys.add(key4)
                                elif not checked and key4 in slip_keys:
                                    bet_slip[:] = [
                                        s for s in bet_slip
                                        if (s["group_id"], s["type"], s["parameter"], s["game_id"]) != key4
                                    ]
                                    slip_keys.discard(key4)

                    st.markdown("---")
                    st.markdown("##### Bet Slip")
                    if not bet_slip:
                        st.caption("No selections yet.")
                    else:
                        slip_df = pd.DataFrame(bet_slip)[
                            ["group_name", "label", "cf_view", "game_id"]
                        ]
                        st.dataframe(slip_df, hide_index=True, use_container_width=True)
                        if st.button("Clear slip", key="bet_slip_clear"):
                            st.session_state["bet_slip"] = []
                            st.rerun()

                        stake = st.number_input(
                            "Stake (units)",
                            min_value=1.0,
                            value=50.0,
                            step=1.0,
                            key="bet_stake",
                        )

                        if st.button("Build coupon preview", key="bet_build_preview"):
                            coupon_events = build_coupon_events(bet_slip)
                            st.warning(
                                "PREVIEW ONLY — live placement not yet enabled "
                                "(needs verified payload)."
                            )
                            st.caption(
                                f"Coupon that WOULD be posted "
                                f"({len(coupon_events)} event(s), stake {stake:g}):"
                            )
                            st.json(coupon_events)

                        # Placement is intentionally a disabled stub in Phase 1 —
                        # no network WRITE call exists yet.
                        st.info(
                            "Place bet is disabled in this phase. Coupon build is "
                            "PREVIEW ONLY; live placement arrives in a later phase "
                            "once the write payload is verified."
                        )

if __name__ == "__main__":
    main()
    time.sleep(15)
    st.rerun()
