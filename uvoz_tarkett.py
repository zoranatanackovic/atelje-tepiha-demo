#!/usr/bin/env python3
"""Best-effort Tarkett/Sintelon carpets catalog extractor. Optional deps: pip install requests beautifulsoup4

Scrapes only the carpet CATEGORY's collection links. Catalog page structure can change.
Generates CSV for manual review; does NOT change the shop or any prices.
"""
import argparse
import csv
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print('Potrebne biblioteke: pip install requests beautifulsoup4')
    sys.exit(2)

ROOT='https://www.tarkett.rs'
CATEGORY=ROOT+'/sr_RS/kategorija-rs_C01017-tepisi'
KNOWN=[
  ROOT+'/sr_RS/kolekcija-C001510-toscana',
  ROOT+'/sr_RS/kolekcija-C001368-creative',
  ROOT+'/sr_RS/kolekcija-C001159-practica',
  ROOT+'/sr_RS/kolekcija-C002938-bella',
  ROOT+'/sr_RS/kolekcija-C003108-deco',
  ROOT+'/sr_RS/kolekcija-C001156-solid',
]
AGENT='Mozilla/5.0 (compatible; CarpetCatalogImport/0.1; personal catalog management)'
SKURE=re.compile(r'\bRef\.?\s*[:#]?\s*(\d{6,14})\b',re.I)
SIZERE=re.compile(r'(?:Tepih\s*|Rug\s*|Staza\s*|Tepih staza\s*)?\b(\d+(?:[,.]\d+)?\s*[x×]\s*\d+(?:[,.]\d+)?\s*(?:m|cm)?)\b',re.I)
TYPES=('tepih','rug','staza','carpet')

def get(session,url,timeout=20):
    try:
        response=session.get(url,timeout=timeout)
        response.raise_for_status()
        return BeautifulSoup(response.text,'html.parser')
    except requests.RequestException as e:
        print('   Neuspešan pristup:',url, '(',str(e)[:130],')')
        return None

def url_ok(url):return url.startswith(ROOT+'/sr_RS/kolekcija-C')

def get_collections(session, limit=37):
    urls=set(KNOWN)
    for page in range(6):
        target=CATEGORY+(f'?page={page}' if page else '')
        soup=get(session,target)
        if soup is None: continue
        for a in soup.select('a[href]'):
            h=urljoin(ROOT,a['href']).split('#')[0].split('?')[0].rstrip('/')
            if url_ok(h):
                # Collection detail, not individual design pages.
                pieces=urlparse(h).path.strip('/').split('/')
                if len(pieces)==2: urls.add(h)
        print(f'  Stranica {page+1}: pronađeno {len(urls)} linkova kolekcija ukupno')
        time.sleep(.4)
        if len(urls)>=limit:break
    return sorted(urls)

def collection_name(soup,link):
    for h in soup.select('h1'):
        val=h.get_text(' ',strip=True)
        if val and val.lower() not in ('tepisi','tepis', 'carpets'):return val.strip()
    slug=link.rsplit('-',1)[-1]
    return slug.title()

def size_cm(raw):
    raw=raw.lower().replace('×','x').replace(' ','').replace(',','.')
    m=re.match(r'(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)(cm|m)?',raw)
    if not m:return ''
    a,b=float(m[1]),float(m[2]);unit=m[3]
    if unit=='m' or ((a<20 and b<40) and unit is None):a*=100;b*=100
    return f'{a:g} × {b:g} cm'

def scan_products(soup, collection,collection_url):
    # Robust-ish text extraction: Tarkett collection listings show
    # design name, "Ref. XXXXXXXXX", and "Tepih 1,6 x 2,3 m" nearby.
    txt=[re.sub(r'\s+',' ',str(s)).strip() for s in soup.stripped_strings]
    results={}
    irrelevant={'odaberi proizvod','pogledaj sve dezene','format','dezen','specifikacije','image','opis','no products found'}
    for i,line in enumerate(txt):
        match=SKURE.search(line)
        if not match:continue
        sku=match[1]
        # Search for a nearby format, skipping duplicate reference and UI tokens.
        fmt=''
        for j in range(i+1,min(i+18,len(txt))):
            candidate=txt[j]
            if SKURE.search(candidate) and j>i+2:break
            if any(k in candidate.lower() for k in TYPES):
                m=SIZERE.search(candidate)
                if m:
                    fmt=size_cm(m[1]);break
        if not fmt:continue
        model=''
        for j in range(i-1,max(-1,i-7),-1):
            candidate=txt[j]
            if not candidate or candidate.lower() in irrelevant or candidate.lower()=='ref.':continue
            if SKURE.search(candidate):break
            if re.match(r'^(tepih|rug|staza)\b',candidate,re.I):continue
            if len(candidate)>95 or re.search(r'\d+\s*[x×]\s*\d+',candidate):continue
            if candidate.lower() in ('ref.','dezen','format'):continue
            model=candidate
            break
        if not model:continue
        model=re.sub(r'^'+re.escape(collection)+r'\s*[-:]\s*','',model,flags=re.I)
        if len(model)<3:continue
        results[sku]={
          'collection':collection,
          'model':model,
          'sku':sku,
          'size':fmt,
          'description':'',
          'image_url':'',
          'source_url':collection_url,
        }
    return list(results.values())

def model_links(soup, collection_url):
    result={}
    for a in soup.select('a[href]'):
        link=urljoin(ROOT,a['href']).split('#')[0].split('?')[0]
        if link.startswith(collection_url+'/'):
            anchor=a.get_text(' ',strip=True).lower()
            if anchor:result[anchor]=link
    return result

def main():
    parser=argparse.ArgumentParser(description='Uvezi kolekcije iz Tarkett/Sintelon kategorije Tepisi')
    parser.add_argument('--output',default='tarkett_tepisi_za_uvoz.csv')
    parser.add_argument('--limit',type=int,default=45,help='Najviše kolekcija')
    parser.add_argument('--images',action='store_true',help='Pokušaj preuzimanje pojedinačnih URL-ova fotografija sa stranica dezena')
    args=parser.parse_args()
    s=requests.Session();s.headers.update({'User-Agent':AGENT,'Accept-Language':'sr-RS,sr;q=.9,en;q=.5'})
    collections=get_collections(s,args.limit)
    print('Kolekcija za proveru:',len(collections),'(linkove treba uporediti sa izvornom kategorijom)')
    all_rows={};possible=0
    for ix,url in enumerate(collections[:args.limit],1):
        soup=get(s,url)
        if not soup:continue
        name=collection_name(soup,url)
        page_text=soup.get_text(' ',strip=True).lower()
        if not any(x in page_text for x in ('tepisi','tepih','staza','carpet','rug')):
            print(f'  [{ix}] {name}: bez potvrde da je kategorija tepisi, preskočeno');continue
        rows=scan_products(soup,name,url)
        print(f'  [{ix}/{len(collections)}] {name}: {len(rows)} šifara')
        if args.images and rows:
            links=model_links(soup,url)
            for model in set(r['model'] for r in rows):
                page=links.get(model.lower())
                if not page:continue
                sp=get(s,page)
                if not sp:continue
                og=sp.find('meta',attrs={'property':'og:image'})
                if og and og.get('content'):
                    for r in rows:
                        if r['model']==model:
                            r['image_url']=urljoin(ROOT,og['content']);r['source_url']=page
                time.sleep(.3)
        for r in rows:all_rows[r['sku']]=r
        time.sleep(.55)
    result=Path(args.output)
    fields=['collection','model','sku','size','description','image_url','source_url']
    with result.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,delimiter=';')
        writer.writeheader();writer.writerows(sorted(all_rows.values(),key=lambda r:(r['collection'],r['model'],r['size'])))
    print(f'\nSnimljeno: {len(all_rows)} jedinstvenih SKU u {result.resolve()}')
    if len(all_rows)<100:print('UPOZORENJE: Katalog je verovatno NEPOTPUN (sajt može učitavati proizvode JavaScript-om).')
    print('Proverite CSV pre uvoza. Skripta nikada ne menja vaše cene u prodavnici.')

if __name__=='__main__':main()
