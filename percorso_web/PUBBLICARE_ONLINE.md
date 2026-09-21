# Mettere "Percorso Economico" online, con login e storico

L'app ora ha login (email aziendale + password) e salva lo storico dei
percorsi per ogni utente. Questo cambia una cosa importante rispetto a
prima: **serve un database vero e persistente**, non basta più il file
SQLite locale (che su Render sparirebbe ad ogni riavvio/redeploy, perché
il piano gratuito non ha disco persistente).

## Cosa ho già preparato nella cartella

- `requirements.txt` — ora include anche `flask-sqlalchemy`, `flask-login`
  e `psycopg2-binary` (driver per PostgreSQL)
- `Procfile` — comando di avvio per la produzione
- `modelli.py` — utenti e percorsi salvati; legge il database da
  impostare tramite variabile d'ambiente `DATABASE_URL`

In locale (doppio clic su `app.py`) non serve fare nulla: senza
`DATABASE_URL` impostata, usa automaticamente un file SQLite locale
(`percorso.db`), comodo per provare l'app.

## 1. Un database Postgres gratuito e permanente

Il Postgres gratuito di Render scade dopo 30 giorni: meglio usarne uno
esterno con piano gratuito **senza scadenza**. Due opzioni valide, scegline
una:

- **[Neon.tech](https://neon.tech)** — registrati gratis, crea un
  progetto, copia la stringa di connessione ("Connection string") che
  inizia con `postgresql://...`
- **[Supabase](https://supabase.com)** — registrati gratis, crea un
  progetto, in "Project Settings" → "Database" trovi la stringa di
  connessione

Tienila da parte, ti serve al passaggio 3.

## 2. Il codice su GitHub (come prima)

Se non l'hai già fatto: crea un repository su [github.com](https://github.com)
e carica tutti i file della cartella `percorso_web` (drag & drop dal
browser, incluse le sottocartelle `static/` e `templates/`).

Se avevi già caricato una versione precedente, ricarica gli stessi file:
GitHub sovrascrive quelli con lo stesso nome (basta trascinarli di nuovo
nella pagina del repository e confermare "Commit changes").

## 3. Il servizio web su Render, con le variabili d'ambiente giuste

Se hai già creato il "Web Service" su Render in precedenza, vai nel suo
pannello, sezione **"Environment"**, e aggiungi queste variabili (poi
Render ripubblica da solo):

| Nome variabile | Valore | A cosa serve |
|---|---|---|
| `DATABASE_URL` | la stringa di connessione di Neon/Supabase | dove salvare utenti e percorsi, in modo permanente |
| `SECRET_KEY` | una stringa lunga e casuale, a tua scelta (es. genera con `python -c "import secrets; print(secrets.token_hex(32))"`) | tiene gli utenti collegati tra un riavvio e l'altro del server |
| `ALLOWED_EMAIL_DOMAINS` | `goupnoleggi.it` (o più domini separati da virgola) | solo chi ha un'email di questi domini può registrarsi |

Se stai creando il servizio da zero, aggiungi queste variabili nella
sezione "Environment Variables" durante la configurazione iniziale
(prima di "Create Web Service"), oltre ai passaggi già descritti in
precedenza (Build command `pip install -r requirements.txt`, piano
**Free**).

**Importante**: senza `SECRET_KEY` impostata esplicitamente, ogni
riavvio del server (Render lo fa periodicamente) disconnette tutti gli
utenti — impostala sempre in produzione.

## 4. Primo accesso

Una volta online, chiunque con un'email `@goupnoleggi.it` (o i domini
che hai indicato) può andare su `/registrati` e crearsi un account. Non
c'è un pannello amministrativo per gestire gli utenti: se in futuro
serve (disattivare un account, vedere chi è registrato, promuovere un
amministratore), fammelo sapere e lo aggiungo.

## Limiti di questa versione

- Nessun recupero password ("ho dimenticato la password") — se serve, lo
  aggiungo (richiede l'invio di email, quindi un servizio come
  SendGrid/Mailgun, anche loro con piano gratuito).
- Lo storico è privato per ogni utente: nessuno vede i percorsi salvati
  dai colleghi. Se preferisci uno storico condiviso da tutta l'azienda,
  è una modifica semplice — dimmelo.
- Resta valido tutto quanto detto in precedenza su Nominatim/OSRM
  gratuiti: con un uso aziendale più intenso, prima o poi conviene
  passare a un servizio di geocodifica/routing a pagamento.
