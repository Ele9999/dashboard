import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from Databases.telegram import get_data_across_all_collections, connect_to_mongo
from st_link_analysis import st_link_analysis, NodeStyle, EdgeStyle
import plotly.express as px
import numpy as np

if "rerun" in st.session_state and st.session_state["rerun"]:
    st.session_state["rerun"] = False
    st.experimental_rerun()

################################################
# Calcola total_posts, total_replies, e stub "top_interactions"
################################################
def get_users_table(collection):
    """
    Ritorna una lista di dict con:
      - user_id (int)
      - total_posts (int)
      - total_replies (int) -> quante volte l'utente ha risposto (quanti di quei post sono messaggi di replay)
      - sender_name (str)
      - sender_username (str)
      - top_interactions (str) -> placeholder con utenti con cui ha interagito di più
    Ordinata discendente su total_posts.
    """

    # 1) total_posts
    pipeline_posts = [
        {"$group": {"_id": "$from_id.user_id", "count_posts": {"$sum": 1}}},
        {"$sort": {"count_posts": -1}}
    ]
    agg_posts = list(collection.aggregate(pipeline_posts))
    posts_dict = {d["_id"]: d["count_posts"] for d in agg_posts}

    # 2) total_replies: quante volte l'utente pubblica un messaggio in reply
    pipeline_replies = [
        {"$match": {"reply_to.reply_to_msg_id": {"$exists": True}}},
        {"$group": {"_id": "$from_id.user_id", "count_replies": {"$sum": 1}}}
    ]
    agg_replies = list(collection.aggregate(pipeline_replies))
    replies_dict = {d["_id"]: d["count_replies"] for d in agg_replies}

    # 3) Prendiamo tutti gli user_id che hanno post
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

        # Esempio semplificato per "utenti con cui ha interagito di più":
        # (in realtà andrebbe fatta un'analisi sulle reply per vedere a chi risponde di più)
        # Mettiamo un placeholder con i primi 2 user_id a cui ha risposto
        top_interactions = _calculate_top_interactions(uid, collection)

        users_data.append({
            "user_id": uid,
            "total_posts": total_p,
            "total_replies": total_r,
            "sender_name": sender_name,
            "sender_username": sender_username,
            "top_interactions": top_interactions,
        })

    # Ordiniamo discendente su total_posts
    users_data.sort(key=lambda x: x["total_posts"], reverse=True)
    return users_data

def _calculate_top_interactions(user_id, collection, limit=2):
    """
    Esempio semplificato: determina a chi questo utente risponde più spesso.
    """
    # Trova i messaggi di 'user_id' che sono in reply
    cursor = collection.find({
        "from_id.user_id": user_id,
        "reply_to.reply_to_msg_id": {"$exists": True}
    }, {"reply_to.reply_to_msg_id": 1})

    reply_counts = {}
    for doc in cursor:
        replied_msg_id = doc["reply_to"]["reply_to_msg_id"]
        # Troviamo chi aveva scritto il messaggio originale
        original = collection.find_one({"id": replied_msg_id}, {"from_id.user_id": 1})
        if original and "from_id" in original:
            original_author = original["from_id"].get("user_id", None)
            if original_author is not None:
                reply_counts[original_author] = reply_counts.get(original_author, 0) + 1

    # Ordino e prendo i primi "limit" user_id
    sorted_authors = sorted(reply_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return ", ".join([f"User {author}" for author, _ in sorted_authors]) if sorted_authors else ""

################################################
# Costruzione sub-grafo (limit 50)
################################################
def build_subgraph_for_user(user_id_str, collection):
    """
    Crea i nodi e gli archi per un singolo utente (fino a 50 messaggi),
    con relative reply.
    """
    nodes = {}
    edges = []

    try:
        user_id_int = int(user_id_str)
    except:
        user_id_int = -1

    # Fino a 50 messaggi dell’utente
    user_docs = list(collection.find({"from_id.user_id": user_id_int}).limit(50))
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

    # Cerchiamo reply a questi messaggi
    replies_cursor = collection.find({
        "reply_to.reply_to_msg_id": {
            "$in": [int(m) for m in user_message_ids if m.isdigit()]
        }
    })
    replies_list = list(replies_cursor)
    total_replies = len(replies_list)

    # Nodo principale “USER_MAIN”
    # (Ci mettiamo delle info aggiuntive, es. quanti post "main" e quante risposte.)
    main_user_id_str = str(user_id_str)
    # Conta quante volte ha scritto un post come "new" e quante come "reply"
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

        # Crea nodo dell'utente che risponde
        if from_user_str not in nodes:
            nodes[from_user_str] = {
                "data": {
                    "id": from_user_str,
                    "label": user_label,
                    "name": f"User {from_user_str}"
                }
            }

        # Crea nodo del messaggio di reply
        if reply_msg_id not in nodes:
            nodes[reply_msg_id] = {
                "data": {
                    "id": reply_msg_id,
                    "label": "MESSAGE_REPLY",
                    "content": doc.get("message", "")
                }
            }

        # Edge "posted"
        edge_posted_id = f"posted_{from_user_str}_{reply_msg_id}"
        edges.append({
            "data": {
                "id": edge_posted_id,
                "label": f"{from_user_str} POSTED {reply_msg_id}",
                "source": from_user_str,
                "target": reply_msg_id
            }
        })

        # Edge "replied to"
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

##############################################
# STREAMLIT: Sezione analytics + grafo
##############################################
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
    st.subheader("1) Tabella ultimi messaggi")
    df_sorted = df.sort_values(by="date", ascending=False)
    st.dataframe(df_sorted.head(10))  # Ultimi 10 messaggi

    # -------------------------------------------------------
    # 2) Tabella pericolosità messaggi
    # -------------------------------------------------------
    st.subheader("2) Tabella pericolosità messaggi")
    if "danger_level" in df.columns:
        # Group by danger_level e contiamo quanti messaggi per livello
        df_danger = df.groupby("danger_level").size().reset_index(name="count")
        st.dataframe(df_danger)
    else:
        st.info("Nessun campo 'danger_level' nei documenti.")

    # -------------------------------------------------------
    # 3) Tabella parole frequenza
    # -------------------------------------------------------
    st.subheader("3) Tabella frequenza parole chiave")
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
    df_users = pd.DataFrame(users_data)
    # Esempio: renaming per chiarezza
    df_users.rename(columns={
        "user_id": "UserID",
        "sender_name": "Name",
        "sender_username": "Username",
        "total_posts": "Total Posts",
        "total_replies": "Total Replies",
        "top_interactions": "Top Interactions",
        "posts_as_new": "Post Nuovi",
        "posts_as_reply": "Post di risposta"

    }, inplace=True)
    st.dataframe(df_users)

    # -------------------------------------------------------
    # 5) Casella testo per user, Bottone
    # -------------------------------------------------------
    st.subheader("5) Seleziona un utente per visualizzare il grafo")
    user_input = st.text_input("Inserisci user_id per vedere il grafo (es. 123456):", "")

    if st.button("Mostra Grafo"):
        if not user_input:
            st.error("Inserisci un user_id valido!")
        else:
            # Costruisce il sub-grafo
            elements = build_subgraph_for_user(user_input, collection)
            if not elements["nodes"] and not elements["edges"]:
                st.info("Nessun dato per questo utente (o limitato a 50).")
            else:
                # ---------------------------------------
                # SEZIONE con i due tab: "Chart" e "Data"
                # ---------------------------------------
                tab_chart, tab_data = st.tabs(["Chart", "Data"])

                with tab_chart:
                    st.subheader("Grafo di interazioni")
                    # Stili
                    node_styles = [
                        NodeStyle("USER_MAIN", color="#FF0000", caption="name", icon="person"),
                        NodeStyle("USER", color="#FF7F3E", caption="name", icon="person"),
                        NodeStyle("MESSAGE_MAIN", color="#3EB489", caption="content", icon="description"),
                        NodeStyle("MESSAGE_REPLY", color="#2A629A", caption="content", icon="description"),
                    ]
                    edge_styles = [EdgeStyle("*", caption="label", directed=True)]
                    
                    layout = "cola"
                    selected_node = st_link_analysis(elements, layout, node_styles, edge_styles)

                    # Memorizziamo il nodo selezionato in session_state, così poi lo leggiamo nel tab "Data"
                    st.session_state["selected_graph_node"] = selected_node

                with tab_data:
                    st.subheader("Dati sul nodo selezionato")

                    #selected_node = st.session_state.get("selected_graph_node", None)
                    if selected_node:
                        # Se è un messaggio
                        if "MESSAGE" in selected_node["label"]:
                            st.write("**Tipo**:", selected_node["label"])
                            st.write("**Contenuto**:", selected_node.get("content", ""))
                        else:
                            # È un utente
                            st.write("**Tipo**:", selected_node["label"])
                            st.write("**Utente**:", selected_node["name"])
                            sn = selected_node.get("sender_name", "")
                            su = selected_node.get("sender_username", "")
                            tp = selected_node.get("total_posts", 0)
                            tr = selected_node.get("total_replies", 0)
                            posts_main = selected_node.get("posts_as_new", 0)
                            posts_reply = selected_node.get("posts_as_reply", 0)

                            if sn: st.write("sender_name:", sn)
                            if su: st.write("sender_username:", su)
                            st.write("total_posts:", tp)
                            st.write("total_replies (reply ricevuti):", tr)
                            st.write("posts_as_new (scritti come nuovi):", posts_main)
                            st.write("posts_as_reply (scritti come risposta):", posts_reply)

                    else:
                        st.info("Seleziona un nodo dal grafo (nel tab 'Chart') per vedere i dettagli.")
