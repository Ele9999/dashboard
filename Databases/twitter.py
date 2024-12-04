import streamlit as st
import pandas as pd
from pymongo import MongoClient

# Connessione al client MongoDB
@st.cache_resource
def connect_to_mongo():
    client = MongoClient('mongodb+srv://eleonorapapa:C6A62LvpNQBfTZ29@cluster0.p5axc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')  # Inserisci la tua connection string
    return client

# Funzione per ottenere le collezioni
def get_collections(client, db_name):
    db = client[db_name]
    return db.list_collection_names()

# Funzione per caricare i dati di una collezione
def load_data(client, db_name, collection_name):
    collection = client[db_name][collection_name]
    data = list(collection.find())

    # Converti _id in stringa per compatibilità con Streamlit
    for record in data:
        record["_id"] = str(record["_id"])

    # Crea il DataFrame
    df = pd.DataFrame(data)
    return df

# Funzione per visualizzare la dashboard della collezione
def twitter_dashboard():
    st.title("Twitter Scraping Dashboard")

    # Connessione al database
    client = connect_to_mongo()
    db_name = 'twitter_scraping'

    # Ottieni le collezioni disponibili
    collections = get_collections(client, db_name)
    selected_collection = st.selectbox("Seleziona una collezione", collections)

    if selected_collection:
        df = load_data(client, db_name, selected_collection)
        if not df.empty:
            st.dataframe(df)
        else:
            st.warning("La collezione selezionata è vuota.")

