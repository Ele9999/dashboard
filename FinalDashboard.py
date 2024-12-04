import streamlit as st
from Databases.ahmia import ahmia_dashboard
from Databases.telegram import telegram_dashboard
from Databases.twitter import twitter_dashboard

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def login():
    st.title("Gestione Dati MongoDB")

    st.snow()
    st.balloons()

    st.markdown("""
    ## Benvenuto nella dashboard di gestione MongoDB!
    Questa applicazione ti consente di esplorare e analizzare i dati memorizzati nel tuo database MongoDB.
    - Scegli un database dalla barra di navigazione per iniziare.
    - Analizza i dati delle collezioni in modo interattivo.
    """)
    if st.button("Search on Databases"):
        st.session_state.logged_in = True
        st.rerun()

def logout():
    #inserire qui titolo e scritta nel caso volessimo riempire pure questa pagina
    if st.button("Return to Homepage"):
        st.session_state.logged_in = False
        st.rerun()

login_page = st.Page(login, title="Search on Databases", icon=":material/login:")
home = st.Page(logout, title="Return Homepage", icon=":material/logout:")

ahmia = st.Page(ahmia_dashboard, title="Ahmia Scraping", icon=":material/database:")
telegram = st.Page(telegram_dashboard, title="Telegram Scraping", icon=":material/database:")
twitter = st.Page(twitter_dashboard, title="Twitter Scraping", icon=":material/database:")

analytics = st.Page("Analytics/TraceUsers.py", title="Analytics", icon=":material/bug_report:")

ransomware= st.Page("RansomwareAndRansomfeed/ransomware.py", title="Ransomware", icon=":material/notification_important:")
ransomfeed= st.Page("RansomwareAndRansomfeed/ransomfeed.py", title="Ransomfeed", icon=":material/notification_important:")


if st.session_state.logged_in:
    pg = st.navigation(
        {
            "Homepage": [home],
            "Databases": [ahmia, telegram, twitter],
            "Analytics": [analytics],
            "RansomwareAndRamsonfeed": [ransomware, ransomfeed],
        }
    )
else:
    pg = st.navigation([login_page])

pg.run()
