import streamlit as st
import openai
from pymongo import MongoClient
import pandas as pd
import sys
import os

#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Databases.telegram import connect_to_mongo
import json
import os
from dotenv import load_dotenv


if "rerun" in st.session_state and st.session_state["rerun"]:
    st.session_state["rerun"] = False
    st.experimental_rerun()

# Carica le variabili dal file .env
load_dotenv()
# Recupera la chiave API
openai_api_key = os.getenv("OPENAI_API_KEY")
# Configura OpenAI
openai.api_key = openai_api_key

# Funzione per ottenere le collezioni
def get_collections(client, db_name):
    db = client[db_name]
    return db.list_collection_names()


# Funzione per generare query MongoDB in base all'input utente
def generate_mongo_query(user_input):
    prompt = f"""
    L'utente sta cercando informazioni nel database MongoDB. Genera una query valida basata su questa richiesta:
    
    '{user_input}'

    Rispondi solo con un oggetto JSON valido senza spiegazioni.
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        store = True,
        messages=[{"role": "system", "content": "Sei un esperto di database MongoDB. Rispondi solo con una query JSON valida."},
                  {"role": "user", "content": prompt}]
    )

    try:
        return eval(response["choices"][0]["title"]["content"])  # Converte JSON in dizionario
    except Exception as e:
        return {"error": str(e)}

# Funzione per eseguire la query su MongoDB
def execute_query(query, collection_name):
    db = connect_to_mongo()
    
    if "error" in query:
        return pd.DataFrame(), query["error"]  # Se c'è un errore, restituisci solo l'errore

    try:
        collection = db[collection_name]
        result = list(collection.find(query))
        return pd.DataFrame(result) if result else pd.DataFrame(), None
    except Exception as e:
        return pd.DataFrame(), str(e)

# Funzione per analizzare i risultati
def analyze_results(df):
    if df.empty:
        return "Nessun risultato trovato."
    
    prompt = f"Analizza questi dati e fornisci un riassunto:\n{df.to_string()}"

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "Sei un analista di dati MongoDB. Riassumi i dati forniti."},
                  {"role": "user", "content": prompt}]
    )

    return response["choices"][0]["title"]["content"]

# Funzione principale
def chat_info_ahmia():
    # Connessione al database
    client = connect_to_mongo()
    db_name = 'darkweb_scraping'

    # Ottieni le collezioni disponibili
    db = client[db_name]
    collections = db.list_collection_names()

    st.title("💬 Chatbot MongoDB con OpenAI")

    # Mantiene lo storico della chat
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Mostra i messaggi precedenti della chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Input utente per la richiesta
    user_input = st.chat_input("Chiedi qualcosa sui tuoi dati...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Seleziona la collezione da interrogare
        selected_collection = st.selectbox("Seleziona una collezione", collections, index=0)

        # Genera la query MongoDB da OpenAI
        query = generate_mongo_query(user_input)

        # Mostra la query generata
        with st.chat_message("assistant"):
            st.code(query, language="json")

        # Esegue la query
        df, error = execute_query(query, selected_collection)

        if error:
            response_text = f"❌ Errore nell'esecuzione della query: {error}"
        elif not df.empty:
            response_text = "📊 Ecco i risultati trovati:"
            st.dataframe(df)  # Mostra i dati in tabella
        else:
            response_text = "⚠️ Nessun dato trovato."

        # Aggiunge il messaggio di risposta alla chat
        st.session_state.messages.append({"role": "assistant", "content": response_text})
        with st.chat_message("assistant"):
            st.markdown(response_text)

        # Analizza i risultati
        if not df.empty:
            summary = analyze_results(df)
            st.session_state.messages.append({"role": "assistant", "content": summary})
            with st.chat_message("assistant"):
                st.markdown(summary)
