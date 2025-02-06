import streamlit as st
import pandas as pd
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from Databases.telegram import get_data_across_all_collections, connect_to_mongo
from st_link_analysis import st_link_analysis, NodeStyle, EdgeStyle
import plotly.express as px

if "rerun" in st.session_state and st.session_state["rerun"]:
    st.session_state["rerun"] = False
    st.experimental_rerun()


################################################
# Aggregazione: user_id -> total_posts
# e si prende un messaggio a campione per
# sender_name e sender_username
################################################
def get_users_table(collection):
    """
    Ritorna una lista di dict con:
      - user_id (int)
      - total_posts (int)
      - sender_name (str, se esiste)
      - sender_username (str, se esiste)
    Ordinata discendente su total_posts.
    """
    pipeline = [
        {"$group": {"_id": "$from_id.user_id", "total_posts": {"$sum": 1}}},
        {"$sort": {"total_posts": -1}}
    ]
    agg_results = list(collection.aggregate(pipeline))

    users_data = []
    for doc in agg_results:
        uid = doc["_id"]
        total = doc["total_posts"]

        # Troviamo un messaggio a caso di questo utente
        example_msg = collection.find_one({"from_id.user_id": uid})
        sender_name = example_msg.get("sender_name", "") if example_msg else ""
        sender_username = example_msg.get("sender_username", "") if example_msg else ""

        users_data.append({
            "user_id": uid,
            "total_posts": total,
            "sender_name": sender_name,
            "sender_username": sender_username
        })

    return users_data

################################################
# Costruzione sub-grafo (limit 50)
################################################
def build_subgraph_for_user(user_id_str, collection):
    """
    - USER_MAIN con info su total_posts (max 50),
    - Messaggi dell’utente (MESSAGE_MAIN se non reply, MESSAGE_REPLY se reply),
    - Altri utenti (USER) che rispondono,
    - Fino a 50 messaggi dell’utente + tutte le reply a quei 50.
    """
    nodes = {}
    edges = []

    try:
        user_id_int = int(user_id_str)
    except:
        user_id_int = -1

    # Prendiamo fino a 50 messaggi dell’utente
    user_docs = list(collection.find({"from_id.user_id": user_id_int}).limit(50))
    total_posts = len(user_docs)

    # Troviamo sender_name/username se c’è
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
    nodes[user_id_str] = {
        "data": {
            "id": user_id_str,
            "label": "USER_MAIN",
            "name": f"User {user_id_str}",
            "sender_name": sender_name,
            "sender_username": sender_username,
            "total_posts": total_posts,
            "total_replies": total_replies
        }
    }

    # A) Costruiamo i nodi messaggi dell’utente
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

        edge_id = f"posted_{user_id_str}_{msg_id}"
        edges.append({
            "data": {
                "id": edge_id,
                "label": f"{user_id_str} POSTED {msg_id}",
                "source": user_id_str,
                "target": msg_id
            }
        })

    # B) Costruiamo nodi e archi delle reply
    for doc in replies_list:
        reply_msg_id = str(doc.get("id","NO_ID"))
        from_user_int = doc.get("from_id",{}).get("user_id","Unknown")
        from_user_str = str(from_user_int)
        # Se risponde l’utente stesso => USER_MAIN, altrimenti “USER”
        user_label = "USER_MAIN" if from_user_str == user_id_str else "USER"

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

##############################################
# STREAMLIT: Sezione analytics + grafo
##############################################
def telegram_analytics_section():
    st.title("📊 Analytics - Telegram Dashboard")

    # Connessione DB
    client = connect_to_mongo()
    db_name = 'telegram_scraping'
    db = client[db_name]

    # Selezione collezione
    collections = db.list_collection_names()
    selected_collection = st.selectbox("Seleziona una collezione per le analisi:", ["(Nessuna)"] + collections, key="collection_key")

    # Selezione periodo
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
    data = list(collection.find(query, {"message": 1, "danger_level": 1, "date": 1}))
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

        fig1 = px.line(df_counts, x=df_counts.index, y="message", 
               labels={"message": "Numero di messaggi"}, 
               render_mode="svg")  # Forza SVG
        st.plotly_chart(fig1)


    # Grafico 2: Distribuzione pericolosità
    if "danger_level" in df.columns:
        st.subheader("⚠️ Distribuzione della pericolosità")
        fig2 = px.histogram(df, x="danger_level", nbins=10)
        st.plotly_chart(fig2)

    # Grafico 3: Frequenza parole chiave (se esiste la colonna "message")
    if "message" in df.columns:
        st.subheader("🔍 Frequenza Parole Chiave")
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

    #######################################################
    # Sezione GRAFO di interazioni
    #######################################################
    st.title("📊 Tabella Utenti e Grafo")
    st.header("Individuare uno user_id di interesse, scriverlo e premere il bottone")

    # 1) Tabella utenti
    users_data = get_users_table(collection)
    if not users_data:
        st.warning("Nessun utente trovato nella collezione.")
        return

    # Convertiamo in DataFrame e mostriamo
    df_users = pd.DataFrame(users_data)
    # Se vuoi lasciare l'ordinamento via code, df_users = df_users.sort_values(by="total_posts", ascending=False)
    st.subheader("Elenco utenti (da più a meno post)")
    st.dataframe(df_users)  # o st.table(df_users)

    # 2) Input manuale dell’user_id
    user_input = st.text_input("Inserisci user_id per vedere il grafo (es. 123456):", "")

    # 3) Pulsante per generare il grafo
    if st.button("Mostra Grafo"):
        if not user_input:
            st.error("Inserisci un user_id valido!")
        else:
            elements = build_subgraph_for_user(user_input, collection)
            if not elements["nodes"] and not elements["edges"]:
                st.info("Nessun dato per questo utente (o limitato a 50).")
            else:
                # Stili
                node_styles = [
                    NodeStyle("USER_MAIN", color="#FF0000", caption="name", icon="person"),
                    NodeStyle("USER", color="#FF7F3E", caption="name", icon="person"),
                    NodeStyle("MESSAGE_MAIN", color="#3EB489", caption="content", icon="description"),
                    NodeStyle("MESSAGE_REPLY", color="#2A629A", caption="content", icon="description"),
                ]
                edge_styles = [EdgeStyle("*", caption="label", directed=True)]
                layout = "circle"

                selected_node = st_link_analysis(elements, layout, node_styles, edge_styles)
                if selected_node:
                    st.markdown(f"### Dettagli del nodo: `{selected_node['name']}`")
                    if "MESSAGE" in selected_node["label"]:
                        st.write("**Contenuto**:", selected_node.get("content", ""))
                    else:
                        st.write("**Utente**:", selected_node["name"])
                        # Info extra se presenti
                        sn = selected_node.get("sender_name","")
                        su = selected_node.get("sender_username","")
                        tp = selected_node.get("total_posts",0)
                        tr = selected_node.get("total_replies",0)
                        if sn: st.write("sender_name:", sn)
                        if su: st.write("sender_username:", su)
                        st.write("total_posts:", tp)
                        st.write("total_replies:", tr)
