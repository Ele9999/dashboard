import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
import math
from datetime import datetime, timedelta
#from st_aggrid import AgGrid, GridOptionsBuilder
import plotly.express as px
from Databases.twitter import get_data_across_all_collections, connect_to_mongo


if "rerun" in st.session_state and st.session_state["rerun"]:
    st.session_state["rerun"] = False
    st.experimental_rerun()


def twitter_analytics_section():
    """Sezione analytics per visualizzare statistiche e grafici."""
    
    st.title("📊 Analytics - Twitter Dashboard")

    # Connessione al database
    client = connect_to_mongo()
    db_name = 'twitter_scraping'

    # Ottieni le collezioni disponibili
    db = client[db_name]
    collections = db.list_collection_names()

    # Selezione della collezione
    selected_collection = st.selectbox("Seleziona una collezione per le analisi:", ["Seleziona una collezione"] + collections)

    # Selezione del periodo di tempo
    time_filter = st.selectbox("Filtro tempo", ["Ultimi 7 giorni", "Ultimo mese", "Ultimi 3 mesi", "Tutto"])
    date_filter = {
        "Ultimi 7 giorni": datetime.now() - timedelta(days=7),
        "Ultimo mese": datetime.now() - timedelta(days=30),
        "Ultimi 3 mesi": datetime.now() - timedelta(days=90),
        "Tutto": None
    }[time_filter]

    # Recupera i dati
    if selected_collection == "Seleziona una collezione":
        df = get_data_across_all_collections(client, db_name, 'analytics')
    else:
        collection = db[selected_collection]
        query = {"timestamp": {"$gte": date_filter}} if date_filter else {}
        data = list(collection.find(query, {"content": 1, "danger_level": 1, "date": 1}))
        df = pd.DataFrame(data)

    if df.empty:
        st.warning("Nessun dato disponibile per questo periodo.")
        return

    # Convertiamo la colonna 'date' in formato datetime
    df["date"] = pd.to_datetime(df["date"])

    # **Grafico 1: Numero di messaggi nel tempo**
    st.subheader("📅 Numero di messaggi nel tempo")
    df_counts = df.resample("D", on="date").count()
    fig1 = px.line(df_counts, x=df_counts.index, y="content", labels={"content": "Numero di messaggi"})
    st.plotly_chart(fig1)

    # **Grafico 2: Distribuzione della pericolosità**
    st.subheader("⚠️ Distribuzione della pericolosità")
    if "danger_level" in df.columns:
        fig2 = px.histogram(df, x="danger_level", nbins=10, labels={"danger_level": "Livello di Pericolosità"})
        st.plotly_chart(fig2)
    else:
        st.info("❌ Nessun livello di pericolosità assegnato ai messaggi")

    # **Grafico 3: Attività per gruppo/canale**
    if selected_collection == "Tutte le collezioni":
        st.subheader("🔥 Attività nei gruppi e canali")
        df_counts = df.groupby("collection_name").size().reset_index(name="conteggio")
        fig3 = px.bar(df_counts, x="collection_name", y="conteggio", labels={"conteggio": "Numero di Messaggi"})
        st.plotly_chart(fig3)


    # **Grafico 4: Trend delle parole chiave**
    if "content" in df.columns:
        st.subheader("🔍 Frequenza delle Parole Chiave")

        # Lista delle parole chiave da monitorare
        keywords = ["murder", "bomb", "hacking", "hate", "knife", "blood", "bad"]

        # Contiamo quante volte ogni parola appare nei messaggi
        word_counts = {word: 0 for word in keywords}
        keyword_messages = {word: [] for word in keywords}  # Dizionario per salvare i messaggi contenenti la parola

        for msg in df["content"].dropna():
            for word in keywords:
                if word in msg.lower():
                    word_counts[word] += msg.lower().split().count(word)
                    keyword_messages[word].append(msg)  # Salva il messaggio se contiene la parola

        # Creiamo un DataFrame per il grafico
        keyword_df = pd.DataFrame(list(word_counts.items()), columns=["Parola", "Frequenza"])

        # Se ci sono parole con frequenza > 0, mostriamo il grafico
        if keyword_df["Frequenza"].sum() > 0:
            fig4 = px.bar(
                keyword_df, 
                x="Parola", 
                y="Frequenza", 
                labels={"Parola": "Parola", "Frequenza": "Numero di occorrenze"},
                #title="🔍 Clicca su una parola per vedere i messaggi correlati"
            )

            ## Mostra il grafico interattivo
            st.plotly_chart(fig4, use_container_width=True)
#
            ## **Aggiunge un'area interattiva per vedere i messaggi contenenti la parola**
            #selected_word = st.selectbox("Seleziona una parola per vedere i messaggi:", [""] + keywords)
#
            #if selected_word and selected_word in keyword_messages:
            #    st.subheader(f"📩 Messaggi che contengono '{selected_word}'")
            #    for message in keyword_messages[selected_word]:
            #        with st.expander("Visualizza messaggio"):
            #            st.write(message)
        else:
            st.info("❌ Nessuna delle parole chiave selezionate è stata trovata nei messaggi.")
