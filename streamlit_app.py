import time
import requests
import json
import pandas as pd
import streamlit as st
from horus import utils
from horus.config import logger
# from schedule import clear
from operator import itemgetter
from horus.json_server import JsonServerProcessor
from horus.enums import MatchStatus


filters = None
column_config = None


# Begin streamlit UI Region
def page_load():
    st.set_page_config(
        page_title="Livescore App",
        page_icon=":soccer:",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
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

    # if filters:
    #     clear()

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
        "h1_score"      : st.column_config.TextColumn(
            label="H1 Score",
            width="small"
        ),
        "half"          : st.column_config.Column(
            label="Half",
            width="small"
        ),
        "time_match"    : st.column_config.Column(
            label="Time",
            width="small"
        ),
        "score"         : st.column_config.TextColumn(
            label="Score",
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
    }
# End Region


page_load()


def highlight_matches(row):
    if row.prediction:
        if float(row.cur_prediction) > 3.5 or row.half not in ('1', '2'):
            return ['color: '] * len(row)  # white
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
            "h1_score",
            "half",
            "time_match",
            "score",
            "prediction",
            "h2_prediction",
            "cur_prediction",
            "scores",
            "status",
            "url",
            "h1_url",
            "quick_events_url",
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


def callback(k):
    edited_rows = st.session_state[k]["edited_rows"]
    print(f"edited_rows: {edited_rows}")
    rows_to_add = []
    for idx, value in edited_rows.items():
        if value["x"] is True:
            rows_to_add.append(idx)
    print(f"rows_to_add: {rows_to_add}")
    print(f"rows_to_add: {edited_rows.items()}")
    # selected_df.session_state["data"] = (
    #     st.session_state["data"].drop(rows_to_add, axis=1).reset_index(drop=True)
    # )
    # with st.sidebar:
    #     st.write("**Callback called**")
    #     st.write(st.session_state.df)

# Callback function to update session state
# def update_selected_row(index):
#     st.session_state.selected_row = index


# Display the initial DataFrame table
dataframe = st.dataframe()
selected_df = st.dataframe()

# Update the DataFrame table every 10 seconds with new data
while True:
    key = time.time()
    st.session_state.data = load_data()
    modified_df = st.session_state["data"].copy()
    modified_df["x"] = False
    # Make Delete be the first column
    modified_df = modified_df[["x"] + modified_df.columns[:-1].tolist()]

    dataframe.data_editor(
        modified_df.style.apply(highlight_matches, axis=1),
        use_container_width=True,
        height=(len(modified_df) + 1) * 35 + 3,
        column_config=column_config,
        hide_index=True,
        on_change=callback,
        key=key,
        args=[key],
    )




    # if st.session_state.selected_row is not None:
    #     st.write('Selected Row:', dataframe.session_state.selected_row)

    # select, compare = st.tabs(["Selected Matches", "Compared Matches"])
    # with select:
    #     if "df" not in st.session_state:
    #         st.session_state["df"] = []
    #
    #     matches = event.selection.rows
    #     filtered_df = df.iloc[matches]
    #     filtered_data = filtered_df.to_json(orient='records')
    #     selected_data = json.loads(filtered_data)
    #     if selected_data:
    #         for d in selected_data:
    #             print(f"d:{d}")
    #             json_data.append(d)
    #         st.session_state["df"] = json_data
    #         # utils.insert_data_into_json_w_path(json_data, f'{TEMP_FOLDER}/test.json')
    #     if st.session_state["df"]:
    #         df = covert_json_to_dataframe(st.session_state["df"])
    #         selected_df.dataframe(
    #             df.style.apply(highlight_matches, axis=1),
    #             use_container_width=True,
    #             hide_index=False,
    #             height=(len(st.session_state["df"]) + 1) * 35 + 3,
    #             column_config=column_config,
    #             key='selected_matches'
    #         )
    time.sleep(15)

    # with compare:
    #     def onClick():
    #         st.session_state["clicked"] = True
    #
    #     existing_data = utils.read_json_w_file_path(f'{TEMP_FOLDER}/test.json')
    #     selected_df = covert_json_to_dataframe(existing_data)
    #     st.dataframe(
    #         selected_df.style.apply(highlight_matches, axis=1),
    #         key=time.time(),
    #         use_container_width=True,
    #         height=(len(existing_data) + 1) * 35 + 3,
    #         column_config=column_config
    #     )
    #     if "clicked" not in st.session_state:
    #         st.session_state["clicked"] = False
    #     st.button("Clear", on_click=onClick, key=time.time())
    #     if st.session_state["clicked"]:
    #         st.success("Done!")
    #         utils.write_json_w_path([], f'{TEMP_FOLDER}/test.json')
