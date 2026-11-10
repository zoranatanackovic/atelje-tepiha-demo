const $ = (s,root=document) => root.querySelector(s);
const $$ = (s,root=document) => [...root.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=n=>new Intl.NumberFormat('sr-RS',{maximumFractionDigits:0}).format(Number(n||0))+' RSD';
const safeUrl=u=>/^https?:\/\//i.test(u||'')?u:'';
const palette=[['#aeb6a9','#d8cdc0'],['#9c8175','#d9bdac'],['#97a9a6','#d8ded6'],['#8c796a','#e0d1bd'],['#b5a29a','#ece0d6'],['#aeb48e','#e0ddc7'],['#d5c1ad','#977f6a'],['#939caa','#d9d7d2'],['#b6b6aa','#e6dbcb']];
const CURRENCY='RSD';
let state={products:[],shop:{shop_name:'Atelje tepiha'},cart:[],chosenProduct:null,chosenSku:null,adminProducts:[],orders:[],activeTab:'overview',adminSelected:null,editorDraft:{},authorized:false};
try {state.cart=JSON.parse(localStorage.getItem('tshop_cart')||'[]');if(!Array.isArray(state.cart))state.cart=[];}catch{state.cart=[];}
const persistCart=()=>localStorage.setItem('tshop_cart',JSON.stringify(state.cart));
let toastTimer;
function toast(text){const el=$('#toast');el.textContent=text;el.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),3800)}
async function api(url,{method='GET',body}={}){
  const r=await fetch(url,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,credentials:'same-origin'});
  let d;try{d=await r.json()}catch{throw Error('Server nije dostupan. Pokrenite python app.py.')}
  if(!r.ok)throw Error(d.error||'Zahtev nije uspeo.');return d;
}
function backgroundArt(p,cl=''){const num=Math.max(0,state.products.findIndex(x=>x.id===p.id));const [a,b]=palette[(num<0?Number(p.id):num)%palette.length];const image=safeUrl(p.image_url);return image?`<img loading="lazy" src="${esc(image)}" alt="${esc(p.model)}" onerror="this.hidden=true;this.nextElementSibling.hidden=false"/><div hidden class="rug-visual variant-${num%4}" style="--rug1:${a};--rug2:${b}"></div>`:`<div class="rug-visual variant-${num%4}" style="--rug1:${a};--rug2:${b}"></div>`}
function lookup(sku){for(const p of state.products){const v=p.variants.find(v=>v.sku===sku);if(v)return {p,v}}return null}
function getPrice(p){const a=p.variants.filter(v=>v.price>0);return a.length?Math.min(...a.map(v=>v.price)):0}
function getFilterProducts(){const q=$('#search').value.trim().toLocaleLowerCase('sr');const collection=$('#filterCollection').value,size=$('#filterSize').value;const sort=$('#sort').value;
  let p=state.products.filter(x=>(!collection||x.collection===collection)&&(!size||x.variants.some(v=>v.size===size))&&(!q||(`${x.collection} ${x.model} ${x.variants.map(v=>v.sku).join(' ')}`).toLocaleLowerCase('sr').includes(q)));
  if(sort==='cheap')p.sort((a,b)=>(getPrice(a)||Infinity)-(getPrice(b)||Infinity));else if(sort==='expensive')p.sort((a,b)=>getPrice(b)-getPrice(a));else p.sort((a,b)=>a.collection.localeCompare(b.collection,'sr')||a.model.localeCompare(b.model,'sr'));return p
}
function populateFilters(){const col=$('#filterCollection'),size=$('#filterSize');let oldcol=col.value,oldsize=size.value;
  col.innerHTML='<option value="">Sve kolekcije</option>'+[...new Set(state.products.map(p=>p.collection))].sort().map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');
  size.innerHTML='<option value="">Sve dimenzije</option>'+[...new Set(state.products.flatMap(p=>p.variants.map(v=>v.size)))].sort((a,b)=>a.localeCompare(b,'sr',{numeric:true})).map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');
  col.value=oldcol;size.value=oldsize
}
function renderCatalog(){const ps=getFilterProducts();$('#shownCount').textContent=ps.length+' modela';$('#heroModels').textContent=state.products.length;
  const area=$('#grid');area.innerHTML=ps.map(p=>{const price=getPrice(p);return `<article class="product-card" tabindex="0" role="button" aria-label="Detalji: ${esc(p.model)}" data-product="${p.id}">
    <div class="product-image">${backgroundArt(p)}<div class="image-chip">${esc(p.collection)}</div></div>
    <div class="card-info"><div class="card-collection">SINTELON / ${esc(p.collection)}</div><h3>${esc(p.model)}</h3>
    <div class="card-extra"><span>${p.variants.length} dimenzija</span><div>${price?'<em>od</em> <strong>'+money(price)+'</strong>':'<em>Cena u pripremi</em>'}</div><span class="card-arrow">↗</span></div></div></article>`}).join('');$('#empty').hidden=ps.length>0;
  $$('[data-product]',area).forEach(card=>{const open=()=>showProduct(Number(card.dataset.product));card.addEventListener('click',open);card.addEventListener('keydown',e=>{if(e.key==='Enter')open()})})
}
function showProduct(id){const p=state.products.find(p=>p.id===id);if(!p)return;state.chosenProduct=id;state.chosenSku=p.variants.find(v=>v.price>0)?.sku||p.variants[0]?.sku;
  $('#detailTitle').textContent=p.model;renderProduct();openPanel('productDrawer')}
function renderProduct(){const p=state.products.find(p=>p.id===state.chosenProduct);if(!p)return;let v=p.variants.find(v=>v.sku===state.chosenSku)||p.variants[0];
 $('#detailBody').innerHTML=`<div class="detail-photo">${backgroundArt(p)}</div><div class="detail-collection">${esc(p.collection.toUpperCase())} / SINTELON</div>
 <p class="detail-desc">${esc(p.description||'Tarkett / Sintelon tepih. Izaberite odgovarajuću dimenziju.')}</p><div class="detail-label">Izaberite dimenziju</div>
 <div class="size-select">${p.variants.map(i=>`<button class="size-option ${i.sku===v?.sku?'chosen':''}" data-sku="${esc(i.sku)}"><span>${esc(i.size)}</span><small>${i.price?money(i.price):'Cena u pripremi'}</small></button>`).join('')}</div>
 <div class="detail-buy"><div class="price"><span>Cena odabrane dimenzije</span><strong>${v?.price?money(v.price):'Na upit'}</strong></div><button id="addToCart" class="primary-btn full" ${!v?.price?'disabled':''}>Dodaj u korpu ${v?.price?'↗':''}</button></div>
 ${p.source_url?`<a class="source-link" target="_blank" rel="noopener noreferrer" href="${esc(safeUrl(p.source_url))}">Pogledaj model u originalnom katalogu ↗</a>`:''}
 <p class="small-note" style="margin-top:16px">Dok nisu dodate fotografije, prikazana je stilizovana ilustracija tepiha.</p>`;
 $$('[data-sku]',$('#detailBody')).forEach(b=>b.addEventListener('click',()=>{state.chosenSku=b.dataset.sku;renderProduct()}));$('#addToCart').onclick=()=>{addToCart(state.chosenSku);closePanel('productDrawer');openPanel('cartDrawer')}
}
function addToCart(sku){let x=lookup(sku);if(!x||!x.v.price)return;const existing=state.cart.find(it=>it.sku===sku);if(existing)existing.quantity=Math.min(100,existing.quantity+1);else state.cart.push({sku,quantity:1});persistCart();renderCart();toast('Tepih je dodat u korpu.')}
function cartTotal(){return state.cart.reduce((sum,it)=>sum+(lookup(it.sku)?.v.price||0)*it.quantity,0)}
function renderCart(){state.cart=state.cart.filter(it=>lookup(it.sku)?.v.price>0);$('#cartCount').textContent=state.cart.reduce((s,x)=>s+x.quantity,0);
 $('#cartBody').innerHTML=!state.cart.length?'<div class="cart-empty"><span>▧</span><h3>Vaša korpa je prazna</h3><p>Otkrijte tepih koji se uklapa u vaš dom.</p></div>':state.cart.map(it=>{const x=lookup(it.sku);if(!x)return '';return `<div class="cart-item"><div class="mini-rug">▧</div><div><strong>${esc(x.p.model)}</strong><div class="meta">${esc(x.v.size)} · ${esc(x.p.collection)}</div><div class="qty"><button data-change="-1" data-key="${esc(it.sku)}">−</button><span>${it.quantity}</span><button data-change="1" data-key="${esc(it.sku)}">+</button></div><button data-remove="${esc(it.sku)}">Ukloni</button></div><div class="line-price">${money(x.v.price*it.quantity)}</div></div>`}).join('');
 $('#cartFooter').innerHTML=state.cart.length?`<div class="cart-total"><span>Ukupno (bez dostave)</span><strong>${money(cartTotal())}</strong></div><button id="goCheckout" class="primary-btn full">Nastavi na poručivanje →</button>`:'<button class="outline-btn full" id="backToShop">Pogledaj tepihe</button>';
 $$('[data-change]').forEach(btn=>btn.onclick=()=>{const it=state.cart.find(x=>x.sku===btn.dataset.key);if(!it)return;it.quantity+=Number(btn.dataset.change);if(it.quantity<=0)state.cart=state.cart.filter(x=>x!==it);it.quantity=Math.min(100,it.quantity);persistCart();renderCart()});
 $$('[data-remove]').forEach(btn=>btn.onclick=()=>{state.cart=state.cart.filter(x=>x.sku!==btn.dataset.remove);persistCart();renderCart()});
 if($('#goCheckout'))$('#goCheckout').onclick=()=>{closePanel('cartDrawer');$('#checkoutTotal').innerHTML=`<span>Ukupno bez dostave</span><strong>${money(cartTotal())}</strong>`;openPanel('checkoutModal')};
 if($('#backToShop'))$('#backToShop').onclick=()=>{closePanel('cartDrawer');document.getElementById('catalog').scrollIntoView()};
}
function openPanel(id){$('#shade').classList.add('open');$('#'+id).classList.add('open');document.body.style.overflow='hidden'}
function closePanel(id){$('#'+id).classList.remove('open');if(!$('.drawer.open')&&!$('#checkoutModal').classList.contains('open')){$('#shade').classList.remove('open');document.body.style.overflow=''}}
function closeAll(){['cartDrawer','productDrawer','checkoutModal'].forEach(closePanel)}
async function refreshCatalog(){const d=await api('/api/catalog');state.products=d.products;state.shop=d.shop;state.demo=!!d.demo;$('#logoShop').textContent=(d.shop.shop_name||'Atelje tepiha').toUpperCase();$('#footerShop').textContent=(d.shop.shop_name||'Atelje tepiha').toUpperCase();$('#shippingNote').textContent=d.shop.shipping_note||'';document.title=d.shop.shop_name+' — Sintelon / Tarkett tepisi';populateFilters();renderCatalog();renderCart()}

// ADMIN
const adminPanels=['overview','prices','orders','import','settings'];
async function openAdmin(){$('#adminLayer').hidden=false;document.body.style.overflow='hidden';try{await refreshAdmin();}catch{$('#adminLogin').hidden=false;$('#adminApp').hidden=true;$('#adminLogout').hidden=true}}
function closeAdmin(){$('#adminLayer').hidden=true;document.body.style.overflow=''}
async function refreshAdmin(){const d=await api('/api/admin/catalog');state.authorized=true;state.adminProducts=d.products;state.shop=d.shop;$('#adminLogin').hidden=true;$('#adminApp').hidden=false;$('#adminLogout').hidden=false;renderAdmin();}
function renderAdmin(){showTab(state.activeTab);}
function showTab(tab){state.activeTab=tab;$$('[data-tab]').forEach(el=>el.classList.toggle('active',el.dataset.tab===tab));$$('[data-panel]').forEach(el=>el.hidden=el.dataset.panel!==tab);
  if(tab==='overview')renderOverview();if(tab==='prices')renderPrices();if(tab==='orders')loadOrders();if(tab==='settings'){const f=$('#settingsForm');f.elements.shop_name.value=state.shop.shop_name||'';f.elements.shipping_note.value=state.shop.shipping_note||'';}}
function renderOverview(){const p=state.adminProducts,variants=p.flatMap(x=>x.variants);const stats=[['Kolekcija',new Set(p.map(x=>x.collection)).size],['Modela',p.length],['Dimenzija / SKU',variants.length],['Sa cenom',variants.filter(x=>x.price>0 && x.availability!=='unavailable' && x.enabled).length]];
 $('#adminStats').innerHTML=stats.map(([label,n])=>`<div class="stat-box"><small>${label}</small><strong>${n}</strong><small>${label==='Sa cenom'?'aktivnih varijanti':'u katalogu'}</small></div>`).join('')}
function renderPrices(){const select=$('#adminProductSelect');const old=state.adminSelected;
 select.innerHTML=state.adminProducts.map(p=>`<option value="${p.id}">${esc(p.collection)} — ${esc(p.model)} (${p.variants.length})</option>`).join('');
 let candidate=state.adminProducts.find(p=>p.id===old)||state.adminProducts[0];if(!candidate){$('#priceEditor').innerHTML='<p>Nema proizvoda. Uvezite katalog.</p>';return;}
 state.adminSelected=candidate.id;select.value=candidate.id;renderPriceEditor(candidate)}
function renderPriceEditor(p){state.editorDraft=Object.fromEntries(p.variants.map(v=>[v.sku,{...v}]));$('#priceEditor').innerHTML=`<div class="price-table-wrap"><table class="price-table"><thead><tr><th>Dimenzija</th><th>Šifra / SKU</th><th>Nabavna (RSD)</th><th>Prodajna (RSD)</th><th>Marža</th><th>Dostupnost</th><th>Stanje</th><th>Aktivno</th></tr></thead><tbody>
  ${p.variants.map(v=>`<tr data-editor-row="${esc(v.sku)}"><td>${esc(v.size)}</td><td>${esc(v.sku)}</td><td><input aria-label="Nabavna cena ${esc(v.sku)}" type="number" min="0" data-field="cost" value="${v.cost}"/></td><td><input aria-label="Prodajna cena ${esc(v.sku)}" type="number" min="0" data-field="price" value="${v.price}"/></td><td class="profit" data-margin>—</td><td><select data-field="availability"><option value="order" ${v.availability==='order'?'selected':''}>Po porudžbini</option><option value="stock" ${v.availability==='stock'?'selected':''}>Na stanju</option><option value="unavailable" ${v.availability==='unavailable'?'selected':''}>Nedostupno</option></select></td><td><input type="number" min="0" data-field="stock" value="${v.stock}" style="width:65px"/></td><td><input type="checkbox" aria-label="Aktivno ${esc(v.sku)}" data-field="enabled" ${v.enabled?'checked':''}/></td></tr>`).join('')}
  </tbody></table></div><div class="editor-bottom"><label>URL fotografije modela<input id="editorImage" value="${esc(p.image_url)}" placeholder="https://.../tepih.jpg"/></label><label>Opis modela<textarea id="editorDescription">${esc(p.description)}</textarea></label></div>`;
 $$('[data-editor-row]').forEach(row=>{
  const sku=row.dataset.editorRow;row.querySelectorAll('[data-field]').forEach(el=>el.addEventListener('input',()=>{
    const f=el.dataset.field;state.editorDraft[sku][f]=f==='enabled'?el.checked:f==='availability'?el.value:Number(el.value||0);calcMargin(row)}));
  calcMargin(row);
 });
}
function calcMargin(row){const v=state.editorDraft[row.dataset.editorRow],el=$('[data-margin]',row);let margin=(v.price>0&&v.cost>0)?((v.price-v.cost)/v.price*100):null;el.textContent=margin===null?'—':margin.toFixed(1)+'%';el.classList.toggle('negative',margin!==null&&margin<0)}
async function savePrices(){const p=state.adminProducts.find(p=>p.id===state.adminSelected);if(!p)return;try{await api('/api/admin/save',{method:'POST',body:{variants:Object.values(state.editorDraft),product_id:p.id,image_url:$('#editorImage').value,description:$('#editorDescription').value}});toast('Sve izmene su sačuvane.');await refreshAdmin();await refreshCatalog()}catch(e){toast('Greška: '+e.message)}}
const statusNames={new:'Nova',confirmed:'Potvrđena',shipped:'Poslata',done:'Završena',cancelled:'Otkazana'};
async function loadOrders(){try{const x=await api('/api/admin/orders');state.orders=x.orders;renderOrders()}catch(e){$('#ordersView').textContent=e.message}}
function renderOrders(){$('#ordersView').innerHTML=!state.orders.length?'<div class="admin-note">Još nema pristiglih porudžbina.</div>':state.orders.map(o=>`<article class="orders-card"><div class="order-main"><div><h3>${esc(o.reference)}</h3><p>${esc(o.created_at.replace('T',' '))}</p></div><div class="order-total">${money(o.total)}</div></div><div class="order-customer"><strong>${esc(o.customer_name)}</strong> · ${esc(o.phone)} ${o.email?'· '+esc(o.email):''}<br/>${esc(o.city)}, ${esc(o.address)}${o.note?'<br/>Napomena: '+esc(o.note):''}</div><div class="order-items">${o.items.map(it=>`${esc(it.model)} — ${esc(it.size)}: ${it.quantity} × ${money(it.price)}`).join('<br/>')}</div><div class="order-state">Status: <select data-order="${o.id}">${Object.entries(statusNames).map(([val,label])=>`<option value="${val}" ${o.status===val?'selected':''}>${label}</option>`).join('')}</select></div></article>`).join('');$$('[data-order]').forEach(s=>s.onchange=async()=>{try{await api('/api/admin/order-status',{method:'POST',body:{id:Number(s.dataset.order),status:s.value}});toast('Status porudžbine je sačuvan.')}catch(e){toast('Greška: '+e.message)}})}
function parseCSV(text){text=text.replace(/^\ufeff/,'');const first=text.split(/\r?\n/,1)[0];const sep=first.includes(';')?';':',';let rows=[],row=[],value='',quoted=false;
 for(let i=0;i<text.length;i++){let ch=text[i];if(quoted){if(ch==='"'&&text[i+1]==='"'){value+='"';i++}else if(ch==='"')quoted=false;else value+=ch}else{if(ch==='"')quoted=true;else if(ch===sep){row.push(value);value=''}else if(ch==='\n'){row.push(value.replace(/\r$/,''));rows.push(row);row=[];value=''}else value+=ch}}
 if(value||row.length){row.push(value.replace(/\r$/,''));rows.push(row)}let head=rows.shift().map(s=>s.trim().toLowerCase());return rows.filter(r=>r.some(t=>t.trim())).map(r=>Object.fromEntries(head.map((k,i)=>[k,(r[i]||'').trim()])))
}
async function doImport(){let f=$('#importFile').files[0];if(!f){toast('Prvo odaberite CSV ili JSON fajl.');return;}try{let text=await f.text();let rows=f.name.toLowerCase().endsWith('.json')?JSON.parse(text):parseCSV(text);
 if(!Array.isArray(rows)&&Array.isArray(rows.products)){rows=rows.products.flatMap(p=>p.variants.map(v=>({...p,...v})))}
 if(!Array.isArray(rows))throw Error('Očekuje se niz proizvoda ili CSV tabela.');const result=await api('/api/admin/import',{method:'POST',body:{rows}});$('#importResult').textContent=`Uvezeno: ${result.added} novih SKU; ${result.updated} ažurirano; ${result.skipped} preskočeno.`;
 toast('Uvoz je uspešno obrađen.');await refreshAdmin();await refreshCatalog();showTab('import')
 }catch(e){toast('Greška uvoza: '+e.message)}}
async function doPricesImport(){let f=$('#pricesImportFile').files[0];if(!f){toast('Izaberite CSV sa cenama.');return;}try{const text=await f.text();const rows=f.name.toLowerCase().endsWith('.json')?JSON.parse(text):parseCSV(text);if(!Array.isArray(rows))throw Error('CSV ili JSON niz redova je obavezan.');const result=await api('/api/admin/import-prices',{method:'POST',body:{rows}});$('#priceImportResult').textContent=`Ažurirane cene: ${result.updated} SKU. Preskočeno: ${result.skipped}.`;toast('Cene su uspešno ažurirane.');await refreshAdmin();await refreshCatalog();showTab('import')}catch(e){toast('Greška: '+e.message)}}
async function saveSettings(e){e.preventDefault();const body={shop_name:e.target.elements.shop_name.value,shipping_note:e.target.elements.shipping_note.value};try{await api('/api/admin/settings',{method:'POST',body});toast('Podešavanja su sačuvana.');await refreshAdmin();await refreshCatalog()}catch(err){toast(err.message)}}
async function loginAdmin(e){e.preventDefault();try{await api('/api/login',{method:'POST',body:{password:e.target.elements.password.value}});e.target.reset();await refreshAdmin();toast('Uspešna prijava.')}catch(err){toast(err.message)}}
async function logoutAdmin(){try{await api('/api/logout',{method:'POST'});}catch{}state.authorized=false;$('#adminLogin').hidden=false;$('#adminApp').hidden=true;$('#adminLogout').hidden=true;toast('Odjavljeni ste.')}

// Bind UI events
['search','filterCollection','filterSize','sort'].forEach(id=>$('#'+id).addEventListener(id==='search'?'input':'change',renderCatalog));
$('#clearFilters').onclick=()=>{$('#search').value='';$('#filterCollection').value='';$('#filterSize').value='';$('#sort').value='name';renderCatalog()};
$('#cartTrigger').onclick=()=>{renderCart();openPanel('cartDrawer')};$('#adminTrigger').onclick=openAdmin;$('#closeAdmin').onclick=closeAdmin;$('#adminLogout').onclick=logoutAdmin;$('#loginForm').onsubmit=loginAdmin;
$('#shade').onclick=closeAll;$$('[data-close]').forEach(b=>b.onclick=()=>closePanel(b.dataset.close));document.addEventListener('keydown',e=>{if(e.key==='Escape')closeAll()});
$$('[data-tab]').forEach(b=>b.onclick=()=>showTab(b.dataset.tab));$('#adminProductSelect').onchange=e=>{state.adminSelected=Number(e.target.value);const p=state.adminProducts.find(p=>p.id===state.adminSelected);if(p)renderPriceEditor(p)};
$('#savePrices').onclick=savePrices;$('#reloadOrders').onclick=loadOrders;$('#overviewExport').onclick=()=>location.href='/api/admin/export.csv';$('#doImport').onclick=doImport;$('#doPricesImport').onclick=doPricesImport;$('#settingsForm').onsubmit=saveSettings;
$('#checkoutForm').onsubmit=async e=>{e.preventDefault();const form=e.target;let body=Object.fromEntries(new FormData(form).entries());body.items=state.cart.map(it=>({...it}));if(!body.items.length)return toast('Korpa je prazna.');const btn=$('#checkoutSubmit');btn.disabled=true;btn.textContent='Slanje...';try{const r=await api('/api/orders',{method:'POST',body});state.cart=[];persistCart();form.reset();closePanel('checkoutModal');await refreshCatalog();toast('Porudžbina '+r.reference+' je primljena. Ukupno: '+money(r.total)+'.');}catch(err){toast('Porudžbina nije poslata: '+err.message)}finally{btn.disabled=false;btn.textContent='Pošalji porudžbinu →'}};
refreshCatalog().then(()=>{if(state.demo){
 const note=document.createElement('div');note.setAttribute('role','status');note.style.cssText='position:sticky;top:0;z-index:1000;background:#fff3d1;color:#3b2a14;text-align:center;padding:11px 15px;font:600 14px system-ui';
 note.textContent='DEMO PRODAVNICA — pregled kataloga. Administracija i naručivanje još nisu aktivirani.';document.body.prepend(note);
 $('#adminTrigger').hidden=true;$('#cartTrigger').hidden=true;$('#checkoutSubmit').disabled=true;
 }}).catch(e=>{console.error(e);$('#grid').innerHTML='<div class="empty-state"><h3>Server nije pokrenut</h3><p>Otvorite projekat pomoću komande <code>python app.py</code> i zatim posetite http://localhost:8765</p></div>';toast('Nema veze sa serverom.')});
