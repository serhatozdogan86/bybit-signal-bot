"""
Dashboard v2.6 - "trading OS" esinli, acik temali, tam genislik konsol.

v2.5'e gore:
- SIDEBAR yerlesimi: sol sutunda marka + STRATEJI karti + PIPELINE karti
  (motorun 7 asamali filtre boru hatti, son taramanin ret dagilimiyla canli)
  + sistem bilgisi. Ana alan ekranin kalanini kullanir (bos kenar kalmaz).
- FEAR & GREED endeksi (/market icindeki fng alani; alternative.me, 1 sa
  onbellek, ulasilamazsa panel gizlenir) - renk skalali serit gosterge.
- MARKET PULSE: kural tabanli anlik piyasa okumasi (BTC/ETH 24s + likit
  evren genisligi + endeks -> sablon cumleler; boyle etiketlenir).
- PIPELINE karti ayni zamanda "ret sebepleri aciklamasi"dir: her asamanin
  ne yaptigi bir satirla anlatilir, son taramada kacar pariteyi eledigi
  gosterilir.
Tek-ekran ilkesi korunur (masaustunde sayfa kaydirmasi yok; ic paneller
kayar). Dar ekranda tek sutuna duser.
"""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>signal-engine // dashboard</title>
<style>
  :root{
    --bg:#EDF0F5; --panel:#FFFFFF; --panel2:#F5F7FB; --side:#F8FAFD;
    --line:#DCE3EE; --text:#1D2534; --muted:#69758D;
    --accent:#9A6A14; --accent-soft:#F6EAD2;
    --win:#177E52; --win-soft:#E3F3EB; --loss:#C43D3D; --loss-soft:#FBE9E9;
    --pend:#9A6A14; --pend-soft:#F6EAD2; --info:#2B66C4; --info-soft:#E7EEFA;
    --nf:#8A96AC; --nf-soft:#EDF0F5;
    --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    --sans:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;
    --shadow:0 1px 2px rgba(20,30,55,.05);
  }
  *{box-sizing:border-box;margin:0}
  html,body{height:100%}
  body{background:var(--bg);color:var(--text);font-family:var(--sans);
       font-size:13px;line-height:1.45;overflow:hidden}
  .app{display:grid;grid-template-columns:225px minmax(0,1fr);height:100vh}
  /* ================= SIDEBAR ================= */
  .side{background:var(--side);border-right:1px solid var(--line);
        display:flex;flex-direction:column;gap:8px;padding:12px 10px;
        min-height:0}
  .brand{font-family:var(--mono);padding:0 4px}
  .brand .t{font-size:14px;font-weight:700;letter-spacing:.02em}
  .brand .t b{color:var(--accent)}
  .brand .s{font-size:10px;color:var(--muted)}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--win);
       display:inline-block;margin-right:5px}
  .dot.err{background:var(--loss)}
  @media (prefers-reduced-motion:no-preference){
    .dot{animation:pulse 2.4s ease-in-out infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}
  }
  .scard{background:var(--panel);border:1px solid var(--line);border-radius:9px;
         box-shadow:var(--shadow);padding:8px 10px;min-height:0;
         display:flex;flex-direction:column}
  .scard h3{font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;
            color:var(--muted);font-weight:700;margin-bottom:5px}
  .scard h3 b{color:var(--accent);font-family:var(--mono)}
  .strat{font-size:11px;color:var(--muted)}
  .strat b{color:var(--text);font-weight:600}
  .strat .row{display:flex;justify-content:space-between;gap:6px;
              padding:1.5px 0;font-family:var(--mono);font-size:10.5px}
  /* pipeline */
  .pipe{overflow-y:auto;scrollbar-width:thin;flex:1;min-height:0}
  .step{padding:4px 0 5px;border-bottom:1px dashed var(--line)}
  .step:last-child{border-bottom:0}
  .step .h{display:flex;justify-content:space-between;align-items:baseline;
           font-family:var(--mono);font-size:10.5px}
  .step .h b{font-weight:600}
  .step .h .n{color:var(--muted)}
  .step .d{font-size:9.8px;color:var(--muted);line-height:1.3}
  .step .g{height:4px;border-radius:2px;background:var(--panel2);
           margin-top:3px;overflow:hidden}
  .step .g div{height:100%;background:#C7CFDD}
  .step.pass .g div{background:var(--win)}
  .step.pass .h b{color:var(--win)}
  .sysinfo{font-family:var(--mono);font-size:10px;color:var(--muted);
           padding:0 4px}
  .sysinfo a{color:var(--info)}
  .sysinfo div{padding:1px 0}
  /* ================= MAIN ================= */
  .mainwrap{display:grid;grid-template-rows:auto auto auto minmax(0,1fr);
            gap:8px;padding:10px 12px;min-height:0}
  .loghead{font-family:var(--mono);font-size:11.5px;color:var(--muted);
           display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center}
  .kv b{color:var(--accent);font-weight:600}
  .kv i{color:var(--text);font-style:normal}
  .ctrl{margin-left:auto;display:flex;gap:6px;align-items:center}
  select,button{background:var(--panel);color:var(--text);border:1px solid var(--line);
    border-radius:6px;padding:4px 9px;font-family:var(--mono);font-size:11px;
    cursor:pointer;box-shadow:var(--shadow)}
  button:hover,select:hover{border-color:var(--accent)}
  :focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  .verdict{padding:7px 14px;background:var(--panel);border:1px solid var(--line);
           border-left:3px solid var(--accent);border-radius:9px;
           font-size:12.8px;box-shadow:var(--shadow)}
  .verdict b{color:var(--accent)}
  .kpis{display:grid;grid-template-columns:repeat(7,1fr);gap:1px;
        background:var(--line);border:1px solid var(--line);border-radius:9px;
        overflow:hidden;box-shadow:var(--shadow)}
  .kpi{background:var(--panel);padding:6px 12px 5px}
  .kpi .lbl{font-size:9.5px;letter-spacing:.07em;text-transform:uppercase;
            color:var(--muted)}
  .kpi .val{font-family:var(--mono);font-size:17.5px;margin-top:1px}
  .kpi .sub{font-family:var(--mono);font-size:10px;color:var(--muted);
            white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .pos{color:var(--win)} .neg{color:var(--loss)} .amb{color:var(--pend)}
  .main{display:grid;grid-template-columns:1fr 1.45fr 1.05fr;gap:9px;
        min-height:0}
  .col{display:flex;flex-direction:column;gap:8px;min-height:0}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:9px;
         box-shadow:var(--shadow);display:flex;flex-direction:column;min-height:0}
  .phead{padding:6px 12px 0;font-size:10px;letter-spacing:.09em;
         text-transform:uppercase;color:var(--muted);font-weight:600;
         display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
  .phead b{color:var(--accent);font-family:var(--mono);font-weight:600}
  .phead .note{font-size:9.8px;text-transform:none;letter-spacing:0;
               font-weight:400;margin-left:auto}
  .pbody{padding:5px 12px 9px;min-height:0}
  .scroll{overflow-y:auto;scrollbar-width:thin}
  .fill{flex:1}
  .empty{color:var(--muted);font-family:var(--mono);font-size:11px;padding:6px 0}
  /* equity */
  .curve svg{width:100%;height:100%;display:block}
  .curve .zero{stroke:var(--muted);stroke-width:1;stroke-dasharray:4 4;opacity:.55}
  .curve .path{fill:none;stroke:var(--accent);stroke-width:2}
  .curve .area{fill:var(--accent);opacity:.09}
  .curve text{font-family:var(--mono);font-size:10px;fill:var(--muted)}
  .dir{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  .dside{background:var(--panel2);border:1px solid var(--line);border-radius:7px;
         padding:5px 10px}
  .dside .big{font-family:var(--mono);font-size:15px}
  .dside .sub{font-family:var(--mono);font-size:10px;color:var(--muted)}
  .bar{display:flex;height:9px;border-radius:5px;overflow:hidden;
       border:1px solid var(--line);margin:4px 0 3px}
  .bar div{height:100%}
  .legend{font-family:var(--mono);font-size:9.8px;color:var(--muted);
          display:flex;gap:9px;flex-wrap:wrap}
  .legend b{color:var(--text);font-weight:600}
  .sw{display:inline-block;width:8px;height:8px;border-radius:2px;
      margin-right:4px;vertical-align:-1px}
  .mline{font-family:var(--mono);font-size:10px;color:var(--muted);
         margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .mline b{color:var(--text);font-weight:600}
  .pill{display:inline-block;padding:0 7px;border-radius:99px;font-size:10px;
        font-family:var(--mono)}
  .pill.WIN{background:var(--win-soft);color:var(--win)}
  .pill.LOSS{background:var(--loss-soft);color:var(--loss)}
  .pill.PENDING,.pill.FILLED{background:var(--pend-soft);color:var(--pend)}
  .pill.NOT_FILLED,.pill.EXPIRED{background:var(--nf-soft);color:var(--nf)}
  .pill.AMBIGUOUS{background:var(--info-soft);color:var(--info)}
  .pill.LONG{color:var(--win)} .pill.SHORT{color:var(--loss)}
  table{width:100%;border-collapse:collapse;font-family:var(--mono);
        font-size:11px}
  th{color:var(--muted);text-align:left;font-weight:600;font-size:9.5px;
     letter-spacing:.06em;text-transform:uppercase;padding:6px 9px;
     border-bottom:1px solid var(--line);background:var(--panel2);
     position:sticky;top:0;z-index:1}
  td{padding:3.5px 9px;border-bottom:1px solid var(--panel2);white-space:nowrap}
  tr:last-child td{border-bottom:0}
  tr.dim td{opacity:.5}
  .age{font-size:9.5px;color:var(--muted)}
  .chips{display:flex;gap:6px;flex-wrap:wrap}
  .chip{background:var(--panel2);border:1px solid var(--line);color:var(--muted);
        border-radius:99px;padding:1.5px 9px;font-family:var(--mono);
        font-size:10px;cursor:pointer}
  .chip.on{border-color:var(--accent);color:var(--accent);
           background:var(--accent-soft)}
  .review p{margin:0 0 6px;font-size:12px}
  .review .rts{font-family:var(--mono);font-size:10px;color:var(--muted)}
  .review .warnline{border-left:3px solid var(--loss);padding-left:8px;
                    background:var(--loss-soft);border-radius:4px}
  .review details{margin-top:3px}
  .review summary{cursor:pointer;font-family:var(--mono);font-size:10.5px;
                  color:var(--info);list-style:none}
  .review summary::-webkit-details-marker{display:none}
  .prev{border-top:1px dashed var(--line);margin-top:6px;padding-top:6px}
  /* market */
  .majors{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  .mj{background:var(--panel2);border:1px solid var(--line);border-radius:7px;
      padding:4px 10px;font-family:var(--mono)}
  .mj .sym{font-size:10px;color:var(--muted)}
  .mj .px{font-size:14.5px}
  .mj .row{font-size:10px;color:var(--muted)}
  .fng{margin-top:7px}
  .fng .lbl{display:flex;justify-content:space-between;font-family:var(--mono);
            font-size:10px;color:var(--muted)}
  .fng .lbl b{color:var(--text)}
  .fng .track{position:relative;height:9px;border-radius:5px;margin-top:3px;
    background:linear-gradient(90deg,#C43D3D 0%,#D98A3D 30%,#B9B9B9 50%,
                               #7FB98A 70%,#177E52 100%);
    border:1px solid var(--line)}
  .fng .mark{position:absolute;top:-3px;width:3px;height:15px;background:var(--text);
             border-radius:2px}
  .movers{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:7px;
          font-family:var(--mono);font-size:10.3px}
  .movers .m{display:flex;justify-content:space-between;padding:1px 0}
  .movers h4{font-size:9.3px;color:var(--muted);letter-spacing:.06em;
             font-weight:600;margin-bottom:1px}
  .pulse{margin-top:7px;font-size:11.3px;background:var(--info-soft);
         border-left:3px solid var(--info);border-radius:5px;padding:6px 9px}
  .pulse .tag{font-family:var(--mono);font-size:9.3px;color:var(--muted)}
  .news li{list-style:none;padding:4px 0;border-bottom:1px solid var(--panel2)}
  .news li:last-child{border-bottom:0}
  .news a{color:var(--text);text-decoration:none;font-size:11.7px;
          line-height:1.3;display:block}
  .news a:hover{color:var(--info);text-decoration:underline}
  .news .src{font-family:var(--mono);font-size:9.3px;color:var(--muted)}
  /* howto overlay */
  #overlay{position:fixed;inset:0;background:rgba(23,32,50,.45);display:none;
           align-items:center;justify-content:center;z-index:50;padding:20px}
  #overlay.show{display:flex}
  .howto{background:var(--panel);border-radius:12px;max-width:640px;
         max-height:82vh;overflow-y:auto;padding:18px 22px;
         box-shadow:0 10px 40px rgba(20,30,55,.25)}
  .howto h3{font-family:var(--mono);color:var(--accent);font-size:14px;
            margin-bottom:8px}
  .howto dt{font-family:var(--mono);font-size:12px;margin-top:9px}
  .howto dd{margin:1px 0 0;color:var(--muted);font-size:12.5px}
  .howto .warn{margin-top:12px;padding:9px 12px;border-left:3px solid var(--loss);
               background:var(--loss-soft);border-radius:6px;font-size:12px}
  a{color:var(--info)}
  @media (prefers-reduced-motion:no-preference){
    .flash{animation:flash .5s ease}
    @keyframes flash{from{color:var(--accent)}to{color:var(--muted)}}
  }
  @media (max-width:1080px){
    body{overflow:auto}
    .app{grid-template-columns:1fr;height:auto}
    .side{flex-direction:column;border-right:0;border-bottom:1px solid var(--line)}
    .mainwrap{grid-template-rows:none}
    .kpis{grid-template-columns:repeat(auto-fit,minmax(120px,1fr))}
    .main{grid-template-columns:1fr}
    .curve{height:170px}
    .scroll{max-height:55vh}
    .pipe{max-height:none}
  }
</style>
</head>
<body>
<div class="app">

  <!-- ================= SIDEBAR ================= -->
  <aside class="side">
    <div class="brand">
      <div class="t"><span class="dot" id="dot"></span>signal<b>-engine</b></div>
      <div class="s">shadow-tracking · telegram=muted</div>
    </div>

    <div class="scard">
      <h3><b>strategy</b> · strateji sözleşmesi</h3>
      <div class="strat">
        <b>Conservative swing.</b> Yapı önce gelir; indikatörler yalnız teyittir.
        Kenar net değilse karar <b>NO_TRADE</b>'dir.
        <div class="row"><span>Zaman dilimi</span><b>4H → 15m</b></div>
        <div class="row"><span>Hacim teyidi</span><b>≥1.5× ort.</b></div>
        <div class="row"><span>Min risk/ödül</span><b>2.0</b></div>
        <div class="row"><span>Setup</span><b>retest · sweep</b></div>
        <div class="row"><span>Evren</span><b id="stratUni">top-150</b></div>
      </div>
    </div>

    <div class="scard" style="flex:1">
      <h3><b>pipeline</b> · filtre boru hattı <span style="float:right" id="pipeMeta"></span></h3>
      <div class="pipe" id="pipe"><div class="empty">tarama bekleniyor…</div></div>
    </div>

    <div class="sysinfo" id="sysline"></div>
    <button id="howtoBtn">Nasıl okunur?</button>
  </aside>

  <!-- ================= MAIN ================= -->
  <div class="mainwrap">
    <div class="loghead">
      <span class="kv"><b>event</b>=<i>dashboard</i></span>
      <span class="kv"><b>updated</b>=<i id="updated">--:--:--</i></span>
      <span class="ctrl">
        <label for="iv" style="font-size:10px;color:var(--muted)">yenileme</label>
        <select id="iv">
          <option value="30000">30 sn</option>
          <option value="60000" selected>60 sn</option>
          <option value="300000">5 dk</option>
        </select>
        <button id="refresh">Yenile</button>
      </span>
    </div>

    <div class="verdict" id="verdict">yükleniyor…</div>
    <div class="kpis" id="kpis"></div>

    <div class="main">
      <div class="col">
        <div class="panel fill">
          <div class="phead"><b>equity</b> kümülatif R
            <span class="note">nokta: sinyal · yeşil WIN / kırmızı LOSS</span></div>
          <div class="pbody fill curve" id="curve"><div class="empty">henüz sonuçlanan sinyal yok</div></div>
        </div>
        <div class="panel">
          <div class="phead"><b>direction</b> yön bilançosu</div>
          <div class="pbody dir"><div class="dside" id="sideL"></div><div class="dside" id="sideS"></div></div>
        </div>
        <div class="panel">
          <div class="phead"><b>distributions</b> sonuçlar + son tarama</div>
          <div class="pbody">
            <div class="bar" id="obar"></div><div class="legend" id="olegend"></div>
            <div class="bar" style="margin-top:7px" id="bar"></div><div class="legend" id="legend"></div>
            <div class="mline" id="activeline"></div>
          </div>
        </div>
      </div>

      <div class="col">
        <div class="panel fill">
          <div class="phead"><b>signals</b> gölge takip
            <span class="chips" id="chips" style="margin-left:auto"></span></div>
          <div class="pbody fill scroll" id="signals"><div class="empty">yükleniyor…</div></div>
        </div>
      </div>

      <div class="col">
        <div class="panel" style="flex:1.2">
          <div class="phead"><b>hourly_review</b> saatlik değerlendirme
            <span class="note">otomatik kural-tabanlı analiz</span></div>
          <div class="pbody fill scroll review" id="review"><div class="empty">ilk değerlendirme bekleniyor…</div></div>
        </div>
        <div class="panel">
          <div class="phead"><b>market</b> canlı metrikler
            <span class="note" id="mupd"></span></div>
          <div class="pbody" id="market"><div class="empty">yükleniyor…</div></div>
        </div>
        <div class="panel fill">
          <div class="phead"><b>news</b> kripto haber akışı
            <span class="note">dış kaynak · yorum içermez</span></div>
          <div class="pbody fill scroll"><ul class="news" id="news"><li class="empty">yükleniyor…</li></ul></div>
        </div>
      </div>
    </div>
  </div>
</div>

<div id="overlay">
  <div class="howto">
    <h3>Nasıl okunur?</h3>
    <dl>
      <dt>R (risk katsayısı)</dt>
      <dd>Her işlemin sonucu, riske atılan birim cinsinden: kayıp = −1R, kazanç = ödül/risk oranı kadar (+2.2R gibi).</dd>
      <dt>Win rate ve başabaş</dt>
      <dd>Kazançlar kayıplardan büyükse %50 isabet gerekmez. Başabaş = 1 / (1 + ort. kazanç R). Win rate eşiğin üzerindeyse sistem artıdadır.</dd>
      <dt>pipeline (filtre boru hattı)</dt>
      <dd>Motor her pariteyi 7 aşamadan geçirir; herhangi biri geçilemezse karar NO_TRADE olur. Kenardaki kart, son taramada her aşamanın kaç pariteyi elediğini gösterir — "neden sinyal yok?" sorusunun cevabı budur.</dd>
      <dt>PENDING → FILLED → WIN/LOSS</dt>
      <dd>Fiyatın giriş bölgesine gelmesi 6 saat beklenir; gelirse 48 saat izlenir. Önce stop = LOSS, önce hedef = WIN. NOT_FILLED orana dahil edilmez; AMBIGUOUS (aynı mumda ikisi) sayılmaz.</dd>
      <dt>market pulse / hourly_review</dt>
      <dd>İkisi de kural tabanlı otomatik üretimdir (canlı insan/LLM yorumu değildir); şablonlar bu projede elle yapılan analizlerden kodlanmıştır. Korku/Açgözlülük endeksi alternative.me kaynağından gelir.</dd>
    </dl>
    <div class="warn">Bu panodaki tüm sonuçlar <b>gölge muhasebedir</b>: varsayımsal giriş, kayma/komisyon yok, gerçek emir yok. Geçmiş performans gelecek için garanti değildir; hiçbir şey yatırım tavsiyesi değildir. Haber başlıkları dış kaynaklardan aynen aktarılır.</div>
    <div style="text-align:right;margin-top:12px"><button id="howtoClose">Kapat</button></div>
  </div>
</div>

<script>
"use strict";
const $=id=>document.getElementById(id);
const num=(v,d=2)=>v==null?"—":Number(v).toFixed(d);
const fmtTs=s=>s?s.replace("T"," ").replace("Z","").slice(5,16):"—";
function fmtAge(iso){
  if(!iso)return "";
  const ms=Date.now()-Date.parse(iso.endsWith("Z")?iso:iso+"Z");
  if(ms<0)return "";
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

/* ---------- verdict / kpis (v2.5 ile ayni mantik) ---------- */
function renderVerdict(perf,status){
  const el=$("verdict");
  if(!status){el.innerHTML="⚠ Bota ulaşılamıyor — servis uykuda olabilir (ücretsiz plan), 30-50 sn içinde tekrar deneyin.";return;}
  if(!perf||!perf.decided_trades){
    el.innerHTML="<b>Motor çalışıyor.</b> Henüz sonuçlanan sinyal yok — filtreler koşul bekliyor, bu tasarım gereğidir.";return;}
  const wr=perf.win_rate*100, tr=perf.total_r_multiple;
  const w=(perf.closed_by_outcome||{}).WIN||{count:0,sum_r:0};
  const be=w.count?100/(1+(w.sum_r/w.count)):null;
  let judge=be==null?"değerlendirme için kazanç örneği bekleniyor":
    (wr>be?"başabaş eşiğinin <b>üzerinde</b>":"başabaş eşiğinin <b>altında</b>");
  const nWarn=perf.decided_trades<30?" — örneklem küçük ("+perf.decided_trades+"), hüküm için erken":"";
  el.innerHTML=`<b>Motor çalışıyor.</b> ${perf.decided_trades} sonuçlanan sinyalde toplam <b>${(tr>0?"+":"")+num(tr)}R</b>, isabet %${num(wr,1)}${be!=null?" (başabaş ~%"+num(be,1)+")":""} → ${judge}${nWarn}.`;
}
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
    kpi("Win rate",wr,"",be?`başabaş ~%${be}`:(perf?(perf.decided_trades||0)+" sonuçlanan":""))+
    kpi("Toplam R",tr==null?"—":(tr>0?"+":"")+num(tr),tr>0?"pos":tr<0?"neg":"",
        `+${num(w.sum_r)} / −${num(Math.abs(l.sum_r))}`)+
    kpi("Açık",perf?perf.open_signals:"—","amb","takipte")+
    kpi("Giriş isabeti",fillRate,"",`${filled} doldu / ${nf} değil`)+
    kpi("Evren",uni?uni.count:"—","",uni?uni.mode:"")+
    kpi("Tarama",meta.scan_count??"—","","son "+fmtTs(meta.last_scan_utc))+
    kpi("Arşiv",ds.candles_archived?(ds.candles_archived/1000).toFixed(1)+"k":"—","",
        (ds.decisions_recorded??0)+" karar");
}

/* ---------- equity / direction / distributions ---------- */
function renderCurve(signals){
  const done=(signals||[]).filter(s=>["WIN","LOSS"].includes(OUT(s)))
    .sort((a,b)=>(a.closed_utc||a.created_utc||"").localeCompare(b.closed_utc||b.created_utc||""));
  if(!done.length){$("curve").innerHTML='<div class="empty">henüz sonuçlanan sinyal yok</div>';return;}
  let c=0; const pts=[[0,0]].concat(done.map((s,i)=>[i+1,c+=(s.r_multiple||0)]));
  const W=560,H=210,P=30;
  const ys=pts.map(p=>p[1]); const ymin=Math.min(0,...ys), ymax=Math.max(0,...ys);
  const yr=(ymax-ymin)||1;
  const X=i=>P+(W-P-8)*i/(pts.length-1||1);
  const Y=v=>10+(H-26)*(1-(v-ymin)/yr);
  const path=pts.map((p,i)=>(i?"L":"M")+X(p[0]).toFixed(1)+" "+Y(p[1]).toFixed(1)).join(" ");
  const area=path+` L${X(pts.length-1).toFixed(1)} ${Y(0).toFixed(1)} L${X(0).toFixed(1)} ${Y(0).toFixed(1)} Z`;
  const last=pts[pts.length-1][1];
  const dots=done.map((s,i)=>{
    const col=OUT(s)==="WIN"?"var(--win)":"var(--loss)";
    return `<circle cx="${X(i+1).toFixed(1)}" cy="${Y(pts[i+1][1]).toFixed(1)}" r="2.7" fill="${col}"><title>${s.pair} ${s.direction} ${OUT(s)} ${(s.r_multiple>0?"+":"")+num(s.r_multiple)}R</title></circle>`;
  }).join("");
  $("curve").innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Kümülatif R eğrisi">
    <line class="zero" x1="${P}" y1="${Y(0)}" x2="${W-8}" y2="${Y(0)}"/>
    <path class="area" d="${area}"/><path class="path" d="${path}"/>${dots}
    <text x="${P}" y="${Y(0)-5}">0R</text>
    <text x="${W-8}" y="${Y(last)-8}" text-anchor="end" fill="${last>=0?'var(--win)':'var(--loss)'}">${(last>0?"+":"")+num(last)}R</text>
  </svg>`;
}
function renderSplit(signals){
  const mk=(dir,el)=>{
    const rows=(signals||[]).filter(s=>s.direction===dir);
    const w=rows.filter(s=>OUT(s)==="WIN"), l=rows.filter(s=>OUT(s)==="LOSS");
    const r=[...w,...l].reduce((a,s)=>a+(s.r_multiple||0),0);
    const open=rows.filter(s=>["PENDING","FILLED"].includes(OUT(s))).length;
    el.innerHTML=`<span class="pill ${dir}">${dir}</span>
      <div class="big ${r>0?"pos":r<0?"neg":""}">${(r>0?"+":"")+num(r)}R</div>
      <div class="sub">${w.length}W / ${l.length}L · ${open} açık</div>`;
  };
  mk("LONG",$("sideL")); mk("SHORT",$("sideS"));
}
function renderOutcomes(signals){
  const order=[["WIN","var(--win)"],["LOSS","var(--loss)"],["FILLED","var(--pend)"],
               ["PENDING","#E4CE9C"],["NOT_FILLED","#C7CFDD"],
               ["AMBIGUOUS","var(--info)"],["EXPIRED","#9AA5BA"]];
  const cnt={}; (signals||[]).forEach(s=>cnt[OUT(s)]=(cnt[OUT(s)]||0)+1);
  const total=(signals||[]).length||1;
  $("obar").innerHTML=order.filter(([k])=>cnt[k])
    .map(([k,c])=>`<div style="width:${100*cnt[k]/total}%;background:${c}"></div>`).join("");
  $("olegend").innerHTML=order.filter(([k])=>cnt[k])
    .map(([k,c])=>`<span><span class="sw" style="background:${c}"></span><b>${cnt[k]}</b> ${k}</span>`).join("")
    +`<span><b>${total}</b> sinyal</span>`;
}

/* ---------- pipeline (sidebar) ---------- */
const STEPS=[
  ["DATA","Yeterli mum yok (yeni listeleme)","insufficient data"],
  ["REGIME","ADX<20: yönsüz/chop piyasa elenir","chop regime"],
  ["HTF STRUCTURE","4H yapı net değil: HH/HL–LH/LL çelişkili","HTF structure unclear"],
  ["LTF SETUP","15m'de doğrulanmış retest/sweep yok","no valid LTF setup"],
  ["VOLUME","Tetik barda hacim <1.5× ortalama","no volume confirmation"],
  ["RISK/REWARD","Plan RR < 2.0: kenar yetersiz","RR "],
];
function renderPipeline(status){
  const res=(status&&status.results)||{};
  const vals=Object.values(res); const total=vals.length;
  if(!total){$("pipe").innerHTML='<div class="empty">tarama bekleniyor…</div>';return;}
  const cnt={}; let signals=0;
  for(const d of vals){
    if(d.decision==="SIGNAL"){signals++;continue;}
    const r=(d.decision==="DATA_MISSING")?"insufficient data":(d.reject_reason||"");
    const step=STEPS.find(([, ,pat])=>r.startsWith(pat)||r.includes(pat));
    const key=step?step[0]:"OTHER";
    cnt[key]=(cnt[key]||0)+1;
  }
  $("pipeMeta").textContent=total+" parite";
  const rows=STEPS.map(([name,desc])=>{
    const n=cnt[name]||0;
    return `<div class="step"><div class="h"><b>${name}</b><span class="n">−${n}</span></div>
      <div class="d">${desc}</div>
      <div class="g"><div style="width:${Math.min(100,100*n/total)}%"></div></div></div>`;
  }).join("");
  const pass=`<div class="step pass"><div class="h"><b>→ SIGNAL</b><span class="n">${signals}</span></div>
    <div class="d">Tüm aşamaları geçenler gölge takibe alınır</div>
    <div class="g"><div style="width:${Math.min(100,100*signals/total*10)}%"></div></div></div>`;
  $("pipe").innerHTML=rows+pass;
}

/* ---------- signals table ---------- */
let FILTER="ALL", SIGNALS=[];
const FILTERS=[["ALL","Tümü"],["OPEN","Açık"],["DONE","Sonuç"],["NF","Dolmayan"]];
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
    `<button class="chip${FILTER===k?" on":""}" data-f="${k}">${lbl} ${c[k]||0}</button>`).join("");
  $("chips").querySelectorAll(".chip").forEach(b=>b.addEventListener("click",()=>{
    FILTER=b.dataset.f; renderChips(); renderSignals();
  }));
}
function renderSignals(){
  const rows=SIGNALS.filter(matches);
  const el=$("signals");
  if(!rows.length){el.innerHTML='<div class="empty">bu filtrede sinyal yok</div>';return;}
  const tr=rows.map(s=>{
    const o=OUT(s), r=s.r_multiple;
    const open=o==="PENDING"||o==="FILLED";
    const age=open?`<div class="age">${fmtAge(s.created_utc)} / ${o==="PENDING"?"6 sa":"48 sa"}</div>`:"";
    return `<tr${o==="NOT_FILLED"?' class="dim"':""}><td>${s.id}</td><td>${s.pair}</td>
      <td><span class="pill ${s.direction}">${s.direction}</span></td>
      <td>${fmtTs(s.created_utc)}${age}</td>
      <td><span class="pill ${o}">${o}</span></td>
      <td>${num(s.entry_min,4)}–${num(s.entry_max,4)}</td>
      <td>${num(s.stop_loss,4)}</td><td>${num(s.tp1,4)}</td>
      <td>${num(s.rr,2)}</td>
      <td class="${r>0?"pos":r<0?"neg":""}">${r==null?"—":(r>0?"+":"")+num(r)}</td></tr>`;}).join("");
  el.innerHTML=`<table><thead><tr><th>#</th><th>parite</th><th>yön</th>
    <th>zaman</th><th>durum</th><th>entry</th><th>stop</th><th>tp1</th>
    <th>RR</th><th>R</th></tr></thead><tbody>${tr}</tbody></table>`;
}

/* ---------- review / market / news ---------- */
function renderReview(comments){
  const el=$("review");
  if(!comments||!comments.length){
    el.innerHTML='<div class="empty">ilk değerlendirme ilk tarama turundan sonra üretilir…</div>';return;}
  const latest=comments[0];
  const paras=latest.text.split("\n").map(t=>{
    const cls=t.startsWith("Uyari")?' class="warnline"':"";
    return `<p${cls}>${t}</p>`;}).join("");
  let prev="";
  if(comments.length>1){
    prev=`<details><summary>önceki değerlendirmeler (${comments.length-1})</summary>`+
      comments.slice(1).map(c=>`<div class="prev"><div class="rts">${fmtTs(c.ts_utc)} UTC</div>`+
        c.text.split("\n").map(t=>`<p>${t}</p>`).join("")+"</div>").join("")+"</details>";
  }
  el.innerHTML=`<div class="rts">${fmtTs(latest.ts_utc)} UTC</div>${paras}${prev}`;
}
function renderMarket(m){
  const el=$("market");
  if(!m){el.innerHTML='<div class="empty">market verisine ulaşılamadı</div>';return;}
  $("mupd").textContent=m.updated_utc?fmtTs(m.updated_utc)+" UTC":"";
  const mj=(m.majors||[]).map(t=>{
    const cls=t.pct24h>0?"pos":t.pct24h<0?"neg":"";
    return `<div class="mj"><div class="sym">${t.symbol.replace("USDT","")}</div>
      <div class="px">${Number(t.last).toLocaleString("en-US",{maximumFractionDigits:2})}</div>
      <div class="row"><span class="${cls}">${(t.pct24h>0?"+":"")+num(t.pct24h,2)}%</span>
       · f ${num(t.funding,3)}%</div></div>`;}).join("");
  let fng="";
  if(m.fng&&m.fng.value!=null){
    fng=`<div class="fng"><div class="lbl"><span>Korku &amp; Açgözlülük</span>
      <b>${m.fng.value} · ${m.fng.label_tr}</b></div>
      <div class="track"><div class="mark" style="left:calc(${m.fng.value}% - 1px)"></div></div></div>`;
  }
  const br=m.breadth?`<div class="mline" style="margin-top:6px">
    <b>genişlik:</b> <span class="pos">${m.breadth.advancers}▲</span> /
    <span class="neg">${m.breadth.decliners}▼</span> (likit ${m.liquid_universe})</div>`:"";
  const mov=list=>list.map(t=>{
    const cls=t.pct24h>0?"pos":"neg";
    return `<div class="m"><span>${t.symbol.replace("USDT","")}</span>
      <span class="${cls}">${(t.pct24h>0?"+":"")+num(t.pct24h,1)}%</span></div>`;}).join("");
  const pulse=m.pulse?`<div class="pulse"><span class="tag">market pulse · kural-tabanlı okuma</span><br>${m.pulse}</div>`:"";
  el.innerHTML=`<div class="majors">${mj}</div>${fng}${br}
    <div class="movers">
      <div><h4>24s yükselen</h4>${mov(m.gainers||[])}</div>
      <div><h4>24s düşen</h4>${mov(m.losers||[])}</div>
    </div>${pulse}`;
}
function renderNews(n){
  const el=$("news");
  if(!n||!n.items||!n.items.length){
    el.innerHTML='<li class="empty">haber kaynağına ulaşılamadı</li>';return;}
  el.innerHTML=n.items.map(it=>
    `<li><a href="${it.url}" target="_blank" rel="noopener">${it.title}</a>
     <span class="src">${it.source}${it.published_utc?" · "+fmtAge(it.published_utc)+" önce":""}</span></li>`).join("");
}

/* ---------- system / howto ---------- */
function renderSys(uni,backup,healthy){
  const rows=[];
  rows.push(`<div><b style="color:var(--accent)">universe</b>=${uni?uni.mode+":"+uni.count:"—"}</div>`);
  if(uni)$("stratUni").textContent=uni.mode+"-"+uni.count;
  if(backup&&backup.gist_url){
    rows.push(`<div><b style="color:var(--accent)">gist</b>=<a href="${backup.gist_url}" target="_blank" rel="noopener">açık</a> · sync ${fmtTs(backup.last_sync_utc)}</div>`);
  }else{rows.push(`<div><b style="color:var(--accent)">gist</b>=kapalı</div>`);}
  rows.push(`<div>/performance /signals /commentary /market /news</div>`);
  $("sysline").innerHTML=rows.join("");
  $("dot").className="dot"+(healthy?"":" err");
}
$("howtoBtn").addEventListener("click",()=>$("overlay").classList.add("show"));
$("howtoClose").addEventListener("click",()=>$("overlay").classList.remove("show"));
$("overlay").addEventListener("click",e=>{if(e.target.id==="overlay")$("overlay").classList.remove("show");});

/* ---------- main loop ---------- */
async function refresh(){
  const [perf,signals,status,uni,backup,comments,market,news]=await Promise.all([
    j("/performance"),j("/signals?limit=200"),j("/status"),
    j("/universe"),j("/backup/info"),j("/commentary?limit=4"),
    j("/market"),j("/news")]);
  SIGNALS=(signals||[]).slice().sort((a,b)=>(b.id||0)-(a.id||0));
  renderVerdict(perf,status);
  renderKpis(perf,status,uni,SIGNALS);
  renderCurve(SIGNALS);
  renderSplit(SIGNALS);
  renderOutcomes(SIGNALS);
  renderChips(); renderSignals();
  renderScanBars(status);
  renderPipeline(status);
  renderReview(comments);
  renderMarket(market);
  renderNews(news);
  renderSys(uni,backup,!!status);
  const u=$("updated");
  u.textContent=new Date().toLocaleTimeString("tr-TR");
  u.classList.remove("flash");void u.offsetWidth;u.classList.add("flash");
}
function renderScanBars(status){
  const res=(status&&status.results)||{};
  const vals=Object.values(res); const total=vals.length||1;
  const counts={SIGNAL:0,NO_TRADE:0,DATA_MISSING:0};
  const active=[];
  for(const d of vals){
    counts[d.decision]=(counts[d.decision]||0)+1;
    if(d.decision==="SIGNAL")active.push(d);
  }
  const seg=(n,c)=>`<div style="width:${100*n/total}%;background:${c}"></div>`;
  $("bar").innerHTML=seg(counts.SIGNAL,"var(--win)")+
    seg(counts.NO_TRADE,"#C7CFDD")+seg(counts.DATA_MISSING,"var(--loss)");
  $("legend").innerHTML=
    `<span><span class="sw" style="background:var(--win)"></span><b>${counts.SIGNAL}</b> SIGNAL</span>`+
    `<span><span class="sw" style="background:#C7CFDD"></span><b>${counts.NO_TRADE}</b> NO_TRADE</span>`+
    `<span><span class="sw" style="background:var(--loss)"></span><b>${counts.DATA_MISSING}</b> DATA_MISSING</span>`+
    `<span><b>${vals.length}</b> tarandı</span>`;
  $("activeline").innerHTML=active.length?
    "<b>aktif:</b> "+active.map(d=>`${d.pair} ${d.direction==="LONG"?"L":"S"} (${num(d.rr,1)})`).join(" · "):
    "<b>aktif:</b> son taramada SIGNAL yok";
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
