import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
import math
from datetime import datetime, timedelta
import plotly.express as px
import os
from dotenv import load_dotenv

@st.cache_resource
def connect_to_mongo():
    client = MongoClient('') 
    return client

# Funzione per ottenere le collezioni
def get_collections(client, db_name):
    db = client[db_name]
    return db.list_collection_names()

# Funzione per caricare i dati di una collezione
def load_data(client, db_name, collection_name):
    collection = client[db_name][collection_name]
    data = list(collection.find())

    for record in data:
        record["_id"] = str(record["_id"])

    return pd.DataFrame(data)

# Funzione per aggiornare un record
def update_record(record_id, pericolosita, comment, revised_by, collection):
    collection.update_one(
        {"_id": ObjectId(record_id)},
        {
            "$set": {
                "danger_level": pericolosita, 
                "user_comment": comment,
                "revisioned": "yes",
                "revised_by": revised_by
            }
        }
    )

# Classificazione tra gruppi e canali
def classify_collections(client, db_name):
    db = client[db_name]
    collections = db.list_collection_names()
    num_groups = 0
    num_channels = 0

    for collection_name in collections:
        collection = db[collection_name]
        has_user = collection.count_documents({"nome": {"$exists": True}}, limit=1) > 0

        if has_user:
            num_groups += 1
        else:
            num_channels += 1

    return num_groups, num_channels

# Ottieni utenti attivi (aziende)
def get_active_users(collection):
    query = {"nome": {"$exists": True}}
    projection = {"_id": 0, "nome": 1, "paese": 1, "risk_assessment.score": 1}
    return list(collection.find(query, projection))

# Funzione per aggregare dati da tutte le collezioni
def show_all_collections_data(client, db_name, fields_to_include):
    db = client[db_name]
    collections = db.list_collection_names()
    combined_data = []

    for collection_name in collections:
        collection = db[collection_name]
        data = list(collection.find({}, {field: 1 for field in fields_to_include}))

        for doc in data:
            for field in fields_to_include:
                doc.setdefault(field, "")
            doc['collection_name'] = collection_name

        combined_data.extend(data)

    return pd.DataFrame(combined_data)

# Dashboard principale
def ransomfeed_dashboard():
    st.title("📊 Ransomfeed Scraping Dashboard")

    client = connect_to_mongo()
    db_name = 'dbScraping'
    db = client[db_name]

    collections = db.list_collection_names()
    collections_with_all = ["Tutte le collezioni"] + collections
    selected_collection = st.selectbox("Seleziona una collezione", collections_with_all)

    # Statistiche principali
    num_groups, num_channels = classify_collections(client, db_name)

    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    num_messages_today = sum(
        client[db_name][col].count_documents({"data": {"$gte": start_of_today}})
        for col in collections
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Gruppi monitorati", num_groups)
    with col2:
        st.metric("Canali monitorati", num_channels)
    with col3:
        st.metric("Nuovi messaggi oggi", num_messages_today)

    # Seconda sezione dashboard
    col1, col2 = st.columns(2)
    fields_to_include = {
        "id": 1, "descrizione": 1, "risk_assessment.score": 1, 
        "risk_assessment.why": 1, "data": 1, "nome": 1, "paese": 1
    }

    with col1:
        if selected_collection:
            st.subheader(f"Dati della collezione: {selected_collection}")

            if selected_collection == "Tutte le collezioni":
                df = show_all_collections_data(client, db_name, fields_to_include)
            else:
                collection = db[selected_collection]
                data = list(collection.find({}, {field: 1 for field in fields_to_include}))

                for doc in data:
                    for field in fields_to_include:
                        doc.setdefault(field, "")
                df = pd.DataFrame(data)

            if not df.empty:
                selected_fields = st.multiselect("Seleziona i campi:", df.columns, default=df.columns)
                st.dataframe(df[selected_fields])

                selected_index = st.selectbox(
                    "Seleziona un record per i dettagli",
                    options=[None] + list(df.index),
                    format_func=lambda idx: df.loc[idx, 'descrizione'] if idx is not None else "Nessuna selezione"
                )

                if selected_index is not None:
                    selected_message = df.loc[selected_index]
                    st.subheader("**Dettagli**")
                    for field in df.columns:
                        st.write(f"- **{field}**: {selected_message[field]}")
            else:
                st.info("Nessun dato disponibile.")

    # Analisi del rischio per le aziende
    with col2:
        st.subheader("🔍 Risk Assessment")
        if selected_collection == "Tutte le collezioni":
            risk_df = show_all_collections_data(client, db_name, ["nome", "risk_assessment.score", "risk_assessment.why"])
        else:
            collection = db[selected_collection]
            data = list(collection.find({}, {"nome": 1, "risk_assessment.score": 1, "risk_assessment.why": 1}))
            risk_df = pd.DataFrame(data)

        if not risk_df.empty:
            st.dataframe(risk_df)
        else:
            st.info("Nessun dato di rischio disponibile.")

    # Grafico distribuzione del rischio
    st.subheader("⚠️ Distribuzione del Rischio")
    if "risk_assessment.score" in risk_df.columns:
        fig = px.histogram(risk_df, x="risk_assessment.score", nbins=5)
        st.plotly_chart(fig)
    else:
        st.info("Nessun dato di rischio disponibile.")

    # Selezione dettagli azienda 
    st.subheader("🏢 Analizza una specifica azienda")
    
    selected_company = st.selectbox(
        "Seleziona un'azienda:", 
        risk_df["nome"].dropna().unique() if not risk_df.empty else []
    )
    
    if selected_company:
        company_data = risk_df[risk_df["nome"] == selected_company].iloc[0]
    
        # Controlliamo che risk_assessment sia un dizionario, altrimenti impostiamo un valore vuoto
        risk_data = company_data["risk_assessment"] if isinstance(company_data["risk_assessment"], dict) else {}
    
        # Estraggo i valori con .get() per evitare errori
        risk_score = risk_data.get("score", "N/A")
        risk_reason = risk_data.get("why", "N/A")
    
        # Mostra i dati con fallback "N/A"
        st.write(f"📌 **Nome**: {company_data.get('nome', 'Sconosciuto')}")
        st.write(f"⚠️ **Risk Score**: {risk_score}")
        st.write(f"📖 **Motivo del rischio**: {risk_reason}")


    # Modifica livello di rischio
    if selected_company:
        new_risk = st.selectbox("Modifica livello di rischio:", ["LOW", "MEDIUM", "HIGH"])
        reason = st.text_area("Motivo della modifica:")
        if st.button("Salva Modifica"):
            collection = db[selected_collection]
            collection.update_one(
                {"nome": selected_company},
                {"$set": {"risk_assessment.score": new_risk, "risk_assessment.why": reason}}
            )
            st.success("Rischio aggiornato con successo!")
            st.experimental_rerun()
