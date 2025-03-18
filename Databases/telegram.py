import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
import math
from datetime import datetime, timedelta
import plotly.express as px
import os
from dotenv import load_dotenv


st.set_page_config(layout="wide")

if "rerun" in st.session_state and st.session_state["rerun"]:
    st.session_state["rerun"] = False
    st.experimental_rerun()


load_dotenv()

def connect_to_mongo():
    mongo_uri = os.getenv("MONGO_URI") 
    
    if not mongo_uri:
        raise ValueError("❌ Errore: MONGO_URI non trovato nel file .env")

    client = MongoClient(mongo_uri)
    return client

# Funzione per ottenere le collezioni
def get_collections(client, db_name):
    db = client[db_name]
    return db.list_collection_names()

# Funzione per caricare i dati di una collezione
def load_data(client, db_name, collection_name):
    collection = client[db_name][collection_name]
    data = list(collection.find())

    # Converti _id in stringa (per compatibilità con Streamlit)
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

def show_messages_from_collection(client, db_name, collection_name, fields_to_include):
    collection = client[db_name][collection_name]
    
    # Ottieniamo i messaggi dalla collezione con solo i campi richiesti
    cursor = collection.find({}, fields_to_include)  # Proiezione dei campi
    messages = list(cursor)  # Converte il cursore in una lista
    
    for message in messages:
        message["_id"] = str(message["_id"])  # Converte l'_id in stringa
    
    # Converte in DataFrame di Pandas
    df = pd.DataFrame(messages)
    
    # Ritorna il DataFrame
    return df

def classify_collections(client, db_name):
    db = client[db_name]  # Connetti al database
    collections = db.list_collection_names() 

    num_groups = 0
    num_channels = 0

    # Itera su ciascuna collezione
    for collection_name in collections:
        collection = db[collection_name]
        # Verifica se almeno un documento ha il campo "sender_username"
        has_user = collection.count_documents({"sender_username": {"$exists": True}}, limit=1) > 0

        if has_user:
            num_groups += 1  # Se esiste almeno un campo "sender_username", è un gruppo
        else:
            num_channels += 1  # Altrimenti è un canale

    return num_groups, num_channels

def get_active_users(collection):
    """
    Recupera gli utenti attivi con campi 'sender_name', 'sender_username' e 'danger_level'.
    """
    query = {"sender_username": {"$exists": True}}  # Solo documenti che contengono 'sender_username'
    projection = {"_id": 0, "sender_username": 1, "sender_name": 1, "danger_level": 1}
    return list(collection.find(query, projection))

def show_all_collections_data(client, db_name, fields_to_include):
    """
    Unisce i dati da tutte le collezioni in un unico DataFrame.
    Gestisce i campi mancanti impostando valori di default.
    """
    db = client[db_name]
    collections = db.list_collection_names()
    combined_data = []

    for collection_name in collections:
        collection = db[collection_name]
        data = list(collection.find({}, {field: 1 for field in fields_to_include}))
        for doc in data:
            for field in fields_to_include:
                doc.setdefault(field, "")  # Imposta "" come valore predefinito per campi mancanti
            doc['collection_name'] = collection_name  
        combined_data.extend(data)

    return pd.DataFrame(combined_data)

##Utenti attivi
def get_group_user_messages(client, db_name):
    """
    Ottiene tutti i messaggi per i gruppi con l'informazione di chi ha inviato cosa e in quale gruppo.
    """
    db = client[db_name]
    collections = db.list_collection_names()
    group_data = []

    for collection_name in collections:
        collection = db[collection_name]
        # Verifica se è un gruppo
        is_group = collection.count_documents({"sender_username": {"$exists": True}}, limit=1) > 0

        if is_group:
            messages = collection.find({}, {"sender_name": 1, "sender_username": 1, "message": 1})
            for msg in messages:
                group_data.append({
                    "group_name": collection_name,
                    "sender_name": msg.get("sender_name", "Sconosciuto"),
                    "sender_username": msg.get("sender_username", "Sconosciuto"),
                    "message": msg.get("message", "Nessun messaggio")
                })
    return pd.DataFrame(group_data)


def get_channel_messages(client, db_name):
    """
    Ottiene tutti i messaggi per i canali con il loro contenuto.
    """
    db = client[db_name]
    collections = db.list_collection_names()
    channel_data = []

    for collection_name in collections:
        collection = db[collection_name]
        # Verifica se è un canale
        is_channel = collection.count_documents({"sender_username": {"$exists": False}}, limit=1) > 0

        if is_channel:
            messages = collection.find({}, {"message": 1})
            for msg in messages:
                channel_data.append({
                    "channel_name": collection_name,
                    "message": msg.get("message", "Nessun messaggio")
                })
    return pd.DataFrame(channel_data)


def get_group_user_messages_for_collection(collection):
    """
    Ottiene messaggi per una collezione gruppo.
    """
    messages = collection.find({}, {"sender_name": 1, "sender_username": 1, "message": 1})
    group_data = []
    for msg in messages:
        group_data.append({
            "sender_name": msg.get("sender_name", "Sconosciuto"),
            "sender_username": msg.get("sender_username", "Sconosciuto"),
            "message": msg.get("message", "Nessun messaggio")
        })
    return pd.DataFrame(group_data)


def get_most_dangerous_messages_for_channel(collection):
    """
    Ottiene i messaggi più pericolosi per un canale, ordinati per 'danger_level'.
    """
    messages = collection.find({}, {"message": 1, "danger_level": 1}).sort("danger_level", -1)
    channel_data = []
    for msg in messages:
        channel_data.append({
            "message": msg.get("message", "Nessun messaggio"),
            "danger_level": msg.get("danger_level", 0)
        })
    return pd.DataFrame(channel_data)

def get_data_across_all_collections(client, db_name, data_type):
    """Recupera dati aggregati da tutte le collezioni per gruppi/canali."""
    db = client[db_name]
    collections = db.list_collection_names()
    combined_data = []

    for collection_name in collections:
        collection = db[collection_name]

        if data_type == 'dangerous_messages':
            messages = collection.find({}, {"message": 1, "danger_level": 1}).sort("danger_level", -1)
            for msg in messages:
                combined_data.append({
                    "message": msg.get("message", "Nessun messaggio"),
                    "danger_level": msg.get("danger_level", 0),
                    "collection_name": collection_name
                })

        elif data_type == 'active_users':
            is_group = collection.count_documents({"sender_username": {"$exists": True}}, limit=1) > 0
            if is_group:
                messages = collection.find({}, {"sender_name": 1, "sender_username": 1, "message": 1})
                for msg in messages:
                    combined_data.append({
                        "sender_name": msg.get("sender_name", "Sconosciuto"),
                        "sender_username": msg.get("sender_username", "Sconosciuto"),
                        "message": msg.get("message", "Nessun messaggio"),
                        "group_name": collection_name
                    })

        elif data_type == 'user_activity':
            user_activity = collection.aggregate([
                {"$group": {"_id": "$sender_username", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ])
            for activity in user_activity:
                combined_data.append({
                    "username": activity["_id"],
                    "message_count": activity["count"],
                    "collection_name": collection_name
                })

    return pd.DataFrame(combined_data)

def show_data_for_selected_collection(selected_collection, client, db_name):
    """Mostra i dati in base alla selezione (Tutte le collezioni o singola collezione)."""
    db = client[db_name]

    if selected_collection == "Tutte le collezioni":
        st.subheader("📊 Dati di tutte le collezioni")

        # Messaggi più pericolosi tra tutti i gruppi/canali
        dangerous_messages_df = get_data_across_all_collections(client, db_name, 'dangerous_messages')
        if not dangerous_messages_df.empty:
            st.subheader("🔥 Messaggi più pericolosi")
            st.dataframe(dangerous_messages_df.rename(columns={"collection_name": "Gruppo/Canale"}))
        else:
            st.info("Nessun messaggio pericoloso trovato.")

        # Utenti attivi nei gruppi
        active_users_df = get_data_across_all_collections(client, db_name, 'active_users')
        if not active_users_df.empty:
            st.subheader("👥 Utenti attivi nei gruppi")
            st.dataframe(active_users_df.rename(columns={"group_name": "Gruppo"}))
        else:
            st.info("Nessun utente attivo trovato nei gruppi.")

        # Utenti più attivi
        user_activity_df = get_data_across_all_collections(client, db_name, 'user_activity')
        if not user_activity_df.empty:
            st.subheader("📈 Utenti più attivi")
            st.dataframe(user_activity_df.rename(columns={"collection_name": "Gruppo/Canale"}))
        else:
            st.info("Nessun dato sugli utenti più attivi.")

    else:
        st.subheader(f"📊 Dati della collezione: {selected_collection}")

        # Messaggi più pericolosi
        st.subheader("⚠️ Messaggi più pericolosi")
        dangerous_messages = get_data_across_all_collections(client, db_name, 'dangerous_messages')
        dangerous_messages = dangerous_messages[dangerous_messages["collection_name"] == selected_collection]

        if not dangerous_messages.empty:
            st.dataframe(dangerous_messages.rename(columns={"message": "Messaggio", "danger_level": "Livello di Pericolosità"}))
        else:
            st.info("Nessun messaggio pericoloso trovato in questa collezione.")


# Dashboard principale
def telegram_dashboard():
    st.title("Telegram Scraping Dashboard")

    # Connessione al database
    client = connect_to_mongo()
    db_name = 'telegram_scraping'

    # Ottieniamo le collezioni disponibili
    db = client[db_name]
    collections = db.list_collection_names()
    collections_with_all = ["Tutte le collezioni"] + collections

    selected_collection = st.selectbox("Seleziona una collezione", collections_with_all)

#################PRIMA SEZIONE DASHBOARD
    num_groups, num_channels = classify_collections(client, db_name)

    # Numero di messaggi nuovi per collezione 
    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    num_messages_today = sum(
        client[db_name][col].count_documents({"date": {"$gte": start_of_today}})
        for col in collections
    )


    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(
            f"<h1 style='text-align: center; color: #4CAF50;'>{num_groups}</h1>"
            f"<h4 style='text-align: center;'>Gruppi monitorati</h4>",
            unsafe_allow_html=True
    )

    with col2:
        st.markdown(
            f"<h1 style='text-align: center; color: #2196F3;'>{num_channels}</h1>"
            f"<h4 style='text-align: center;'>Canali monitorati</h4>",
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            f"<h1 style='text-align: center; color: #FF5722;'>{num_messages_today}</h1>"
            f"<h4 style='text-align: center;'>Nuovi messaggi oggi</h4>",
            unsafe_allow_html=True
        )
#################PRIMA SEZIONE DASHBOARD

#################SECONDA SEZIONE DASHBOARD

    col1, col2 = st.columns(2)

    fields_to_include = {
        "id": 1,  
        "message": 1,  
        "danger_level": 1,  
        "revised_by": 1,  
        "revisioned": 1,
        "user_comment": 1,
        "date": 1,
        "sender_name": 1,
        "sender_username": 1
    }

    fields_user_to_include = {
        "sender_name": 1,
        "sender_username": 1,
        "danger_level": 1
    }

    with col1:
        if selected_collection:
            st.subheader(f"Dati della collezione: {selected_collection}")
        
            if selected_collection == "Tutte le collezioni":
                st.subheader("Dati di tutte le collezioni")
                df = show_all_collections_data(client, db_name, fields_to_include)
            else:
                collection = db[selected_collection]
                data = list(collection.find({}, {field: 1 for field in fields_to_include}))
                for doc in data:
                    for field in fields_to_include:
                        doc.setdefault(field, "")
                df = pd.DataFrame(data)
        
            if not df.empty:
                # Visualizza una lista dei campi disponibili nel DataFrame
                available_columns = list(df.columns)
                selected_fields = st.multiselect("Seleziona i campi da mostrare:", available_columns, default=available_columns)
        
                # Filtra il DataFrame per mostrare solo i campi selezionati
                filtered_df = df[selected_fields] if selected_fields else df
        
                # Mostra la tabella con i campi selezionati
                st.dataframe(filtered_df)
        
                # Seleziona una riga dalla tabella usando il messaggio
                selected_index = None
                if 'message' in filtered_df.columns:  # Verifica che la colonna 'message' esista
                    selected_index = st.selectbox(
                        "Seleziona una riga per vedere i dettagli",
                        options=[None] + list(filtered_df.index),  
                        format_func=lambda idx: filtered_df.loc[idx, 'message'] if idx is not None else "Nessuna selezione"
                    )
                else:
                    selected_index = st.selectbox(
                        "Seleziona una riga per vedere i dettagli",
                        options=[None] + list(filtered_df.index),  
                        format_func=lambda idx: f"Riga {idx}" if idx is not None else "Nessuna selezione"
                    )
        

                if selected_index is not None:
                    # Mostra i dettagli della riga selezionata
                    selected_message = df.loc[selected_index]
                    st.subheader("**Dettagli del Messaggio**")
                    for field in available_columns:  # Mostra tutti i campi nella riga selezionata
                        st.write(f"- **{field.capitalize()}**: {selected_message[field]}")
            else:
                st.info("Nessun messaggio trovato nella collezione selezionata.")


    with col2:

        if selected_collection:
            st.subheader(f"Utenti Attivi: {selected_collection}")

            if selected_collection == "Tutte le collezioni":
                # Per gruppi
                group_user_messages = get_group_user_messages(client, db_name)
                if not group_user_messages.empty:
                    st.subheader("Messaggi nei gruppi")
                    st.dataframe(group_user_messages.rename(
                        columns={"sender_name": "Utente", "message": "Messaggio", "group_name": "Gruppo"}
                    ))

                # Per canali
                channel_messages = get_channel_messages(client, db_name)
                if not channel_messages.empty:
                    st.subheader("Messaggi nei canali")
                    st.dataframe(channel_messages.rename(
                        columns={"message": "Messaggio", "channel_name": "Canale"}
                    ))
            else:
                collection = db[selected_collection]
                # Verifica se è un gruppo o un canale
                is_group = collection.count_documents({"sender_username": {"$exists": True}}, limit=1) > 0

                if is_group:
                    # Mostra messaggi nei gruppi
                    group_messages = get_group_user_messages_for_collection(collection)
                    if not group_messages.empty:
                        st.dataframe(group_messages.rename(
                            columns={"sender_name": "Utente", "message": "Messaggio"}
                        ))
                    else:
                        st.info("Nessun messaggio trovato per questo gruppo.")
                else:
                    # Mostra messaggi più pericolosi nei canali
                    dangerous_messages = get_most_dangerous_messages_for_channel(collection)
                    if not dangerous_messages.empty:
                        st.dataframe(dangerous_messages.rename(
                            columns={"message": "Messaggio", "danger_level": "Livello di Pericolosità"}
                        ))
                    else:
                        st.info("Nessun messaggio trovato per questo canale.")
#################SECONDA SEZIONE DASHBOARD

#################TERZA SEZIONE DASHBOARD
    if selected_collection:
        df = load_data(client, db_name, selected_collection)

        ## Selezione del messaggio da analizzare
        if not df.empty:
            with st.expander(f"Dati della collezione: {selected_collection} (Database: {db_name})"):
                st.dataframe(df)

            selected_index = st.selectbox("Seleiona un record", df.index)

            if selected_index is not None:
                # Mostra il record selezionato
                selected_record = df.loc[selected_index]
                with st.expander("Record selezionato"):
                    st.json(selected_record.to_dict())

                # Modifica del record selezionato
                st.subheader("Modifica Record")
                pericolosita = selected_record.get("danger_level", 5)
                if pericolosita is None or math.isnan(pericolosita):
                    pericolosita = 5  # Imposta valore predefinito a 5 se danger_level è NaN

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

    ##Tabella dei messaggi revisionati
    # Verifica se la colonna "revisioned" esiste nel DataFrame
    if "revisioned" in df.columns:
        revisionati = df[df["revisioned"] == "yes"]  # Filtra i messaggi revisionati
    else:
        revisionati = pd.DataFrame()  # Crea un DataFrame vuoto se la colonna non esiste

    # Mostra i messaggi revisionati solo se ci sono dati
    if not revisionati.empty:
        st.subheader("Messaggi revisionati")
        st.dataframe(revisionati[["message", "danger_level", "user_comment"]])

        # Modifica dei feedback
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

            # Form per modificare i feedback
            nuovo_pericolosita = st.slider(
                "Pericolosità (0-10)",
                0,
                10,
                int(record["danger_level"]) if "danger_level" in record else 5,
                key="slider_modifica_feedback"
            )
            comment = st.text_area("Motivo del cambiamento")
            revised_by = st.text_input("Revisionato da (nome utente)", "", key="modifica_feedback")
            if st.button("Aggiorna feedback"):
                collection = client[db_name][selected_collection]
                update_record(record["_id"], nuovo_pericolosita, comment, revised_by, collection)
                st.success("Feedback aggiornato con successo!")
                st.session_state["rerun"] = True
                st.stop()
    else:
        st.info("Nessun messaggio revisionato.")

#####QUARTA SEZIONE DASHBOARD
    show_data_for_selected_collection(selected_collection, client, db_name)
