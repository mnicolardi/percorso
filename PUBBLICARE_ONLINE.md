# Mettere "Percorso Economico" online (raggiungibile dal telefono da ovunque)

Per usarla dal telefono anche fuori WiFi (con i dati mobili), l'app deve
girare su un server sempre acceso, non sul tuo PC. Qui sotto la procedura
gratuita più semplice, con **Render.com**.

Perché Render e non un altro hosting gratuito: molti hosting gratuiti
(es. PythonAnywhere sul piano free) bloccano le chiamate in uscita verso
siti esterni non in una loro "lista bianca" — e questa app ha bisogno di
chiamare Nominatim (geocodifica) e OSRM (percorso), quindi smetterebbe di
funzionare. Render non ha questa restrizione sul piano gratuito.

**Limite del piano gratuito di Render**: se l'app resta inutilizzata per
un po', "si addormenta" e il primo caricamento dopo un periodo di inattività
può richiedere 30-60 secondi in più. Dopo essersi svegliata funziona
normale. Per un uso personale va benissimo.

## Cosa ho già preparato nella cartella

- `requirements.txt` — le librerie necessarie (Flask, requests, gunicorn)
- `Procfile` — dice a Render come avviare l'app in produzione

Non serve modificare nessun altro file: `app.py` funziona sia per il
doppio clic sul PC sia per l'hosting online, senza cambiamenti.

## Procedura (circa 10 minuti, tutto gratuito)

### 1. Metti il codice su GitHub (serve per collegarlo a Render)

1. Vai su [github.com](https://github.com) e crea un account gratuito (se
   non ne hai già uno).
2. Clicca "New repository", dagli un nome (es. `percorso-economico`),
   lascialo "Public" o "Private" (indifferente), NON aggiungere nulla
   (niente README/licenza), poi "Create repository".
3. Nella pagina del repository appena creato, clicca "uploading an
   existing file" (o "Add file" → "Upload files").
4. Trascina dentro **tutti** i file e le cartelle di `percorso_web`
   (`app.py`, `motore.py`, `requirements.txt`, `Procfile`, la cartella
   `static/` e la cartella `templates/` — trascinale così come sono,
   GitHub mantiene le sottocartelle).
5. In basso, scrivi un messaggio a caso (es. "primo caricamento") e
   clicca "Commit changes".

### 2. Collega Render al repository

1. Vai su [render.com](https://render.com) e registrati gratuitamente
   (puoi usare "Sign up with GitHub" per collegare subito l'account).
2. Nella dashboard, clicca **"New +"** → **"Web Service"**.
3. Scegli il repository `percorso-economico` che hai appena creato
   (Render chiederà il permesso di accedere ai tuoi repository GitHub la
   prima volta).
4. Nella schermata di configurazione:
   - **Name**: quello che vuoi (es. `percorso-economico`) — diventerà
     parte dell'indirizzo web
   - **Region**: una vicina (es. Frankfurt)
   - **Branch**: `main`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: lascialo vuoto (Render legge il `Procfile`)
     oppure scrivi `gunicorn app:app`
   - **Instance Type**: **Free**
5. Clicca **"Create Web Service"**.

Render inizia a installare le librerie e avviare l'app (qualche minuto).
Quando la scritta in alto diventa "Live", la tua app è online, con un
indirizzo tipo:

```
https://percorso-economico.onrender.com
```

### 3. Usala dal telefono

Apri quell'indirizzo dal browser del telefono. Per un accesso più comodo,
usa "Aggiungi a schermata Home" (Safari su iPhone) o "Aggiungi a
schermata principale" (Chrome su Android): si comporta come un'app vera,
con un'icona sulla home.

## Aggiornare l'app in futuro

Se in futuro ti mando delle modifiche: carichi i file aggiornati sullo
stesso repository GitHub (sostituendo quelli vecchi), Render se ne accorge
da solo e ripubblica l'app in automatico in un paio di minuti.

## Attenzione: l'app è pubblica

Chiunque conosca l'indirizzo può usarla (non ci sono dati sensibili
memorizzati, ma consuma comunque le tue chiamate a Nominatim/OSRM). Se
vuoi, posso aggiungere una password semplice per proteggerla — fammelo
sapere.
