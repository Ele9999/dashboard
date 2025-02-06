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
db_name = 'twitter_scraping'
db = client[db_name]  # Assicuriamoci che db sia il database, non il client
collection = db["Killnet"] 

#############################################
##### Funzione per costruire nodi e archi
#############################################
####def get_graph_data():
####    docs = collection.find({})
####    
####    nodes = {}
####    edges = []
####
####    for doc in docs:
####        # Convertiamo ObjectId a stringa
####        post_id = str(doc["_id"])
####        
####        # Cerchiamo un identificativo utente (usando 'username' o 'tag_username' se esiste)
####        user_id = doc.get("tag_username") or doc.get("username", "UnknownUser")
####        
####        # Crea il nodo utente se non esiste già
####        if user_id not in nodes:
####            nodes[user_id] = {
####                "data": {
####                    "id": user_id,
####                    "label": "USER",
####                    "name": user_id
####                }
####            }
####
####        # Crea il nodo post
####        nodes[post_id] = {
####            "data": {
####                "id": post_id,
####                "label": "POST",
####                "content": doc.get("content", ""),
####                "likes": doc.get("likes", 0),
####                "views": doc.get("views", 0),
####                "url": doc.get("url", "")
####            }
####        }
####
####        # Arco: l'utente "POSTED" il post
####        edges.append({
####            "data": {
####                "id": f"user_post_{post_id}",
####                "label": "POSTED",
####                "source": user_id,
####                "target": post_id
####            }
####        })
####
####        # Gestione "reshared" (se esiste e se è una lista di post_id)
####        reshared = doc.get("reshared", [])
####        if reshared:
####            for original_post_id in reshared:
####                # Converti in stringa se è un ObjectId
####                original_post_id = str(original_post_id)
####                if original_post_id not in nodes:
####                    nodes[original_post_id] = {
####                        "data": {
####                            "id": original_post_id,
####                            "label": "POST",
####                            "content": "Unknown Reshared Post"
####                        }
####                    }
####                edges.append({
####                    "data": {
####                        "id": f"reshare_{post_id}_{original_post_id}",
####                        "label": "RESHARED",
####                        "source": post_id,
####                        "target": original_post_id
####                    }
####                })
####
####    return {
####        "nodes": list(nodes.values()),
####        "edges": edges
####    }
####
########################################
##### Interfaccia Streamlit
########################################
####st.title("🔍 Rete di interazioni")
####
##### Debug: conta i documenti in collezione
####count_docs = collection.count_documents({})
####st.write(f"**Numero di documenti in '{collection}':**", count_docs)
####
##### Debug: Recupera gli elementi (nodi e archi) e mostriamoli
####elements = get_graph_data()
####st.write("**Anteprima dei dati del grafo (nodes/edges):**")
####st.write(elements)
####
##### Se la struttura è vuota, ovviamente il grafo non mostrerà niente
####if not elements["nodes"] and not elements["edges"]:
####    st.warning("Nessun nodo o arco trovato! Controlla che la collezione contenga dati validi.")
####else:
####    # Definizione stili
####    node_styles = [
####        NodeStyle("USER", color="#FF7F3E", caption="name", icon="person"),
####        NodeStyle("POST", color="#2A629A", caption="content", icon="description"),
####    ]
####    edge_styles = [
####        EdgeStyle("POSTED", caption='label', directed=True),
####        EdgeStyle("RESHARED", caption='label', directed=True),
####    ]
####
####    # Proviamo un layout "random" per semplicità
####    layout = "random"
####
####    # Mostra il grafo
####    selected_node = st_link_analysis(elements, layout, node_styles, edge_styles)
####
####    # Selezionando un nodo, mostra dettagli
####    if selected_node:
####        st.markdown(f"### Dettagli per: `{selected_node['name']}`")
####
####        # Nodo utente
####        if selected_node["label"] == "USER":
####            user_posts = list(collection.find({
####                "$or": [
####                    {"username": selected_node["name"]},
####                    {"tag_username": selected_node["name"]}
####                ]
####            }))
####            if user_posts:
####                st.write("**Post pubblicati**:")
####                for up in user_posts:
####                    st.write(f"- {up.get('content','')} (likes: {up.get('likes','0')}, views: {up.get('views','0')})")
####            else:
####                st.info("Nessun post trovato per questo utente.")
####
####        # Nodo post
####        elif selected_node["label"] == "POST":
####            try:
####                post_data = collection.find_one({"_id": ObjectId(selected_node["id"])})
####            except:
####                post_data = collection.find_one({"_id": selected_node["id"]})
####
####            if post_data:
####                st.write(f"**Contenuto**: {post_data.get('content','')}")
####                st.write(f"**Autore**: {post_data.get('username') or post_data.get('tag_username','Anonimo')}")
####                st.write(f"**Likes**: {post_data.get('likes','0')}")
####                st.write(f"**Views**: {post_data.get('views','0')}")
####                st.write(f"**URL**: {post_data.get('url','')}")
####
####                if post_data.get("reshared"):
####                    st.write("**Reshared**:")
####                    for rid in post_data["reshared"]:
####                        st.write(f"- {rid}")
####            else:
####                st.info("Dettagli del post non trovati.")
####
def build_subgraph_for_user(user_id_str):
    nodes = {}
    edges = []

    try:
        user_id_int = int(user_id_str)
    except:
        user_id_int = -1

    # --- 1) Tutti i messaggi postati dall'utente selezionato ---
    user_docs = list(collection.find({
        "from_id.user_id": user_id_int,
        #filtro per visualizzare solo utenti per cui esiste o il campo sendername o il campo senderusername
        "$or": [
            {"username": {"$exists": True, "$ne": ""}},
            {"tag_username": {"$exists": True, "$ne": ""}}
        ]
        
        }))

    # Nodo dell’utente
    nodes[user_id_str] = {
        "data": {
            "id": user_id_str,
            "label": "USER",
            "name": f"User {user_id_str}",
        }
    }

    user_message_ids = set()
    for doc in user_docs:
        msg_id = str(doc.get("id", "NO_ID"))
        user_message_ids.add(msg_id)

        # Nodo del messaggio
        if msg_id not in nodes:
            date_str = str(doc.get("date", ""))
            nodes[msg_id] = {
                "data": {
                    "id": msg_id,
                    "label": "MESSAGE",
                    "content": doc.get("title", ""),
                    "date": date_str,
                    "username": doc.get("username", ""),
                    "tag_username": doc.get("tag_username", "")
                }
            }

        # Arco: user -> message
        edge_id = f"posted_{user_id_str}_{msg_id}"
        edges.append({
            "data": {
                "id": edge_id,
                # Etichetta più parlante:
                "label": f"User {user_id_str} POSTED msg {msg_id}",
                "source": user_id_str,
                "target": msg_id
            }
        })

    # --- 2) Trova messaggi che rispondono ai msg dell'utente ---
    replies = collection.find({
        "reply_to.reply_to_msg_id": {
            "$in": [int(m) for m in user_message_ids if m.isdigit()]
        },
        #trova i messaggi solo degli utenti filtrati
        "$or": [
            {"username": {"$exists": True, "$ne": ""}},
            {"tag_username": {"$exists": True, "$ne": ""}}
        ]
    })

    for doc in replies:
        reply_msg_id = str(doc.get("id", "NO_ID"))
        # Nodo del messaggio di risposta
        if reply_msg_id not in nodes:
            date_str = str(doc.get("date", ""))
            nodes[reply_msg_id] = {
                "data": {
                    "id": reply_msg_id,
                    "label": "MESSAGE",
                    "content": doc.get("title", ""),
                    "date": date_str,
                    "username": doc.get("username", ""),
                    "tag_username": doc.get("tag_username", "")
                }
            }

        # Nodo dell’utente che risponde
        replier_id_int = doc.get("from_id", {}).get("user_id", "UnknownReplier")
        replier_id_str = str(replier_id_int)
        if replier_id_str not in nodes:
            nodes[replier_id_str] = {
                "data": {
                    "id": replier_id_str,
                    "label": "USER",
                    "name": f"User {replier_id_str}"
                }
            }

        # Arco: quell’utente -> msg di risposta
        edges.append({
            "data": {
                "id": f"posted_{replier_id_str}_{reply_msg_id}",
                "label": f"User {replier_id_str} POSTED msg {reply_msg_id}",
                "source": replier_id_str,
                "target": reply_msg_id
            }
        })

        # Arco: il msg di risposta REPLIED al msg dell’utente
        replied_to_id = doc["reply_to"]["reply_to_msg_id"]
        replied_to_str = str(replied_to_id)
        edges.append({
            "data": {
                "id": f"replied_{reply_msg_id}_{replied_to_str}",
                "label": f"Msg {reply_msg_id} REPLIED to {replied_to_str}",
                "source": reply_msg_id,
                "target": replied_to_str
            }
        })

    # (Opzionale) --- 3) Gestione forward (fwd_from), se presente ---
    # ... analogamente a replies, cerchi i doc che forwardano i msg dell’utente
    # ... e crei nodi/archi con label “FORWARDED”.

    elements = {
        "nodes": list(nodes.values()),
        "edges": edges
    }
    return elements
