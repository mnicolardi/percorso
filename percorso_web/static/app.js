// Percorso Economico - logica dell'interfaccia
(function () {
  "use strict";

  const listaTappeEl = document.getElementById("lista-tappe");
  const selPartenzaEl = document.getElementById("sel-partenza");
  const selArrivoEl = document.getElementById("sel-arrivo");
  const risultatiEl = document.getElementById("risultati");
  const messaggiEl = document.getElementById("messaggi");
  const mappaEl = document.getElementById("mappa");
  const btnCalcola = document.getElementById("btn-calcola");

  let contatoreTappe = 0;
  let mappaLeaflet = null;
  let ultimaRisposta = null;
  let ultimoCerchio = null;

  // Legge la risposta come JSON, ma se il server ha risposto con una
  // pagina di errore (es. timeout del server, non riuscendo a rispondere
  // in tempo con molte tappe da geocodificare) da' un messaggio chiaro in
  // italiano invece del criptico errore di sintassi JavaScript.
  async function leggiJsonSicuro(rispostaFetch) {
    const testo = await rispostaFetch.text();
    try {
      return JSON.parse(testo);
    } catch (e) {
      if (rispostaFetch.status >= 500) {
        throw new Error(
          "Il server ha impiegato troppo tempo o non ha risposto correttamente " +
            "(probabilmente troppe tappe da geocodificare tutte insieme). " +
            "Riprova con meno tappe alla volta, oppure attendi qualche secondo e riprova."
        );
      }
      throw new Error("Risposta del server non valida (" + rispostaFetch.status + ").");
    }
  }
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

  function riempiSelettore(selettoreEl, testoVuoto, valorePrecedente) {
    selettoreEl.innerHTML = `<option value="">${testoVuoto}</option>`;
    Array.from(listaTappeEl.children).forEach((div, i) => {
      const indirizzo = div.querySelector(".campo-indirizzo").value.trim();
      const opt = document.createElement("option");
      opt.value = i;
      opt.textContent = indirizzo ? `${i + 1}. ${indirizzo}` : `${i + 1}. (tappa senza indirizzo)`;
      selettoreEl.appendChild(opt);
    });
    if ([...selettoreEl.options].some((o) => o.value === valorePrecedente)) {
      selettoreEl.value = valorePrecedente;
    }
  }

  function aggiornaSelettorePartenza() {
    riempiSelettore(selPartenzaEl, "Nessuna (scelta automatica)", selPartenzaEl.value);
    riempiSelettore(selArrivoEl, "Nessuno (scelta automatica)", selArrivoEl.value);
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

  // --- Geolocalizzazione: aggiunge la posizione attuale del dispositivo
  // come tappa di partenza o di arrivo, chiedendo il permesso al browser
  // e trasformando le coordinate in un indirizzo leggibile lato server.
  function rilevaPosizioneAttuale() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Il tuo browser non supporta la geolocalizzazione."));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        (err) => {
          if (err.code === err.PERMISSION_DENIED) {
            reject(new Error(
              "Permesso di geolocalizzazione negato. Abilitalo nelle impostazioni del browser/sito per usare questa funzione."
            ));
          } else {
            reject(new Error("Non sono riuscito a rilevare la tua posizione attuale."));
          }
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
      );
    });
  }

  async function usaPosizioneAttualeCome(ruolo) {
    // ruolo: "partenza" oppure "arrivo"
    mostraMessaggio("Rilevamento della posizione in corso...", "avviso");
    try {
      const { lat, lon } = await rilevaPosizioneAttuale();
      const r = await fetch("/api/geolocalizza", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat, lon }),
      });
      if (gestisciSessioneScaduta(r)) return;
      const dati = await leggiJsonSicuro(r);
      if (!dati.ok) {
        mostraMessaggio(dati.errore || "Non sono riuscito a determinare l'indirizzo dalla tua posizione.", "errore");
        return;
      }

      const div = nuovaRigaTappa(dati.indirizzo);
      if (ruolo === "partenza") {
        listaTappeEl.insertBefore(div, listaTappeEl.firstChild);
      } else {
        listaTappeEl.appendChild(div); // nuovaRigaTappa la mette gia' in fondo, per chiarezza
      }
      rinumeraTappe();
      aggiornaSelettorePartenza();

      const idx = Array.from(listaTappeEl.children).indexOf(div);
      if (ruolo === "partenza") {
        selPartenzaEl.value = String(idx);
      } else {
        selArrivoEl.value = String(idx);
      }
      mostraMessaggio(`Posizione attuale aggiunta come ${ruolo}: ${dati.indirizzo}`, "avviso");
    } catch (e) {
      mostraMessaggio(e.message || String(e), "errore");
    }
  }

  document.getElementById("btn-posizione-partenza").addEventListener("click", () => usaPosizioneAttualeCome("partenza"));
  document.getElementById("btn-posizione-arrivo").addEventListener("click", () => usaPosizioneAttualeCome("arrivo"));

  // --- Importazione indirizzi da un Google Sheet condiviso via link:
  // si scaricano TUTTE le righe/colonne, poi l'utente filtra e seleziona
  // quali righe usare (utile per un foglio AppSheet con tante colonne). ---
  const btnImportaFoglio = document.getElementById("btn-importa-foglio");
  const inputFoglioGoogle = document.getElementById("input-foglio-google");
  const pannelloFoglio = document.getElementById("pannello-foglio-google");
  const filtroFoglioEl = document.getElementById("filtro-foglio");
  const selColonnaIndirizzoEl = document.getElementById("sel-colonna-indirizzo");
  const tabellaFoglioEl = document.getElementById("tabella-foglio");
  const conteggioSelezionatiEl = document.getElementById("conteggio-selezionati-foglio");

  let righeFoglio = [];        // tutte le righe scaricate (array di oggetti colonna->valore)
  let intestazioniFoglio = []; // nomi delle colonne, nell'ordine
  let selezionateFoglio = new Set(); // indici (in righeFoglio) selezionati

  btnImportaFoglio.addEventListener("click", async () => {
    const link = inputFoglioGoogle.value.trim();
    if (!link) {
      mostraMessaggio("Incolla prima il link del foglio Google.", "errore");
      return;
    }
    btnImportaFoglio.disabled = true;
    const testoOriginale = btnImportaFoglio.textContent;
    btnImportaFoglio.textContent = "Caricamento in corso...";
    mostraMessaggio("", "");
    try {
      const r = await fetch("/api/importa-foglio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ link }),
      });
      if (gestisciSessioneScaduta(r)) return;
      const dati = await leggiJsonSicuro(r);
      if (!dati.ok) {
        mostraMessaggio(dati.errore || "Errore nel caricamento del foglio.", "errore");
        return;
      }
      intestazioniFoglio = dati.intestazioni;
      righeFoglio = dati.righe;
      selezionateFoglio = new Set();

      selColonnaIndirizzoEl.innerHTML = intestazioniFoglio
        .map((c) => `<option value="${c.replace(/"/g, "&quot;")}">${c}</option>`)
        .join("");
      if (dati.colonna_indirizzo_suggerita) {
        selColonnaIndirizzoEl.value = dati.colonna_indirizzo_suggerita;
      }

      filtroFoglioEl.value = "";
      pannelloFoglio.style.display = "block";
      renderTabellaFoglio();
      mostraMessaggio(`Caricate ${righeFoglio.length} righe dal foglio Google. Filtra e seleziona quelle da usare come tappe.`, "avviso");
    } catch (e) {
      mostraMessaggio("Errore di comunicazione con il server: " + e, "errore");
    } finally {
      btnImportaFoglio.disabled = false;
      btnImportaFoglio.textContent = testoOriginale;
    }
  });

  function aggiornaConteggioSelezionati() {
    conteggioSelezionatiEl.textContent = `${selezionateFoglio.size} righe selezionate`;
  }

  function renderTabellaFoglio() {
    const filtro = filtroFoglioEl.value.trim().toLowerCase();
    tabellaFoglioEl.innerHTML = "";
    righeFoglio.forEach((riga, idx) => {
      const testoRiga = intestazioniFoglio.map((c) => riga[c] || "").join(" ").toLowerCase();
      if (filtro && !testoRiga.includes(filtro)) return;

      const div = document.createElement("div");
      div.className = "riga-foglio-elemento";
      const anteprima = intestazioniFoglio
        .slice(0, 4)
        .map((c) => riga[c])
        .filter((v) => v)
        .join(" · ");
      div.innerHTML = `
        <label>
          <input type="checkbox" class="chk-riga-foglio" data-idx="${idx}" ${selezionateFoglio.has(idx) ? "checked" : ""}>
          <span>${anteprima || "(riga vuota)"}</span>
        </label>
      `;
      div.querySelector(".chk-riga-foglio").addEventListener("change", (ev) => {
        if (ev.target.checked) selezionateFoglio.add(idx);
        else selezionateFoglio.delete(idx);
        aggiornaConteggioSelezionati();
      });
      tabellaFoglioEl.appendChild(div);
    });
    if (!tabellaFoglioEl.children.length) {
      tabellaFoglioEl.innerHTML = '<div class="nota-piccola">Nessuna riga corrisponde al filtro.</div>';
    }
    aggiornaConteggioSelezionati();
  }

  filtroFoglioEl.addEventListener("input", renderTabellaFoglio);

  document.getElementById("btn-seleziona-tutti-foglio").addEventListener("click", () => {
    Array.from(tabellaFoglioEl.querySelectorAll(".chk-riga-foglio")).forEach((chk) => {
      chk.checked = true;
      selezionateFoglio.add(parseInt(chk.dataset.idx, 10));
    });
    aggiornaConteggioSelezionati();
  });
  document.getElementById("btn-deseleziona-tutti-foglio").addEventListener("click", () => {
    Array.from(tabellaFoglioEl.querySelectorAll(".chk-riga-foglio")).forEach((chk) => {
      chk.checked = false;
    });
    selezionateFoglio.clear();
    aggiornaConteggioSelezionati();
  });

  document.getElementById("btn-aggiungi-selezionati-foglio").addEventListener("click", () => {
    const colonna = selColonnaIndirizzoEl.value;
    if (!colonna) {
      mostraMessaggio("Scegli quale colonna contiene l'indirizzo.", "errore");
      return;
    }
    if (!selezionateFoglio.size) {
      mostraMessaggio("Seleziona almeno una riga da aggiungere.", "errore");
      return;
    }
    let aggiunte = 0;
    Array.from(selezionateFoglio)
      .sort((a, b) => a - b)
      .forEach((idx) => {
        const indirizzo = (righeFoglio[idx][colonna] || "").trim();
        if (indirizzo) {
          nuovaRigaTappa(indirizzo);
          aggiunte += 1;
        }
      });
    aggiornaSelettorePartenza();
    mostraMessaggio(`Aggiunte ${aggiunte} tappe dal foglio Google.`, "avviso");
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
    const arrivoVal = selArrivoEl.value;
    if (partenzaVal !== "" && arrivoVal !== "" && partenzaVal === arrivoVal) {
      mostraMessaggio("La tappa di partenza e quella di arrivo non possono essere la stessa.", "errore");
      return;
    }
    const corpo = {
      tappe,
      partenza: partenzaVal === "" ? null : parseInt(partenzaVal, 10),
      arrivo: arrivoVal === "" ? null : parseInt(arrivoVal, 10),
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
      if (gestisciSessioneScaduta(r)) return;
      const dati = await leggiJsonSicuro(r);
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
          <button type="button" class="btn-salva">Salva percorso</button>
          <button type="button" class="btn-navigatore">Apri in Google Maps</button>
        </div>
      `;
      div.querySelector(".btn-mappa").addEventListener("click", () => {
        Array.from(risultatiEl.children).forEach((c) => c.classList.remove("selezionata"));
        div.classList.add("selezionata");
        mostraSuMappa(alt);
      });
      div.querySelector(".btn-csv").addEventListener("click", () => scaricaCsv(alt, i));
      div.querySelector(".btn-salva").addEventListener("click", (ev) => salvaPercorso(alt, ev.target));
      div.querySelector(".btn-navigatore").addEventListener("click", () => apriInGoogleMaps(alt));
      risultatiEl.appendChild(div);
    });
  }

  async function salvaPercorso(alt, bottone) {
    const nome = prompt("Nome per questo percorso (es. \"Giro clienti Bari nord\"):", "");
    if (nome === null) return; // annullato
    bottone.disabled = true;
    const testoOriginale = bottone.textContent;
    bottone.textContent = "Salvataggio...";
    try {
      const r = await fetch("/api/salva", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome: nome.trim() || "Percorso senza nome", alternativa: alt }),
      });
      if (gestisciSessioneScaduta(r)) return;
      const dati = await leggiJsonSicuro(r);
      if (dati.ok) {
        bottone.textContent = "Salvato ✓";
        setTimeout(() => { bottone.textContent = testoOriginale; bottone.disabled = false; }, 2000);
      } else {
        mostraMessaggio(dati.errore || "Errore nel salvataggio.", "errore");
        bottone.textContent = testoOriginale;
        bottone.disabled = false;
      }
    } catch (e) {
      mostraMessaggio("Errore di comunicazione con il server: " + e, "errore");
      bottone.textContent = testoOriginale;
      bottone.disabled = false;
    }
  }

  function gestisciSessioneScaduta(rispostaFetch) {
    if (rispostaFetch.status === 401) {
      mostraMessaggio("Sessione scaduta. Verrai reindirizzato alla pagina di accesso...", "avviso");
      setTimeout(() => { window.location.href = "/login"; }, 1500);
      return true;
    }
    return false;
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

  function apriInGoogleMaps(alt) {
    // Apre il percorso calcolato nell'app/sito di Google Maps, con tutte le
    // tappe come waypoint nell'ordine scelto: sul telefono, se l'app di
    // Google Maps e' installata, si apre direttamente li' con la
    // navigazione pronta da avviare.
    const tappe = alt.tappe;
    if (!tappe.length) return;
    const sequenzaCompleta = alt.andata_ritorno ? tappe.concat([tappe[0]]) : tappe;

    // Google Maps accetta un numero limitato di tappe in un link diretto:
    // teniamoci larghi ma avvisiamo se il percorso e' piu' lungo di cosi'.
    const MASSIMO_TAPPE_LINK = 25;
    let elenco = sequenzaCompleta;
    let troncato = false;
    if (elenco.length > MASSIMO_TAPPE_LINK) {
      elenco = elenco.slice(0, MASSIMO_TAPPE_LINK);
      troncato = true;
    }

    const origine = `${elenco[0].lat},${elenco[0].lon}`;
    const destinazione = `${elenco[elenco.length - 1].lat},${elenco[elenco.length - 1].lon}`;
    const intermedie = elenco.slice(1, -1).map((t) => `${t.lat},${t.lon}`).join("|");

    const params = new URLSearchParams({
      api: "1",
      origin: origine,
      destination: destinazione,
      travelmode: "driving",
    });
    let url = `https://www.google.com/maps/dir/?${params.toString()}`;
    if (intermedie) url += `&waypoints=${encodeURIComponent(intermedie)}`;

    window.open(url, "_blank");

    if (troncato) {
      mostraMessaggio(
        `Google Maps accetta al massimo ${MASSIMO_TAPPE_LINK} tappe in un link diretto: sono state incluse solo le prime ${MASSIMO_TAPPE_LINK}.`,
        "avviso"
      );
    }
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
      if (gestisciSessioneScaduta(r)) return;
      const dati = await leggiJsonSicuro(r);
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
