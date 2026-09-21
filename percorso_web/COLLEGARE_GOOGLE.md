# Collegare l'app al tuo account Google (per leggere fogli privati)

Questa funzione permette di importare le tappe da un Google Sheet (anche
quello dietro un'app AppSheet) **senza condividerlo con nessuno**: ogni
utente collega il proprio account Google una volta sola, e da quel momento
l'app legge i SUOI fogli come se li stesse aprendo lui in prima persona.

Va configurata una volta sola dall'amministratore (tu), poi ogni collega può
collegare il proprio account cliccando un pulsante nell'app - non serve che
tu faccia nulla per loro.

## 1. Crea le credenziali su Google Cloud Console

1. Vai su [console.cloud.google.com](https://console.cloud.google.com) e
   accedi con un account Google (va benissimo uno aziendale se ne avete
   uno, altrimenti uno qualsiasi).
2. In alto, crea un nuovo progetto (o usane uno esistente): **"Seleziona
   progetto"** → **"Nuovo progetto"** → dagli un nome tipo
   `percorso-economico` → **"Crea"**.
3. Nel menu di sinistra (o dalla barra di ricerca in alto): **"API e
   servizi"** → **"Libreria"**, cerca **"Google Sheets API"** e clicca
   **"Abilita"**.
4. Sempre in **"API e servizi"** → **"Schermata consenso OAuth"**:
   - Tipo utente: **"Esterno"** (va bene anche se userete l'app solo in
     azienda) — se il vostro dominio `goupnoleggi.it` è un account Google
     Workspace, potete scegliere **"Interno"**, più semplice perché non
     richiede la fase di verifica.
   - Compila i campi obbligatori (nome app, email di supporto, email
     sviluppatore) e salva.
   - Nella sezione **"Ambiti"** aggiungi l'ambito
     `.../auth/spreadsheets.readonly` (cerca "Google Sheets API" e scegli
     quello con descrizione "Visualizza i tuoi fogli Google").
   - Se hai scelto "Esterno": nella sezione **"Utenti di test"** aggiungi
     le email dei colleghi che useranno la funzione (finché l'app non è
     "pubblicata" da Google, solo queste email possono collegarsi — per un
     uso aziendale interno va benissimo così, non serve pubblicarla).
5. **"API e servizi"** → **"Credenziali"** → **"Crea credenziali"** →
   **"ID client OAuth"**:
   - Tipo applicazione: **"Applicazione web"**
   - Nome: quello che vuoi (es. `percorso-economico-web`)
   - **"URI di reindirizzamento autorizzati"**, aggiungi ENTRAMBI:
     - `http://127.0.0.1:5000/google/callback` (per quando la usi in
       locale, doppio clic su `app.py`)
     - `https://tuonome.onrender.com/google/callback` (l'indirizzo vero
       del tuo servizio online, sostituendo `tuonome` con il tuo — se non
       l'hai ancora pubblicata online, aggiungi questo dopo, tornando qui)
   - **"Crea"**

Ti compaiono **Client ID** e **Client secret**: ti servono al passo
seguente. Puoi anche cliccare **"Scarica JSON"** per salvarli in un file.

## 2. Configura l'app con queste credenziali

**In locale** (più semplice): rinomina il file scaricato al passo
precedente in `google_client_secret.json` e mettilo nella stessa cartella
di `app.py`. L'app lo trova da sola al riavvio. (È già escluso da
`.gitignore`, quindi non verrà mai caricato per sbaglio su GitHub.)

**Online (Render)**: nel pannello del servizio → **"Environment"**,
aggiungi due nuove variabili:

| Nome | Valore |
|---|---|
| `GOOGLE_CLIENT_ID` | il "Client ID" mostrato da Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | il "Client secret" mostrato da Google Cloud Console |

Salva: Render ripubblica da solo.

## 3. Collegare un account (ogni utente, una volta sola)

Nell'app, sopra il campo per importare da Google Fogli, ogni utente vedrà
il pulsante **"Collega il mio account Google"**. Cliccandolo:

1. Si apre la schermata di login/consenso di Google
2. L'utente sceglie CON QUALE account Google accedere (deve essere lo
   stesso account che possiede il foglio, o con cui il foglio è
   condiviso — anche solo con lui, non serve renderlo pubblico)
3. Concede il permesso di **sola lettura** ai fogli Google
4. Torna automaticamente nell'app, che ora mostra "Account Google
   collegato ✓"

Da quel momento, incollando il link di un QUALSIASI Google Sheet a cui
quell'account ha accesso (anche privatissimo), l'app riesce a leggerlo -
niente condivisione pubblica necessaria. Il collegamento si può revocare
in ogni momento cliccando "Scollega" nell'app, o da
[myaccount.google.com/permissions](https://myaccount.google.com/permissions).

## Note

- Il permesso richiesto è **solo lettura** (`spreadsheets.readonly`):
  l'app non può modificare né cancellare nulla nei fogli Google altrui.
- Se scegli "Esterno" nella schermata di consenso e NON pubblichi l'app,
  solo le email che hai aggiunto come "utenti di test" possono collegarsi
  (limite di sicurezza di Google, va benissimo per un uso aziendale
  interno con pochi utenti; se in futuro servono più di ~100 utenti di
  test, fammelo sapere e vediamo la pubblicazione).
- Se non configuri queste credenziali, il pulsante "Collega il mio account
  Google" resta disponibile ma darà un errore: l'importazione da Google
  Fogli continuerà comunque a funzionare con il metodo precedente (link
  del foglio condiviso pubblicamente).
