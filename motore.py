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

import itertools
import math
import re
import time
import unicodedata
from typing import Dict, List, Optional, Tuple

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
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


def _candidati_via(via: str) -> List[str]:
    if _RE_HA_PREFISSO_VIA.match(via.strip()):
        return [via]
    return [f"Via {via}"] + [via] + [f"{p} {via}" for p in _PREFISSI_VIA[1:]]


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
) -> List[int]:
    """Costruisce un percorso: prima piazza (in ordine) le tappe 'fissi_in_ordine'
    rispettando il loro ordine relativo (e la partenza obbligatoria in
    posizione 0, se richiesta), poi inserisce le tappe libere una alla
    volta nella posizione piu' economica, poi affina con una ricerca locale
    che sposta solo le tappe libere."""
    pos_min_prossimo_fisso = 0
    seq: List[int] = []
    posizione_bloccata = partenza_fissa is not None

    if partenza_fissa is not None:
        seq = [partenza_fissa]
        pos_min_prossimo_fisso = 1

    for f in fissi_in_ordine:
        if f == partenza_fissa:
            continue
        migliore_pos, migliore_costo = None, float("inf")
        for pos in range(pos_min_prossimo_fisso, len(seq) + 1):
            c = _costo_inserimento(seq, pos, f, matrice, chiudi_anello)
            if c < migliore_costo:
                migliore_costo, migliore_pos = c, pos
        seq.insert(migliore_pos, f)
        pos_min_prossimo_fisso = migliore_pos + 1

    # Inserimento delle tappe libere, nell'ordine dato, sempre nella
    # posizione piu' economica del momento.
    pos_iniziale_consentita = 1 if posizione_bloccata else 0
    for nodo in liberi_ordine_inserimento:
        migliore_pos, migliore_costo = None, float("inf")
        for pos in range(pos_iniziale_consentita, len(seq) + 1):
            c = _costo_inserimento(seq, pos, nodo, matrice, chiudi_anello)
            if c < migliore_costo:
                migliore_costo, migliore_pos = c, pos
        seq.insert(migliore_pos, nodo)

    # Ricerca locale: per ogni tappa LIBERA proviamo a rimuoverla e
    # reinserirla nella posizione migliore del momento (senza mai toccare
    # le tappe fisse, che restano dove sono rispetto alle altre tappe
    # fisse). Si ripete finche' la lunghezza totale continua a scendere.
    insieme_fissi = set(fissi_in_ordine) | ({partenza_fissa} if partenza_fissa is not None else set())
    lunghezza_attuale = lunghezza_percorso(seq, matrice, chiudi_anello)
    for _ in range(25):
        migliorato_in_questo_giro = False
        for nodo in [x for x in seq if x not in insieme_fissi]:
            seq.remove(nodo)
            migliore_pos, migliore_costo = None, float("inf")
            for pos in range(pos_iniziale_consentita, len(seq) + 1):
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
) -> List[List[int]]:
    """Ritorna fino a n_alternative percorsi (liste di indici) distinti,
    ordinati dal piu' economico. Rispetta:
    - indice_partenza: se dato, e' sempre la prima tappa del percorso
    - indici_fissi_in_ordine: queste tappe compaiono nel percorso rispettando
      il loro ordine relativo (le tappe libere si inseriscono dove conviene)
    """
    tutti = list(range(n))
    fissi = [f for f in indici_fissi_in_ordine if f != indice_partenza]
    esclusi = set(fissi) | ({indice_partenza} if indice_partenza is not None else set())
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
        seq = _costruisci_percorso(n, fissi, indice_partenza, variante, matrice, chiudi_anello)
        if seq not in candidati:
            candidati.append(seq)

    # Se non ci sono vincoli (nessuna tappa fissa ne' partenza) e n e'
    # piccolo, aggiungiamo anche l'ottimo esatto come ulteriore candidato.
    if not fissi and indice_partenza is None and n <= 9:
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
