import time
import requests
import pandas as pd
import streamlit as st
from horus import utils
from horus.config import logger
from schedule import clear
from operator import itemgetter
from horus.json_server import JsonServerProcessor
from horus.enums import MatchStatus

# Set page config as the first Streamlit command
st.set_page_config(
    page_title="Livescore App",
    page_icon=":soccer:",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize global variables
filters = None
column_config = None
page_num = 1
page_size = 50
data = []

# Display the initial DataFrame table
dataframe = st.dataframe()


# Begin streamlit UI Region
def page_load():
    global filters
    global page_num
    global page_size
    global column_config
    global data

    option1 = st.radio(
        "Filters:",
        ["All", "Potential Match"],
        horizontal=True
    )
    if option1 == "All":
        filters = ''
    elif option1 == "Potential Match":
        filters = "?risk=0"

    option2 = st.radio(
        "Filters:",
        ["All", "H1", "H2", "NS", "HT", "FT", "Unknown"],
        horizontal=True
    )

    page_num = st.sidebar.number_input("Page Number", min_value=1, value=1)
    # page_size = st.sidebar.number_input("Page Size", min_value=1, value=20)
    page_size = st.sidebar.selectbox("Page Size", options=[10, 25, 50, 100], index=2)

    # Create text input boxes for "TOK" and "UID" in the sidebar
    tok = st.sidebar.text_input("TOK", "")
    uid = st.sidebar.text_input("UID", "")

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
        "league"        : st.column_config.Column(
            label="League",
            width="small"
        ),
        "team1"         : st.column_config.Column(
            label="T1",
            width="small"
        ),
        "team2"         : st.column_config.Column(
            label="T2",
            width="small"
        ),
        "half"          : st.column_config.Column(
            label="Half",
            width="small"
        ),
        "h1_score"      : st.column_config.TextColumn(
            label="H1 Score",
            width="small"
        ),
        "score"         : st.column_config.TextColumn(
            label="Score",
            width="small"
        ),
        "time_match"    : st.column_config.Column(
            label="Time",
            width="small"
        ),
        "prediction"    : st.column_config.NumberColumn(
            label="Pre",
            format="%.1f",
            width="small"
        ),
        "h2_prediction" : st.column_config.NumberColumn(
            label="H2 Pre",
            format="%.1f",
            width="small"
        ),
        "cur_prediction": st.column_config.NumberColumn(
            label="Cur Pre",
            format="%.1f",
            width="small"
        ),
        "team1_shots": st.column_config.TextColumn(
            label="T1 Shots",
            width="small"
        ),
        "team2_shots": st.column_config.TextColumn(
            label="T2 Shots",
            width="small"
        ),
        "scores"        : st.column_config.TextColumn(
            label="Scored",
            width="medium"
        ),
        "url"           : st.column_config.LinkColumn(
            label="Link",
            display_text=f"Link",
            width="small"
        ),
        "h1_url": st.column_config.LinkColumn(
            label="H1 Link",
            display_text=f"H1 Link",
            width="small"
        ),
        "quick_events_url": st.column_config.LinkColumn(
            label="QE Link",
            display_text=f"QE Link",
            width="small"
        )

    }
# End Region


def highlight_matches(row):
    if row.prediction:
        if float(row.cur_prediction) > 3.5 or row.half not in ('1', '2'):
            return ['color: '] * len(row)  # white

        team1_shots = str(row.team1_shots) if pd.notna(row.team1_shots) else '0'
        team2_shots = str(row.team2_shots) if pd.notna(row.team2_shots) else '0'
        team1_shots_total = sum(int(x.strip()) for x in team1_shots.split('+') if x.strip().isdigit())
        team2_shots_total = sum(int(x.strip()) for x in team2_shots.split('+') if x.strip().isdigit())
        total_shots = team1_shots_total + team2_shots_total

        if row.half == '1':
            if (
                    (
                            float(row.prediction) <= 2.5 and
                            row.score in ('0 - 0', '0 - 1', '1 - 0', '1 - 1')
                    ) or (
                    float(row.prediction) <= 3 and
                    row.score in ('0 - 0', '0 - 1', '1 - 0', '1 - 1', '0 - 2', '2 - 0')
                )
            ):
                if (
                        ':' in str(row.scores) and
                        ':' in str(row.time_match) and
                        0 < utils.convert_timematch_to_seconds(row.time_match) - utils.convert_timematch_to_seconds(
                    row.scores.split(',')[0]) <= 720
                ):
                    # Calculate total shots for both teams in first half
                    if total_shots <= 11 and total_shots > 0:
                        return ['color: cyan; opacity: 0.5'] * len(row)  # cyan for matches meeting all conditions
                    return ['color: #FFA500; opacity: 0.5'] * len(row)  # orange
                else:
                    return ['color: #00FF00; opacity: 0.5'] * len(row)  # green
            else:
                return ['color: '] * len(row)  # white
        elif row.half == '2':
            if (
                    float(row.prediction) <= 3 and
                    row.score in ('0 - 0', '0 - 1', '1 - 0', '1 - 1', '2 - 1', '1 - 2', '2 - 0', '0 - 2')
            ):
                if (
                        ':' in str(row.scores) and
                        ':' in str(row.time_match) and
                        0 < utils.convert_timematch_to_seconds(row.time_match) - utils.convert_timematch_to_seconds(
                    row.scores.split(',')[0]) <= 600
                ):
                    # Calculate total shots for both teams in second half
                    if total_shots <= 22 and total_shots > 0:
                        return ['color: cyan; opacity: 0.5'] * len(row)  # cyan for matches meeting all conditions
                    return ['color: #FFA500; opacity: 0.5'] * len(row)  # orange
                else:
                    return ['color: #00FF00; opacity: 0.5'] * len(row)  # green
            else:
                return ['color: '] * len(row)  # white


def paginate_dataframe(dataframe, page_size, page_num):
    page_size = page_size
    if page_size is None:
        return None

    offset = page_size * (page_num - 1)
    return dataframe[offset:offset + page_size]


def covert_json_to_dataframe(j_data):
    return pd.DataFrame(
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
            "prediction",
            "h2_prediction",
            "cur_prediction",
            "team1_shots",
            "team2_shots",
            "scores",
            "status",
            "url",
            "h1_url",
            "quick_events_url",
            "video",
            "freeze_time",
        )
    )


# Function to simulate loading new data into the DataFrame
def load_data():
    try:
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
            return df
    except requests.exceptions.RequestException as e:
        logger.error(f'RequestException: {e}')
    except ConnectionResetError:
        logger.error('ConnectionResetError')
    return None


def main():
    page_load()
    
    # Update the DataFrame table every 15 seconds with new data
    while True:
        df = load_data()
        if df is not None:
            dataframe.dataframe(
                df.style.apply(highlight_matches, axis=1),
                use_container_width=True,
                hide_index=False,
                height=(len(df) + 1) * 35 + 3,
                column_config=column_config,
                key='live_matches'
            )
        time.sleep(15)

if __name__ == "__main__":
    main()
