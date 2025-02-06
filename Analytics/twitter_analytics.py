import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
import math
from datetime import datetime, timedelta
#from st_aggrid import AgGrid, GridOptionsBuilder
import plotly.express as px
from Databases.twitter import get_data_across_all_collections, connect_to_mongo
from st_link_analysis import st_link_analysis, NodeStyle, EdgeStyle

if "rerun" in st.session_state and st.session_state["rerun"]:
    st.session_state["rerun"] = False
    st.experimental_rerun()

def get_users_table(collection):

    pipeline = [
        {"$group": {"_id": "$username", "total_posts": {"$sum": 1}}},
        {"$sort": {"total_posts": -1}}
    ]
    agg_results = list(collection.aggregate(pipeline))

    users_data = []
    for doc in agg_results:
        user = doc["_id"]
        total = doc["total_posts"]

        # Troviamo un messaggio a caso di questo utente
        example_msg = collection.find_one({"username": user})
        tag_user = example_msg.get("tag_username", "") if example_msg else ""

        users_data.append({
            "username": user,
            "total_posts": total,
            "tag_username": tag_user
        })

    return users_data

def build_subgraph_for_user(chosen_username, collection):
    
    nodes = {}
    edges = []

    # Prendiamo fino a 50 messaggi dell’utente
    user_docs = list(collection.find({"username": chosen_username}).limit(50))
    total_posts = len(user_docs)

    # Troviamo sender_name/username se c’è
    tag_user = ""
    if user_docs:
        tag_user = user_docs[0].get("tag_username", "")

    # Determiniamo i messaggi ID
    user_node_ids = chosen_username

    # Nodo principale “USER_MAIN”
    nodes[user_node_ids] = {
        "data": {
            "id": user_node_ids,
            "label": "USER_MAIN",
            "name": chosen_username,
            "tag_username": tag_user,
            "total_posts": total_posts
        }
    }

    # A) Costruiamo i nodi messaggi dell’utente
    for doc in user_docs:
        msg_id = str(doc.get("id","NO_ID"))
        content = doc.get("content", "")
        
        if msg_id not in nodes:
            nodes[msg_id] = {
                "data": {
                    "id": msg_id,
                    "label": "MESSAGE_MAIN",
                    "content": content
                }
            }

        edge_id = f"posted_{user_node_ids}_{msg_id}"
        edges.append({
            "data": {
                "id": edge_id,
                "label": f"{chosen_username} POSTED {msg_id}",
                "source": user_node_ids,
                "target": msg_id
            }
        })

        # Se doc["reshared"] non è vuoto (lista di ID?), creiamo archi
        reshared_list = doc.get("reshared", [])
        for original in reshared_list:
            # Esempio: creiamo un nodo placeholder "MSG_ORIG_{original}"
            original_id = f"MSG_ORIG_{original}"
            if original_id not in nodes:
                nodes[original_id] = {
                    "data": {
                        "id": original_id,
                        "label": "MESSAGE_RESHARED",
                        "content": f"Original: {original}"
                    }
                }
            # Arco: msg_id_str -> original_id
            e_id = f"reshare_{msg_id}_{original_id}"
            edges.append({
                "data": {
                    "id": e_id,
                    "label": "RESHARED",
                    "source": msg_id,
                    "target": original_id
                }
            })

        # Se doc["reposts"] non è vuoto (dipende da come è strutturato),
        # gestisci analogamente, creando archi "REPOST"

        # Se doc["comments"] è una lista di commenti, potresti fare un nodo per ogni comment, ecc.
    return {
        "nodes": list(nodes.values()),
        "edges": edges
    }


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
    selected_collection = st.selectbox("Seleziona una collezione per le analisi:", ["(Nessuna)"] + collections, key="collection_key")
    # Selezione del periodo di tempo
    time_filter = st.selectbox("Filtro tempo", ["Ultimi 7 giorni", "Ultimo mese", "Ultimi 3 mesi", "Tutto"], key="time_filter_key")
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

    # Esempio di query per estrarre i dati
    query = {}
    if date_filter:
        query["timestamp"] = {"$gte": date_filter}
    data = list(collection.find(query, {"content": 1, "danger_level": 1, "date": 1}))
    df = pd.DataFrame(data)
    
    if df.empty:
        st.warning("Nessun dato disponibile per questo periodo.")
        return

   # Converte colonna 'date' in datetime
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    # Grafico 1: numero messaggi nel tempo
    if "date" in df.columns:
        st.subheader("📅 Numero di messaggi nel tempo")
        df_counts = df.resample("D", on="date").count()
        #fig1 = px.line(df_counts, x=df_counts.index, y="message", labels={"message": "Numero di messaggi"})
        #st.plotly_chart(fig1)

        fig1 = px.line(df_counts, x=df_counts.index, y="content", 
               labels={"content": "Numero di messaggi"}, 
               render_mode="svg")  # Forza SVG
        st.plotly_chart(fig1)


    # **Grafico 2: Distribuzione della pericolosità**
    st.subheader("⚠️ Distribuzione della pericolosità")
    if "danger_level" in df.columns:
        fig2 = px.histogram(df, x="danger_level", nbins=10, labels={"danger_level": "Livello di Pericolosità"})
        st.plotly_chart(fig2)
    else:
        st.info("❌ Nessun livello di pericolosità assegnato ai messaggi")

    # Grafico 3: Frequenza parole chiave (se esiste la colonna "message")
    if "content" in df.columns:
        st.subheader("🔍 Frequenza Parole Chiave")
        keywords = ["murder", "bomb", "hacking", "hate", "knife", "blood", "bad"]
        word_counts = {k:0 for k in keywords}

        for msg in df["content"].dropna():
            lower_msg = msg.lower()
            for kw in keywords:
                word_counts[kw] += lower_msg.count(kw)

        keyword_df = pd.DataFrame(list(word_counts.items()), columns=["Parola", "Frequenza"])
        if keyword_df["Frequenza"].sum() > 0:
            fig4 = px.bar(keyword_df, x="Parola", y="Frequenza")
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("❌ Nessuna parola chiave trovata nei messaggi.")


    #######################################################
    # Sezione GRAFO di interazioni
    #######################################################
    st.title("📊 Tabella Utenti e Grafo")
    st.header("Individuare un utente di interesse, scriverlo e premere il bottone")

    # 1) Mostriamo tabella utenti
    users_data = get_users_table(collection)
    if not users_data:
        st.warning("Nessun utente trovato.")
        return

    df_users = pd.DataFrame(users_data)
    st.subheader("Elenco utenti (ordinati per post)")
    st.dataframe(df_users)

    # 2) Input manuale: user digita un `username`
    chosen_user = st.text_input("Scrivi il 'username' da analizzare (es. 'FAISAL ABBAS')", "")

    # 3) Bottone
    if st.button("Mostra Grafo"):
        if not chosen_user:
            st.error("Inserisci un username valido!")
        else:
            elements = build_subgraph_for_user(chosen_user, collection)
            if not elements["nodes"] and not elements["edges"]:
                st.info("Nessun dato per questo utente (o limitato a 50).")
            else:
                # Definiamo stili
                node_styles = [
                    NodeStyle("USER_MAIN", color="#FF0000", caption="name", icon="person"),
                    NodeStyle("MESSAGE_MAIN", color="#3EB489", caption="content", icon="description"),
                    NodeStyle("MESSAGE_RESHARED", color="#2A629A", caption="content", icon="description"),
                ]
                edge_styles = [
                    EdgeStyle("*", caption="label", directed=True),
                ]

                layout = "circle"
                selected_node = st_link_analysis(elements, layout, node_styles, edge_styles)

                # Mostriamo dettagli del nodo
                if selected_node:
                    st.markdown(f"### Dettagli: `{selected_node['name']}`")
                    if "MESSAGE" in selected_node["label"]:
                        st.write("**Contenuto**:", selected_node.get("content",""))
                    else:
                        st.write("**Utente**:", selected_node["name"])
                        if "tag_username" in selected_node:
                            st.write("tag_username:", selected_node["tag_username"])
                        if "total_posts" in selected_node:
                            st.write("Post pubblicati:", selected_node["total_posts"])
