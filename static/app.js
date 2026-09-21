// Percorso Economico - logica dell'interfaccia
(function () {
  "use strict";

  const listaTappeEl = document.getElementById("lista-tappe");
  const selPartenzaEl = document.getElementById("sel-partenza");
  const risultatiEl = document.getElementById("risultati");
  const messaggiEl = document.getElementById("messaggi");
  const mappaEl = document.getElementById("mappa");
  const btnCalcola = document.getElementById("btn-calcola");

  let contatoreTappe = 0;
  let mappaLeaflet = null;
  let ultimaRisposta = null;
  let ultimoCerchio = null;
  let layerCerchio = null;

  const INDIRIZZI_ESEMPIO = [
    "Piazza del Duomo, Milano",
    "Stazione Centrale, Milano",
    "Navigli, Milano",
    "Castello Sforzesco, Milano",
  ];

  function nuovaRigaTappa(valore) {
    contatoreTappe += 1;
    const id = contatoreTappe;
    const div = document.createElement("div");
    div.className = "tappa";
    div.dataset.id = id;
    div.innerHTML = `
      <div class="numero">${id}</div>
      <input type="text" class="campo-indirizzo" placeholder="Via, civico - CAP - Comune - PR"
             value="${valore ? valore.replace(/"/g, "&quot;") : ""}">
      <div class="tappa-azioni">
        <label title="Questa tappa deve mantenere la sua posizione relativa rispetto alle altre tappe con ordine fisso">
          <input type="checkbox" class="chk-ordine-fisso"> ordine fisso
        </label>
        <button type="button" class="btn-icona btn-su" title="Sposta su">&uarr;</button>
        <button type="button" class="btn-icona btn-giu" title="Sposta gi&ugrave;">&darr;</button>
        <button type="button" class="btn-icona btn-rimuovi" title="Rimuovi">&times;</button>
      </div>
    `;
    listaTappeEl.appendChild(div);
    div.querySelector(".btn-su").addEventListener("click", () => spostaRiga(div, -1));
    div.querySelector(".btn-giu").addEventListener("click", () => spostaRiga(div, 1));
    div.querySelector(".btn-rimuovi").addEventListener("click", () => {
      div.remove();
      rinumeraTappe();
      aggiornaSelettorePartenza();
    });
    div.querySelector(".campo-indirizzo").addEventListener("input", aggiornaSelettorePartenza);
    return div;
  }

  function spostaRiga(div, delta) {
    const righe = Array.from(listaTappeEl.children);
    const idx = righe.indexOf(div);
    const nuovoIdx = idx + delta;
    if (nuovoIdx < 0 || nuovoIdx >= righe.length) return;
    if (delta < 0) {
      listaTappeEl.insertBefore(div, righe[nuovoIdx]);
    } else {
      listaTappeEl.insertBefore(righe[nuovoIdx], div);
    }
    rinumeraTappe();
    aggiornaSelettorePartenza();
  }

  function rinumeraTappe() {
    Array.from(listaTappeEl.children).forEach((div, i) => {
      div.querySelector(".numero").textContent = i + 1;
    });
  }

  function aggiornaSelettorePartenza() {
    const valorePrecedente = selPartenzaEl.value;
    selPartenzaEl.innerHTML = '<option value="">Nessuna (scelta automatica)</option>';
    Array.from(listaTappeEl.children).forEach((div, i) => {
      const indirizzo = div.querySelector(".campo-indirizzo").value.trim();
      const opt = document.createElement("option");
      opt.value = i;
      opt.textContent = indirizzo ? `${i + 1}. ${indirizzo}` : `${i + 1}. (tappa senza indirizzo)`;
      selPartenzaEl.appendChild(opt);
    });
    if ([...selPartenzaEl.options].some((o) => o.value === valorePrecedente)) {
      selPartenzaEl.value = valorePrecedente;
    }
  }

  function leggiTappe() {
    return Array.from(listaTappeEl.children).map((div) => ({
      indirizzo: div.querySelector(".campo-indirizzo").value.trim(),
      ordine_fisso: div.querySelector(".chk-ordine-fisso").checked,
    }));
  }

  function mostraMessaggio(testo, tipo) {
    messaggiEl.innerHTML = testo ? `<div class="msg-${tipo}">${testo}</div>` : "";
  }

  document.getElementById("btn-aggiungi").addEventListener("click", () => {
    nuovaRigaTappa("");
    aggiornaSelettorePartenza();
  });

  const inputFile = document.getElementById("file-importa");
  document.getElementById("btn-importa").addEventListener("click", () => inputFile.click());
  inputFile.addEventListener("change", () => {
    const file = inputFile.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      // Un indirizzo per riga (va bene anche se l'indirizzo stesso contiene
      // virgole, come "Piazza del Duomo, Milano" o il formato con CAP/comune).
      const righe = String(reader.result)
        .split(/\r?\n/)
        .map((r) => r.trim())
        .filter((r) => r && r.toLowerCase() !== "indirizzo");
      if (!righe.length) {
        mostraMessaggio("Il file non contiene indirizzi utilizzabili.", "errore");
        return;
      }
      listaTappeEl.innerHTML = "";
      righe.forEach((ind) => nuovaRigaTappa(ind));
      aggiornaSelettorePartenza();
      mostraMessaggio(`Importati ${righe.length} indirizzi da ${file.name}.`, "avviso");
    };
    reader.onerror = () => mostraMessaggio("Non sono riuscito a leggere il file.", "errore");
    reader.readAsText(file, "utf-8");
    inputFile.value = "";
  });

  // Precompila con alcune tappe di esempio al primo avvio
  INDIRIZZI_ESEMPIO.forEach((ind) => nuovaRigaTappa(ind));
  aggiornaSelettorePartenza();

  btnCalcola.addEventListener("click", calcola);

  function centroComeTappaDiPartenza() {
    const usaComePartenza = document.getElementById("chk-centro-e-partenza").checked;
    const centroIndirizzo = document.getElementById("input-centro-raggio").value.trim();
    if (!usaComePartenza || !centroIndirizzo) return;

    // Se una tappa con questo indirizzo esiste gia', la usiamo com'e'
    // (evitando un doppione); altrimenti la aggiungiamo alla lista.
    const righe = Array.from(listaTappeEl.children);
    let indiceEsistente = righe.findIndex(
      (div) => div.querySelector(".campo-indirizzo").value.trim().toLowerCase() === centroIndirizzo.toLowerCase()
    );
    if (indiceEsistente === -1) {
      nuovaRigaTappa(centroIndirizzo);
      aggiornaSelettorePartenza();
      indiceEsistente = listaTappeEl.children.length - 1;
    }
    selPartenzaEl.value = String(indiceEsistente);
  }

  const chkCentroPartenza = document.getElementById("chk-centro-e-partenza");
  chkCentroPartenza.addEventListener("change", () => {
    selPartenzaEl.disabled = chkCentroPartenza.checked;
  });

  async function calcola() {
    mostraMessaggio("", "");
    centroComeTappaDiPartenza();
    const tappe = leggiTappe();
    if (tappe.length < 2 || tappe.some((t) => !t.indirizzo)) {
      mostraMessaggio("Inserisci almeno 2 tappe, tutte con un indirizzo.", "errore");
      return;
    }
    const partenzaVal = selPartenzaEl.value;
    const corpo = {
      tappe,
      partenza: partenzaVal === "" ? null : parseInt(partenzaVal, 10),
      andata_ritorno: document.getElementById("chk-andata-ritorno").checked,
      consumo: document.getElementById("input-consumo").value || null,
      prezzo: document.getElementById("input-prezzo").value || null,
      n_alternative: parseInt(document.getElementById("input-alternative").value, 10),
      centro_raggio_indirizzo: document.getElementById("input-centro-raggio").value.trim() || null,
      raggio_km: document.getElementById("input-raggio-km").value || null,
    };

    btnCalcola.disabled = true;
    btnCalcola.textContent = "Calcolo in corso... (puo' richiedere qualche secondo)";
    risultatiEl.innerHTML = '<div class="vuoto">Calcolo in corso...</div>';
    mappaEl.style.display = "none";

    try {
      const r = await fetch("/api/calcola", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpo),
      });
      const dati = await r.json();
      if (!dati.ok) {
        mostraMessaggio(dati.errore || "Errore nel calcolo.", "errore");
        risultatiEl.innerHTML = '<div class="vuoto">Nessun risultato.</div>';
        return;
      }
      ultimaRisposta = dati;
      const messaggiAvviso = [];
      if (dati.falliti && dati.falliti.length) {
        messaggiAvviso.push("Indirizzi non trovati (esclusi dal calcolo): " + dati.falliti.join(" | "));
      }
      if (dati.fuori_raggio && dati.fuori_raggio.length) {
        messaggiAvviso.push(
          "Tappe escluse perche' oltre la distanza massima: " +
            dati.fuori_raggio.map((f) => `${f.indirizzo} (${f.distanza_km} km)`).join(" | ")
        );
      }
      if (messaggiAvviso.length) {
        mostraMessaggio(messaggiAvviso.join("<br>"), "avviso");
      }
      ultimoCerchio = dati.cerchio || null;
      mostraRisultati(dati.alternative);
    } catch (e) {
      mostraMessaggio("Errore di comunicazione con il server: " + e, "errore");
    } finally {
      btnCalcola.disabled = false;
      btnCalcola.textContent = "Calcola percorso";
    }
  }

  function mostraRisultati(alternative) {
    if (!alternative.length) {
      risultatiEl.innerHTML = '<div class="vuoto">Nessun percorso trovato.</div>';
      return;
    }
    risultatiEl.innerHTML = "";
    alternative.forEach((alt, i) => {
      const div = document.createElement("div");
      div.className = "alternativa" + (i === 0 ? " selezionata" : "");
      const elencoTappe = alt.tappe
        .map((t, pos) => `<li>${pos + 1}. ${t.indirizzo}</li>`)
        .join("");
      const costoHtml = alt.costo_eur != null
        ? `<span>costo stimato: <b>${alt.costo_eur.toFixed(2)} &euro;</b></span>`
        : "";
      div.innerHTML = `
        <div class="alternativa-testata">
          <strong>${i === 0 ? "Percorso migliore" : "Alternativa " + i}</strong>
          ${i === 0 ? '<span class="badge">consigliato</span>' : ""}
        </div>
        <div class="alternativa-cifre">
          <span>distanza: <b>${alt.distanza_km} km</b></span>
          <span>tempo di guida: <b>${alt.tempo}</b></span>
          ${costoHtml}
        </div>
        <ol class="elenco-tappe-ordinate">${elencoTappe}</ol>
        <div class="alternativa-azioni">
          <button type="button" class="btn-mappa">Mostra su mappa</button>
          <button type="button" class="btn-csv">Scarica CSV</button>
        </div>
      `;
      div.querySelector(".btn-mappa").addEventListener("click", () => {
        Array.from(risultatiEl.children).forEach((c) => c.classList.remove("selezionata"));
        div.classList.add("selezionata");
        mostraSuMappa(alt);
      });
      div.querySelector(".btn-csv").addEventListener("click", () => scaricaCsv(alt, i));
      risultatiEl.appendChild(div);
    });
  }

  function scaricaCsv(alt, indice) {
    const righe = ["ordine,indirizzo,lat,lon,km_dalla_precedente,min_dalla_precedente"];
    alt.tappe.forEach((t, pos) => {
      const seg = pos === 0 ? null : alt.segmenti[pos - 1];
      righe.push(
        [pos + 1, `"${t.indirizzo.replace(/"/g, '""')}"`, t.lat, t.lon,
          seg ? seg.km : 0, seg ? seg.min : 0].join(",")
      );
    });
    if (alt.andata_ritorno) {
      const ultimoSeg = alt.segmenti[alt.segmenti.length - 1];
      righe.push(
        [alt.tappe.length + 1, `"${alt.tappe[0].indirizzo.replace(/"/g, '""')} (ritorno)"`,
          alt.tappe[0].lat, alt.tappe[0].lon, ultimoSeg.km, ultimoSeg.min].join(",")
      );
    }
    const blob = new Blob([righe.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `itinerario_alternativa_${indice + 1}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function mostraSuMappa(alt) {
    mappaEl.style.display = "block";
    mappaEl.scrollIntoView({ behavior: "smooth", block: "nearest" });

    if (!mappaLeaflet) {
      mappaLeaflet = L.map(mappaEl).setView([alt.tappe[0].lat, alt.tappe[0].lon], 12);
      L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        { attribution: "Tiles &copy; Esri", maxZoom: 19 }
      ).addTo(mappaLeaflet);
    }
    // ripulisce marker/linee/cerchio precedenti
    mappaLeaflet.eachLayer((layer) => {
      if (layer instanceof L.Marker || layer instanceof L.Polyline || layer instanceof L.Circle) {
        mappaLeaflet.removeLayer(layer);
      }
    });
    layerCerchio = null;

    // Coordinate delle SOLE tappe del percorso: usate per disegnare la
    // linea del percorso (il cerchio e le tappe escluse non fanno parte
    // del tragitto, servono solo da riferimento visivo sulla mappa).
    const puntiRotta = alt.tappe.map((t) => [t.lat, t.lon]);
    const puntiVisibili = puntiRotta.slice();

    if (ultimoCerchio) {
      layerCerchio = L.circle([ultimoCerchio.lat, ultimoCerchio.lon], {
        radius: ultimoCerchio.raggio_km * 1000,
        color: "#a15c00",
        weight: 2,
        fillColor: "#a15c00",
        fillOpacity: 0.06,
        dashArray: "4 6",
      }).bindTooltip(`Raggio massimo: ${ultimoCerchio.raggio_km} km`).addTo(mappaLeaflet);
    }

    alt.tappe.forEach((t, pos) => {
      const colore = pos === 0 ? "green" : pos === alt.tappe.length - 1 && !alt.andata_ritorno ? "red" : "blue";
      L.circleMarker([t.lat, t.lon], {
        radius: 9, color: "#fff", weight: 2, fillColor: colore, fillOpacity: 1,
      }).bindTooltip(`${pos + 1}. ${t.indirizzo}`, { permanent: false }).addTo(mappaLeaflet);
    });

    // Tappe escluse perche' fuori dal raggio massimo: le mostriamo sulla
    // mappa (grigie, tratteggiate) ma il percorso non le tocca.
    const fuoriRaggio = (ultimaRisposta && ultimaRisposta.fuori_raggio) || [];
    fuoriRaggio.forEach((t) => {
      if (t.lat == null || t.lon == null) return;
      L.circleMarker([t.lat, t.lon], {
        radius: 7, color: "#8a8578", weight: 2, fillColor: "#c9c4b6", fillOpacity: 0.9, dashArray: "3 3",
      }).bindTooltip(`Esclusa (fuori raggio, ${t.distanza_km} km): ${t.indirizzo}`, { permanent: false }).addTo(mappaLeaflet);
      puntiVisibili.push([t.lat, t.lon]);
    });

    let confini = L.latLngBounds(puntiVisibili);
    if (layerCerchio) {
      confini = confini.extend(layerCerchio.getBounds());
    }
    mappaLeaflet.fitBounds(confini, { padding: [30, 30] });

    // linea diretta provvisoria, subito visibile, poi sostituita dal tracciato stradale reale
    const lineaDiretta = L.polyline(puntiRotta.concat(alt.andata_ritorno ? [puntiRotta[0]] : []), {
      color: "#2b6cb0", weight: 2, dashArray: "6 6", opacity: 0.6,
    }).addTo(mappaLeaflet);

    try {
      const r = await fetch("/api/geometria", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          punti: alt.tappe.map((t) => [t.lat, t.lon]),
          andata_ritorno: alt.andata_ritorno,
        }),
      });
      const dati = await r.json();
      if (dati.ok) {
        mappaLeaflet.removeLayer(lineaDiretta);
        L.polyline(dati.punti, { color: "#2b6cb0", weight: 4, opacity: 0.85 }).addTo(mappaLeaflet);
      }
    } catch (e) {
      // Se il tracciato stradale non si riesce a calcolare, resta visibile
      // la linea diretta tratteggiata: il risultato del percorso resta comunque leggibile.
    }
  }
})();
