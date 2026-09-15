# Jak to spustit

Repozitář je zdrojový kód, ne hotová stránka. Aby aplikace naběhla, musí
běžet tři věci: **databáze**, **dokumentová služba** a **web**.

Až bude nasazená na Vercelu, tohle odpadne a stačí otevřít odkaz.

---

## Co je potřeba mít nainstalované

| Program | K čemu | Odkud |
|---|---|---|
| Node.js 20+ | web | nodejs.org |
| Python 3.11+ | dokumentová služba | python.org (při instalaci zaškrtnout „Add to PATH“) |
| PostgreSQL 16 | databáze | postgresql.org |

Ověření, že to jde:

```
node -v
python --version
psql --version
```

Když některý příkaz hlásí, že není známý, chybí instalace nebo se program
nedostal do PATH.

---

## 1. Databáze

```
createdb -U postgres fve
psql -U postgres -d fve -f db/schema.sql
```

Mělo by se vypsat několik řádků `CREATE TABLE`. Když `createdb` hlásí, že
databáze existuje, je to v pořádku — pokračujte druhým příkazem.

## 2. Dokumentová služba

```
cd packages/docx-engine
pip install -r requirements.txt
uvicorn app.main:app --port 8100
```

Okno nechte otevřené. Na `http://localhost:8100/health` se musí objevit
`{"status":"ok"}`.

## 3. Web

Nové okno terminálu:

```
cd apps/web
copy ..\..\.env.example .env
npm install
npm run dev
```

V souboru `apps/web/.env` musí `DATABASE_URL` odpovídat vašemu heslu
k PostgreSQL:

```
DATABASE_URL="postgresql://postgres:VASE_HESLO@127.0.0.1:5432/fve"
```

Aplikace pak běží na `http://localhost:3000`.

---

## Když to nejede

| Co vidíte | Co s tím |
|---|---|
| `ECONNREFUSED` nebo „nedostala se k databázi“ | neběží PostgreSQL, nebo je špatné heslo v `DATABASE_URL` |
| „Dokumentová služba neběží“ | neběží krok 2, nebo běží na jiném portu |
| `'npm' is not recognized` | není nainstalovaný Node.js |
| `'uvicorn' is not recognized` | neproběhl `pip install -r requirements.txt` |
| stránka je prázdná | podívejte se do okna, kde běží `npm run dev` — chyba je tam |

Chybová stránka v aplikaci sama napoví, která z těch tří věcí chybí.

---

## První kroky v aplikaci

1. **Šablony → Nahrát šablonu.** Vyberte sadu, napište označení (`D.2.2`)
   a nahrajte .docx tak, jak je — i s razítkem a barevným značením.
2. Otevře se **průvodce importem**. Projděte skupinu „Vyžaduje rozhodnutí“;
   u každé hodnoty vyberte, čemu v projektu odpovídá, nebo ji označte jako
   fixní text či firemní konstantu.
3. **Potvrdit šablonu.** Vaše rozhodnutí se uloží a použijí se i u dalších
   šablon.
