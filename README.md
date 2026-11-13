# 💰 RisparmioCasa

App personale che **ogni mattina cerca in rete** le opportunità per abbattere i costi di famiglia, ti **invia una notifica** sul telefono, ti permette di **salvare in archivio** quelle utili (con note) e di **condividerle** (WhatsApp, Telegram, mail, ecc.).

**Categorie monitorate:** luce e gas · fibra e mobile · RC auto · spesa e coupon · abbonamenti · Comune di Roma · Regione Lazio · Governo/INPS (bonus, detrazioni, voucher) · auto elettriche (tariffe di ricarica, incentivi) · finanziamenti agevolati.

**Costo: zero.** Usa GitHub (gratis) per la scansione automatica e l'hosting e ntfy o Telegram (gratis) per le notifiche.

---

## Come funziona
```
GitHub Actions (ogni giorno alle 7:30) ──► scanner/scan.py ──► Google News, ultime 48h, ~35 ricerche
        │                                        │
        │                                        ├─► data/feed.json (storico di 30 giorni)
        │                                        └─► notifica push (ntfy / Telegram) con le migliori 6
        ▼
GitHub Pages ──► App sul telefono (index.html, installabile) ──► Oggi · Tutte · Archivio ⭐ · Fonti · Impostazioni
```

## Installazione (circa 15 minuti, una volta sola)

### 1. Pubblica il progetto
1. Crea un account su **github.com** e poi un repository **privato o pubblico** chiamato `risparmiocasa`.
2. Carica tutti i file di questa cartella con *Add file → Upload files*. Carica anche la cartella `.github`: su Windows, se non la vedi, attiva la visualizzazione dei file nascosti.
3. **Settings → Pages → Branch: `main` / root → Save.** Dopo un minuto l'app sarà su `https://TUOUTENTE.github.io/risparmiocasa/`.
   *(GitHub Pages su repository privati richiede un piano a pagamento: usa un repository pubblico. L'archivio personale resta comunque solo sul tuo telefono.)*

### 2. Attiva le notifiche giornaliere (scegli una delle due opzioni)
**Opzione A – ntfy (la più semplice)**
1. Installa l'app **ntfy** (Play Store o App Store).
2. Iscriviti a un topic con un nome difficile da indovinare, ad esempio `risparmio-mazza-8471`.
3. Su GitHub vai in **Settings → Secrets and variables → Actions → New secret**, con nome `NTFY_TOPIC` e valore `risparmio-mazza-8471`.

**Opzione B – Telegram**
1. Su Telegram crea un bot con **@BotFather** e copia il token.
2. Scrivi un messaggio al tuo bot, poi apri `https://api.telegram.org/bot<TOKEN>/getUpdates` per leggere il tuo `chat.id`.
3. Crea i secret `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.

*(Facoltativo)* In **Variables** crea `APP_URL` con l'indirizzo GitHub Pages: toccando la notifica si aprirà l'app.

### 3. Prima scansione
Vai su **Actions → Scansione giornaliera risparmi → Run workflow**. Da quel momento la scansione partirà da sola ogni mattina.

### 4. Installa l'app sul telefono
Apri l'indirizzo GitHub Pages e scegli **Android/Chrome: menu ⋮ → Installa app** oppure **iPhone/Safari: Condividi → Aggiungi a Home**.

---

## Uso
| Sezione | Cosa fa |
|---|---|
| 🔥 **Oggi** | Opportunità delle ultime 36 ore ordinate per rilevanza: fonti istituzionali, importi in €/%, parole come bonus, voucher e scadenza |
| 📰 **Tutte** | Storico degli ultimi 30 giorni, con filtri per categoria e ricerca libera |
| ⭐ **Archivio** | Le opportunità che salvi, con una **nota personale** (scadenza, documenti, ISEE…). Puoi esportarlo e importarlo in JSON |
| 🏛️ **Fonti** | Collegamenti ufficiali: Portale Offerte ARERA, bonus sociale, preventivatore IVASS, INPS, Agenzia Entrate, MIMIT, Roma Capitale, Regione Lazio |
| 📤 **Condividi** | Usa il menu di condivisione del telefono oppure WhatsApp diretto, con il link alla fonte |

## Personalizzazione
Modifica `scanner/config.json` direttamente da GitHub per:
- aggiungere o cambiare **ricerche** (es. `"bonus asilo nido Roma"`, `"offerte ricarica Enel X Way"`, `"tariffe ricarica Ionity abbonamento"`);
- aggiungere **categorie** nuove (es. `"scuola"`, `"salute"`, `"viaggi"`);
- cambiare le **parole che aumentano la rilevanza** o quelle da **escludere**.

Per cambiare l'orario della scansione modifica `cron` in `.github/workflows/scansione-giornaliera.yml` (l'orario è in UTC).

## Note importanti
- L'app **segnala** le opportunità, ma **requisiti, importi e scadenze vanno sempre verificati sulla fonte ufficiale** prima di fare domanda (sezione Fonti).
- **Modalità diretta:** se l'app non trova `data/feed.json`, cerca direttamente da telefono tramite un proxy pubblico. Funziona, ma è meno affidabile della scansione giornaliera.
- **Fonti ufficiali verificate (13/11/2026):** Roma Capitale, Città metropolitana, Regione Lazio, LazioEuropa, INPS (Assegno unico, Portale Famiglie), Agenzia Entrate, MIMIT, Incentivi Italia, incentivi.gov.it, ARERA, IVASS. Lo scanner cerca anche direttamente sui siti `comune.roma.it`, `lazioeuropa.it`, `regione.lazio.it`, `inps.it` e `agenziaentrate.gov.it`.
- **Notifiche ad app chiusa:** quelle affidabili arrivano da ntfy o Telegram. Le notifiche interne della PWA funzionano quando apri l'app e, solo su Chrome Android con l'app installata, anche in background, con frequenza decisa dal sistema.
- L'archivio è salvato **solo sul dispositivo** (localStorage). Usa *Esporta archivio* per farne un backup o spostarlo su un altro telefono.
