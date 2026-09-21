"""
modelli.py
==========
Modelli dati (utenti aziendali + percorsi salvati) e configurazione del
database. Usa SQLite in locale (nessuna installazione richiesta) e
PostgreSQL in produzione (impostando la variabile d'ambiente DATABASE_URL,
es. su Neon.tech o Supabase, entrambi con un piano gratuito permanente).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def url_database() -> str:
    """URL del database: DATABASE_URL se impostata (produzione, Postgres),
    altrimenti un file SQLite locale (comodo per lo sviluppo e per l'uso
    a doppio clic sul PC)."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        from pathlib import Path
        base_dir = Path(__file__).resolve().parent
        return f"sqlite:///{base_dir / 'percorso.db'}"
    # Render/Heroku forniscono a volte "postgres://", SQLAlchemy vuole "postgresql://"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Utente(UserMixin, db.Model):
    __tablename__ = "utenti"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    creato_il = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    percorsi = db.relationship("PercorsoSalvato", backref="utente", lazy=True, cascade="all, delete-orphan")

    def imposta_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def verifica_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class PercorsoSalvato(db.Model):
    __tablename__ = "percorsi_salvati"

    id = db.Column(db.Integer, primary_key=True)
    utente_id = db.Column(db.Integer, db.ForeignKey("utenti.id"), nullable=False, index=True)
    nome = db.Column(db.String(255), nullable=False)
    creato_il = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # L'intero risultato (tappe nell'ordine calcolato, distanza, tempo,
    # costo, eventuale cerchio) salvato cosi' com'era al momento del salvataggio.
    dati_json = db.Column(db.JSON, nullable=False)

    distanza_km = db.Column(db.Float)
    tempo_min = db.Column(db.Float)
    numero_tappe = db.Column(db.Integer)


class IndirizzoGeocodificato(db.Model):
    """Cache permanente indirizzo -> coordinate. Nominatim impone 1
    richiesta al secondo, quindi geocodificare da zero ogni volta e' lento
    (specie con piu' tappe, ed e' comune che gli stessi indirizzi - clienti,
    sedi, depositi - vengano riusati spesso). Qui il risultato si calcola
    una volta sola e da allora in poi e' una lettura istantanea dal database,
    condivisa tra tutti gli utenti dell'azienda."""
    __tablename__ = "indirizzi_geocodificati"

    id = db.Column(db.Integer, primary_key=True)
    indirizzo = db.Column(db.String(500), unique=True, nullable=False, index=True)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    creato_il = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


def domini_email_consentiti() -> list[str]:
    """Domini email autorizzati alla registrazione (solo colleghi
    dell'azienda). Configurabile con la variabile d'ambiente
    ALLOWED_EMAIL_DOMAINS (domini separati da virgola)."""
    grezzo = os.environ.get("ALLOWED_EMAIL_DOMAINS", "goupnoleggi.it")
    return [d.strip().lower().lstrip("@") for d in grezzo.split(",") if d.strip()]


def email_autorizzata(email: str) -> bool:
    domini = domini_email_consentiti()
    if not domini:
        return True  # nessuna restrizione configurata
    email = email.strip().lower()
    return any(email.endswith("@" + d) for d in domini)
