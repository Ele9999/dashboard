import streamlit as st
from Databases.ahmia import ahmia_dashboard
from Databases.telegram import telegram_dashboard
from Databases.twitter import twitter_dashboard
from Analytics.telegram_analytics import telegram_analytics_section
from Analytics.ahmia_analytics import ahmia_analytics_section
from Analytics.twitter_analytics import twitter_analytics_section
from QuestionsToDB.telegram_info import chat_info_telegram
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def login():
    st.title("Gestione Dati MongoDB")

    #st.snow()
    #st.balloons()

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

telegram_analytics = st.Page(telegram_analytics_section, title="Telegram Analytics", icon=":material/bug_report:")
ahmia_analytics = st.Page(ahmia_analytics_section, title="Ahmia Analytics", icon=":material/bug_report:")
twitter_analytics = st.Page(twitter_analytics_section, title="Twitter Analytics", icon=":material/bug_report:")

question_to_db_telegram = st.Page(chat_info_telegram, title="Telegram: Question to DB", icon= ":material/manage_search:")

ransomware= st.Page("RansomwareAndRansomfeed/ransomware.py", title="Ransomware", icon=":material/notification_important:")

if st.session_state.logged_in:
    pg = st.navigation(
        {
            "Homepage": [home],
            "Databases": [ahmia, telegram, twitter],
            "Analytics": [telegram_analytics, ahmia_analytics, twitter_analytics],
            "Question to DB": [question_to_db_telegram],
            "RansomwareAndRamsonfeed": [ransomware],
        }
    )
else:
    pg = st.navigation([login_page])

pg.run()
