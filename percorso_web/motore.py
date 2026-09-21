"""
motore.py
=========
Logica di calcolo per l'app web "Percorso Economico":
- geocodifica robusta di indirizzi italiani (via/CAP/comune/provincia
  separati, verifica del comune trovato, correzione prefisso via mancante)
- matrice distanze/tempi reali di guida (OSRM)
- calcolo del percorso ottimale con eventuale partenza obbligatoria e un
  sottoinsieme di tappe in "ordine fisso" (le altre si inseriscono libere
  nel punto piu' conveniente), con generazione di alternative
"""

from __future__ import annotations

import csv
import io
import itertools
import math
import re
import time
import unicodedata
from typing import Dict, List, Optional, Tuple

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving/"
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/"
USER_AGENT = "percorso-economico-web/1.0 (uso personale)"
NOMINATIM_DELAY_S = 1.05  # rispetta il rate limit di 1 richiesta/secondo


# ----------------------------------------------------------------------
# GEOCODIFICA (stessa logica dello script da riga di comando)
# ----------------------------------------------------------------------

_SIGLE_PROVINCE_IT = {
    "AG", "AL", "AN", "AO", "AR", "AP", "AT", "AV", "BA", "BT", "BL", "BN", "BG", "BI", "BO",
    "BZ", "BS", "BR", "CA", "CL", "CB", "CI", "CE", "CT", "CZ", "CH", "CO", "CS", "CR", "KR",
    "CN", "EN", "FM", "FE", "FI", "FG", "FC", "FR", "GE", "GO", "GR", "IM", "IS", "SP", "AQ",
    "LT", "LE", "LC", "LI", "LO", "LU", "MC", "MN", "MS", "MT", "VS", "ME", "MI", "MO", "MB",
    "NA", "NO", "NU", "OG", "OT", "OR", "PD", "PA", "PR", "PV", "PG", "PU", "PE", "PC", "PI",
    "PT", "PN", "PZ", "PO", "RG", "RA", "RC", "RE", "RI", "RN", "RM", "RO", "SA", "SS", "SV",
    "SI", "SR", "SO", "TA", "TE", "TR", "TO", "TP", "TN", "TV", "TS", "UD", "VA", "VE", "VB",
    "VC", "VR", "VV", "VI", "VT",
}

_RE_INDIRIZZO_STRUTTURATO = re.compile(
    r"^(?P<via>.+?)\s*-\s*(?P<cap>\d{5})\s*-\s*(?P<comune>[^-]+?)\s*-\s*(?P<prov>[A-Za-z]{2})\s*$"
)

_PREFISSI_VIA = [
    "Via", "Viale", "Piazza", "Piazzale", "Corso", "Largo", "Vicolo",
    "Strada", "Vico", "Contrada", "Traversa", "Calata", "Borgo",
    "Lungomare", "Lungarno", "Circonvallazione", "Rotonda",
]
_RE_HA_PREFISSO_VIA = re.compile(r"^(" + "|".join(_PREFISSI_VIA) + r")\b", re.IGNORECASE)


def _normalizza(testo: str) -> str:
    testo = "".join(c for c in unicodedata.normalize("NFKD", testo) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", testo.lower())


def _parsifica_indirizzo_it(indirizzo: str) -> Optional[Dict[str, str]]:
    m = _RE_INDIRIZZO_STRUTTURATO.match(indirizzo)
    if not m:
        return None
    prov = m.group("prov").upper()
    if prov not in _SIGLE_PROVINCE_IT:
        return None
    return {
        "via": m.group("via").strip(),
        "cap": m.group("cap").strip(),
        "comune": m.group("comune").strip(),
        "prov": prov,
    }


_PREFISSI_VIA_FALLBACK = ["Via", "Viale", "Corso", "Piazza"]


def _candidati_via(via: str) -> List[str]:
    """Varianti del nome-via da provare quando manca il prefisso
    (Via/Viale/...). Limitato ai prefissi piu' comuni: con Nominatim che
    impone 1 richiesta/secondo, provare tutti e 16 i prefissi possibili
    renderebbe il calcolo lentissimo per un solo indirizzo mal scritto —
    "Via" da sola copre la grande maggioranza dei casi reali."""
    if _RE_HA_PREFISSO_VIA.match(via.strip()):
        return [via]
    return [via] + [f"{p} {via}" for p in _PREFISSI_VIA_FALLBACK]


def _chiamata_nominatim(params: dict) -> List[dict]:
    base_params = {"format": "json", "addressdetails": 1, "countrycodes": "it", "limit": 3}
    base_params.update(params)
    headers = {"User-Agent": USER_AGENT}
    for tentativo in range(3):
        try:
            r = requests.get(NOMINATIM_URL, params=base_params, headers=headers, timeout=15)
            if r.status_code == 429:
                time.sleep(2 * (tentativo + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            time.sleep(1.5 * (tentativo + 1))
        finally:
            time.sleep(NOMINATIM_DELAY_S)
    return []


def _comune_corrisponde(risultato: dict, comune_atteso: str) -> bool:
    atteso = _normalizza(comune_atteso)
    indirizzo = risultato.get("address", {})
    candidati = [indirizzo.get(c, "") for c in ("city", "town", "village", "municipality", "hamlet")]
    candidati.append(risultato.get("display_name", ""))
    return any(atteso and atteso in _normalizza(c) for c in candidati if c)


def geocodifica(indirizzo: str) -> Optional[Tuple[float, float]]:
    """Restituisce (lat, lon) o None se non trovato con ragionevole certezza."""
    strutturato = _parsifica_indirizzo_it(indirizzo)

    if strutturato:
        via, cap, comune = strutturato["via"], strutturato["cap"], strutturato["comune"]
        for via_prova in _candidati_via(via):
            for params in (
                {"street": via_prova, "postalcode": cap, "city": comune, "country": "Italia"},
                {"street": via_prova, "city": comune, "country": "Italia"},
            ):
                for risultato in _chiamata_nominatim(params):
                    if _comune_corrisponde(risultato, comune):
                        return float(risultato["lat"]), float(risultato["lon"])
        for risultato in _chiamata_nominatim({"city": comune, "postalcode": cap, "country": "Italia"}):
            if _comune_corrisponde(risultato, comune):
                return float(risultato["lat"]), float(risultato["lon"])
        for risultato in _chiamata_nominatim({"q": indirizzo}):
            if _comune_corrisponde(risultato, comune):
                return float(risultato["lat"]), float(risultato["lon"])
        return None

    tentativi = [indirizzo]
    parti = [p.strip() for p in indirizzo.split(",")]
    while len(parti) > 1:
        parti = parti[:-1]
        tentativi.append(", ".join(parti))
    for query in tentativi:
        risultati = _chiamata_nominatim({"q": query})
        if risultati:
            return float(risultati[0]["lat"]), float(risultati[0]["lon"])
    return None


def geocodifica_inversa(lat: float, lon: float) -> Optional[str]:
    """Da coordinate GPS (geolocalizzazione del browser) a un indirizzo
    leggibile, nello stesso formato strutturato "Via, civico - CAP - Comune
    - PR" usato dal resto del programma quando i dati sono completi;
    altrimenti restituisce il nome esteso del punto trovato da Nominatim."""
    headers = {"User-Agent": USER_AGENT}
    params = {"format": "json", "lat": lat, "lon": lon, "addressdetails": 1, "zoom": 18}
    dati = {}
    try:
        r = requests.get(NOMINATIM_REVERSE_URL, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        dati = r.json()
    except requests.RequestException:
        return None
    finally:
        time.sleep(NOMINATIM_DELAY_S)

    indirizzo = dati.get("address", {})
    via = indirizzo.get("road") or indirizzo.get("pedestrian") or indirizzo.get("footway") or ""
    civico = indirizzo.get("house_number", "")
    cap = indirizzo.get("postcode", "")
    comune = (
        indirizzo.get("city") or indirizzo.get("town") or indirizzo.get("village")
        or indirizzo.get("municipality") or indirizzo.get("hamlet") or ""
    )
    prov_raw = indirizzo.get("ISO3166-2-lvl4", "")
    prov = prov_raw.split("-")[-1].upper() if "-" in prov_raw else ""
    if prov not in _SIGLE_PROVINCE_IT:
        prov = ""

    via_completa = f"{via}, {civico}".strip(", ") if via else ""
    if via_completa and cap and comune and prov:
        return f"{via_completa} - {cap} - {comune} - {prov}"
    return dati.get("display_name")


# ----------------------------------------------------------------------
# IMPORTAZIONE INDIRIZZI DA GOOGLE FOGLI (link pubblico)
# ----------------------------------------------------------------------

_RE_ID_FOGLIO_GOOGLE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")
_RE_GID_FOGLIO_GOOGLE = re.compile(r"[#&?]gid=(\d+)")


class ErroreImportazioneFoglio(Exception):
    """Errore riconoscibile per problemi nell'importazione da Google Fogli,
    con un messaggio gia' pronto per l'utente (in italiano)."""


def _url_esportazione_csv(link: str) -> str:
    m = _RE_ID_FOGLIO_GOOGLE.search(link)
    if not m:
        raise ErroreImportazioneFoglio(
            "Il link non sembra un link di Google Fogli valido "
            "(deve contenere .../spreadsheets/d/ID.../...)."
        )
    id_foglio = m.group(1)
    m_gid = _RE_GID_FOGLIO_GOOGLE.search(link)
    gid = m_gid.group(1) if m_gid else "0"
    return f"https://docs.google.com/spreadsheets/d/{id_foglio}/export?format=csv&gid={gid}"


def _scarica_csv_foglio(link: str) -> List[List[str]]:
    url = _url_esportazione_csv(link)
    try:
        r = requests.get(url, timeout=20, allow_redirects=True)
    except requests.RequestException as e:
        raise ErroreImportazioneFoglio(f"Impossibile raggiungere Google Fogli: {e}")

    content_type = r.headers.get("Content-Type", "")
    # Se il foglio non e' condiviso pubblicamente, Google reindirizza a una
    # pagina di login HTML invece di restituire il CSV.
    if "accounts.google.com" in r.url or "text/html" in content_type:
        raise ErroreImportazioneFoglio(
            "Non riesco a leggere questo foglio: assicurati che la condivisione sia "
            'impostata su "Chiunque abbia il link" (almeno come visualizzatore), poi riprova.'
        )
    if r.status_code != 200:
        raise ErroreImportazioneFoglio(
            f"Google Fogli ha risposto con un errore (codice {r.status_code})."
        )

    testo = r.content.decode("utf-8-sig", errors="replace")
    return list(csv.reader(io.StringIO(testo)))


_INTESTAZIONI_INDIRIZZO_PROBABILI = (
    "indirizzo", "indirizzi", "address", "via", "ubicazione", "luogo", "tappa", "tappe",
)


def _righe_da_matrice(matrice: List[List[str]]) -> Tuple[List[str], List[Dict[str, str]]]:
    """Converte una matrice grezza di celle (righe x colonne, come CSV o
    come risposta dell'API Google Sheets) in (intestazioni, righe) - lista
    di dizionari colonna->valore, saltando le righe completamente vuote."""
    if not matrice:
        return [], []

    prima_riga = [str(c).strip() for c in matrice[0]]
    # Consideriamo la prima riga un'intestazione se contiene testo non
    # numerico in almeno una cella (tipico di un foglio con colonne tipo
    # "Cliente, Indirizzo, Zona, ..."), altrimenti generiamo nomi di
    # colonna generici e trattiamo la prima riga come dato.
    ha_intestazione = any(c and not c.replace(",", ".").replace("-", "").isdigit() for c in prima_riga)
    if ha_intestazione:
        intestazioni = [c or f"Colonna {i + 1}" for i, c in enumerate(prima_riga)]
        corpo = matrice[1:]
    else:
        intestazioni = [f"Colonna {i + 1}" for i in range(len(prima_riga))]
        corpo = matrice

    righe = []
    for riga_grezza in corpo:
        riga_grezza = [str(c).strip() for c in riga_grezza]
        if not any(riga_grezza):
            continue  # riga completamente vuota
        riga = {}
        for i, intestazione in enumerate(intestazioni):
            riga[intestazione] = riga_grezza[i] if i < len(riga_grezza) else ""
        righe.append(riga)

    return intestazioni, righe


def importa_righe_da_google_sheet(link: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """Scarica un Google Sheet condiviso pubblicamente (link, "chiunque
    abbia il link puo' visualizzare") e restituisce (intestazioni, righe)
    con TUTTE le colonne, cosi' l'utente puo' filtrare/selezionare le righe
    da usare come tappe (es. un foglio AppSheet con clienti, indirizzi,
    zona, note, ecc., non solo gli indirizzi)."""
    righe_csv = _scarica_csv_foglio(link)
    return _righe_da_matrice(righe_csv)


def importa_righe_da_google_sheet_api(link: str, credenziali) -> Tuple[List[str], List[Dict[str, str]]]:
    """Come importa_righe_da_google_sheet, ma legge il foglio tramite
    l'API ufficiale di Google Sheets usando le credenziali OAuth
    dell'utente che ha collegato il proprio account Google: funziona anche
    con fogli PRIVATI (non condivisi pubblicamente), perche' e' come se ad
    aprirlo fosse direttamente l'utente proprietario."""
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    m = _RE_ID_FOGLIO_GOOGLE.search(link)
    if not m:
        raise ErroreImportazioneFoglio(
            "Il link non sembra un link di Google Fogli valido "
            "(deve contenere .../spreadsheets/d/ID.../...)."
        )
    id_foglio = m.group(1)
    m_gid = _RE_GID_FOGLIO_GOOGLE.search(link)
    gid = m_gid.group(1) if m_gid else None

    try:
        servizio = build("sheets", "v4", credentials=credenziali, cache_discovery=False)
        metadati = servizio.spreadsheets().get(
            spreadsheetId=id_foglio, fields="sheets.properties"
        ).execute()
        fogli = metadati.get("sheets", [])
        titolo_foglio = None
        if gid is not None:
            for f in fogli:
                if str(f["properties"].get("sheetId")) == gid:
                    titolo_foglio = f["properties"]["title"]
                    break
        if titolo_foglio is None and fogli:
            titolo_foglio = fogli[0]["properties"]["title"]
        if titolo_foglio is None:
            raise ErroreImportazioneFoglio("Il foglio Google non contiene nessuna scheda leggibile.")

        risposta = servizio.spreadsheets().values().get(
            spreadsheetId=id_foglio, range=f"'{titolo_foglio}'"
        ).execute()
    except HttpError as e:
        if e.resp.status in (403, 404):
            raise ErroreImportazioneFoglio(
                "Il tuo account Google collegato non ha accesso a questo foglio "
                "(controlla di aver incollato il link del foglio giusto, con lo "
                "stesso account Google che lo possiede o con cui e' condiviso)."
            )
        raise ErroreImportazioneFoglio(f"Errore dall'API di Google Fogli: {e}")

    valori = risposta.get("values", [])
    return _righe_da_matrice(valori)


def indovina_colonna_indirizzo(intestazioni: List[str]) -> Optional[str]:
    """Prova a indovinare quale colonna contiene l'indirizzo, per
    precompilare la scelta nell'interfaccia (l'utente puo' sempre cambiarla)."""
    for intestazione in intestazioni:
        if _normalizza(intestazione) in _INTESTAZIONI_INDIRIZZO_PROBABILI:
            return intestazione
    for intestazione in intestazioni:
        norm = _normalizza(intestazione)
        if any(parola in norm for parola in _INTESTAZIONI_INDIRIZZO_PROBABILI):
            return intestazione
    return intestazioni[0] if intestazioni else None


# ----------------------------------------------------------------------
# MATRICE DISTANZE/TEMPI E GEOMETRIA STRADALE (OSRM)
# ----------------------------------------------------------------------

def matrice_osrm(coordinate: List[Tuple[float, float]]):
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in coordinate)
    url = f"{OSRM_TABLE_URL}{coord_str}"
    params = {"annotations": "distance,duration"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    dati = r.json()
    if dati.get("code") != "Ok":
        raise RuntimeError(f"OSRM ha risposto con errore: {dati}")
    return dati["distances"], dati["durations"]


def geometria_tratta(a: Tuple[float, float], b: Tuple[float, float]) -> List[Tuple[float, float]]:
    coord_str = f"{a[1]},{a[0]};{b[1]},{b[0]}"
    url = f"{OSRM_ROUTE_URL}{coord_str}"
    params = {"overview": "full", "geometries": "geojson"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    dati = r.json()
    if dati.get("code") != "Ok":
        return [a, b]
    coords = dati["routes"][0]["geometry"]["coordinates"]
    return [(lat, lon) for lon, lat in coords]


# ----------------------------------------------------------------------
# OTTIMIZZAZIONE DEL PERCORSO CON ORDINE PARZIALE FISSO
# ----------------------------------------------------------------------

def lunghezza_percorso(ordine: List[int], matrice, chiudi_anello: bool) -> float:
    tot = 0.0
    for i in range(len(ordine) - 1):
        tot += matrice[ordine[i]][ordine[i + 1]]
    if chiudi_anello:
        tot += matrice[ordine[-1]][ordine[0]]
    return tot


def _costo_inserimento(seq: List[int], pos: int, nodo: int, matrice, chiudi_anello: bool) -> float:
    """Costo aggiuntivo per inserire 'nodo' nella posizione 'pos' di seq."""
    n = len(seq)
    if n == 0:
        return 0.0
    if pos == 0:
        dopo = seq[0]
        if chiudi_anello:
            prima = seq[-1]
            return matrice[prima][nodo] + matrice[nodo][dopo] - matrice[prima][dopo]
        return matrice[nodo][dopo]
    if pos == n:
        prima = seq[-1]
        if chiudi_anello:
            dopo = seq[0]
            return matrice[prima][nodo] + matrice[nodo][dopo] - matrice[prima][dopo]
        return matrice[prima][nodo]
    prima, dopo = seq[pos - 1], seq[pos]
    return matrice[prima][nodo] + matrice[nodo][dopo] - matrice[prima][dopo]


def _costruisci_percorso(
    n: int,
    fissi_in_ordine: List[int],
    partenza_fissa: Optional[int],
    liberi_ordine_inserimento: List[int],
    matrice,
    chiudi_anello: bool,
    arrivo_fissa: Optional[int] = None,
) -> List[int]:
    """Costruisce un percorso: prima piazza (in ordine) le tappe 'fissi_in_ordine'
    rispettando il loro ordine relativo (e la partenza obbligatoria in
    posizione 0, se richiesta), poi - se c'e' un arrivo obbligatorio - lo
    mette in ultima posizione e la riserva (nessuna tappa libera puo' essere
    inserita dopo), poi inserisce le tappe libere una alla volta nella
    posizione piu' economica, infine affina con una ricerca locale che
    sposta solo le tappe libere."""
    pos_min_prossimo_fisso = 0
    seq: List[int] = []
    posizione_bloccata = partenza_fissa is not None

    if partenza_fissa is not None:
        seq = [partenza_fissa]
        pos_min_prossimo_fisso = 1

    for f in fissi_in_ordine:
        if f == partenza_fissa or f == arrivo_fissa:
            continue
        migliore_pos, migliore_costo = None, float("inf")
        for pos in range(pos_min_prossimo_fisso, len(seq) + 1):
            c = _costo_inserimento(seq, pos, f, matrice, chiudi_anello)
            if c < migliore_costo:
                migliore_costo, migliore_pos = c, pos
        seq.insert(migliore_pos, f)
        pos_min_prossimo_fisso = migliore_pos + 1

    # L'arrivo obbligatorio va sempre in ultima posizione: lo aggiungiamo
    # subito e da qui in poi limitiamo di un passo il "tetto" delle
    # posizioni disponibili, cosi' nessuna tappa libera puo' finire dopo di lui.
    if arrivo_fissa is not None:
        seq.append(arrivo_fissa)
    limite_extra = -1 if arrivo_fissa is not None else 0

    # Inserimento delle tappe libere, nell'ordine dato, sempre nella
    # posizione piu' economica del momento (mai dopo l'arrivo obbligatorio).
    pos_iniziale_consentita = 1 if posizione_bloccata else 0
    for nodo in liberi_ordine_inserimento:
        migliore_pos, migliore_costo = None, float("inf")
        for pos in range(pos_iniziale_consentita, len(seq) + 1 + limite_extra):
            c = _costo_inserimento(seq, pos, nodo, matrice, chiudi_anello)
            if c < migliore_costo:
                migliore_costo, migliore_pos = c, pos
        seq.insert(migliore_pos, nodo)

    # Ricerca locale: per ogni tappa LIBERA proviamo a rimuoverla e
    # reinserirla nella posizione migliore del momento (senza mai toccare
    # le tappe fisse, che restano dove sono rispetto alle altre tappe
    # fisse, ne' l'eventuale arrivo obbligatorio). Si ripete finche' la
    # lunghezza totale continua a scendere.
    insieme_fissi = (
        set(fissi_in_ordine)
        | ({partenza_fissa} if partenza_fissa is not None else set())
        | ({arrivo_fissa} if arrivo_fissa is not None else set())
    )
    lunghezza_attuale = lunghezza_percorso(seq, matrice, chiudi_anello)
    for _ in range(25):
        migliorato_in_questo_giro = False
        for nodo in [x for x in seq if x not in insieme_fissi]:
            seq.remove(nodo)
            migliore_pos, migliore_costo = None, float("inf")
            for pos in range(pos_iniziale_consentita, len(seq) + 1 + limite_extra):
                c = _costo_inserimento(seq, pos, nodo, matrice, chiudi_anello)
                if c < migliore_costo:
                    migliore_costo, migliore_pos = c, pos
            seq.insert(migliore_pos, nodo)
        nuova_lunghezza = lunghezza_percorso(seq, matrice, chiudi_anello)
        if nuova_lunghezza < lunghezza_attuale - 1e-6:
            lunghezza_attuale = nuova_lunghezza
            migliorato_in_questo_giro = True
        if not migliorato_in_questo_giro:
            break

    return seq


def ottimizza_con_alternative(
    n: int,
    indici_fissi_in_ordine: List[int],
    indice_partenza: Optional[int],
    matrice,
    chiudi_anello: bool,
    n_alternative: int = 3,
    indice_arrivo: Optional[int] = None,
) -> List[List[int]]:
    """Ritorna fino a n_alternative percorsi (liste di indici) distinti,
    ordinati dal piu' economico. Rispetta:
    - indice_partenza: se dato, e' sempre la prima tappa del percorso
    - indice_arrivo: se dato, e' sempre l'ultima tappa del percorso
    - indici_fissi_in_ordine: queste tappe compaiono nel percorso rispettando
      il loro ordine relativo (le tappe libere si inseriscono dove conviene)
    """
    tutti = list(range(n))
    fissi = [f for f in indici_fissi_in_ordine if f != indice_partenza and f != indice_arrivo]
    esclusi = (
        set(fissi)
        | ({indice_partenza} if indice_partenza is not None else set())
        | ({indice_arrivo} if indice_arrivo is not None else set())
    )
    liberi_base = [i for i in tutti if i not in esclusi]

    # Se il problema e' piccolo e senza vincoli di ordine fisso ne' di
    # partenza, proviamo la ricerca esaustiva (ottimo garantito) come primo
    # candidato: da' un buon riferimento di qualita' per le alternative.
    candidati: List[List[int]] = []

    varianti_ordine_inserimento = [
        liberi_base,
        list(reversed(liberi_base)),
        sorted(liberi_base, key=lambda i: matrice[indice_partenza or (fissi[0] if fissi else (liberi_base[0] if liberi_base else 0))][i]),
        sorted(liberi_base, key=lambda i: -matrice[indice_partenza or (fissi[0] if fissi else (liberi_base[0] if liberi_base else 0))][i]),
    ]

    if not liberi_base:
        varianti_ordine_inserimento = [[]]

    for variante in varianti_ordine_inserimento:
        seq = _costruisci_percorso(
            n, fissi, indice_partenza, variante, matrice, chiudi_anello, arrivo_fissa=indice_arrivo
        )
        if seq not in candidati:
            candidati.append(seq)

    # Se non ci sono vincoli (nessuna tappa fissa, ne' partenza, ne' arrivo)
    # e n e' piccolo, aggiungiamo anche l'ottimo esatto come ulteriore candidato.
    if not fissi and indice_partenza is None and indice_arrivo is None and n <= 9:
        migliore_esatta, migliore_len = None, float("inf")
        for partenza_prova in range(n):
            liberi_prova = [i for i in tutti if i != partenza_prova]
            for perm in itertools.permutations(liberi_prova):
                ordine = [partenza_prova] + list(perm)
                lung = lunghezza_percorso(ordine, matrice, chiudi_anello)
                if lung < migliore_len:
                    migliore_len, migliore_esatta = lung, ordine
        if migliore_esatta and migliore_esatta not in candidati:
            candidati.insert(0, migliore_esatta)

    candidati.sort(key=lambda o: lunghezza_percorso(o, matrice, chiudi_anello))

    # Dedup e taglio a n_alternative
    risultato: List[List[int]] = []
    for c in candidati:
        if c not in risultato:
            risultato.append(c)
        if len(risultato) >= n_alternative:
            break
    return risultato


# ----------------------------------------------------------------------
# UTILITA' VARIE
# ----------------------------------------------------------------------

def distanza_km_linea_aria(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Distanza in linea d'aria (haversine) in km tra due punti (lat, lon).
    Usata per il filtro 'distanza massima da un centro' (un cerchio sulla
    mappa), non per il calcolo del percorso vero e proprio (quello usa le
    distanze stradali reali di OSRM)."""
    r_terra_km = 6371.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r_terra_km * math.asin(math.sqrt(h))


def formatta_durata(sec: float) -> str:
    minuti = int(round(sec / 60))
    h, m = divmod(minuti, 60)
    return f"{h}h{m:02d}m" if h else f"{m}min"
