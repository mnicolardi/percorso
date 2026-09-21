# Percorso Economico — app web (locale)

Versione con interfaccia web interattiva del programma "Percorso
Economico": gira **sul tuo computer** (non è una pagina online), così può
usare liberamente i servizi gratuiti di geocodifica (Nominatim) e routing
(OSRM) — una pagina ospitata online non potrebbe farlo.

## Installazione (una volta sola)

```
pip install -r requirements.txt
```

## Avvio

Doppio clic su **`app.py`** (oppure `python app.py` da terminale). Si apre
automaticamente il browser su `http://127.0.0.1:5000`.

Per chiudere il programma: torna alla finestra nera del terminale e premi
**CTRL+C** (chiudere solo la scheda del browser non ferma il server).

## Login

Ora serve un account per usare l'app:

- La prima volta, vai su **"Registrati"** e crea un account con la tua
  email aziendale (di default sono ammesse solo le email `@goupnoleggi.it`
  — configurabile, vedi `PUBBLICARE_ONLINE.md` se pubblichi l'app online
  per tutta l'azienda).
- In locale, gli account creati restano salvati in un file `percorso.db`
  nella stessa cartella dello script (creato automaticamente al primo
  avvio).
- **"I miei percorsi"** in alto mostra lo storico dei percorsi che hai
  salvato: ogni alternativa calcolata ha un pulsante **"Salva percorso"**
  per aggiungerla allo storico (con un nome a tua scelta), e da lì puoi
  eliminarli quando non servono più. Lo storico è privato per ogni
  utente: nessuno vede i percorsi salvati da un collega.

## Cosa puoi fare

- **Aggiungere/rimuovere tappe**, riordinarle con le frecce ↑ ↓.
- **Partenza obbligatoria** / **Arrivo obbligatorio**: scegli dal menu
  quale tappa dev'essere sempre la prima e/o l'ultima del percorso
  (oppure lascia decidere al programma). Puoi anche cliccare i pulsanti
  **"Posizione attuale come partenza"** / **"...come arrivo"**: il browser
  chiede il permesso di geolocalizzazione, rileva dove ti trovi ora e
  aggiunge automaticamente quella posizione come tappa (funziona da PC e
  da telefono; su PC di solito e' meno precisa perche' stima la posizione
  dalla rete invece che dal GPS).
- **Ordine fisso**: spunta la casella "ordine fisso" sulle tappe che
  devono mantenere il loro ordine relativo tra loro. Le altre tappe (non
  spuntate) vengono inserite automaticamente nel punto più conveniente.
  Esempio: se marchi come "ordine fisso" le tappe 2 e 5, nel risultato la
  tappa 2 comparirà sempre prima della tappa 5, ma le altre tappe possono
  finire ovunque, anche prima, tra le due o dopo.
- **Andata e ritorno**: il percorso torna alla tappa di partenza.
- **Alternative**: mostra fino a 3 percorsi diversi tra cui scegliere,
  ordinati dal più economico.
- **Consumo/prezzo carburante** (opzionali): se li compili, ogni
  alternativa mostra anche una stima del costo in euro.
- Per ogni alternativa: **"Mostra su mappa"** (percorso stradale reale,
  interattivo), **"Scarica CSV"** (elenco tappe con km/minuti parziali) e
  **"Apri in Google Maps"** (apre il percorso, con tutte le tappe
  nell'ordine calcolato, nell'app o sul sito di Google Maps: sul telefono,
  se l'app e' installata, la navigazione e' pronta da avviare. Limite:
  Google Maps accetta al massimo 25 tappe in un link diretto).
- **Importare tappe da un Google Sheet** (anche il foglio dietro un'app
  AppSheet): incolla il link nel campo apposito e clicca "Carica da Google
  Fogli". Si apre una tabella con tutte le righe e colonne del foglio: puoi
  **filtrare** (cerca in tutte le colonne), scegliere **quale colonna
  contiene l'indirizzo** (indovinata automaticamente quando possibile) e
  **selezionare solo le righe che ti interessano** prima di aggiungerle
  come tappe.
  - Se il foglio non è condiviso con nessuno (caso tipico di un foglio
    AppSheet), clicca prima **"Collega il mio account Google"**: dopo
    aver dato il consenso una volta, l'app legge i tuoi fogli privati
    come se li aprissi tu, senza bisogno di condividerli. Va configurato
    una volta sola (vedi `COLLEGARE_GOOGLE.md`).
  - Senza account Google collegato, il foglio va condiviso con "Chiunque
    abbia il link" (almeno come visualizzatore).
- **Distanza massima ("cerchio")**: indica un indirizzo come centro e un
  raggio in km — le tappe che si trovano oltre quel raggio (in linea
  d'aria dal centro, non su strada) vengono escluse automaticamente dal
  calcolo, con un avviso che elenca quali e a che distanza. Se lasci
  vuoti questi due campi il filtro non si applica. Il cerchio viene
  disegnato anche sulla mappa quando mostri un'alternativa. Se la tappa
  di partenza obbligatoria risulta fuori dal raggio, il programma te lo
  segnala con un errore invece di ignorarlo silenziosamente.

## Note

- Gli indirizzi vanno bene sia nel formato libero ("Piazza Duomo, Milano")
  sia nel formato strutturato "Via, civico - CAP - Comune - PR" (quello
  usato di solito nei gestionali) — quest'ultimo è più affidabile perché
  la geocodifica verifica che il comune trovato corrisponda davvero.
- Un indirizzo non trovato viene escluso dal calcolo con un avviso, non
  blocca gli altri — a meno che sia proprio quello indicato come
  "partenza obbligatoria".
- Il traffico in tempo reale **non** è incluso: i servizi gratuiti usati
  non lo forniscono. Per quello servirebbe un servizio a pagamento con
  API key (Google Maps, TomTom, HERE...) — se ti serve, fammelo sapere e
  vediamo come integrarlo.
- Resta disponibile anche la versione a riga di comando/doppio clic più
  semplice (`percorso_economico.py`, consegnata in precedenza), se non ti
  serve l'interfaccia web.
- **Velocità**: la geocodifica di ogni indirizzo, la prima volta, richiede
  qualche secondo (Nominatim impone 1 richiesta al secondo). Da allora in
  poi lo stesso indirizzo viene salvato in una cache nel database e i
  calcoli successivi che lo riusano sono praticamente istantanei — utile
  perché i percorsi aziendali spesso ripetono gli stessi indirizzi
  (clienti, sedi, depositi).
