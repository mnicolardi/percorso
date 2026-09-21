# Percorso Economico — app web (locale)

Versione con interfaccia web interattiva del programma "Percorso
Economico": gira **sul tuo computer** (non è una pagina online), così può
usare liberamente i servizi gratuiti di geocodifica (Nominatim) e routing
(OSRM) — una pagina ospitata online non potrebbe farlo.

## Installazione (una volta sola)

```
pip install flask requests
```

## Avvio

Doppio clic su **`app.py`** (oppure `python app.py` da terminale). Si apre
automaticamente il browser su `http://127.0.0.1:5000`.

Per chiudere il programma: torna alla finestra nera del terminale e premi
**CTRL+C** (chiudere solo la scheda del browser non ferma il server).

## Cosa puoi fare

- **Aggiungere/rimuovere tappe**, riordinarle con le frecce ↑ ↓.
- **Partenza obbligatoria**: scegli dal menu quale tappa dev'essere
  sempre la prima del percorso (oppure lascia decidere al programma).
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
  interattivo) e **"Scarica CSV"** (elenco tappe con km/minuti parziali).
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
