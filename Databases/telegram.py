import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
import math

if "rerun" in st.session_state and st.session_state["rerun"]:
    st.session_state["rerun"] = False
    st.experimental_rerun()

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

# Dashboard principale
def telegram_dashboard():
    st.title("Telegram Scraping Dashboard")

    # Connessione al database
    client = connect_to_mongo()
    db_name = 'telegram_scraping'

    # Ottieni le collezioni disponibili
    collections = get_collections(client, db_name)
    selected_collection = st.selectbox("Seleziona una collezione", collections)

    if selected_collection:
        df = load_data(client, db_name, selected_collection)

        ## Selezione del messaggio da analizzare
        if not df.empty:
            #st.subheader(f"Dati della collezione: {selected_collection} (Database: {db_name})")
            with st.expander(f"Dati della collezione: {selected_collection} (Database: {db_name})"):
                st.dataframe(df)

            #seleziona un record
            selected_index = st.selectbox("Seleiona un record", df.index)

            if selected_index is not None:
                # Mostra il record selezionato
                selected_record = df.loc[selected_index]
                #st.write("Record selezionato:")
                with st.expander("Record selezionato"):
                    st.json(selected_record.to_dict())

                # Modifica del record
                st.subheader("Modifica Record")
                pericolosita = selected_record.get("danger_level", 5)
                if pericolosita is None or math.isnan(pericolosita):
                    pericolosita = 5  # Imposta valore predefinito se danger_level è NaN

                pericolosita = st.slider("Pericolosità (0-10)", 0, 10, int(pericolosita), key="slider_modifica_record")
                comment = st.text_input("Commento Utente", selected_record.get("user_comment", ""))
                revised_by = st.text_input("Revisionato da (nome utente)", "", key="modifica_record")

                if st.button("Salva Modifiche"):
                    if revised_by.strip() == "":
                        st.error("Il campo 'Revisionato da' non può essere vuoto!")
                    else:
                        collection = client[db_name][selected_collection]
                        update_record(
                            selected_record["_id"],
                            pericolosita,
                            comment,
                            revised_by,
                            collection
                        )
                        st.success("Modifiche salvate con successo!")
                        st.query_params.update(st.query_params)

            ## Tabella dei messaggi revisionati
            revisionati = df[df.get("revisioned", "no") == "yes"]
            if not revisionati.empty:
                st.subheader("Messaggi revisionati")
                st.dataframe(revisionati[["message", "danger_level", "user_comment"]])

                # Modifica feedback
                revisionati["selezione"] = revisionati["message"] + " (ID: " + revisionati["_id"] + ")"
                selected_revised = st.selectbox(
                    "Seleziona un messaggio revisionato per cambiare feedback",
                    revisionati["selezione"]
                )
                if selected_revised:
                    record_id = selected_revised.split("ID: ")[-1].replace(")", "").strip()
                    record = revisionati[revisionati["_id"] == record_id].iloc[0]
                    st.write("**Contenuto del messaggio:**")
                    st.write(record["message"])

                    # Form per modificare feedback
                    #nuovo_pericolosita = st.selectbox("Nuovo livello di pericolosità", ["Basso", "Medio", "Alto"])
                    nuovo_pericolosita = st.slider("Pericolosità (0-10)", 0, 10, int(pericolosita), key="slider_modifica_feedback")
                    comment = st.text_area("Motivo del cambiamento")
                    revised_by = st.text_input("Revisionato da (nome utente)", "", key="modifica_feedback")
                    if st.button("Aggiorna feedback"):
                        collection = client[db_name][selected_collection]
                        update_record(record["_id"], nuovo_pericolosita, comment, revised_by, collection)
                        st.success("Feedback aggiornato con successo!")
                        #st.query_params.update(st.query_params)
                        st.session_state["rerun"] = True
                        st.stop()
            else:
                st.info("Nessun messaggio revisionato.")