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

import os
import secrets
import sys
import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import (
    LoginManager, current_user, login_required, login_user, logout_user,
)

import motore
from modelli import (
    IndirizzoGeocodificato, PercorsoSalvato, Utente, db,
    email_autorizzata, domini_email_consentiti, url_database,
)

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(BASE_DIR / "static"), template_folder=str(BASE_DIR / "templates"))

app.config["SQLALCHEMY_DATABASE_URI"] = url_database()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    # In produzione VA impostata la variabile d'ambiente SECRET_KEY (vedi
    # PUBBLICARE_ONLINE.md), altrimenti ogni riavvio del server disconnette
    # tutti gli utenti (perche' cambia la chiave usata per firmare le
    # sessioni). In locale una chiave casuale ad ogni avvio va benissimo.
    _secret_key = secrets.token_hex(32)
    if os.environ.get("DATABASE_URL"):
        print(
            "ATTENZIONE: SECRET_KEY non impostata in produzione. "
            "Imposta questa variabile d'ambiente per evitare che gli utenti "
            "vengano disconnessi ad ogni riavvio.",
            file=sys.stderr,
        )
app.config["SECRET_KEY"] = _secret_key

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Accedi per usare Percorso Economico."
login_manager.init_app(app)


@login_manager.unauthorized_handler
def non_autorizzato():
    # Le chiamate alle API (fetch da app.js) vogliono un errore JSON pulito
    # da gestire lato client, non un redirect alla pagina di login.
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "errore": "Sessione scaduta: ricarica la pagina e accedi di nuovo."}), 401
    return redirect(url_for("login"))


@login_manager.user_loader
def carica_utente(utente_id):
    return db.session.get(Utente, int(utente_id))


with app.app_context():
    db.create_all()


def geocodifica_con_cache(indirizzo: str):
    """Come motore.geocodifica, ma controlla prima una cache permanente nel
    database (condivisa da tutta l'azienda): se l'indirizzo e' gia' stato
    cercato in passato, la risposta e' immediata invece di richiedere
    nuove chiamate a Nominatim (che impone 1 richiesta al secondo e in
    passato ha reso il calcolo online molto lento su elenchi di tappe che
    si ripetono, com'e' tipico di percorsi aziendali)."""
    voce = IndirizzoGeocodificato.query.filter_by(indirizzo=indirizzo).first()
    if voce is not None:
        return (voce.lat, voce.lon)

    risultato = motore.geocodifica(indirizzo)
    if risultato is not None:
        lat, lon = risultato
        # Un altro utente potrebbe aver geocodificato lo stesso indirizzo
        # nel frattempo: in quel caso teniamo il suo risultato ed evitiamo
        # un duplicato (l'indirizzo ha un vincolo di unicita').
        try:
            db.session.add(IndirizzoGeocodificato(indirizzo=indirizzo, lat=lat, lon=lon))
            db.session.commit()
        except Exception:
            db.session.rollback()
    return risultato


@app.get("/")
@login_required
def index():
    return render_template("index.html", utente_nome=current_user.nome)


@app.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html", errore=None, email=None)


@app.post("/login")
def login_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    utente = Utente.query.filter_by(email=email).first()
    if not utente or not utente.verifica_password(password):
        return render_template("login.html", errore="Email o password non corrette.", email=email), 401
    login_user(utente, remember=True)
    return redirect(url_for("index"))


@app.get("/registrati")
def registrati():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template(
        "registrati.html", errore=None, nome=None, email=None,
        domini_ammessi=", ".join("@" + d for d in domini_email_consentiti()) or "qualsiasi dominio",
    )


@app.post("/registrati")
def registrati_post():
    nome = request.form.get("nome", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    domini_ammessi_testo = ", ".join("@" + d for d in domini_email_consentiti()) or "qualsiasi dominio"

    errore = None
    if not nome or not email or not password:
        errore = "Compila tutti i campi."
    elif len(password) < 8:
        errore = "La password deve avere almeno 8 caratteri."
    elif not email_autorizzata(email):
        errore = f"Puoi registrarti solo con un'email aziendale ({domini_ammessi_testo})."
    elif Utente.query.filter_by(email=email).first() is not None:
        errore = "Esiste gia' un account con questa email. Prova ad accedere."

    if errore:
        return render_template(
            "registrati.html", errore=errore, nome=nome, email=email, domini_ammessi=domini_ammessi_testo
        ), 400

    utente = Utente(email=email, nome=nome)
    utente.imposta_password(password)
    db.session.add(utente)
    db.session.commit()
    login_user(utente, remember=True)
    return redirect(url_for("index"))


@app.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.get("/storico")
@login_required
def storico():
    percorsi = (
        PercorsoSalvato.query.filter_by(utente_id=current_user.id)
        .order_by(PercorsoSalvato.creato_il.desc())
        .all()
    )
    return render_template("storico.html", percorsi=percorsi, utente_nome=current_user.nome)


@app.post("/storico/<int:percorso_id>/elimina")
@login_required
def elimina_percorso(percorso_id):
    percorso = db.session.get(PercorsoSalvato, percorso_id)
    if percorso is not None and percorso.utente_id == current_user.id:
        db.session.delete(percorso)
        db.session.commit()
    return redirect(url_for("storico"))


@app.post("/api/salva")
@login_required
def api_salva():
    dati = request.get_json(force=True, silent=True) or {}
    nome = (dati.get("nome") or "").strip() or "Percorso senza nome"
    alternativa = dati.get("alternativa")
    if not alternativa or not isinstance(alternativa, dict):
        return jsonify({"ok": False, "errore": "Nessun percorso da salvare."}), 400

    percorso = PercorsoSalvato(
        utente_id=current_user.id,
        nome=nome[:255],
        dati_json=alternativa,
        distanza_km=alternativa.get("distanza_km"),
        tempo_min=alternativa.get("tempo_min"),
        numero_tappe=len(alternativa.get("tappe", [])),
    )
    db.session.add(percorso)
    db.session.commit()
    return jsonify({"ok": True, "id": percorso.id})


@app.post("/api/calcola")
@login_required
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
            centro_coord = geocodifica_con_cache(centro_raggio_indirizzo)
            if centro_coord is None:
                return jsonify({
                    "ok": False,
                    "errore": f"Centro del cerchio non trovato: {centro_raggio_indirizzo!r}",
                }), 400

    # --- geocodifica di tutte le tappe, mantenendo la corrispondenza con gli indici originali ---
    geocodificate = []  # lista di (indice_originale, indirizzo, lat, lon)
    falliti = []
    for i, ind in enumerate(indirizzi):
        risultato = geocodifica_con_cache(ind)
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
@login_required
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
