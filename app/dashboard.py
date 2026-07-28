"""
Dashboard v2.4 - botun kok URL'inde ("/") sundugu karar-destek konsolu.

v2.3'e gore yenilikler:
- Tek cumlelik ozet (verdict): motor sagligi + performans, duz Turkce.
- Kumulatif R egrisi (equity curve) - saf SVG, kutuphanesiz.
- Win rate yaninda basabas esigi: ortalama kazanc R'sinden turetilir
  (basabas = 1 / (1 + ortalama kazanc R)); %33 tek basina anlamsizdir.
- LONG / SHORT yon bilancosu - sinyal listesinden istemci tarafinda hesaplanir.
- Giris isabeti (fill orani): dolan / (dolan + NOT_FILLED).
- Sinyal tablosunda durum filtreleri (Tumu/Acik/Sonuclanan/Dolmayan) ve
  acik sinyaller icin yas gostergesi (fill penceresi 6 sa / izleme 48 sa).
- "Nasil okunur?" acilir rehberi - terminoloji ve golge muhasebe uyarisi.

Tasarim dili korunur: koyu operasyon terminali, kv log-line imzasi,
monospace veri, kehribar vurgu. Harici bagimlilik yok; veri botun kendi
JSON endpoint'lerinden cekilir, secilen aralikta kendini yeniler.
"""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>signal-engine // dashboard</title>
<style>
  :root{
    --bg:#0E1420; --panel:#151D2C; --panel2:#111827; --line:#243049;
    --text:#D7E0F0; --muted:#7C8AA5; --accent:#E8B44C;
    --win:#4CC38A; --loss:#E5534B; --pend:#E8B44C; --info:#6CA0F0;
    --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    --sans:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;
  }
  *{box-sizing:border-box;margin:0}
  body{background:var(--bg);color:var(--text);font-family:var(--sans);
       font-size:14px;line-height:1.5;padding:20px 16px 60px}
  .wrap{max-width:1100px;margin:0 auto}
  /* --- kv log-line header (imza) --- */
  .loghead{font-family:var(--mono);font-size:13px;color:var(--muted);
           display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;
           border-bottom:1px solid var(--line);padding-bottom:14px}
  .kv b{color:var(--accent);font-weight:500}
  .kv i{color:var(--text);font-style:normal}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--win);
       display:inline-block;margin-right:4px}
  .dot.err{background:var(--loss)}
  @media (prefers-reduced-motion:no-preference){
    .dot{animation:pulse 2.4s ease-in-out infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}
  }
  .ctrl{margin-left:auto;display:flex;gap:8px;align-items:center}
  select,button{background:var(--panel);color:var(--text);border:1px solid var(--line);
    border-radius:6px;padding:5px 10px;font-family:var(--mono);font-size:12px;cursor:pointer}
  button:hover,select:hover{border-color:var(--accent)}
  :focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  /* --- verdict --- */
  .verdict{margin:18px 0 4px;padding:12px 16px;background:var(--panel);
           border:1px solid var(--line);border-left:3px solid var(--accent);
           border-radius:10px;font-size:14.5px}
  .verdict b{color:var(--accent);font-weight:600}
  /* --- KPI quote-board --- */
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));
        gap:1px;background:var(--line);border:1px solid var(--line);
        border-radius:10px;overflow:hidden;margin:14px 0}
  .kpi{background:var(--panel);padding:13px 15px}
  .kpi .lbl{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
  .kpi .val{font-family:var(--mono);font-size:23px;margin-top:2px}
  .kpi .sub{font-family:var(--mono);font-size:11px;color:var(--muted)}
  .pos{color:var(--win)} .neg{color:var(--loss)} .amb{color:var(--pend)}
  /* --- sections --- */
  h2{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
     margin:24px 0 4px;font-weight:600}
  h2 b{color:var(--accent);font-family:var(--mono);font-weight:500}
  .hint{font-size:11.5px;color:var(--muted);margin:0 0 8px}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
  /* --- equity curve --- */
  .curve{padding:14px 16px 8px}
  .curve svg{width:100%;height:170px;display:block}
  .curve .axis{stroke:var(--line);stroke-width:1}
  .curve .zero{stroke:var(--muted);stroke-width:1;stroke-dasharray:4 4;opacity:.6}
  .curve .path{fill:none;stroke:var(--accent);stroke-width:2}
  .curve .area{fill:var(--accent);opacity:.08}
  .curve .pt:last-of-type{fill:var(--accent)}
  .curve text{font-family:var(--mono);font-size:10px;fill:var(--muted)}
  /* --- direction split --- */
  .split{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  @media (max-width:640px){.split{grid-template-columns:1fr}}
  .side{padding:13px 16px}
  .side .ttl{font-family:var(--mono);font-size:12px;letter-spacing:.06em}
  .side .big{font-family:var(--mono);font-size:21px;margin:3px 0 1px}
  .side .sub{font-family:var(--mono);font-size:11.5px;color:var(--muted)}
  /* --- outcome bar --- */
  .bar{display:flex;height:14px;border-radius:7px;overflow:hidden;
       border:1px solid var(--line);margin:10px 0 6px}
  .bar div{height:100%}
  .legend{font-family:var(--mono);font-size:11.5px;color:var(--muted);
          display:flex;gap:14px;flex-wrap:wrap}
  .legend b{color:var(--text);font-weight:500}
  .sw{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;
      vertical-align:-1px}
  /* --- tables --- */
  table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12.5px}
  th{color:var(--muted);text-align:left;font-weight:500;font-size:11px;
     letter-spacing:.06em;text-transform:uppercase;padding:10px 12px;
     border-bottom:1px solid var(--line);background:var(--panel2)}
  td{padding:8px 12px;border-bottom:1px solid var(--panel2);white-space:nowrap}
  tr:last-child td{border-bottom:0}
  tr.dim td{opacity:.55}
  .tblwrap{overflow-x:auto}
  .pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11px}
  .pill.WIN{background:rgba(76,195,138,.15);color:var(--win)}
  .pill.LOSS{background:rgba(229,83,75,.15);color:var(--loss)}
  .pill.PENDING,.pill.FILLED{background:rgba(232,180,76,.12);color:var(--pend)}
  .pill.NOT_FILLED,.pill.EXPIRED{background:rgba(124,138,165,.15);color:var(--muted)}
  .pill.AMBIGUOUS{background:rgba(108,160,240,.15);color:var(--info)}
  .pill.LONG{color:var(--win)} .pill.SHORT{color:var(--loss)}
  .age{font-size:10.5px;color:var(--muted)}
  /* --- filter chips --- */
  .chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 10px}
  .chip{background:var(--panel);border:1px solid var(--line);color:var(--muted);
        border-radius:99px;padding:4px 12px;font-family:var(--mono);font-size:11.5px;
        cursor:pointer}
  .chip.on{border-color:var(--accent);color:var(--accent)}
  .reasons li{font-family:var(--mono);font-size:12px;color:var(--muted);
              padding:6px 12px;border-bottom:1px solid var(--panel2);list-style:none;
              display:flex;justify-content:space-between;gap:12px}
  .reasons li:last-child{border-bottom:0}
  .reasons b{color:var(--text);font-weight:500;flex-shrink:0}
  .empty{padding:18px;color:var(--muted);font-family:var(--mono);font-size:12.5px}
  a{color:var(--info)}
  /* --- howto --- */
  details{margin-top:22px;background:var(--panel);border:1px solid var(--line);
          border-radius:10px;padding:0}
  summary{cursor:pointer;padding:12px 16px;font-family:var(--mono);font-size:12.5px;
          color:var(--accent);list-style:none}
  summary::-webkit-details-marker{display:none}
  summary::before{content:"» ";color:var(--muted)}
  details[open] summary::before{content:"« "}
  .howto{padding:2px 18px 14px;font-size:13px;color:var(--muted)}
  .howto dt{color:var(--text);font-family:var(--mono);font-size:12.5px;margin-top:9px}
  .howto dd{margin:1px 0 0 0}
  .howto .warn{margin-top:12px;padding:9px 12px;border-left:3px solid var(--loss);
               background:rgba(229,83,75,.06);border-radius:6px;color:var(--text);
               font-size:12.5px}
  @media (prefers-reduced-motion:no-preference){
    .flash{animation:flash .5s ease}
    @keyframes flash{from{color:var(--accent)}to{color:var(--muted)}}
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="loghead">
    <span class="kv"><span class="dot" id="dot"></span><b>event</b>=<i>dashboard</i></span>
    <span class="kv"><b>mode</b>=<i>shadow-tracking</i></span>
    <span class="kv"><b>telegram</b>=<i>muted</i></span>
    <span class="kv"><b>updated</b>=<i id="updated">--:--:--</i></span>
    <span class="ctrl">
      <label for="iv" style="font-size:11px;color:var(--muted)">yenileme</label>
      <select id="iv">
        <option value="30000">30 sn</option>
        <option value="60000" selected>60 sn</option>
        <option value="300000">5 dk</option>
      </select>
      <button id="refresh">Şimdi yenile</button>
    </span>
  </div>

  <div class="verdict" id="verdict">yükleniyor…</div>

  <div class="kpis" id="kpis"></div>

  <h2><b>equity</b> — kümülatif R eğrisi</h2>
  <p class="hint">Sonuçlanan her sinyalin R katkısı sırayla toplanır; çizgi yukarı eğimliyse sistem birikimli olarak kazandırıyor demektir.</p>
  <div class="panel curve" id="curve"><div class="empty">henüz sonuçlanan sinyal yok</div></div>

  <h2><b>direction</b> — yön bilançosu</h2>
  <p class="hint">Aynı motorun LONG ve SHORT tarafı ayrı ayrı: piyasa rejimiyle uyum burada görünür.</p>
  <div class="split">
    <div class="panel side" id="sideL"></div>
    <div class="panel side" id="sideS"></div>
  </div>

  <h2><b>outcomes</b> — sonuç dağılımı</h2>
  <div class="panel" style="padding:12px 16px">
    <div class="bar" id="obar"></div>
    <div class="legend" id="olegend"></div>
  </div>

  <h2><b>signals</b> — gölge takipteki sinyaller</h2>
  <div class="chips" id="chips"></div>
  <div class="panel tblwrap"><div id="signals" class="empty">yükleniyor…</div></div>

  <h2><b>last_scan</b> — son tarama dağılımı</h2>
  <div class="panel" style="padding:12px 16px">
    <div class="bar" id="bar"></div>
    <div class="legend" id="legend"></div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-top:14px">
    <div>
      <h2 style="margin-top:0"><b>active</b> — aktif SIGNAL kararları</h2>
      <div class="panel tblwrap"><div id="active" class="empty">yükleniyor…</div></div>
    </div>
    <div>
      <h2 style="margin-top:0"><b>rejects</b> — en sık ret nedenleri</h2>
      <div class="panel"><ul class="reasons" id="reasons"></ul></div>
    </div>
  </div>

  <details>
    <summary>Nasıl okunur?</summary>
    <div class="howto">
      <dl>
        <dt>R (risk katsayısı)</dt>
        <dd>Her işlemin sonucu, riske atılan birim cinsinden: kayıp = −1R, kazanç = ödül/risk oranı kadar (+2.2R gibi). Para yerine R kullanmak farklı fiyatlı pariteleri karşılaştırılabilir yapar.</dd>
        <dt>Win rate ve başabaş</dt>
        <dd>Kazançlar kayıplardan büyükse %50 isabet gerekmez. Başabaş eşiği ortalama kazançtan hesaplanır: 1 / (1 + ort. kazanç R). Win rate bu eşiğin üzerindeyse sistem artıdadır.</dd>
        <dt>PENDING → FILLED → WIN/LOSS</dt>
        <dd>Sinyal üretilince fiyatın giriş bölgesine gelmesi 6 saat beklenir (PENDING). Gelirse pozisyon dolmuş sayılır (FILLED) ve 48 saat izlenir; önce stop görülürse LOSS, önce hedef görülürse WIN.</dd>
        <dt>NOT_FILLED</dt>
        <dd>Fiyat giriş bölgesine hiç gelmedi; işlem açılmadı. Kazanç/kayıp oranına dahil edilmez — ama oranı yüksekse giriş yöntemi tartışılır (izlediğimiz metrik).</dd>
        <dt>AMBIGUOUS</dt>
        <dd>Aynı mumda hem stop hem hedef görüldü; hangisinin önce olduğu bilinemez, dürüstlük gereği sayılmaz.</dd>
      </dl>
      <div class="warn">Bu panodaki tüm sonuçlar <b>gölge muhasebedir</b>: varsayımsal giriş, kayma ve komisyon yok, gerçek emir yok. Geçmiş performans gelecek için garanti değildir; hiçbir şey yatırım tavsiyesi sayılmaz.</div>
    </div>
  </details>

  <h2><b>system</b></h2>
  <div class="loghead" style="border:1px solid var(--line);border-radius:10px;
       padding:12px 16px;background:var(--panel)" id="sysline"></div>
</div>

<script>
"use strict";
const $=id=>document.getElementById(id);
const num=(v,d=2)=>v==null?"—":Number(v).toFixed(d);
const fmtTs=s=>s?s.replace("T"," ").replace("Z","").slice(5,16):"—";
function fmtAge(iso){
  if(!iso)return "";
  const ms=Date.now()-Date.parse(iso.endsWith("Z")?iso:iso+"Z");
  const h=ms/3600000;
  if(h<1)return Math.max(1,Math.round(ms/60000))+" dk";
  if(h<24)return h.toFixed(1)+" sa";
  return Math.floor(h/24)+"g "+Math.round(h%24)+"sa";
}
async function j(url){
  try{const r=await fetch(url);if(!r.ok)return null;return await r.json();}
  catch(e){return null;}
}
const OUT=s=>s.outcome||s.status;

/* ---------- verdict ---------- */
function renderVerdict(perf,status){
  const el=$("verdict");
  if(!status){el.innerHTML="⚠ Bota ulaşılamıyor — servis uykuda olabilir (ücretsiz plan), 30-50 sn içinde tekrar deneyin.";return;}
  if(!perf||!perf.decided_trades){
    el.innerHTML="<b>Motor çalışıyor.</b> Henüz sonuçlanan sinyal yok — filtreler koşul bekliyor, bu tasarım gereğidir.";return;}
  const wr=perf.win_rate*100, tr=perf.total_r_multiple;
  const w=perf.closed_by_outcome?.WIN||{count:0,sum_r:0};
  const be=w.count?100/(1+(w.sum_r/w.count)):null;
  const trTxt=(tr>0?"+":"")+num(tr)+"R";
  let judge;
  if(be==null) judge="değerlendirme için kazanç örneği bekleniyor";
  else if(wr>be) judge="başabaş eşiğinin <b>üzerinde</b>";
  else judge="başabaş eşiğinin <b>altında</b>";
  const nWarn=perf.decided_trades<30?" — örneklem küçük ("+perf.decided_trades+"), hüküm için erken":"";
  el.innerHTML=`<b>Motor çalışıyor.</b> ${perf.decided_trades} sonuçlanan sinyalde toplam <b>${trTxt}</b>, isabet %${num(wr,1)}${be!=null?" (başabaş ~%"+num(be,1)+")":""} → ${judge}${nWarn}.`;
}

/* ---------- KPIs ---------- */
function renderKpis(perf,status,uni,signals){
  const meta=(status&&status.meta)||{};
  const cbo=(perf&&perf.closed_by_outcome)||{};
  const w=cbo.WIN||{count:0,sum_r:0}, l=cbo.LOSS||{count:0,sum_r:0};
  const wr=perf&&perf.win_rate!=null?(perf.win_rate*100).toFixed(1)+"%":"—";
  const be=w.count?(100/(1+(w.sum_r/w.count))).toFixed(1):null;
  const tr=perf?perf.total_r_multiple:null;
  const filled=(signals||[]).filter(s=>["WIN","LOSS","AMBIGUOUS","FILLED"].includes(OUT(s))).length;
  const nf=(signals||[]).filter(s=>OUT(s)==="NOT_FILLED").length;
  const fillRate=(filled+nf)?Math.round(100*filled/(filled+nf))+"%":"—";
  const ds=(perf&&perf.dataset)||{};
  const kpi=(lbl,val,cls,sub)=>`<div class="kpi"><div class="lbl">${lbl}</div>
    <div class="val ${cls||""}">${val}</div><div class="sub">${sub||""}</div></div>`;
  $("kpis").innerHTML=
    kpi("Win rate",wr,"",be?`başabaş ~%${be}`:(perf?perf.decided_trades+" sonuçlanan":""))+
    kpi("Toplam R",tr==null?"—":(tr>0?"+":"")+num(tr),tr>0?"pos":tr<0?"neg":"",
        `+${num(w.sum_r)} / −${num(Math.abs(l.sum_r))}`)+
    kpi("Açık sinyal",perf?perf.open_signals:"—","amb","takipte")+
    kpi("Giriş isabeti",fillRate,"",`${filled} doldu / ${nf} dolmadı`)+
    kpi("Evren",uni?uni.count:"—","",uni?uni.mode:"")+
    kpi("Tarama",meta.scan_count??"—","","son: "+fmtTs(meta.last_scan_utc))+
    kpi("Arşiv",ds.candles_archived?(ds.candles_archived/1000).toFixed(1)+"k":"—","",
        (ds.decisions_recorded??0)+" karar");
}

/* ---------- equity curve ---------- */
function renderCurve(signals){
  const done=(signals||[]).filter(s=>["WIN","LOSS"].includes(OUT(s)))
    .sort((a,b)=>(a.resolved_utc||a.created_utc||"").localeCompare(b.resolved_utc||b.created_utc||""));
  if(!done.length){$("curve").innerHTML='<div class="empty">henüz sonuçlanan sinyal yok</div>';return;}
  let c=0; const pts=[[0,0]].concat(done.map((s,i)=>[i+1,c+=(s.r_multiple||0)]));
  const W=600,H=150,P=28;
  const ys=pts.map(p=>p[1]); const ymin=Math.min(0,...ys), ymax=Math.max(0,...ys);
  const yr=(ymax-ymin)||1;
  const X=i=>P+ (W-P-8) * i/(pts.length-1||1);
  const Y=v=>8+ (H-24) * (1-(v-ymin)/yr);
  const path=pts.map((p,i)=>(i?"L":"M")+X(p[0]).toFixed(1)+" "+Y(p[1]).toFixed(1)).join(" ");
  const area=path+` L${X(pts.length-1).toFixed(1)} ${Y(0).toFixed(1)} L${X(0).toFixed(1)} ${Y(0).toFixed(1)} Z`;
  const last=pts[pts.length-1][1];
  const dots=done.map((s,i)=>{
    const col=OUT(s)==="WIN"?"var(--win)":"var(--loss)";
    return `<circle class="pt" cx="${X(i+1).toFixed(1)}" cy="${Y(pts[i+1][1]).toFixed(1)}" r="2.6" fill="${col}"><title>${s.pair} ${s.direction} ${OUT(s)} ${(s.r_multiple>0?"+":"")+num(s.r_multiple)}R</title></circle>`;
  }).join("");
  $("curve").innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Kümülatif R eğrisi">
    <line class="zero" x1="${P}" y1="${Y(0)}" x2="${W-8}" y2="${Y(0)}"/>
    <path class="area" d="${area}"/><path class="path" d="${path}"/>${dots}
    <text x="${P}" y="${Y(0)-5}">0R</text>
    <text x="${W-8}" y="${Y(last)-7}" text-anchor="end" fill="${last>=0?'var(--win)':'var(--loss)'}">${(last>0?"+":"")+num(last)}R</text>
  </svg>`;
}

/* ---------- direction split ---------- */
function renderSplit(signals){
  const mk=(dir,el)=>{
    const rows=(signals||[]).filter(s=>s.direction===dir);
    const w=rows.filter(s=>OUT(s)==="WIN"), l=rows.filter(s=>OUT(s)==="LOSS");
    const r=[...w,...l].reduce((a,s)=>a+(s.r_multiple||0),0);
    const open=rows.filter(s=>["PENDING","FILLED"].includes(OUT(s))).length;
    const cls=r>0?"pos":r<0?"neg":"";
    el.innerHTML=`<div class="ttl"><span class="pill ${dir}">${dir}</span></div>
      <div class="big ${cls}">${(r>0?"+":"")+num(r)}R</div>
      <div class="sub">${w.length} WIN / ${l.length} LOSS · ${open} açık</div>`;
  };
  mk("LONG",$("sideL")); mk("SHORT",$("sideS"));
}

/* ---------- outcome bar ---------- */
function renderOutcomes(signals){
  const order=[["WIN","var(--win)"],["LOSS","var(--loss)"],["FILLED","var(--pend)"],
               ["PENDING","rgba(232,180,76,.45)"],["NOT_FILLED","var(--line)"],
               ["AMBIGUOUS","var(--info)"],["EXPIRED","#3a4763"]];
  const cnt={}; (signals||[]).forEach(s=>cnt[OUT(s)]=(cnt[OUT(s)]||0)+1);
  const total=(signals||[]).length||1;
  $("obar").innerHTML=order.filter(([k])=>cnt[k])
    .map(([k,c])=>`<div style="width:${100*cnt[k]/total}%;background:${c}"></div>`).join("");
  $("olegend").innerHTML=order.filter(([k])=>cnt[k])
    .map(([k,c])=>`<span><span class="sw" style="background:${c}"></span><b>${cnt[k]}</b> ${k}</span>`).join("")
    +`<span><b>${total}</b> toplam</span>`;
}

/* ---------- signals table + filters ---------- */
let FILTER="ALL", SIGNALS=[];
const FILTERS=[["ALL","Tümü"],["OPEN","Açık"],["DONE","Sonuçlanan"],["NF","Dolmayan"]];
function matches(s){
  const o=OUT(s);
  if(FILTER==="OPEN")return o==="PENDING"||o==="FILLED";
  if(FILTER==="DONE")return o==="WIN"||o==="LOSS"||o==="AMBIGUOUS";
  if(FILTER==="NF")return o==="NOT_FILLED"||o==="EXPIRED";
  return true;
}
function renderChips(){
  const c={ALL:SIGNALS.length,
    OPEN:SIGNALS.filter(s=>["PENDING","FILLED"].includes(OUT(s))).length,
    DONE:SIGNALS.filter(s=>["WIN","LOSS","AMBIGUOUS"].includes(OUT(s))).length,
    NF:SIGNALS.filter(s=>["NOT_FILLED","EXPIRED"].includes(OUT(s))).length};
  $("chips").innerHTML=FILTERS.map(([k,lbl])=>
    `<button class="chip${FILTER===k?" on":""}" data-f="${k}">${lbl} (${c[k]||0})</button>`).join("");
  $("chips").querySelectorAll(".chip").forEach(b=>b.addEventListener("click",()=>{
    FILTER=b.dataset.f; renderChips(); renderSignals();
  }));
}
function renderSignals(){
  const rows=SIGNALS.filter(matches);
  if(!rows.length){$("signals").className="empty";
    $("signals").innerHTML="bu filtrede sinyal yok";return;}
  const tr=rows.map(s=>{
    const o=OUT(s), r=s.r_multiple;
    const rCls=r>0?"pos":r<0?"neg":"";
    const open=o==="PENDING"||o==="FILLED";
    const age=open?`<div class="age">${fmtAge(s.created_utc)} / ${o==="PENDING"?"6 sa":"48 sa"}</div>`:"";
    const dim=o==="NOT_FILLED"?' class="dim"':"";
    return `<tr${dim}><td>${s.id}</td><td>${s.pair}</td>
      <td><span class="pill ${s.direction}">${s.direction}</span></td>
      <td>${fmtTs(s.created_utc)}${age}</td>
      <td><span class="pill ${o}">${o}</span></td>
      <td>${num(s.entry_min,4)}–${num(s.entry_max,4)}</td>
      <td>${num(s.stop_loss,4)}</td><td>${num(s.tp1,4)}</td>
      <td>${num(s.rr,2)}</td>
      <td class="${rCls}">${r==null?"—":(r>0?"+":"")+num(r)}</td></tr>`;}).join("");
  $("signals").className="";
  $("signals").innerHTML=`<table><thead><tr><th>#</th><th>parite</th><th>yön</th>
    <th>oluşturma</th><th>durum</th><th>entry</th><th>stop</th><th>tp1</th>
    <th>plan RR</th><th>R</th></tr></thead><tbody>${tr}</tbody></table>`;
}

/* ---------- last scan ---------- */
function renderScan(status){
  const res=(status&&status.results)||{};
  const vals=Object.values(res);
  const total=vals.length||1;
  const counts={SIGNAL:0,NO_TRADE:0,DATA_MISSING:0};
  const reasons={}; const active=[];
  for(const d of vals){
    counts[d.decision]=(counts[d.decision]||0)+1;
    if(d.decision==="SIGNAL")active.push(d);
    else if(d.reject_reason){
      const key=d.reject_reason.split("(")[0].trim();
      reasons[key]=(reasons[key]||0)+1;
    }
  }
  const seg=(n,color)=>`<div style="width:${(100*n/total)}%;background:${color}"></div>`;
  $("bar").innerHTML=seg(counts.SIGNAL,"var(--win)")+
    seg(counts.NO_TRADE,"var(--line)")+seg(counts.DATA_MISSING,"var(--loss)");
  $("legend").innerHTML=
    `<span><span class="sw" style="background:var(--win)"></span><b>${counts.SIGNAL}</b> SIGNAL</span>`+
    `<span><span class="sw" style="background:var(--line)"></span><b>${counts.NO_TRADE}</b> NO_TRADE</span>`+
    `<span><span class="sw" style="background:var(--loss)"></span><b>${counts.DATA_MISSING}</b> DATA_MISSING</span>`+
    `<span><b>${vals.length}</b> parite tarandı</span>`;
  if(active.length){
    $("active").className="";
    $("active").innerHTML="<table><thead><tr><th>parite</th><th>yön</th><th>setup</th>"+
      "<th>RR</th><th>conf</th></tr></thead><tbody>"+
      active.map(d=>`<tr><td>${d.pair}</td>
        <td><span class="pill ${d.direction}">${d.direction}</span></td>
        <td>${d.setup_type}</td><td>${num(d.rr,2)}</td>
        <td>${d.confidence}</td></tr>`).join("")+"</tbody></table>";
  }else{
    $("active").className="empty";
    $("active").innerHTML="son taramada SIGNAL yok — koşullar filtreleri geçmedi";
  }
  const top=Object.entries(reasons).sort((a,b)=>b[1]-a[1]).slice(0,6);
  $("reasons").innerHTML=top.length?
    top.map(([k,v])=>`<li><span>${k}</span><b>${v}</b></li>`).join(""):
    '<li><span>veri bekleniyor</span></li>';
}

/* ---------- system ---------- */
function renderSys(uni,backup,healthy){
  const parts=[];
  parts.push(`<span class="kv"><b>universe</b>=<i>${uni?uni.mode+":"+uni.count:"—"}</i></span>`);
  if(backup&&backup.gist_url){
    parts.push(`<span class="kv"><b>gist</b>=<i><a href="${backup.gist_url}" target="_blank" rel="noopener">açık</a></i></span>`);
    parts.push(`<span class="kv"><b>last_sync</b>=<i>${fmtTs(backup.last_sync_utc)}</i></span>`);
  }else{
    parts.push(`<span class="kv"><b>gist</b>=<i>kapalı (GITHUB_TOKEN bekleniyor)</i></span>`);
  }
  parts.push(`<span class="kv"><b>endpoints</b>=<i>/performance /signals /status /universe /scan/dry</i></span>`);
  $("sysline").innerHTML=parts.join("");
  $("dot").className="dot"+(healthy?"":" err");
}

/* ---------- main ---------- */
async function refresh(){
  const [perf,signals,status,uni,backup]=await Promise.all([
    j("/performance"),j("/signals?limit=200"),j("/status"),
    j("/universe"),j("/backup/info")]);
  SIGNALS=(signals||[]).slice().sort((a,b)=>(b.id||0)-(a.id||0));
  renderVerdict(perf,status);
  renderKpis(perf,status,uni,SIGNALS);
  renderCurve(SIGNALS);
  renderSplit(SIGNALS);
  renderOutcomes(SIGNALS);
  renderChips(); renderSignals();
  renderScan(status);
  renderSys(uni,backup,!!status);
  const u=$("updated");
  u.textContent=new Date().toLocaleTimeString("tr-TR");
  u.classList.remove("flash");void u.offsetWidth;u.classList.add("flash");
}
let timer=null;
function schedule(){
  if(timer)clearInterval(timer);
  timer=setInterval(refresh,parseInt($("iv").value,10));
}
$("iv").addEventListener("change",schedule);
$("refresh").addEventListener("click",refresh);
refresh();schedule();
</script>
</body>
</html>
"""
