import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta
#from Databases.telegram import get_data_across_all_collections, connect_to_mongo
from st_link_analysis import st_link_analysis, NodeStyle, EdgeStyle
import plotly.express as px
import numpy as np

if "rerun" in st.session_state and st.session_state["rerun"]:
    st.session_state["rerun"] = False
    st.experimental_rerun()

# Connessione al client MongoDB
@st.cache_resource
def connect_to_mongo():
    client = MongoClient('mongodb+srv://eleonorapapa:C6A62LvpNQBfTZ29@cluster0.p5axc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0') 
    return client

# Funzione per ottenere le collezioni
def get_collections(client, db_name):
    db = client[db_name]
    return db.list_collection_names()

def get_users_table(collection):
    """
    Ritorna una lista di dict con:
      - user_id (int)
      - total_posts (int)
      - total_replies (int)
      - sender_name (str)
      - sender_username (str)
      - top_interactions (str) -> utenti che rispondono di più a questo user
    Ordinata discendente su total_posts.
    """

    # 1) total_posts: quanti messaggi totali un utente ha scritto
    pipeline_posts = [
        {"$group": {"_id": "$from_id.user_id", "count_posts": {"$sum": 1}}},
        {"$sort": {"count_posts": -1}}
    ]
    agg_posts = list(collection.aggregate(pipeline_posts))
    posts_dict = {d["_id"]: d["count_posts"] for d in agg_posts}

    # 2) total_replies: quante volte l'utente scrive un messaggio in reply
    pipeline_replies = [
        {"$match": {"reply_to.reply_to_msg_id": {"$exists": True}}},
        {"$group": {"_id": "$from_id.user_id", "count_replies": {"$sum": 1}}}
    ]
    agg_replies = list(collection.aggregate(pipeline_replies))
    replies_dict = {d["_id"]: d["count_replies"] for d in agg_replies}

    # Raccolta di tutti gli user_id trovati
    all_user_ids = set(posts_dict.keys()) | set(replies_dict.keys())

    users_data = []
    for uid in all_user_ids:
        total_p = posts_dict.get(uid, 0)
        total_r = replies_dict.get(uid, 0)

        # Prendiamo un messaggio di esempio per sender_name e username
        example_msg = collection.find_one({"from_id.user_id": uid})
        if example_msg:
            sender_name = example_msg.get("sender_name", "")
            sender_username = example_msg.get("sender_username", "")
        else:
            sender_name = ""
            sender_username = ""

        # Calcoliamo chi risponde di più a QUESTO utente
        top_interactions = _calculate_top_interactions(uid, collection)

        users_data.append({
            "user_id": uid,
            "total_posts": total_p,
            "total_replies": total_r,
            "sender_name": sender_name,
            "sender_username": sender_username,
            "top_interactions": top_interactions
        })

    # Ordiniamo discendente su total_posts
    users_data.sort(key=lambda x: x["total_posts"], reverse=True)
    return users_data

def _calculate_top_interactions(user_id, collection, limit=5):
    """
    Determina quali utenti rispondono di più all'utente `user_id`.
      1) Troviamo tutti i messaggi pubblicati da user_id.
      2) Troviamo chi risponde a quei messaggi (reply_to).
      3) Raggruppiamo per l'autore delle risposte, ordiniamo e prendiamo i primi `limit`.
    Restituisce una stringa, es: "User 123 (8 risposte), User 999 (3 risposte)".
    """
    # 1) Tutti i msg ID postati da user_id
    my_msg_ids = [doc["id"] for doc in collection.find(
        {"from_id.user_id": user_id},
        {"id": 1}
    )]

    if not my_msg_ids:
        return ""

    # 2) Troviamo i messaggi che rispondono ai msg in my_msg_ids
    cursor = collection.find({
        "reply_to.reply_to_msg_id": {"$in": my_msg_ids}
    }, {"from_id.user_id": 1})

    # Contiamo quante risposte arrivano da ciascun autore
    from_counts = {}
    for doc in cursor:
        replier = doc.get("from_id", {}).get("user_id", None)
        if replier is not None:
            from_counts[replier] = from_counts.get(replier, 0) + 1

    if not from_counts:
        return ""

    # 3) Ordino in base al numero di risposte (discendente)
    sorted_repliers = sorted(from_counts.items(), key=lambda x: x[1], reverse=True)
    top_n = sorted_repliers[:limit]

    # Formatto la stringa con l’user_id e il conteggio risposte
    result_str = ", ".join([f"User {u} ({cnt} risp.)" for (u, cnt) in top_n])
    return result_str

def build_subgraph_for_user(user_id_str, collection):
    """
    Crea i nodi e gli archi per un singolo utente,
    con relative reply.
    """
    nodes = {}
    edges = []

    try:
        user_id_int = int(user_id_str)
    except:
        user_id_int = -1

    # Fino a 50 messaggi dell’utente
    user_docs = list(collection.find({"from_id.user_id": user_id_int}).limit(100))
    total_posts = len(user_docs)

    # Troviamo sender_name/username
    sender_name = ""
    sender_username = ""
    if user_docs:
        doc0 = user_docs[0]
        sender_name = doc0.get("sender_name", "")
        sender_username = doc0.get("sender_username", "")

    # Determiniamo i messaggi ID
    user_message_ids = {str(d.get("id","NO_ID")) for d in user_docs}

    # Cerchiamo reply a questi 50 messaggi
    replies_cursor = collection.find({
        "reply_to.reply_to_msg_id": {
            "$in": [int(m) for m in user_message_ids if m.isdigit()]
        }
    })
    replies_list = list(replies_cursor)
    total_replies = len(replies_list)

    # Nodo principale “USER_MAIN”
    main_user_id_str = str(user_id_str)
    # Conta quanti post "main" e quanti "reply"
    user_main_posts = sum(1 for d in user_docs if "reply_to" not in d or not d["reply_to"])
    user_reply_posts = total_posts - user_main_posts

    nodes[main_user_id_str] = {
        "data": {
            "id": main_user_id_str,
            "label": "USER_MAIN",
            "name": f"User {main_user_id_str}",
            "sender_name": sender_name,
            "sender_username": sender_username,
            "total_posts": total_posts,
            "total_replies": total_replies,
            "posts_as_new": user_main_posts,
            "posts_as_reply": user_reply_posts
        }
    }

    # A) Costruiamo i nodi "messaggio" dell’utente
    for doc in user_docs:
        msg_id = str(doc.get("id","NO_ID"))
        reply_info = doc.get("reply_to")
        is_main = not (reply_info and "reply_to_msg_id" in reply_info)
        label_type = "MESSAGE_MAIN" if is_main else "MESSAGE_REPLY"

        if msg_id not in nodes:
            nodes[msg_id] = {
                "data": {
                    "id": msg_id,
                    "label": label_type,
                    "content": doc.get("message", "")
                }
            }

        # Edge di "posted"
        edge_id = f"posted_{user_id_str}_{msg_id}"
        edges.append({
            "data": {
                "id": edge_id,
                "label": f"{user_id_str} POSTED {msg_id}",
                "source": user_id_str,
                "target": msg_id
            }
        })

    # B) Nodi e archi delle reply
    for doc in replies_list:
        reply_msg_id = str(doc.get("id","NO_ID"))
        from_user_int = doc.get("from_id",{}).get("user_id","Unknown")
        from_user_str = str(from_user_int)
        # Se risponde l’utente stesso => USER_MAIN, altrimenti “USER”
        user_label = "USER_MAIN" if from_user_str == main_user_id_str else "USER"

        if from_user_str not in nodes:
            nodes[from_user_str] = {
                "data": {
                    "id": from_user_str,
                    "label": user_label,
                    "name": f"User {from_user_str}"
                }
            }

        if reply_msg_id not in nodes:
            nodes[reply_msg_id] = {
                "data": {
                    "id": reply_msg_id,
                    "label": "MESSAGE_REPLY",
                    "content": doc.get("message", "")
                }
            }

        edge_posted_id = f"posted_{from_user_str}_{reply_msg_id}"
        edges.append({
            "data": {
                "id": edge_posted_id,
                "label": f"{from_user_str} POSTED {reply_msg_id}",
                "source": from_user_str,
                "target": reply_msg_id
            }
        })

        replied_to_id_int = doc["reply_to"]["reply_to_msg_id"]
        replied_to_id_str = str(replied_to_id_int)
        edge_reply_id = f"replied_{reply_msg_id}_{replied_to_id_str}"
        edges.append({
            "data": {
                "id": edge_reply_id,
                "label": f"{reply_msg_id} REPLIED to {replied_to_id_str}",
                "source": reply_msg_id,
                "target": replied_to_id_str
            }
        })

    return {
        "nodes": list(nodes.values()),
        "edges": edges
    }


def telegram_analytics_section():
    st.title("📊 Analytics - Telegram Dashboard")

    # Connessione DB
    client = connect_to_mongo()
    db_name = 'telegram_scraping'
    db = client[db_name]

    # Seleziona collezione
    collections = db.list_collection_names()
    selected_collection = st.selectbox(
        "Seleziona una collezione per le analisi:",
        ["(Nessuna)"] + collections,
        key="collection_key"
    )

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

    # Costruisce la query
    query = {}
    if date_filter:
        query["date"] = {"$gte": date_filter}

    data = list(collection.find(query, {"message": 1, "danger_level": 1, "date": 1}))
    df = pd.DataFrame(data)

    if df.empty:
        st.warning("Nessun dato disponibile per questo periodo.")
        return

    # Converte colonna 'date' in datetime
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    # -------------------------------------------------------
    # 1) Tabella ultimi messaggi (es. 10)
    # -------------------------------------------------------
    ("📅 Numero di messaggi nel tempo")
    tab_chart_1, tab_data_1 = st.tabs(["Chart", "Data"])
    with tab_chart_1:
        # Grafico 1: numero messaggi nel tempo
        if "date" in df.columns:
            st.subheader("📅 Numero di messaggi nel tempo")
            df_counts = df.resample("D", on="date").count()
            #fig1 = px.line(df_counts, x=df_counts.index, y="message", labels={"message": "Numero di messaggi"})
            #st.plotly_chart(fig1)

            fig1 = px.line(df_counts, x=df_counts.index, y="message", 
                   labels={"message": "Numero di messaggi"}, 
                   render_mode="svg")  # Forza SVG
            st.plotly_chart(fig1)
    with tab_data_1:
        st.subheader("Tabella ultimi messaggi")
        df_sorted = df.sort_values(by="date", ascending=False)
        st.dataframe(df_sorted.head(10))  # Ultimi 10 messaggi
    # -------------------------------------------------------
    # 2) Tabella pericolosità messaggi
    # -------------------------------------------------------
    st.subheader("⚠️ Distribuzione della pericolosità")
    tab_chart_2, tab_data_2 = st.tabs(["Chart", "Data"])
    with tab_chart_2:
        if "danger_level" in df.columns:
            fig2 = px.histogram(df, x="danger_level", nbins=10)
            st.plotly_chart(fig2)
    with tab_data_2:
        if "danger_level" in df.columns:
            # Group by danger_level e contiamo quanti messaggi per livello
            df_danger = df.groupby("danger_level").size().reset_index(name="count")
            st.dataframe(df_danger)
        else:
            st.info("Nessun campo 'danger_level' nei documenti.")
    # -------------------------------------------------------
    # 3) Tabella parole frequenza
    # -------------------------------------------------------
    st.subheader("🔍 Frequenza Parole Chiave")
    tab_chart_3, tab_data_3 = st.tabs(["Chart", "Data"])
    with tab_chart_3:
        if "message" in df.columns:
            keywords = ["murder", "bomb", "hacking", "hate", "knife", "blood", "bad"]
            word_counts = {k:0 for k in keywords}

            for msg in df["message"].dropna():
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
        if "message" in df.columns:
            keywords = ["murder", "bomb", "hacking", "hate", "knife", "blood", "bad"]
            word_counts = {k: 0 for k in keywords}

            for msg in df["message"].dropna():
                lower_msg = msg.lower()
                for kw in keywords:
                    word_counts[kw] += lower_msg.count(kw)

            keyword_df = pd.DataFrame(list(word_counts.items()), columns=["keyword", "frequency"])
            st.dataframe(keyword_df)
        else:
            st.info("Nessuna colonna 'message' trovata.")

    # -------------------------------------------------------
    # 4) Tabella elenco utenti
    # -------------------------------------------------------
    st.subheader("4) Tabella utenti (da chi ha più post a chi ne ha meno)")
    users_data = get_users_table(collection)
    df_users = pd.DataFrame(users_data).rename(columns={
        "user_id": "UserID",
        "sender_name": "Name",
        "sender_username": "Username",
        "total_posts": "Total Posts",
        "total_replies": "Total Replies",
        "top_interactions": "Who Replies Most"
    })
    st.dataframe(df_users)

    
    st.subheader("5) Seleziona un utente per visualizzare il grafo")
    user_input = st.text_input("Inserisci user_id per vedere il grafo (es. 123456):", "")

    if st.button("Mostra Grafo"):
        if not user_input:
            st.error("Inserisci un user_id valido!")
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