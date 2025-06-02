import streamlit as st, pandas as pd
from heat_score import calc_scores

st.set_page_config(page_title="Sector Heat")
st.title("Sector Heat Dashboard")

scores = calc_scores()
df = pd.DataFrame(scores.items(), columns=["Basket","Heat Score"])
st.bar_chart(df.set_index("Basket"))
st.dataframe(df)
