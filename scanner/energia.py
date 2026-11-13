#!/usr/bin/env python3
"""
RisparmioCasa - Classifica offerte luce e gas a PREZZO FISSO dal Portale Offerte ARERA
(Open Data pubblicati da Acquirente Unico su ilportaleofferte.it).

Scarica l'XML più recente delle offerte del mercato libero (E = luce, G = gas),
tiene solo offerte: domestiche, singola fornitura (no dual), prezzo fisso, valide oggi,
disponibili a Roma/Lazio, senza condizioni limitanti. Stima la spesa annua della sola
parte "fornitore" (materia energia + quota fissa di vendita) su un profilo standard
e salva le migliori in data/energia.json (una sola offerta per fornitore).

Le componenti di rete, oneri di sistema e imposte sono uguali per tutti i fornitori a parità
di consumo, quindi la classifica sulla parte fornitore è equivalente a quella sulla spesa totale.
"""
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "energia.json")
BASE = "https://www.ilportaleofferte.it/portaleOfferte/resources/opendata/csv/offerteML/{y}_{m}/PO_Offerte_{c}_MLIBERO_{d}.xml"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

PROFILO = {"E": {"consumo": 2700, "kw": 3.0, "unita": "kWh"}, "G": {"consumo": 1400, "kw": 0, "unita": "Smc"}}
LAZIO_REG = {"12", "012"}
ROMA_PROV = {"058", "58", "258"}
ROMA_COM = {"058091", "58091", "258091"}
TOP_N = 3            # fornitori mostrati
CANDIDATI = 40       # offerte salvate per ricalcolo con i consumi dell'utente


def log(*a):
    print("[energia]", *a, file=sys.stderr, flush=True)


def local(tag):
    return tag.rsplit("}", 1)[-1].upper()


def num(s):
    if s is None:
        return None
    s = str(s).strip().replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def download(commodity):
    """Cerca il file più recente (fino a 15 giorni indietro)."""
    for back in range(0, 15):
        d = date.today() - timedelta(days=back)
        url = BASE.format(y=d.year, m=d.month, c=commodity, d=d.strftime("%Y%m%d"))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Connection": "close"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if data.lstrip()[:1] == b"<" and b"<html" not in data[:500].lower():
                log(f"{commodity}: scaricato {url} ({len(data)//1024} KB)")
                return data, url, d
        except Exception as e:
            if back == 0:
                log(f"{commodity}: {url} -> {e}")
    raise RuntimeError(f"Nessun file offerte {commodity} trovato negli ultimi 15 giorni")


def flatten(el):
    """Ritorna (campi_foglia: dict TAG->[valori], blocchi: dict TAG->[sotto-elementi])."""
    fields, blocks = {}, {}
    for sub in el.iter():
        if sub is el:
            continue
        t = local(sub.tag)
        if len(sub) == 0:
            fields.setdefault(t, []).append((sub.text or "").strip())
        else:
            blocks.setdefault(t, []).append(sub)
    return fields, blocks


def first(fields, *names):
    for n in names:
        v = fields.get(n)
        if v and v[0] != "":
            return v[0]
    return None


def seller_name(fields):
    url = first(fields, "URL_SITO_VENDITORE", "URL_SITO", "SITO_VENDITORE") or ""
    host = urllib.parse.urlparse(url if "://" in url else "https://" + url).hostname or ""
    host = re.sub(r"^(www\d?|offerte|casa|privati|clienti)\.", "", host)
    name = host.split(".")[0] if host else ""
    return name.replace("-", " ").title() if name else (first(fields, "PIVA_UTENTE", "PIVA") or "Fornitore")


def is_limited(blocks):
    for cond in blocks.get("CONDIZIONICONTRATTUALI", []):
        f, _ = flatten(cond)
        lim = (first(f, "LIMITANTE") or "").upper()
        if lim in ("01", "1", "SI", "S", "TRUE"):
            return True
    return False


def in_zone(blocks, fields):
    zones = blocks.get("ZONEOFFERTA", [])
    regs, provs, coms = fields.get("REGIONE", []), fields.get("PROVINCIA", []), fields.get("COMUNE", [])
    if not zones and not (regs or provs or coms):
        return True  # nessuna restrizione = offerta nazionale
    if any(r in LAZIO_REG for r in regs) or any(p in ROMA_PROV for p in provs) or any(c in ROMA_COM for c in coms):
        return True
    return False


def components(blocks, commodity):
    """Restituisce (prezzo_variabile_medio €/unità, fisso €/anno, dettagli)."""
    var_by_fascia, fisso, kw_cost, una_tantum = {}, 0.0, 0.0, 0.0
    kw = PROFILO[commodity]["kw"]
    for comp in blocks.get("COMPONENTEIMPRESA", []):
        f, b = flatten(comp)
        tipologia = (first(f, "TIPOLOGIA") or "01")
        # ogni componente può avere più intervalli di prezzo
        intervals = b.get("INTERVALLOPREZZI") or [comp]
        for iv in intervals:
            fi, _ = flatten(iv) if iv is not comp else (f, None)
            prezzo = num(first(fi, "PREZZO"))
            if prezzo is None:
                continue
            if tipologia == "02" and prezzo > 0:
                prezzo = -prezzo  # sconto
            um = first(fi, "UNITA_MISURA") or first(f, "UNITA_MISURA") or ""
            cons_da = num(first(fi, "CONSUMO_DA")) or 0
            cons_a = num(first(fi, "CONSUMO_A"))
            consumo = PROFILO[commodity]["consumo"]
            if cons_a not in (None, 0) and not (cons_da <= consumo <= cons_a):
                continue  # scaglione non pertinente al profilo
            fascia = first(fi, "FASCIA_COMPONENTE") or "F0"
            if um == "01":                         # €/anno
                fisso += prezzo
            elif um == "02":                       # €/kW (anno)
                kw_cost += prezzo * kw
            elif um in ("03", "04"):               # €/kWh, €/Smc
                var_by_fascia[fascia] = var_by_fascia.get(fascia, 0) + prezzo
            elif um == "05":                       # € una tantum
                una_tantum += prezzo
            else:                                  # unità sconosciuta: euristica
                if abs(prezzo) < 2:
                    var_by_fascia[fascia] = var_by_fascia.get(fascia, 0) + prezzo
                else:
                    fisso += prezzo
    if not var_by_fascia:
        return None
    # media pesata per fasce (profilo domestico tipico: F1 33%, F2 31%, F3 36%)
    pesi = {"F1": .33, "F2": .31, "F3": .36, "F23": .67, "F0": 1.0}
    if "F0" in var_by_fascia and len(var_by_fascia) == 1:
        var = var_by_fascia["F0"]
    else:
        base = var_by_fascia.get("F0", 0)  # componenti valide in tutte le fasce
        fasce = {k: v for k, v in var_by_fascia.items() if k != "F0"}
        tot_peso = sum(pesi.get(k, 0) for k in fasce) or 1
        var = base + sum(v * pesi.get(k, 1 / len(fasce)) for k, v in fasce.items()) / tot_peso
    return var, fisso + kw_cost, una_tantum


def analizza(xml_bytes, commodity):
    oggi = date.today()
    cands, scartate, esempio = [], {}, None
    def skip(motivo):
        scartate[motivo] = scartate.get(motivo, 0) + 1
    for _, el in ET.iterparse(io.BytesIO(xml_bytes), events=("end",)):
        if local(el.tag) != "OFFERTA":
            continue
        if esempio is None:
            esempio = sorted({local(x.tag) for x in el.iter()})
        f, b = flatten(el)
        el.clear()
        mercato = first(f, "TIPO_MERCATO")
        if mercato and mercato not in ("01", "02"):
            skip("dual o altro mercato"); continue
        if (first(f, "OFFERTA_SINGOLA") or "").upper() in ("02", "NO", "N"):
            skip("non singola"); continue
        if (first(f, "TIPO_CLIENTE") or "01") != "01":
            skip("non domestico"); continue
        if (first(f, "TIPO_OFFERTA") or "") != "01":
            skip("non prezzo fisso"); continue
        di, df = parse_date(first(f, "DATA_INIZIO")), parse_date(first(f, "DATA_FINE"))
        if (di and di > oggi) or (df and df < oggi):
            skip("non valida oggi"); continue
        if not in_zone(b, f):
            skip("non disponibile a Roma"); continue
        if is_limited(b):
            skip("condizioni limitanti"); continue
        comp = components(b, commodity)
        if not comp:
            skip("prezzi non leggibili"); continue
        var, fisso, una = comp
        lo, hi = (0.02, 1.0) if commodity == "E" else (0.1, 3.0)
        if not (lo <= var <= hi) or fisso < 0 or fisso > 1000:
            skip("prezzi fuori scala"); continue
        consumo = PROFILO[commodity]["consumo"]
        durata = num(first(f, "DURATA"))
        cands.append({
            "fornitore": seller_name(f),
            "piva": first(f, "PIVA_UTENTE", "PIVA") or "",
            "offerta": first(f, "NOME_OFFERTA", "NOME") or "Offerta",
            "codice": first(f, "COD_OFFERTA", "CODICE_OFFERTA") or "",
            "prezzo": round(var, 5),
            "fisso_anno": round(fisso, 2),
            "una_tantum": round(una, 2),
            "durata_mesi": int(durata) if durata and durata > 0 else None,
            "spesa_fornitore": round(var * consumo + fisso, 2),
            "url": first(f, "URL_OFFERTA") or first(f, "URL_SITO_VENDITORE") or "",
            "valida_fino": df.isoformat() if df else None,
        })
    cands.sort(key=lambda x: x["spesa_fornitore"])
    # una sola offerta (la migliore) per fornitore
    best, seen = [], set()
    for c in cands:
        k = c["piva"] or c["fornitore"]
        if k in seen:
            continue
        seen.add(k)
        best.append(c)
    log(f"{commodity}: {len(cands)} offerte valide, {len(best)} fornitori. Scartate: {scartate}")
    if not cands and esempio:
        log(f"{commodity}: NESSUNA OFFERTA LETTA. Tag trovati nella prima offerta: {esempio}")
    return best[:CANDIDATI], len(cands), scartate


def main():
    out = {"aggiornato": datetime.now(timezone.utc).isoformat(), "profilo": PROFILO, "luce": None, "gas": None}
    for c, key in (("E", "luce"), ("G", "gas")):
        try:
            data, url, d = download(c)
            offerte, n, scartate = analizza(data, c)
            out[key] = {"fonte": url, "data_file": d.isoformat(), "offerte_valide": n,
                        "top": offerte[:TOP_N], "candidati": offerte, "errore": None if offerte else "Nessuna offerta leggibile: vedi il log di GitHub Actions"}
        except Exception as e:
            log(f"{key}: errore {e}")
            out[key] = {"errore": str(e), "top": [], "candidati": []}
    # se fallisce, conserva i dati del giorno precedente
    try:
        old = json.load(open(OUT, encoding="utf-8"))
        for key in ("luce", "gas"):
            if not out[key]["top"] and old.get(key, {}) and old[key].get("top"):
                old[key]["errore"] = "Aggiornamento di oggi non riuscito: dati del " + old[key].get("data_file", "giorno precedente")
                out[key] = old[key]
    except Exception:
        pass
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


def riepilogo_notifica(out):
    righe = []
    for key, em, un in (("luce", "⚡", "kWh"), ("gas", "🔥", "Smc")):
        t = (out.get(key) or {}).get("top") or []
        if t:
            righe.append(f"{em} {key.capitalize()} fissa più bassa: {t[0]['fornitore']} – {t[0]['prezzo']:.3f} €/{un}")
    return righe


if __name__ == "__main__":
    o = main()
    print("\n".join(riepilogo_notifica(o)))
