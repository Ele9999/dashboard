import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta
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

        # Troviamo un messaggio d'esempio di questo utente
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

    # Troviamo tag_username se c’è
    tag_user = ""
    if user_docs:
        tag_user = user_docs[0].get("tag_username", "")

    # Determiniamo l'id dei messaggi
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

    # Costruiamo i nodi messaggi dell’utente
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

        # Se doc["reshared"] non è vuoto, creiamo archi
        reshared_list = doc.get("reshared", [])
        for original in reshared_list:

            original_id = f"MSG_ORIG_{original}"
            if original_id not in nodes:
                nodes[original_id] = {
                    "data": {
                        "id": original_id,
                        "label": "MESSAGE_RESHARED",
                        "content": f"Original: {original}"
                    }
                }
           
            e_id = f"reshare_{msg_id}_{original_id}"
            edges.append({
                "data": {
                    "id": e_id,
                    "label": "RESHARED",
                    "source": msg_id,
                    "target": original_id
                }
            })

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
    # Selezione periodo
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
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    # Grafico numero messaggi nel tempo
    st.subheader("📅 Numero di messaggi nel tempo")
    tab_chart_1, tab_data_1 = st.tabs(["Chart", "Data"])
    with tab_chart_1:

        if "date" in df.columns:
            st.subheader("📅 Numero di messaggi nel tempo")
            df_counts = df.resample("D", on="date").count()
           

            fig1 = px.line(df_counts, x=df_counts.index, y="content", 
                   labels={"content": "Numero di messaggi"}, 
                   render_mode="svg")  
            st.plotly_chart(fig1)

    with tab_data_1:
        st.subheader("Tabella ultimi messaggi")
        df_sorted = df.sort_values(by="date", ascending=False)
        st.dataframe(df_sorted.head(10)) 

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
        if "content" in df.columns:
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
    with tab_data_3:
        if "content" in df.columns:
            keywords = ["murder", "bomb", "hacking", "hate", "knife", "blood", "bad"]
            word_counts = {k: 0 for k in keywords}

            for msg in df["content"].dropna():
                lower_msg = msg.lower()
                for kw in keywords:
                    word_counts[kw] += lower_msg.count(kw)

            keyword_df = pd.DataFrame(list(word_counts.items()), columns=["keyword", "frequency"])
            st.dataframe(keyword_df)
        else:
            st.info("Nessuna colonna 'content' trovata.")


    
    # Creazione grafo di interazioni

    st.subheader("📊 Tabella utenti e grafo")
    users_data = get_users_table(collection)
    df_users = pd.DataFrame(users_data).rename(columns={
        "id": "id",
        "username": "Username",
        "tag_username": "Tag Username",
        "total_posts": "Total Posts"
    })
    st.dataframe(df_users)

    
    st.subheader("Scrivi un utente per visualizzare il grafo")
    user_input = st.text_input("Inserisci username per vedere il grafo:", "")

    if st.button("Mostra Grafo"):
        if not user_input:
            st.error("Inserisci uno username valido!")
        else:
            elements = build_subgraph_for_user(user_input, collection)
            if not elements["nodes"] and not elements["edges"]:
                st.info("Nessun dato per questo utente (o limitato a 50).")
            else:
                st.subheader("Grafo di interazioni")
                node_styles = [
                    NodeStyle("USER_MAIN", color="#FF0000", caption="name", icon="person"),
                    NodeStyle("USER", color="#FF7F3E", caption="name", icon="person"),
                    NodeStyle("MESSAGE_MAIN", color="#3EB489", caption="content", icon="description"),
                    NodeStyle("MESSAGE_REPLY", color="#2A629A", caption="content", icon="description"),
                ]
                edge_styles = [EdgeStyle("*", caption="label", directed=True)]
                
                layout = "cola"
                selected_node = st_link_analysis(elements, layout, node_styles, edge_styles)
                st.session_state["selected_graph_node"] = selected_node
