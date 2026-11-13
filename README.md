# 💰 RisparmioCasa

App personale che **ogni mattina** cerca in rete le opportunità per abbattere i costi di famiglia, aggiorna la **classifica delle 3 offerte luce e gas a prezzo fisso più basse** (dati ufficiali del Portale Offerte ARERA) e ti invia una **notifica** sul telefono. Puoi **salvare** in archivio le opportunità che ti interessano e **condividerle**.

## Sezioni dell'app
| Sezione | Cosa fa |
|---|---|
| 🔥 **Oggi** | Opportunità delle ultime 36 ore, ordinate per rilevanza |
| ⚡ **Tariffe** | Top 3 fornitori luce e gas a **prezzo fisso**, ricalcolata sul **tuo consumo annuo** |
| 📰 **Tutte** | Storico di 30 giorni, con filtri per categoria e ricerca |
| ⭐ **Archivio** | Le opportunità salvate, con note; esportabile e importabile |
| 🏛️ **Fonti** | Fonti ufficiali con filtri per ISEE, categoria, stato della domanda e scadenza |
| ⚙️ **Opzioni** | Notifiche dell'app, backup dell'archivio |

## Come funziona la classifica luce e gas
- **Fonte:** gli Open Data del Portale Offerte (Acquirente Unico/ARERA), cioè i file XML pubblicati ogni giorno con tutte le offerte del mercato libero.
- **Filtri:** solo offerte per clienti domestici, a prezzo fisso, sola luce o solo gas (non dual), valide oggi, disponibili a Roma e senza condizioni limitanti (per esempio "solo soci"). Si tiene un'offerta per fornitore, la più economica.
- **Calcolo:** prezzo dell'energia × consumo + quota fissa di vendita. Il profilo standard è 2.700 kWh e 3 kW per la luce, 1.400 Smc per il gas. Rete, oneri e imposte sono uguali per tutti i fornitori, quindi non cambiano la classifica.
- **Avvertenza:** prima di firmare verifica sempre la scheda sintetica dell'offerta e il Portale Offerte.
- **Se il Portale blocca GitHub (errore 403):** lo scanner prova prima il download diretto con le intestazioni di un browser, poi tre proxy pubblici. Se falliscono entrambi, usa il file più recente che hai caricato in `data/arera/` (istruzioni in `data/arera/LEGGIMI.md`).
- **Se un giorno non riesce a leggere i dati:** il log di GitHub Actions mostra la riga `[energia] ...` con il motivo, e l'app continua a mostrare i dati dell'ultimo aggiornamento riuscito.

## Installazione
Vedi le istruzioni nella chat: GitHub (repository pubblico) → Pages → secret `NTFY_TOPIC` → variabile `APP_URL` → Actions → Run workflow → installazione da Chrome su Android.

## Personalizzazione
- **Ricerche delle notizie:** `scanner/config.json`.
- **Profilo di consumo e numero di fornitori in classifica:** costanti `PROFILO` e `TOP_N` in `scanner/energia.py`.
- **Orario della scansione:** `cron` in `.github/workflows/scansione-giornaliera.yml` (l'orario è in UTC).
