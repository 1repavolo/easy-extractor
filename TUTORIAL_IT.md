# Tutorial per l'Estrazione della Keybox (Versione Ottimizzata per la RAM)

Questo progetto contiene gli script per eseguire il dump e l'estrazione dei dati **Android Attestation Keybox** dai dispositivi Android con processori **MediaTek (MTK)** (con bootloader sbloccato e root, come Magisk).

Questa guida spiega in particolare l'uso del nuovo script ottimizzato per non sovraccaricare la RAM (`run_all_partitions_extraction.ps1`), che prova tutte le partizioni una per una in modo efficiente.

---

## Prerequisiti

1. **Dispositivo MTK:** Uno smartphone MediaTek (MT67xx, Dimensity, ecc.).
2. **Root (Magisk):** Il dispositivo deve avere i permessi di root, e il root deve essere stato concesso alla shell (adb).
3. **Debug USB abilitato:** Dal menù Opzioni Sviluppatore del telefono.
4. **PC Windows (PowerShell):** Questo script master utilizza PowerShell.
5. **Dipendenze Python:** Installa i pacchetti necessari per la verifica del certificato:
   ```powershell
   pip install cryptography
   ```

---

## Cos'è `run_all_partitions_extraction.ps1`?

Nelle versioni base del progetto, l'operazione esegue prima il dump di tutte le partizioni sul PC, per poi analizzarle tutte assieme caricando i file in memoria RAM. Su dispositivi con partizioni molto grandi, o dumpando *tutte* le partizioni, questo approccio saturava la RAM e consumava molto spazio su disco rigido.

Il nuovo script `run_all_partitions_extraction.ps1` risolve questo problema:
1. Scopre in automatico tutte le partizioni dal dispositivo.
2. Esclude le partizioni standard del sistema Android (es. `boot`, `system`, `vendor`).
3. Cerca sequenzialmente una Keybox su ogni partizione rimanente:
   - Scarica la singola partizione (es. `persist`).
   - Usa script Python pesantemente ottimizzati (`mmap`, che caricano i file a pezzi, non riempiendo la RAM) per scansionare marcatori e provare ad estrarre.
   - Verifica se la Keybox estratta è valida.
   - **Elimina la partizione appena scaricata (risparmio spazio/RAM)** e passa alla successiva.
   - Interrompe la ricerca non appena trova una Keybox valida.

---

## Come Usarlo

Collega il tuo dispositivo MTK acceso ed esegui questi passaggi da PowerShell:

1. **Verifica il Root e ADB:**
   ```powershell
   adb devices
   adb shell su -c id
   ```
   Dovresti vedere il dispositivo nella lista e un output simile a `uid=0(root)`.

2. **Esegui lo Script:**
   Apri il terminale PowerShell nella cartella principale del progetto, ed esegui lo script:
   ```powershell
   .\run_all_partitions_extraction.ps1
   ```

3. **Cosa Aspettarsi:**
   - Lo script identificherà il numero totale di partizioni sul dispositivo (es. 40 partizioni candidate).
   - Analizzerà una partizione alla volta mostrando in tempo reale il tentativo di scaricamento e analisi.
   - Se una partizione contiene dati Keybox validi e con i certificati in regola (es. `persist`), lo script scriverà il file `.xml` nella cartella `dumps/`, avviserà dell'avvenuto successo in verde e terminerà immediatamente il lavoro per farti risparmiare tempo.

### Opzioni Avanzate

Puoi personalizzare il nome e la destinazione del file XML estratto, ad esempio:

```powershell
.\run_all_partitions_extraction.ps1 -DeviceLabel "MioTelefono" -OutputXml "dumps\LaMiaKeybox.xml"
```

## Struttura del Risultato

Se completato con successo, nella tua cartella `dumps/` troverai:
- `*_Pvt_kb.xml` (o il nome specificato) – La Keybox pulita pronta per l'uso.
- `*_validity.json` – Il resoconto sull'autenticità e validità dei certificati per la Keybox estratta.

> **Avvertenza Sicurezza:** I file nella cartella `dumps/` contengono chiavi private sensibili specifiche del tuo dispositivo. **Non committare mai** questi file su repository pubbliche come GitHub.
