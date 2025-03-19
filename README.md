# Realizzazione di una piattaforma di threat intelligence: gestione di fonti OSINT e visualizzazione delle informazioni

Per la mia tesi, ho sviluppato una piattaforma di Cyber Threat Intelligence in grado di analizzare dati raccolti da fonti OSINT (Telegram, Twitter, Ahmia Browser), già presenti in un database MongoDB (precedentemente raccolti tramite scraping da un mio collega). L'obiettivo è identificare utenti, messaggi e trend potenzialmente pericolosi attraverso strumenti di analisi avanzata e Intelligenza Artificiale.

## Tecnologie utilizzate:

- **MongoDB**: per la gestione e l’archiviazione dei dati

- **Streamlit**: per creare un’interfaccia interattiva e intuitiva

- **Plotly e Pandas**: per la visualizzazione e l’analisi statistica dei dati

- **st_link_analysis**: per la creazione di grafi interattivi, utili a individuare connessioni tra utenti

- **OpenAI API**: per consentire interrogazioni del database in linguaggio naturale, semplificando l’accesso ai dati

## Funzionalità principali:

- *Dashboard interattiva per visualizzare e filtrare i dati presenti su MongoDB*

- *Assegnazione del livello di pericolosità ai messaggi, con possibilità di modifica e revisione*

- *Grafi di interazione tra utenti, per analizzare connessioni sospette e pattern di comunicazione*

- *Ricerca avanzata con AI, che permette di interrogare il database con domande in linguaggio naturale (es. “Mostrami gli utenti più attivi negli ultimi 7 giorni”)*
