# FVE dokumentace

Nástroj pro tvorbu projektové dokumentace fotovoltaických elektráren.
Projekt se založí, uloží, kdykoliv upraví a dokumentace se z něj vygeneruje znovu.

Zadání a analýza jsou v projektu „Webová aplikace“ na claude.ai:
`00-zadani.md`, `01-analyza-podkladu.md`, `02-navrh-architektury.md`,
`03-otazky.md`, `04-odpovedi-a-rozhodnuti.md`.

## Stav

| Část | Stav |
|---|---|
| Datový model projektu (JSON Schema) | hotovo — `docs/project-data.schema.json` |
| Databázové schéma | hotovo — `db/schema.sql` |
| Parser šablon .docx | hotovo — `packages/docx-engine/app/parser.py` |
| Navázání hodnot uvnitř vět | hotovo — `packages/docx-engine/app/binder.py` |
| Opakující se bloky (stringy, kabeláž) | hotovo — `packages/docx-engine/app/sequences.py` |
| Generátor DOCX | hotovo — `packages/docx-engine/app/render.py` |
| Pre-flight kontrola dat | hotovo — `packages/docx-engine/app/validate.py` |
| Kontrola hotového dokumentu | hotovo — `packages/docx-engine/app/verify.py` |
| HTTP rozhraní dokumentové služby | hotovo — `packages/docx-engine/app/main.py` |
| Webové rozhraní (Next.js) | běží — seznam projektů, šablony, průvodce importem |
| Výkaz výměr (XLSX) | připraveno v modelu, generátor přijde |
| Dimenzování kabeláže a jištění | chybí, přijde po výpočetní vrstvě |

## Jak je to postavené

Aplikace má tři části:

```
apps/web              Next.js (PWA) + server-side API, jediné místo s tajemstvími
packages/docx-engine  Python služba nad OOXML – import šablon a generování DOCX
db/schema.sql         schéma databáze (PostgreSQL)
docs                  datový model projektu (JSON Schema)
```

Databáze se ovládá přes **Kysely** nad `pg` – dotazy jsou psané v SQL a typy
popisují `db/schema.sql`. Prisma se neosvědčila: stahuje si nativní engine
z vlastního serveru při každé instalaci i buildu, což je v uzavřeném
prostředí i na serverless zbytečná závislost navíc.

Klíče (AI, úložiště, SMTP, databáze) jsou výhradně v proměnných prostředí
na serveru. Frontend je nikdy nevidí a v repozitáři nejsou.

### Proč se dokument negeneruje od nuly

Šablony mají razítkovou tabulku, záhlaví, zápatí, obrázky, styly, automatický
obsah a číslování. Kdyby se dokument skládal znovu, nedalo by se zaručit, že
se všechno přenese. Engine proto otevře **originální .docx**, změní obsah
konkrétních runů a uloží ho pod novým jménem. Ověřeno testem
`test_structure_preserved`: vygenerovaný dokument má stejný počet odstavců,
tabulek, sekcí, obrázků i stylů jako originál a shodné záhlaví.

### Role textu podle zvýraznění

| Barva | Role | Chování |
|---|---|---|
| žlutá | proměnná | nahradí se hodnotou z projektu |
| zelená | generovaný text | vytvoří AI z dat projektu |
| bez zvýraznění | fixní text | zůstane beze změny |

Barva je ale jen primární indikace, ne jediný zdroj pravdy. Import proto vrací
**kandidáty s evidencí** z křížové analýzy referenčních projektů, které
uživatel potvrdí; jeho opravy se ukládají jako pravidla pro další šablony.

**Nevyplněná proměnná zůstane v dokumentu zvýrazněná.** Kdyby se zvýraznění
smazalo, stará hodnota ze šablony by vypadala jako platný údaj projektu —
přesně to, co v podkladech způsobilo většinu nalezených chyb.

### Dvě kontroly

**Před generováním** projdou data pre-flightem (`validate.py`). Každé pravidlo
je psané podle chyby, která se opravdu stala: instalovaný výkon proti počtu
panelů, součet stringů i orientací, jedinečnost označení stringů, napětí a
proud proti limitům střídače, počet optimizérů počítaný po střechách,
roční výroba, bezpečné napětí na střeše, jedna varianta LPS. Chyba generování
zastaví; projde jen s `--force`.

**Po generování** se hotový dokument prohledá (`verify.py`), jestli v něm
nezůstala hodnota ze šablony tam, kde projekt má jinou. Čte i neoznačený text,
protože právě tam se zapomenuté hodnoty schovávají. Citace norem se přeskakují —
„ochrana … do 1000 V na straně AC“ není parametr střídače.

## Spuštění

Databáze:

```bash
createdb fve && psql -d fve -f db/schema.sql
```

Web (potřebuje běžící dokumentovou službu):

```bash
cd apps/web
cp ../../.env.example .env      # a doplnit DATABASE_URL
npm install
npm run dev                     # http://localhost:3000
```

## Spuštění dokumentové služby

```bash
cd packages/docx-engine
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100
```

Import šablony a vygenerování dokumentu z příkazové řádky:

```bash
python -m app.parser "../../data/templates/V1/D.2.2-TZ-FVE-MS Tichá.docx" manifest.json
python -m app.render  "../../data/templates/V1/D.2.2-TZ-FVE-MS Tichá.docx" \
                      manifest.json data.json vystup.docx
```

Testy (potřebují šablony v `data/templates/`):

```bash
cd packages/docx-engine && FVE_TEMPLATES=../../data/templates pytest -q
```

## Nasazení

Kód je na GitHubu, běh aplikace ne — GitHub Pages umí jen statické stránky
a klíče by musely být ve frontendu. Nasazuje se na:

- **Vercel** — web a server-side API, nasazení při každém commitu
- **Neon** — PostgreSQL
- **Cloudflare R2** — šablony, podklady, vygenerované dokumenty

Všechno běží i v Dockeru (`docker compose up`), takže přestěhování na vlastní
server je otázka změny proměnných prostředí.

## Rozhodnutí, která se promítla do kódu

- výstup jen **DOCX**, PDF se negeneruje (odpadá konverze i deformace formátování)
- výkaz výměr jako **XLSX** se zachovaným listem *Razítko*
- množství ve výkazu je **text**, ne číslo — „dle trasy“ a „netýká se“ jsou platné hodnoty
- verze projektu je **neměnný snapshot**, původní se nikdy nepřepisuje
- ruční úprava dokumentu ve Wordu se nepřepíše — přegenerováním vznikne **nový soubor vedle**
- LPS má **4 varianty** (není / izolovaný / neizolovaný / oddálený) a nezávisle „bude projekt LPS“
- čísla zakázek mimo V1 se generují ve tvaru `26VI100`, `26VI101`, …
