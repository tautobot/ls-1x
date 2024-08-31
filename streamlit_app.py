import time
import os
import streamlit as st
import requests
import pandas as pd
from horus import utils
from horus.config import logger, JSON_SERVER_BASE_URL
from schedule import every, run_pending, clear
from operator import itemgetter
from horus.json_server import JsonServerProcessor


def fetch_emojis():
    resp = requests.get(
        'https://raw.githubusercontent.com/omnidan/node-emoji/master/lib/emoji.json')
    json = resp.json()
    codes, emojis = zip(*json.items())
    return pd.DataFrame({
        'Emojis': emojis,
        'Shortcodes': [f':{code}:' for code in codes],
    })


# Begin streamlit UI
def page_load():
    st.set_page_config(
        page_title="Livescore App",
        page_icon=":soccer:",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.header("1XBET", divider="rainbow")
# End


# # Create the flag file to stop the schedule in x8.py
# open("stop_8x.flag", "w").close()
# # Remove the flag file to start the schedule in x1.py
# if os.path.exists("stop_1x.flag"):
#     os.remove("stop_1x.flag")


page_load()
with st.empty():

    def highlight_matches(row):
        if row.prediction:
            if row.half == "1" and float(row.cur_prediction) <= 3.5 and (
                float(row.prediction) <= 2 and row.score in ('0 - 0', '0 - 1', '1 - 0', '1 - 1')
            ) or (
                float(row.prediction) == 3 and row.score in ('0 - 0', '0 - 1', '1 - 0', '1 - 1', '0 - 2', '2 - 0')
            ):
                if ':' in str(row.scores) and ':' in str(row.time_match):
                    if 0 < utils.convert_timematch_to_seconds(row.time_match) - utils.convert_timematch_to_seconds(row.scores.split(',')[0]) <= 720:
                        return ['color: #FFA500; opacity: 0.5'] * len(row)
                return ['color: #00FF00; opacity: 0.5'] * len(row)

            elif (
                row.half == "2" and
                float(row.cur_prediction) <= 3.5 and
                float(row.prediction) <= 3 and
                row.score in ('0 - 0', '0 - 1', '1 - 0', '1 - 1', '2 - 1', '1 - 2', '2 - 0', '0 - 2')
            ):
                if ':' in str(row.scores) and ':' in str(row.time_match):
                    if 0 < utils.convert_timematch_to_seconds(row.time_match) - utils.convert_timematch_to_seconds(row.scores.split(',')[0]) <= 420:
                        return ['color: #FFA500; opacity: 0.5'] * len(row)
                return ['color: #00FF00; opacity: 0.5'] * len(row)

            else:
                return ['color: '] * len(row)

    def load_data():
        try:
            # url = f"{JSON_SERVER_BASE_URL}/1x/"
            # response = requests.request("GET", url, headers={}, data={})
            res = JsonServerProcessor(source='1x', params={'skip_convert_data_types': True}).get_all_matches()
            if res.get('success'):
                data = res.get('data') or []
                data = utils.sort_json(data, keys=itemgetter('half', 'time_match'))
                total_data = len(data)
                count_data = 0
                while total_data > count_data:
                    page = 1  # Page number
                    limit = 30  # Number of items per page
                    paginated_data = utils.pagination(data, page, limit)
                    count_data += len(paginated_data)

                    if paginated_data:
                        df = pd.DataFrame(
                            data=data,
                            columns=(
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
                                "url")
                        )  # .sort_values(by='time_match', ascending=False)
                        st.dataframe(
                            df.style.apply(highlight_matches, axis=1),
                            height=(len(data) + 1) * 35 + 3,
                            column_config={
                                "league": st.column_config.Column(
                                    label="League",
                                    width="medium"
                                ),
                                "team1": st.column_config.Column(
                                    label="T1",
                                    width="small"
                                ),
                                "team2": st.column_config.Column(
                                    label="T2",
                                    width="small"
                                ),
                                "h1_score": st.column_config.TextColumn(
                                    label="H1 Score",
                                    width="small"
                                ),
                                "half": st.column_config.Column(
                                    label="Half",
                                    width="small"
                                ),
                                "time_match": st.column_config.Column(
                                    label="Time",
                                    width="small"
                                ),
                                "score": st.column_config.TextColumn(
                                    label="Score",
                                    width="small"
                                ),
                                "prediction": st.column_config.NumberColumn(
                                    label="Pre",
                                    format="%.1f",
                                    width="small"
                                ),
                                "h2_prediction": st.column_config.NumberColumn(
                                    label="H2 Pre",
                                    format="%.1f",
                                    width="small"
                                ),
                                "cur_prediction": st.column_config.NumberColumn(
                                    label="Cur Pre",
                                    format="%.1f",
                                    width="small"
                                ),
                                "scores": st.column_config.TextColumn(
                                    label="Scored",
                                    width="medium"
                                ),
                                "url": st.column_config.LinkColumn(
                                    label="Link",
                                    display_text=f"Link",
                                    width="small"
                                ),

                            }
                        )
        except requests.exceptions.RequestException as e:
            logger.error(f'RequestException: {e}')
        except ConnectionResetError:
            logger.error('ConnectionResetError')
        return None

    every(15).seconds.do(load_data)
    load_data()

    while 1:
        run_pending()
        time.sleep(1)

    # while not os.path.exists("stop_1x.flag"):
    #     run_pending()
    #     time.sleep(1)
    #
    # clear()

