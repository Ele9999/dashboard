import streamlit as st
from st_link_analysis import st_link_analysis, NodeStyle, EdgeStyle
from pymongo import MongoClient
from bson import ObjectId
import sys
import os

sys.path.append(os.path.abspath(".."))
from Databases.twitter import connect_to_mongo

if "rerun" in st.session_state and st.session_state["rerun"]:
    st.session_state["rerun"] = False
    st.experimental_rerun()

# 📌 Connessione al database
client = connect_to_mongo()
db_name = 'telegram_scraping'
db = client[db_name]  # Assicuriamoci che db sia il database, non il client
collection = db["BugCrowd"] 

##############################################
# 2) Aggregazione per ottenere statistiche utenti
##############################################
def get_user_stats():
    """
    Raggruppa i documenti per user_id e calcola:
      - total_posts: quanti messaggi pubblicati
    Ordina dal più alto al più basso numero di post.
    """
    pipeline = [
        {
            "$group": {
                "_id": "$from_id.user_id",
                "total_posts": {"$sum": 1},
            }
        },
        {"$sort": {"total_posts": -1}}
    ]
    user_stats = list(collection.aggregate(pipeline))
    return user_stats

##############################################
# 3) Costruisce un sub-grafo con un limite di 50 post
##############################################
def build_subgraph_for_user(user_id_str):
    """
    Sub-grafo che mostra:
      - L'utente "principale" (USER_MAIN) in rosso
      - Fino a 50 messaggi postati da quell’utente
        -> Se un messaggio non è reply, label="MESSAGE_MAIN" (verde)
        -> Se un messaggio è reply, label="MESSAGE_REPLY" (blu)
      - Gli utenti che rispondono (USER, arancione)
      - I messaggi di risposta (MESSAGE_REPLY)
    """

    nodes = {}
    edges = []

    # Convertiamo user_id in int
    try:
        user_id_int = int(user_id_str)
    except:
        user_id_int = -1

    # Nodo principale dell'utente
    # (etichetta speciale: USER_MAIN)
    nodes[user_id_str] = {
        "data": {
            "id": user_id_str,
            "label": "USER_MAIN",
            "name": f"User {user_id_str}",
        }
    }

    # 1) Recuperiamo **al massimo 50** messaggi dell’utente
    user_docs = list(
        collection.find({"from_id.user_id": user_id_int}).limit(50)
    )

    user_message_ids = set()

    for doc in user_docs:
        msg_id_str = str(doc.get("id", "NO_ID"))
        user_message_ids.add(msg_id_str)

        # Se doc["reply_to"] è assente => è un messaggio "principale"
        reply_info = doc.get("reply_to")
        is_main = (not reply_info or "reply_to_msg_id" not in reply_info)
        label_type = "MESSAGE_MAIN" if is_main else "MESSAGE_REPLY"

        if msg_id_str not in nodes:
            nodes[msg_id_str] = {
                "data": {
                    "id": msg_id_str,
                    "label": label_type,
                    "content": doc.get("message", ""),
                }
            }

        # Arco: utente principale -> messaggio
        edge_id = f"posted_{user_id_str}_{msg_id_str}"
        edges.append({
            "data": {
                "id": edge_id,
                "label": f"User {user_id_str} POSTED msg {msg_id_str}",
                "source": user_id_str,
                "target": msg_id_str
            }
        })

    # 2) Cerchiamo i messaggi di risposta (reply) ai messaggi dell'utente principale
    replies_cursor = collection.find({
        "reply_to.reply_to_msg_id": {
            "$in": [int(m) for m in user_message_ids if m.isdigit()]
        }
    })
    for doc in replies_cursor:
        reply_msg_id_str = str(doc.get("id", "NO_ID"))
        from_user_id = doc.get("from_id", {}).get("user_id", "Unknown")
        from_user_id_str = str(from_user_id)

        # Se il replier è lo stesso utente principale, rimane "USER_MAIN";
        # altrimenti è "USER" (altro utente).
        if from_user_id_str == user_id_str:
            replier_label = "USER_MAIN"
        else:
            replier_label = "USER"

        # Creiamo o recuperiamo il nodo user che risponde
        if from_user_id_str not in nodes:
            nodes[from_user_id_str] = {
                "data": {
                    "id": from_user_id_str,
                    "label": replier_label,
                    "name": f"User {from_user_id_str}"
                }
            }
        else:
            # Se esiste già e sappiamo che è lo user_main,
            # lasciamo invariato. Se fosse "USER_MAIN" e ora scoprissimo
            # che non coincide, potremmo gestirlo... (in questo caso user_id è univoco)
            pass

        # Nodo del messaggio di risposta
        if reply_msg_id_str not in nodes:
            nodes[reply_msg_id_str] = {
                "data": {
                    "id": reply_msg_id_str,
                    "label": "MESSAGE_REPLY",
                    "content": doc.get("message", ""),
                }
            }

        # Arco: replier -> msg di risposta
        posted_edge_id = f"posted_{from_user_id_str}_{reply_msg_id_str}"
        edges.append({
            "data": {
                "id": posted_edge_id,
                "label": f"User {from_user_id_str} POSTED msg {reply_msg_id_str}",
                "source": from_user_id_str,
                "target": reply_msg_id_str
            }
        })

        # Arco: msg di risposta REPLIED to main_msg
        replied_to_id_int = doc["reply_to"]["reply_to_msg_id"]
        replied_to_id_str = str(replied_to_id_int)
        reply_edge_id = f"replied_{reply_msg_id_str}_{replied_to_id_str}"
        edges.append({
            "data": {
                "id": reply_edge_id,
                "label": f"Msg {reply_msg_id_str} REPLIED to {replied_to_id_str}",
                "source": reply_msg_id_str,
                "target": replied_to_id_str
            }
        })

    return {
        "nodes": list(nodes.values()),
        "edges": edges
    }

##############################################
# 4) Interfaccia Streamlit
##############################################
st.title("🔍 Rete di interazioni - Colori diversi e max 50 post")

# A) Recuperiamo la lista utenti
user_stats = get_user_stats()

#st.write("Debug user_stats:", user_stats)

if not user_stats:
    st.warning("Nessun utente trovato.")
else:
    # Creiamo la lista di user_id
    user_list_str = [str(u["_id"]) for u in user_stats if u["_id"] is not None]
    
    # B) Selectbox per selezionare l'utente
    selected_user_id = st.selectbox(
        "Seleziona un utente:",
        user_list_str,
        #index=0  # di default mostra il primo (quello con + post)
        key="select_user"
    )

    # C) Una volta selezionato l'utente, costruiamo il sub-grafo
    if selected_user_id:
        elements = build_subgraph_for_user(selected_user_id)

        if not elements["nodes"] and not elements["edges"]:
            st.info("Nessun dato per questo utente (o non rientra nei primi 50).")
        else:
            # D) Stili
            node_styles = [
                NodeStyle("USER_MAIN", color="#FF0000", caption="name", icon="person"),    # rosso
                NodeStyle("USER", color="#FF7F3E", caption="name", icon="person"),        # arancio
                NodeStyle("MESSAGE_MAIN", color="#3EB489", caption="content", icon="description"), # verde
                NodeStyle("MESSAGE_REPLY", color="#2A629A", caption="content", icon="description"), # blu
            ]
            edge_styles = [
                EdgeStyle("*", caption="label", directed=True),
            ]

            # E) Layout: circle per tenerli in vista
            layout = "circle"

            selected_node = st_link_analysis(
                elements,
                layout,
                node_styles,
                edge_styles
            )

            # F) Mostriamo dettagli del nodo cliccato
            if selected_node:
                st.markdown(f"### Dettagli del nodo: `{selected_node['name']}`")
                if "MESSAGE" in selected_node["label"]:
                    st.write("**Contenuto**:", selected_node.get("content", ""))
                else:
                    st.write("**Utente**:", selected_node["name"])