import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
import math
from datetime import datetime, timedelta
import plotly.express as px
from Databases.ahmia import get_data_across_all_collections, connect_to_mongo


if "rerun" in st.session_state and st.session_state["rerun"]:
    st.session_state["rerun"] = False
    st.experimental_rerun()


def ahmia_analytics_section():
    """Sezione analytics per visualizzare statistiche e grafici."""
    
    st.title("📊 Analytics - Ahmia Dashboard")

    # Connessione al database
    client = connect_to_mongo()
    db_name = 'darkweb_scraping'

    # Ottieni le collezioni disponibili
    db = client[db_name]
    collections = db.list_collection_names()

    # Selezione della collezione
    selected_collection = st.selectbox("Seleziona una collezione per le analisi:", ["Seleziona una collezione"] + collections)

    # Selezione del periodo di tempo
    time_filter = st.selectbox(
        "Filtro tempo",
        ["Ultimi 7 giorni", "Ultimo mese", "Ultimi 3 mesi", "Tutto"],
        key="time_filter_key"
    )
    date_filter = {
        "Ultimi 7 giorni": datetime.now() - timedelta(days=7),
        "Ultimo mese": datetime.now() - timedelta(days=30),
        "Ultimi 3 mesi": datetime.now() - timedelta(days=90),
        "Tutto": None
    }[time_filter]

    if selected_collection == "(Nessuna)":
        st.info("Seleziona una collezione per iniziare.")
        return

    collection = db[selected_collection]

    # Query per estrarre i dati
    query = {}
    if date_filter:
        query["date"] = {"$gte": date_filter} 
    data = list(collection.find(query, {"content": 1, "danger_level": 1, "date": 1}))
    df = pd.DataFrame(data)
    
    if df.empty:
        st.warning("Nessun dato disponibile per questo periodo.")
        return
    
    # Converte colonna 'date' in datetime
    if date_filter in df.columns:
        df[date_filter] = pd.to_datetime(df[date_filter])


    # Grafico distribuzione della pericolosità
    st.subheader("⚠️ Distribuzione della pericolosità")
    tab_chart_2, tab_data_2 = st.tabs(["Chart", "Data"])
    with tab_chart_2:
        if "danger_level" in df.columns:
            fig2 = px.histogram(df, x="danger_level", nbins=10, labels={"danger_level": "Livello di Pericolosità"})
            st.plotly_chart(fig2)
        else:
            st.info("❌ Nessun livello di pericolosità assegnato ai messaggi")

    with tab_data_2:
        if "danger_level" in df.columns:
            # Group by danger_level e contiamo quanti messaggi per livello
            df_danger = df.groupby("danger_level").size().reset_index(name="count")
            st.dataframe(df_danger)
        else:
            st.info("Nessun campo 'danger_level' nei documenti.")

    # Grafico frequenza parole chiave
    st.subheader("🔍 Frequenza Parole Chiave")
    tab_chart_3, tab_data_3 = st.tabs(["Chart", "Data"])
    with tab_chart_3:
        if "title" in df.columns:
            keywords = ["murder", "bomb", "hacking", "hate", "knife", "blood", "bad"]
            word_counts = {k:0 for k in keywords}

            for msg in df["title"].dropna():
                lower_msg = msg.lower()
                for kw in keywords:
                    word_counts[kw] += lower_msg.count(kw)

            keyword_df = pd.DataFrame(list(word_counts.items()), columns=["Parola", "Frequenza"])
            if keyword_df["Frequenza"].sum() > 0:
                fig4 = px.bar(keyword_df, x="Parola", y="Frequenza")
                st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("❌ Nessuna parola chiave trovata nei messaggi.")
    with tab_data_3:
        if "title" in df.columns:
            keywords = ["murder", "bomb", "hacking", "hate", "knife", "blood", "bad"]
            word_counts = {k: 0 for k in keywords}

            for msg in df["title"].dropna():
                lower_msg = msg.lower()
                for kw in keywords:
                    word_counts[kw] += lower_msg.count(kw)

            keyword_df = pd.DataFrame(list(word_counts.items()), columns=["keyword", "frequency"])
            st.dataframe(keyword_df)
        else:
            st.info("Nessuna colonna 'title' trovata.")
