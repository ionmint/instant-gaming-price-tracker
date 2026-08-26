# Instant Gaming Price Tracker

Traccia nel tempo il prezzo di prodotti [Instant Gaming](https://www.instant-gaming.com/) e pubblica un report HTML aggiornato automaticamente.

**Report live:** https://ionmint.github.io/instant-gaming-price-tracker/

## Funzionalità

- Aggiunta/rimozione prodotti da tracciare (per URL, sku o nome).
- Aggiornamento automatico dei prezzi 2 volte al giorno via GitHub Actions (funziona anche a PC spento).
- Nuovo punto in cronologia solo quando il prezzo cambia davvero — nessuna riga duplicata.
- Prezzo sempre in EUR, indipendentemente da dove gira lo script (evita il geo-pricing di Instant Gaming).
- Report statico e autoconclusivo (`index.html`): prezzo attuale, variazione, tabella storico, sparkline SVG — nessuna libreria esterna, pubblicato su GitHub Pages.

## Utilizzo

### Da GitHub (senza PC, anche da telefono)

Dal repo, tab **Actions**, workflow da lanciare con *Run workflow*:

| Workflow | Cosa fa | Input |
|---|---|---|
| `Add product` | Aggiunge un prodotto | `url` (link del prodotto Instant Gaming) |
| `Remove product` | Rimuove un prodotto tracciato | `identifier` (sku, URL o nome anche parziale) |
| `Update prices` | Forza subito un controllo prezzi (oltre al cron automatico) | — |

### Da riga di comando (locale)

```bash
pip install -r requirements.txt

python tracker.py add <url>          # aggiungi un prodotto
python tracker.py remove <sku|url|nome>  # rimuovi un prodotto
python tracker.py update             # aggiorna i prezzi di tutti i prodotti tracciati
python tracker.py report             # rigenera index.html senza fare richieste di rete
```

Ogni comando aggiorna `data.json` (dati grezzi) e rigenera `index.html` (report).
