#!/usr/bin/env python3
"""
Percorso Economico - app web locale
====================================
Avvia un piccolo server sul tuo computer e apre il browser su
http://127.0.0.1:5000 dove puoi:
- inserire le tappe (indirizzi)
- imporre una tappa di partenza obbligatoria
- marcare alcune tappe come "ordine fisso" (le altre si ottimizzano
  liberamente attorno)
- vedere fino a 3 percorsi alternativi con distanza/tempo/costo stimato
- visualizzare il percorso scelto su una mappa interattiva

Avvio:  doppio clic su questo file (o: python app.py)
Per chiudere il server: torna alla finestra nera e premi CTRL+C
(chiudere solo la scheda del browser NON lo ferma).
"""

from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request

import motore

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(BASE_DIR / "static"), template_folder=str(BASE_DIR / "templates"))


@app.get("/")
def index():
    return (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")


@app.post("/api/calcola")
def api_calcola():
    dati = request.get_json(force=True, silent=True) or {}
    tappe_in = dati.get("tappe", [])
    partenza_idx_originale = dati.get("partenza")  # indice nella lista originale, o None
    andata_ritorno = bool(dati.get("andata_ritorno", False))
    consumo = dati.get("consumo")
    prezzo = dati.get("prezzo")
    n_alternative = int(dati.get("n_alternative", 3))
    centro_raggio_indirizzo = (dati.get("centro_raggio_indirizzo") or "").strip()
    raggio_km_raw = dati.get("raggio_km")

    if not isinstance(tappe_in, list) or len(tappe_in) < 2:
        return jsonify({"ok": False, "errore": "Servono almeno 2 tappe."}), 400

    indirizzi = [str(t.get("indirizzo", "")).strip() for t in tappe_in]
    ordine_fisso_flag = [bool(t.get("ordine_fisso", False)) for t in tappe_in]

    if any(not ind for ind in indirizzi):
        return jsonify({"ok": False, "errore": "Uno o piu' indirizzi sono vuoti."}), 400

    # --- distanza massima da un centro (un "cerchio" sulla mappa), opzionale ---
    centro_coord = None
    raggio_km = None
    if centro_raggio_indirizzo and raggio_km_raw:
        try:
            raggio_km = float(raggio_km_raw)
        except (TypeError, ValueError):
            raggio_km = None
        if raggio_km and raggio_km > 0:
            centro_coord = motore.geocodifica(centro_raggio_indirizzo)
            if centro_coord is None:
                return jsonify({
                    "ok": False,
                    "errore": f"Centro del cerchio non trovato: {centro_raggio_indirizzo!r}",
                }), 400

    # --- geocodifica di tutte le tappe, mantenendo la corrispondenza con gli indici originali ---
    geocodificate = []  # lista di (indice_originale, indirizzo, lat, lon)
    falliti = []
    for i, ind in enumerate(indirizzi):
        risultato = motore.geocodifica(ind)
        if risultato is None:
            falliti.append(ind)
            continue
        lat, lon = risultato
        geocodificate.append((i, ind, lat, lon))

    if partenza_idx_originale is not None:
        indirizzo_partenza = indirizzi[partenza_idx_originale]
        if indirizzo_partenza in falliti:
            return jsonify({
                "ok": False,
                "errore": f"L'indirizzo di partenza non e' stato trovato: {indirizzo_partenza!r}",
                "falliti": falliti,
            }), 400

    # --- esclude le tappe fuori dal raggio massimo dal centro (se impostato) ---
    fuori_raggio = []
    if centro_coord is not None and raggio_km:
        dentro = []
        for orig, ind, lat, lon in geocodificate:
            d = motore.distanza_km_linea_aria(centro_coord, (lat, lon))
            if d <= raggio_km:
                dentro.append((orig, ind, lat, lon))
            else:
                fuori_raggio.append({"indirizzo": ind, "distanza_km": round(d, 1), "lat": lat, "lon": lon})
        geocodificate = dentro

        if partenza_idx_originale is not None:
            indirizzo_partenza = indirizzi[partenza_idx_originale]
            if any(f["indirizzo"] == indirizzo_partenza for f in fuori_raggio):
                return jsonify({
                    "ok": False,
                    "errore": (
                        f"La tappa di partenza e' fuori dal raggio massimo impostato: "
                        f"{indirizzo_partenza!r}"
                    ),
                    "falliti": falliti,
                    "fuori_raggio": fuori_raggio,
                }), 400

    if len(geocodificate) < 2:
        return jsonify({
            "ok": False,
            "errore": (
                "Meno di 2 tappe utilizzabili (dopo aver escluso indirizzi non trovati "
                "e/o fuori dal raggio massimo): impossibile calcolare un percorso."
            ),
            "falliti": falliti,
            "fuori_raggio": fuori_raggio,
        }), 400

    # Da qui in poi lavoriamo solo sull'elenco di tappe effettivamente geocodificate.
    mappa_orig_a_nuovo = {orig: nuovo for nuovo, (orig, _, _, _) in enumerate(geocodificate)}
    tappe = [(ind, lat, lon) for _, ind, lat, lon in geocodificate]

    indice_partenza = None
    if partenza_idx_originale is not None and partenza_idx_originale in mappa_orig_a_nuovo:
        indice_partenza = mappa_orig_a_nuovo[partenza_idx_originale]

    indici_fissi_in_ordine = [
        mappa_orig_a_nuovo[orig]
        for orig, ind, _, _ in geocodificate
        if ordine_fisso_flag[orig] and mappa_orig_a_nuovo[orig] != indice_partenza
    ]

    try:
        coordinate = [(lat, lon) for _, lat, lon in tappe]
        matrice_dist, matrice_tempo = motore.matrice_osrm(coordinate)
    except Exception as e:
        return jsonify({"ok": False, "errore": f"Errore nel calcolo delle distanze (OSRM): {e}"}), 502

    ordini = motore.ottimizza_con_alternative(
        len(tappe), indici_fissi_in_ordine, indice_partenza, matrice_dist, andata_ritorno,
        n_alternative=max(1, min(n_alternative, 5)),
    )

    alternative = []
    for ordine in ordini:
        segmenti = []
        dist_tot = 0.0
        tempo_tot = 0.0
        sequenza_completa = ordine + ([ordine[0]] if andata_ritorno else [])
        for i in range(len(sequenza_completa) - 1):
            a, b = sequenza_completa[i], sequenza_completa[i + 1]
            d = matrice_dist[a][b]
            t = matrice_tempo[a][b]
            dist_tot += d
            tempo_tot += t
            segmenti.append({
                "da": tappe[a][0], "a": tappe[b][0],
                "km": round(d / 1000, 2), "min": round(t / 60, 1),
            })

        costo = None
        if consumo and prezzo:
            try:
                litri = dist_tot / 1000 * float(consumo) / 100
                costo = round(litri * float(prezzo), 2)
            except (TypeError, ValueError):
                costo = None

        alternative.append({
            "ordine": ordine,
            "tappe": [
                {"indirizzo": tappe[i][0], "lat": tappe[i][1], "lon": tappe[i][2]}
                for i in ordine
            ],
            "andata_ritorno": andata_ritorno,
            "distanza_km": round(dist_tot / 1000, 1),
            "tempo": motore.formatta_durata(tempo_tot),
            "tempo_min": round(tempo_tot / 60, 1),
            "costo_eur": costo,
            "segmenti": segmenti,
        })

    risposta = {"ok": True, "falliti": falliti, "fuori_raggio": fuori_raggio, "alternative": alternative}
    if centro_coord is not None and raggio_km:
        risposta["cerchio"] = {"lat": centro_coord[0], "lon": centro_coord[1], "raggio_km": raggio_km}
    return jsonify(risposta)


@app.post("/api/geometria")
def api_geometria():
    """Calcola il tracciato stradale reale (per disegnarlo sulla mappa) per
    una sequenza di tappe gia' geocodificate. Chiamato solo quando l'utente
    sceglie di visualizzare una specifica alternativa, per non sprecare
    richieste su percorsi che non verranno mai guardati."""
    dati = request.get_json(force=True, silent=True) or {}
    punti = dati.get("punti", [])  # lista di [lat, lon]
    andata_ritorno = bool(dati.get("andata_ritorno", False))

    if len(punti) < 2:
        return jsonify({"ok": False, "errore": "Servono almeno 2 punti."}), 400

    sequenza = [tuple(p) for p in punti]
    if andata_ritorno:
        sequenza = sequenza + [sequenza[0]]

    percorso = []
    try:
        for i in range(len(sequenza) - 1):
            tratta = motore.geometria_tratta(sequenza[i], sequenza[i + 1])
            percorso.extend(tratta)
    except Exception as e:
        return jsonify({"ok": False, "errore": f"Errore nel calcolo del tracciato: {e}"}), 502

    return jsonify({"ok": True, "punti": percorso})


def _apri_browser():
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    lanciato_con_doppio_clic = len(sys.argv) == 1
    threading.Thread(target=_apri_browser, daemon=True).start()
    print("Percorso Economico e' in esecuzione su http://127.0.0.1:5000")
    print("Per chiuderlo: torna a questa finestra e premi CTRL+C\n")
    try:
        app.run(host="127.0.0.1", port=5000, debug=False)
    finally:
        if lanciato_con_doppio_clic:
            input("\nServer fermato. Premi INVIO per chiudere questa finestra...")
