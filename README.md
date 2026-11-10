# ATELJE TEPIHA — online shop (razvojna verzija)

**Samo Tarkett / Sintelon tepisi**, ništa od ostalih kategorija podova.

## Kako da pokrenete u Windows-u

1. Raspakujte ceo ZIP u jednu fasciklu.
2. Potrebno je da imate instaliran **Python 3.10 ili noviji** sa https://www.python.org/downloads/ (pri instalaciji uključiti *Add Python to PATH*).
3. Dvaput kliknite na **POKRENI_PRODAVNICU.bat** (ili otvorite terminal u toj fascikli i unesite `python app.py`).
4. U pretraživaču otvorite **http://localhost:8765**.
5. Kliknite na ikonicu osobe gore desno da otvorite **Administraciju**. Na **prvom pokretanju** u crnom prozoru ispisuje se jednokratno generisana administratorska lozinka. **Zapišite je.**
6. Otvorite *Cene i zalihe*, odaberite model, upišite nabavnu i prodajnu cenu za svaku dimenziju i kliknite **Sačuvaj izmene**. Nabavnu cenu kupac ne vidi. Ako je prodajna cena 0, varijanta se ne može poručiti.

Podaci se automatski čuvaju u lokalnoj **SQLite** bazi `data/shop.sqlite3`. Podaci ostaju i posle gašenja programa. Za rezervnu kopiju kopirajte **celu fasciklu `data`** kada je program isključen.

## Šta već radi

- Prodajna stranica sa pretragom, kolekcijama, modelima, izborom dimenzije, korpom.
- Slanje porudžbine — server izračunava cenu iz baze i evidentira porudžbinu.
- Admin prijava lozinkom; nabavne/prodajne cene, izračunavanje marže `(prodajna-nabavna)/prodajna × 100`.
- Dostupnost: *po porudžbini*, *na stanju*, *nedostupno*; stanje komada, vidljivost.
- Pregled pristiglih porudžbina, promene statusa, izvoz kompletnog kataloga u CSV.
- Uvoz CSV/JSON kataloga (spajanje po SKU), **bez brisanja ranije unetih cena**; odvojen masovni uvoz cena iz Excela/CSV.
- Podešavanje naziva radnje i teksta o dostavi.

## Katalog — šta je već preuzeto

Početna baza sadrži **16 proverenih modela i 75 šifara/dimenzija** sa Tarkettovih stranica Toscana, Creative i Practica. Nisu izmišljene cene niti dostupnost. Tri modela imaju proverene Tarkett fotografije, a ostali privremene ilustracije koje NISU fotografije proizvoda. Ako dodate `image_url` u CSV ili u administraciji, prikazuje se fotografija.

**Kompletan Tarkett katalog još nije uvezen.** Na zvaničnoj stranici kategorije Tepisi trenutno je navedeno 37 kolekcija i 241 proizvod, ali to nije isto što i broj varijanti sa šiframa. Uvoz svih varijanti zahteva proveru svake stranice i skripte na računaru sa internetom.

### Uvoz celog kataloga — pripremljen alat

Potreban je internet i biblioteke:

```bash
py -3 -m pip install requests beautifulsoup4
py -3 uvoz_tarkett.py --output tarkett_tepisi_za_uvoz.csv
```

Skripta traži kolekcije iz **isključivo** kategorije Tepisi na `https://www.tarkett.rs/sr_RS/kategorija-rs_C01017-tepisi`, prati linkove kolekcija, pokušava da izvuče naziv modela, šifru i dimenziju i pravi CSV. Za pokušaj pronalaženja fotografija svakog modela dodajte `--images` (sporije):

```bash
py -3 uvoz_tarkett.py --images
```

Važno: ovo je *best-effort* alat. Tarkettov sajt može učitavati katalog JavaScript-om ili menjati HTML, pa se kompletan uvoz **ne može garantovati bez testa**. Pre uvoza proverite redove CSV-a, naročito šifre, dimenzije, model i odgovarajuću fotografiju. Ako je uvoz nepotpun, potreban je prilagođeni importer ili službeni feed/katalog dobavljača.

U administraciji otvorite **Uvoz kataloga → Izaberi CSV → Uvezi proizvode**. Postojeći artikli sa istom šifrom biće ažurirani, a unete nabavne/prodajne cene i zalihe sačuvane. Format CSV:

```csv
collection;model;sku;size;image_url;source_url;description
Toscana;Toscana 01 MMM;331974004;80 × 150 cm;;https://www.tarkett.rs/sr_RS/kolekcija-C001510-toscana/toscana-01-mmm;Mek tepih
```

**Cene iz Excela:** u administraciji na kartici *Pregled* kliknite „Preuzmi katalog CSV“, otvorite ga u Excelu, popunite kolone `cost` i `price` (celobrojni dinari; prazne ćelije ostaju nepromenjene), sačuvajte kao CSV (UTF-8), a zatim u *Uvoz kataloga → Unesite cene iz Excela* učitajte fajl. Za bezbednost su uvoz novih artikala i uvoz cena odvojene operacije.

## Važno pre javnog puštanja u rad

Ovo je **lokalna radna verzija/MVP**, **nije postavljena na internet** i još nije spremna za obradu stvarnih porudžbina na javnom serveru. Pre javne prodaje potrebno je:

- Hosting, domen, HTTPS i produkciona baza sa rezervnim kopijama i nadzorom.
- Dodatno učvršćivanje prijave (ograničenje pokušaja prijave, zaštita sesije i CSRF, politike lozinki), sigurnosni testovi i testovi opterećenja.
- Podaci o prodavcu, kontakt, politika privatnosti, uslovi kupovine, odustanak, reklamacije, dostava i obračun troškova; usklađivanje sa propisima o trgovini i zaštiti podataka.
- Dobavljački katalog sa proverenim modelima, dimenzijama i pravima na komercijalno korišćenje fotografija.
- Definisati rok dostave, trošak dostave, fiskalizaciju i način plaćanja. **Nema ugrađenog kartičnog plaćanja.**
- Obaveštenja o porudžbinama putem email-a/SMS-a — sada se narudžbine vide samo u administratorskom panelu.

Ne otvarajte lokalni port 8765 ka internetu bez prethodne dorade zaštite.

## Napomene

- Ako izgubite lozinku, **isključite program**, napravite backup `data/admin_credentials.json`, uklonite tu datoteku i ponovo pokrenite program da kreira novu lozinku. Ovo je dozvoljeno zato što imate lokalni pristup celom projektu.
- Server sluša samo `127.0.0.1`; sa drugog uređaja se ne može otvoriti dok se ne preuredi mrežna konfiguracija.
- Ilustracije služe kao privremeni prikazi i ne predstavljaju stvarne fotografije proizvoda.
