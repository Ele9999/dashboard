import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
import math
from datetime import datetime, timedelta
#from st_aggrid import AgGrid, GridOptionsBuilder

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

def show_messages_from_collection(client, db_name, collection_name, fields_to_include):
    # Ottieni la collezione specifica
    collection = client[db_name][collection_name]
    
    # Ottieni i messaggi dalla collezione con solo i campi richiesti
    cursor = collection.find({}, fields_to_include)  # Proiezione dei campi
    messages = list(cursor)  # Converte il cursore in una lista
    
    # Rimuove il campo _id o lo trasforma in stringa per compatibilità con Pandas
    for message in messages:
        message["_id"] = str(message["_id"])  # Converte l'_id in stringa
    
    # Converte in DataFrame di Pandas
    df = pd.DataFrame(messages)
    
    # Ritorna il DataFrame
    return df


# Dashboard principale
def telegram_dashboard():
    st.title("Telegram Scraping Dashboard")

    # Connessione al database
    client = connect_to_mongo()
    db_name = 'telegram_scraping'

    # Ottieni le collezioni disponibili
    collections = get_collections(client, db_name)
    selected_collection = st.selectbox("Seleziona una collezione", collections)

#################PRIMA SEZIONE DASHBOARD
    num_group = len(collections)
    num_channel = len(collections)

    #numero di messaggi nuovi per collezione
    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    num_messages_today = 0
    for col_name in selected_collection: #conta i nuovi messaggi dalla collezione selezionata (modificare con "collections" nel caso di una unica)
        collection = client[db_name][col_name]
        num_messages_today += collection.count_documents({"timestamp": {"$gte": start_of_today}})

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(
            f"<h1 style='text-align: center; color: #4CAF50;'>{num_group}</h1>"
            f"<h4 style='text-align: center;'>Gruppi monitorati</h4>",
            unsafe_allow_html=True
    )

    with col2:
        st.markdown(
            f"<h1 style='text-align: center; color: #2196F3;'>{num_channel}</h1>"
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
    #selected_collection = st.selectbox("Seleziona una collezione", collections) #scommentare se si vuole sotto a "statistiche" questa scelta

    # Definisci i campi che vuoi visualizzare
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
            st.subheader(f"Messaggi della collezione: {selected_collection}")
            df = show_messages_from_collection(client, db_name, selected_collection, fields_to_include)

            if not df.empty:
                # Visualizza una lista dei campi disponibili nel DataFrame
                available_columns = list(df.columns)
                selected_fields = st.multiselect("Seleziona i campi da mostrare:", available_columns, default=available_columns)

                # Filtra il DataFrame per mostrare solo i campi selezionati
                filtered_df = df[selected_fields] if selected_fields else df

                # Mostra la tabella con i campi selezionati
                st.dataframe(filtered_df)

                # Seleziona una riga dalla tabella usando il messaggio come opzione visibile
                selected_index = None
                if 'message' in filtered_df.columns:  # Verifica che la colonna 'message' esista
                    selected_index = st.selectbox(
                        "Seleziona una riga per vedere i dettagli",
                        options=[None] + list(filtered_df.index),  # Aggiungi l'opzione None
                        format_func=lambda idx: filtered_df.loc[idx, 'message'] if idx is not None else "Nessuna selezione"
                    )
                else:
                    selected_index = st.selectbox(
                        "Seleziona una riga per vedere i dettagli",
                        options=[None] + list(filtered_df.index),  # Aggiungi l'opzione None
                        format_func=lambda idx: f"Riga {idx}" if idx is not None else "Nessuna selezione"
                    )

                # Mostra i dettagli solo se una riga è stata selezionata
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
            st.subheader(f"Utenti attivi: {selected_collection}")
            df = show_messages_from_collection(client, db_name, selected_collection, fields_user_to_include) #Non si vede il livello di perciolosità al momento

            if not df.empty:
                # Visualizza una lista dei campi disponibili nel DataFrame
                available_columns = list(df.columns)
                selected_fields = st.multiselect("Seleziona i campi da mostrare:", available_columns, default=available_columns)

                # Filtra il DataFrame per mostrare solo i campi selezionati
                filtered_df = df[selected_fields] if selected_fields else df

#####Impostare la tabella in ordine di pericolosità degli utenti (dal livello più alto al più basso)
#####Se è una collezione vedere solo la scritta "questa è una collezione non ci sono utenti attivi"

                # Mostra la tabella con i campi selezionati
                st.dataframe(filtered_df)

        else:
            st.info("Nessun utente trovato nella collezione selezionata.")
#################SECONDA SEZIONE DASHBOARD

#################TERZA SEZIONE DASHBOARD (Feedback e pericolosità)
    ####Impostare il fatto che quando si seleziona un messaggio si possa espandere il messaggio e poter inserire un livello di pericolosità con i dati sotto
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