#!/usr/bin/env python3
"""Local-first carpet shop MVP: SQLite, session auth, orders, CSV/JSON catalog import.
No third-party dependencies. For demonstration/staging use. Run: python app.py
"""
import csv
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import hashlib
from datetime import datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE = Path(__file__).resolve().parent
DBFILE = BASE/'data'/'shop.sqlite3'
STATIC = BASE/'static'
PORT = int(os.environ.get('PORT') or os.environ.get('SHOP_PORT','8765'))
DEMO_MODE = os.environ.get('SHOP_DEMO_MODE', '0') == '1'
ADMIN_FILE = BASE/'data'/'admin_credentials.json'
SESSIONS = {}
LOCK = threading.RLock()
SIZE_RE = re.compile(r'^[\w\s×x.,/()-]{2,36}$',re.UNICODE)

def conn():
    c = sqlite3.connect(DBFILE, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=30000')
    return c

def initialize():
    DBFILE.parent.mkdir(parents=True,exist_ok=True)
    with conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection TEXT NOT NULL, model TEXT NOT NULL, description TEXT DEFAULT '',
            image_url TEXT DEFAULT '', source_url TEXT DEFAULT '',
            UNIQUE(collection, model)
        );
        CREATE TABLE IF NOT EXISTS variants (
            sku TEXT PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            size TEXT NOT NULL,
            cost INTEGER DEFAULT 0, price INTEGER DEFAULT 0,
            stock INTEGER DEFAULT 0, availability TEXT DEFAULT 'order',
            enabled INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL,
            customer_name TEXT NOT NULL, phone TEXT NOT NULL,
            email TEXT DEFAULT '', city TEXT NOT NULL, address TEXT NOT NULL,
            note TEXT DEFAULT '', total INTEGER NOT NULL,
            status TEXT DEFAULT 'new', items TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('shop_name','Atelje tepiha')")
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('shipping_note','Dostava i rok isporuke biće potvrđeni nakon poručivanja.')")
        if c.execute('SELECT COUNT(*) AS n FROM products').fetchone()['n']==0:
            seed(c)
    if not DEMO_MODE and not ADMIN_FILE.exists():
        passwd = os.environ.get('SHOP_ADMIN_PASSWORD') or secrets.token_urlsafe(12)
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac('sha256', passwd.encode(), bytes.fromhex(salt),200000).hex()
        ADMIN_FILE.write_text(json.dumps({'salt':salt,'hash':digest},indent=2),encoding='utf-8')
        try: os.chmod(ADMIN_FILE,0o600)
        except OSError: pass
        print('\n'+'='*60+'\n  ADMIN LOZINKA (sacuvaj je): '+passwd+'\n'+'='*60+'\n',flush=True)
    elif not DEMO_MODE:
        print('Admin lozinka je vec kreirana u prethodnom pokretanju.',flush=True)

def seed(c):
    """Verified SKUs from Tarkett collection pages, with NO invented prices."""
    common='https://www.tarkett.rs/sr_RS/kolekcija-C001510-toscana'
    def add(coll,name,description,source,rows):
        cur=c.execute('INSERT INTO products(collection,model,description,source_url) VALUES(?,?,?,?)', (coll,name,description,source))
        for sku,size in rows:
            c.execute('INSERT INTO variants(sku,product_id,size) VALUES(?,?,?)',(sku,cur.lastrowid,size))
    sizes=['200 × 290 cm','160 × 230 cm','140 × 200 cm','120 × 170 cm','80 × 150 cm']
    add('Toscana','Toscana 01 MMM','Mekan, gust polipropilenski flor, visine 17 mm.',common+'/toscana-01-mmm',list(zip(['331970004','331971004','331972004','331973004','331974004'],sizes)))
    add('Toscana','Toscana 01 AAA','Baršunasti tepih u nežnim bojama, 100% PP.',common,list(zip(['331970001','331971001','331972001','331973001','331974001'],sizes))+[('332796007','240 × 340 cm'),('332554005','300 × 400 cm')])
    add('Toscana','Toscana 01 BBB','Baršunasta Toscana kolekcija.',common,list(zip(['331970068','331971071','331972076','331973073','331974068'],sizes)))
    add('Toscana','Toscana 01 OOO','Gust i prijatan flor.',common+'/toscana-01-ooo',list(zip(['331970005','331971005','331972005','331973005','331974005'],sizes))+[('332796000','240 × 340 cm'),('332554003','300 × 400 cm')])
    add('Toscana','Toscana 15 WOW','Savremeni izgled, mek i baršunast flor.',common,list(zip(['331970046','331971043','331972043','331973049','331974046'],sizes)))
    add('Toscana','Toscana 16 SMS','Toscana, 100% polipropilen.',common,list(zip(['331970047','331971044','331972044','331973050'],sizes[:4])))
    add('Creative','Creative 49 EWE','Moderni geometrijski tepisi od poliesterskog mikrofibera.', 'https://www.tarkett.rs/sr_RS/kolekcija-C001368-creative', [('331827081','160 × 230 cm'),('331828078','140 × 200 cm'),('331829100','120 × 170 cm'),('332354059','200 × 290 cm'),('332355044','80 × 150 cm')])
    add('Practica','Practica A5 BDB','Tradicionalni dezeni; ekonomična kolekcija.', 'https://www.tarkett.rs/sr_RS/kolekcija-C001159-practica',[('330315074','Staza 80 × 2500 cm'),('330324224','120 × 170 cm')])
    creative_source='https://www.tarkett.rs/sr_RS/kolekcija-C001368-creative'
    add('Creative','Creative 49 GWG','Moderni geometrijski dezen u mekom poliesterskom mikrofiberu.',creative_source, list(zip(['331827066','331828061','331829081','332354027','332355027'],['160 × 230 cm','140 × 200 cm','120 × 170 cm','200 × 290 cm','80 × 150 cm'])))
    add('Creative','Creative 51 SYS','Ultra soft touch poliesterski mikrofiber.',creative_source,[('331827069','160 × 230 cm'),('331829084','120 × 170 cm'),('332355030','80 × 150 cm')])
    add('Creative','Creative 74 GYG','Geometrijski dezen, 100% poliester.',creative_source,list(zip(['331827071','331828069','331829089','332354058','332355035'],['160 × 230 cm','140 × 200 cm','120 × 170 cm','200 × 290 cm','80 × 150 cm'])))
    add('Creative','Creative 74 SWS','Geometrijski dezen, 100% poliester.',creative_source,[('331827082','160 × 230 cm'),('331828079','140 × 200 cm'),('331829101','120 × 170 cm')])
    practica_source='https://www.tarkett.rs/sr_RS/kolekcija-C001159-practica'
    add('Practica','Practica A6 VMB','Tradicionalni dezen, ekonomična kolekcija.',practica_source,[('330315075','Staza 80 × 2500 cm'),('330324225','120 × 170 cm'),('330327047','160 × 230 cm'),('330330390','200 × 300 cm')])
    add('Practica','Practica A7 BCV','Tradicionalni dezen, ekonomična kolekcija.',practica_source,[('330315076','Staza 80 × 2500 cm'),('330324226','120 × 170 cm'),('330327048','160 × 230 cm'),('330330391','200 × 300 cm')])
    add('Practica','Practica A8 VCD','Tradicionalni dezen, ekonomična kolekcija.',practica_source,[('330315077','Staza 80 × 2500 cm'),('330324227','120 × 170 cm'),('330327049','160 × 230 cm'),('330330392','200 × 300 cm')])
    add('Practica','Practica 26 CPC','Tradicionalni dezeni i polipropilenski flor.',practica_source,[('330315028','Staza 80 × 2500 cm'),('330318035','Staza 100 × 2500 cm'),('330319031','Staza 120 × 2500 cm'),('330324176','120 × 170 cm'),('330327003','160 × 230 cm')])
    c.execute('INSERT INTO variants(sku,product_id,size) VALUES(?,?,?)',('330327046',c.execute("SELECT id FROM products WHERE collection='Practica' AND model='Practica A5 BDB'").fetchone()['id'],'160 × 230 cm'))
    c.execute('INSERT INTO variants(sku,product_id,size) VALUES(?,?,?)',('330330389',c.execute("SELECT id FROM products WHERE collection='Practica' AND model='Practica A5 BDB'").fetchone()['id'],'200 × 300 cm'))
    # Verified Tarkett product thumbnail URLs (the other models remain visually unassigned until imported).
    for name,url in [
        ('Toscana 01 MMM','https://www.tarkett.rs/media/img/M/THH_TOSCANA_01MMM.jpg'),
        ('Toscana 01 OOO','https://www.tarkett.rs/media/img/M/THH_TOSCANA_01OOO.jpg'),
        ('Toscana 15 WOW','https://www.tarkett.rs/media/img/M/THH_TOSCANA_15WOW.jpg'),
    ]:
        c.execute('UPDATE products SET image_url=? WHERE model=?',(url,name))

def settings(c):
    return {r['key']:r['value'] for r in c.execute('SELECT key,value FROM settings')}

def products_public(c):
    out={}
    for r in c.execute('''SELECT p.id, p.collection,p.model,p.description,p.image_url,p.source_url,
        v.sku,v.size,v.price,v.stock,v.availability
        FROM products p JOIN variants v ON p.id=v.product_id
        WHERE v.enabled=1 AND v.availability != 'unavailable'
        ORDER BY p.collection,p.model,v.size'''):
        d=dict(r)
        pid=d['id']
        if pid not in out:
            out[pid]={k:d[k] for k in ('id','collection','model','description','image_url','source_url')}
            out[pid]['variants']=[]
        out[pid]['variants'].append({k:d[k] for k in ('sku','size','price','stock','availability')})
    return list(out.values())

def products_admin(c):
    out={}
    for r in c.execute('''SELECT p.*,v.sku,v.size,v.cost,v.price,v.stock,v.availability,v.enabled FROM products p
        LEFT JOIN variants v ON p.id=v.product_id ORDER BY p.collection,p.model,v.size'''):
        d=dict(r);pid=d['id']
        if pid not in out:
            out[pid]={k:d[k] for k in ('id','collection','model','description','image_url','source_url')}
            out[pid]['variants']=[]
        if d['sku']:
            out[pid]['variants'].append({k:d[k] for k in ('sku','size','cost','price','stock','availability','enabled')})
    return list(out.values())

def safe_str(x,maxlen=200):
    return str(x or '').strip()[:maxlen]

def validate_url(s):
    s=safe_str(s,1200)
    return s if not s or urlparse(s).scheme in ('https','http') else ''

def upsert_rows(c,rows):
    added=changed=skipped=0
    for it in rows:
        if not isinstance(it,dict): skipped+=1;continue
        collection=safe_str(it.get('collection') or it.get('kolekcija'),90)
        model=safe_str(it.get('model') or it.get('dezen'),130)
        sku=safe_str(it.get('sku') or it.get('sifra') or it.get('ref'),45)
        size=safe_str(it.get('size') or it.get('dimenzija'),40)
        if not collection or not model or not sku or not size or len(sku)<3:
            skipped+=1;continue
        if any(x in (collection+' '+model).lower() for x in ['laminat','parket','vinil','linoleum','tepsoni']):
            skipped+=1;continue
        image=validate_url(it.get('image_url') or it.get('fotografija'))
        source=validate_url(it.get('source_url') or it.get('izvor'))
        desc=safe_str(it.get('description') or it.get('opis'),1000)
        c.execute('INSERT OR IGNORE INTO products(collection,model,description,image_url,source_url) VALUES(?,?,?,?,?)',(collection,model,desc,image,source))
        product=c.execute('SELECT id FROM products WHERE collection=? AND model=?',(collection,model)).fetchone()
        if image or source or desc:
            c.execute('''UPDATE products SET image_url=CASE WHEN ?!='' THEN ? ELSE image_url END,
                source_url=CASE WHEN ?!='' THEN ? ELSE source_url END,
                description=CASE WHEN ?!='' THEN ? ELSE description END WHERE id=?''',
                (image,image,source,source,desc,desc,product['id']))
        existing=c.execute('SELECT sku FROM variants WHERE sku=?',(sku,)).fetchone()
        if existing:
            c.execute('UPDATE variants SET product_id=?, size=? WHERE sku=?',(product['id'],size,sku));changed+=1
        else:
            c.execute('INSERT INTO variants(sku,product_id,size) VALUES(?,?,?)',(sku,product['id'],size));added+=1
    return {'added':added,'updated':changed,'skipped':skipped}

class Handler(BaseHTTPRequestHandler):
    server_version='TepihShop/0.1'
    def log_message(self,fmt,*args):
        print('%s - %s' %(self.address_string(),fmt%args))
    def send(self,status,obj):
        payload=json.dumps(obj,ensure_ascii=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(payload)
    def body(self):
        n=int(self.headers.get('Content-Length','0'))
        if n>4_000_000:raise ValueError('Prevelik zahtev (maksimalno 4 MB).')
        return json.loads(self.rfile.read(n).decode('utf-8'))
    def cookie(self):
        ck=SimpleCookie()
        try: ck.load(self.headers.get('Cookie',''))
        except Exception:return ''
        return ck.get('shop_session').value if ck.get('shop_session') else ''
    def authed(self):
        ses=SESSIONS.get(self.cookie())
        return bool(ses and ses>time.time())
    def require(self):
        if not self.authed():
            self.send(401,{'error':'Prijavite se kao administrator.'})
            return False
        return True
    def do_GET(self):
        route=urlparse(self.path).path
        try:
            if route=='/api/catalog':
                with conn() as c: data=products_public(c); shop=settings(c)
                return self.send(200,{'products':data,'shop':shop,'demo':DEMO_MODE})
            if route=='/api/admin/catalog':
                if not self.require():return
                with conn() as c:data=products_admin(c);shop=settings(c)
                return self.send(200,{'products':data,'shop':shop,'demo':DEMO_MODE})
            if route=='/api/admin/orders':
                if not self.require():return
                with conn() as c: rows=[dict(r) for r in c.execute('SELECT * FROM orders ORDER BY id DESC')]
                for d in rows:d['items']=json.loads(d['items'])
                return self.send(200,{'orders':rows})
            if route=='/api/admin/export.csv':
                if not self.require():return
                with conn() as c: products=products_admin(c)
                buf=io.StringIO();w=csv.writer(buf,delimiter=';')
                w.writerow(['collection','model','sku','size','cost','price','stock','availability','enabled','image_url','source_url','description'])
                for p in products:
                    for v in p['variants']:
                        w.writerow([p['collection'],p['model'],v['sku'],v['size'],v['cost'],v['price'],v['stock'],v['availability'],v['enabled'],p['image_url'],p['source_url'],p['description']])
                data=('\ufeff'+buf.getvalue()).encode('utf-8')
                self.send_response(200);self.send_header('Content-Type','text/csv; charset=utf-8')
                self.send_header('Content-Disposition','attachment; filename="tepisi_katalog.csv"')
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            if route.startswith('/api/'):return self.send(404,{'error':'Nije pronađeno.'})
            filename=STATIC/('index.html' if route in ['/','/index.html'] else route.lstrip('/'))
            if not filename.resolve().is_relative_to(STATIC.resolve()) or not filename.is_file():
                self.send_error(404);return
            mime='text/html' if filename.suffix=='.html' else 'application/javascript' if filename.suffix=='.js' else 'text/css' if filename.suffix=='.css' else 'application/octet-stream'
            data=filename.read_bytes();self.send_response(200)
            self.send_header('Content-Type',mime+'; charset=utf-8');self.send_header('Content-Length',str(len(data)))
            self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
        except Exception as e:
            print('GET ERROR:',repr(e));self.send(500,{'error':'Greška servera.'})
    def do_POST(self):
        route=urlparse(self.path).path
        try:
            if DEMO_MODE:
                return self.send(403,{'error':'Ovo je javna demonstracija kataloga. Administracija i porudzbine su iskljucene.'})
            data=self.body()
            if route=='/api/login':
                secret=safe_str(data.get('password'),300)
                rec=json.loads(ADMIN_FILE.read_text(encoding='utf-8'))
                dig=hashlib.pbkdf2_hmac('sha256',secret.encode(),bytes.fromhex(rec['salt']),200000).hex()
                if not hmac.compare_digest(dig,rec['hash']):return self.send(401,{'error':'Netačna lozinka.'})
                token=secrets.token_urlsafe(32);SESSIONS[token]=time.time()+12*3600
                payload=json.dumps({'ok':True}).encode();self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Set-Cookie',f'shop_session={token}; HttpOnly; Path=/; SameSite=Lax; Max-Age=43200')
                self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload);return
            if route=='/api/logout':
                SESSIONS.pop(self.cookie(),None)
                payload=b'{"ok":true}';self.send_response(200)
                self.send_header('Set-Cookie','shop_session=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0')
                self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload);return
            if route=='/api/orders':
                name=safe_str(data.get('name'),110);phone=safe_str(data.get('phone'),55)
                city=safe_str(data.get('city'),100);address=safe_str(data.get('address'),190)
                email=safe_str(data.get('email'),160);note=safe_str(data.get('note'),500)
                if any(len(x)<3 for x in [name,phone,city,address]):return self.send(400,{'error':'Popunite ime, telefon, mesto i adresu.'})
                if not isinstance(data.get('items'),list) or not 1<=len(data['items'])<=60:return self.send(400,{'error':'Korpa nije ispravna.'})
                with LOCK,conn() as c:
                    order=[];total=0
                    merged={}
                    for it in data['items']:
                        sku=safe_str(it.get('sku'),45)
                        try:q=int(it.get('quantity'))
                        except Exception:q=0
                        if not 1<=q<=100:raise ValueError('Neispravna količina.')
                        merged[sku]=merged.get(sku,0)+q
                        if merged[sku]>100:raise ValueError('Neispravna ukupna količina.')
                    for sku,q in merged.items():
                        r=c.execute('''SELECT p.model,p.collection,v.* FROM variants v JOIN products p ON p.id=v.product_id
                            WHERE v.sku=? AND v.enabled=1 AND v.price>0''',(sku,)).fetchone()
                        if not r or r['availability']=='unavailable':raise ValueError('Artikal više nije dostupan.')
                        if r['availability']=='stock' and r['stock']<q:raise ValueError('Nema dovoljno komada na stanju.')
                        total+=r['price']*q
                        order.append({'sku':sku,'model':r['model'],'collection':r['collection'],'size':r['size'],'price':r['price'],'quantity':q})
                    ref='TP-'+datetime.now().strftime('%y%m%d')+'-'+secrets.token_hex(3).upper()
                    c.execute('''INSERT INTO orders(reference,created_at,customer_name,phone,email,city,address,note,total,items)
                        VALUES(?,?,?,?,?,?,?,?,?,?)''',(ref,datetime.now().isoformat(timespec='seconds'),name,phone,email,city,address,note,total,json.dumps(order,ensure_ascii=False)))
                    for it in order:
                        c.execute("UPDATE variants SET stock=stock-? WHERE sku=? AND availability='stock'",(it['quantity'],it['sku']))
                return self.send(200,{'ok':True,'reference':ref,'total':total})
            if not self.require():return
            if route=='/api/admin/save':
                updates=data.get('variants',[])
                if not isinstance(updates,list) or len(updates)>3000:raise ValueError('Neispravan skup izmena.')
                with LOCK,conn() as c:
                    for v in updates:
                        sku=safe_str(v.get('sku'),45)
                        if not c.execute('SELECT 1 FROM variants WHERE sku=?',(sku,)).fetchone():continue
                        cost=int(v.get('cost') or 0);price=int(v.get('price') or 0);stock=int(v.get('stock') or 0)
                        avail=v.get('availability','order')
                        if cost<0 or price<0 or stock<0 or avail not in ('stock','order','unavailable'):
                            raise ValueError('Cena, zaliha ili status nisu ispravni.')
                        c.execute('''UPDATE variants SET cost=?,price=?,stock=?,availability=?,enabled=? WHERE sku=?''',
                                  (cost,price,stock,avail,1 if v.get('enabled',True) else 0,sku))
                    pid=data.get('product_id')
                    if pid:
                        image=validate_url(data.get('image_url'));desc=safe_str(data.get('description'),1000)
                        c.execute('UPDATE products SET image_url=?, description=? WHERE id=?',(image,desc,int(pid)))
                return self.send(200,{'ok':True})
            if route=='/api/admin/import':
                rows=data.get('rows',[])
                if not isinstance(rows,list) or len(rows)>20000:raise ValueError('Neispravan uvoz.')
                with LOCK,conn() as c:result=upsert_rows(c,rows)
                return self.send(200,{'ok':True,**result})
            if route=='/api/admin/import-prices':
                rows=data.get('rows',[])
                if not isinstance(rows,list) or len(rows)>20000:raise ValueError('Neispravan uvoz cena.')
                updated=skipped=0
                with LOCK,conn() as c:
                    for r in rows:
                        if not isinstance(r,dict):skipped+=1;continue
                        sku=safe_str(r.get('sku') or r.get('sifra'),45)
                        current=c.execute('SELECT * FROM variants WHERE sku=?',(sku,)).fetchone()
                        if not current:skipped+=1;continue
                        row=dict(current)
                        for field in ['cost','price','stock']:
                            if field in r and str(r[field]).strip()!='':
                                val=int(str(r[field]).strip().replace(' ','').replace('.','').replace(',','.'))
                                if val<0:raise ValueError(f'Negativna vrednost za {sku}: {field}')
                                row[field]=val
                        if r.get('availability') not in (None,''):
                            if r['availability'] not in ('stock','order','unavailable'):
                                raise ValueError('Status mora biti stock, order ili unavailable.')
                            row['availability']=r['availability']
                        if r.get('enabled') not in (None,''):
                            row['enabled']=1 if str(r['enabled']).lower() in ('1','true','da','yes') else 0
                        c.execute('''UPDATE variants SET cost=?,price=?,stock=?,availability=?,enabled=? WHERE sku=?''',
                            (row['cost'],row['price'],row['stock'],row['availability'],row['enabled'],sku))
                        updated+=1
                return self.send(200,{'ok':True,'updated':updated,'skipped':skipped})
            if route=='/api/admin/order-status':
                oid=int(data.get('id'));status=data.get('status')
                if status not in ('new','confirmed','shipped','done','cancelled'):raise ValueError('Nepoznat status.')
                with conn() as c:c.execute('UPDATE orders SET status=? WHERE id=?',(status,oid))
                return self.send(200,{'ok':True})
            if route=='/api/admin/settings':
                n=safe_str(data.get('shop_name'),85);shipping=safe_str(data.get('shipping_note'),250)
                if not n:raise ValueError('Naziv ne sme biti prazan.')
                with conn() as c:
                    c.execute("UPDATE settings SET value=? WHERE key='shop_name'",(n,))
                    c.execute("UPDATE settings SET value=? WHERE key='shipping_note'",(shipping,))
                return self.send(200,{'ok':True})
            return self.send(404,{'error':'Nije pronađeno.'})
        except (ValueError,TypeError,KeyError,sqlite3.IntegrityError) as e:self.send(400,{'error':str(e)[:250]})
        except Exception as e:
            print('POST ERROR:',repr(e));self.send(500,{'error':'Greška servera.'})

if __name__=='__main__':
    initialize()
    host = '0.0.0.0' if os.environ.get('PORT') else '127.0.0.1'
    print(f'\nServing on {host}:{PORT} (demo={DEMO_MODE})\n',flush=True)
    ThreadingHTTPServer((host,PORT),Handler).serve_forever()
