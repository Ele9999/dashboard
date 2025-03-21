import streamlit as st
from Databases.ahmia import ahmia_dashboard
from Databases.telegram import telegram_dashboard
from Databases.twitter import twitter_dashboard
from Analytics.telegram_analytics import telegram_analytics_section
from Analytics.ahmia_analytics import ahmia_analytics_section
from Analytics.twitter_analytics import twitter_analytics_section
from QuestionsToDB.telegram_info import chat_info_telegram
from QuestionsToDB.twitter_info import chat_info_twitter
from QuestionsToDB.ahmia_info import chat_info_ahmia
from RansomwareAndRansomfeed.ransomfeed import ransomfeed_dashboard

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def login():
    st.title("Piattaforma di Threat Intelligence")

    st.markdown("""
    ## Benvenuto nella Piattaforma di threat intelligence
    Questa piattaforma ti consente di gestire fonti OSINT e visualizzare le informazioni.
    - Scegli un database dalla barra di navigazione per iniziare ed assegna un livello di pericolosità ai messaggi.
    - Analizza i dati delle collezioni in modo interattivo e studia le interazioni tra gli utenti con dei grafi.
    - Interroga il database di tuo interesse grazie all'IA
    """)
    if st.button("Analizza piattaforma"):
        st.session_state.logged_in = True
        st.rerun()

def logout():

    if st.button("Torna all'homepage"):
        st.session_state.logged_in = False
        st.rerun()

login_page = st.Page(login, title="Analizza piattaforma", icon=":material/login:")
home = st.Page(logout, title="Torna all'homepage", icon=":material/logout:")

ahmia = st.Page(ahmia_dashboard, title="Ahmia Scraping", icon=":material/database:")
telegram = st.Page(telegram_dashboard, title="Telegram Scraping", icon=":material/database:")
twitter = st.Page(twitter_dashboard, title="Twitter Scraping", icon=":material/database:")

telegram_analytics = st.Page(telegram_analytics_section, title="Telegram Analytics", icon=":material/bug_report:")
ahmia_analytics = st.Page(ahmia_analytics_section, title="Ahmia Analytics", icon=":material/bug_report:")
twitter_analytics = st.Page(twitter_analytics_section, title="Twitter Analytics", icon=":material/bug_report:")

question_to_db_telegram = st.Page(chat_info_telegram, title="Telegram: Question to DB", icon= ":material/manage_search:")
question_to_db_twitter = st.Page(chat_info_twitter, title="Twitter: Question to DB", icon= ":material/manage_search:")
question_to_db_ahmia = st.Page(chat_info_ahmia, title="Ahmia: Question to DB", icon= ":material/manage_search:")


ransomfeed= st.Page(ransomfeed_dashboard, title="Ransomfeed", icon=":material/notification_important:")

if st.session_state.logged_in:
    pg = st.navigation(
        {
            "Homepage": [home],
            "Databases": [ahmia, telegram, twitter],
            "Analytics": [telegram_analytics, ahmia_analytics, twitter_analytics],
            "Question to DB": [question_to_db_telegram, question_to_db_twitter, question_to_db_ahmia],
            "Ransomware And Ramsonfeed": [ransomfeed],
        }
    )
else:
    pg = st.navigation([login_page])

pg.run()


