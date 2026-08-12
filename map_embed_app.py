import streamlit as st

with open("index.html", encoding="utf-8") as f:
    html = f.read()

st.components.v1.html(html, height=650)
