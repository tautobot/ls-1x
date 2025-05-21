import streamlit as st
import pandas as pd
import time

if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(
        {"first column": [1, 2, 3, 4], "second column": [10, 20, 30, 40]}
    )


def callback(k):
    edited_rows = st.session_state[k]["edited_rows"]
    print(f"edited_rows: {edited_rows}")
    rows_to_delete = []

    for idx, value in edited_rows.items():
        if value["x"] is True:
            rows_to_delete.append(idx)

    st.session_state["data"] = (
        st.session_state["data"].drop(rows_to_delete, axis=0).reset_index(drop=True)
    )


columns = st.session_state["data"].columns
column_config = {column: st.column_config.Column(disabled=True) for column in columns}

modified_df = st.session_state["data"].copy()
modified_df["x"] = False
# Make Delete be the first column
modified_df = modified_df[["x"] + modified_df.columns[:-1].tolist()]
key = time.time()
st.data_editor(
    modified_df,
    key=key,
    args=[key],
    on_change=callback,
    hide_index=True,
    column_config=column_config,
)


# import pandas as pd
# import streamlit as st
#
# st.sidebar.header("Submit results")
#
# if 'data' not in st.session_state:
#     st.session_state["data"] = pd.DataFrame(columns=["Track", "Result"])
#
# def onAddRow():
#     row = pd.DataFrame({'Track':[st.session_state["option"]], 'Result':[st.session_state["number"]]})
#     st.session_state["data"] = pd.concat([st.session_state["data"], row])
#
# def onDeleteRows():
#     row = pd.DataFrame({'Track':[st.session_state["option"]], 'Result':[st.session_state["number"]]})
#     st.session_state["data"] = pd.DataFrame([])
#
# with st.form('Form1'):
#     st.selectbox("Select track",  ("ds Mario Kart", "Toad Harbour", "Koopa Cape"), key="option")
#     st.slider("Pick a number", 1, 12, key="number")
#     st.form_submit_button('Add', on_click=onAddRow)
#     st.form_submit_button('Delete', on_click=onDeleteRows)
#
#
# st.dataframe(st.session_state["data"])