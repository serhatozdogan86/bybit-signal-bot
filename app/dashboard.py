"""
Dashboard - botun kok URL'inde ("/") sundugu operasyon konsolu.
Telegram susturuldugunda sinyaller ve performans buradan izlenir.

Tasarim dili: botun kendi structured-log estetigi. Basliklar ve meta bilgiler
`key=value` cipleri olarak, veriler quote-board tarzi monospace ile gosterilir.
Harici bagimlilik yok: tek HTML, inline CSS/JS; veriyi botun kendi JSON
endpoint'lerinden (/performance, /signals, /status, /universe, /backup/info)
ceker ve secilen aralikta kendini yeniler.
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
  .ctrl{margin-left:auto;display:flex;gap:8px;align-items:center}
  select,button{background:var(--panel);color:var(--text);border:1px solid var(--line);
    border-radius:6px;padding:5px 10px;font-family:var(--mono);font-size:12px;cursor:pointer}
  button:hover,select:hover{border-color:var(--accent)}
  :focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  /* --- KPI quote-board --- */
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
        gap:1px;background:var(--line);border:1px solid var(--line);
        border-radius:10px;overflow:hidden;margin:20px 0}
  .kpi{background:var(--panel);padding:14px 16px}
  .kpi .lbl{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
  .kpi .val{font-family:var(--mono);font-size:24px;margin-top:2px}
  .kpi .sub{font-family:var(--mono);font-size:11px;color:var(--muted)}
  .pos{color:var(--win)} .neg{color:var(--loss)} .amb{color:var(--pend)}
  /* --- sections --- */
  h2{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
     margin:26px 0 10px;font-weight:600}
  h2 b{color:var(--accent);font-family:var(--mono);font-weight:500}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
  table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12.5px}
  th{color:var(--muted);text-align:left;font-weight:500;font-size:11px;
     letter-spacing:.06em;text-transform:uppercase;padding:10px 12px;
     border-bottom:1px solid var(--line);background:var(--panel2)}
  td{padding:8px 12px;border-bottom:1px solid var(--panel2);white-space:nowrap}
  tr:last-child td{border-bottom:0}
  .tblwrap{overflow-x:auto}
  .pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11px}
  .pill.WIN{background:rgba(76,195,138,.15);color:var(--win)}
  .pill.LOSS{background:rgba(229,83,75,.15);color:var(--loss)}
  .pill.PENDING,.pill.FILLED{background:rgba(232,180,76,.12);color:var(--pend)}
  .pill.NOT_FILLED,.pill.EXPIRED{background:rgba(124,138,165,.15);color:var(--muted)}
  .pill.AMBIGUOUS{background:rgba(108,160,240,.15);color:var(--info)}
  .pill.LONG{color:var(--win)} .pill.SHORT{color:var(--loss)}
  /* --- decision stacked bar --- */
  .bar{display:flex;height:14px;border-radius:7px;overflow:hidden;
       border:1px solid var(--line);margin:10px 0 6px}
  .bar div{height:100%}
  .legend{font-family:var(--mono);font-size:11.5px;color:var(--muted);
          display:flex;gap:16px;flex-wrap:wrap}
  .legend b{color:var(--text);font-weight:500}
  .reasons li{font-family:var(--mono);font-size:12px;color:var(--muted);
              padding:6px 12px;border-bottom:1px solid var(--panel2);list-style:none;
              display:flex;justify-content:space-between;gap:12px}
  .reasons li:last-child{border-bottom:0}
  .reasons b{color:var(--text);font-weight:500;flex-shrink:0}
  .empty{padding:18px;color:var(--muted);font-family:var(--mono);font-size:12.5px}
  .note{font-size:12px;color:var(--muted);margin-top:8px}
  a{color:var(--info)}
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

  <div class="kpis" id="kpis"></div>

  <h2><b>signals</b> — gölge takipteki sinyaller</h2>
  <div class="panel tblwrap"><div id="signals" class="empty">yükleniyor…</div></div>
  <p class="note">R = gerçekleşen risk katsayısı (WIN=+ödül/risk, LOSS=−1). Tahmini gölge muhasebesi; gerçek işlem sonucu değildir.</p>

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

  <h2><b>system</b></h2>
  <div class="loghead" style="border:1px solid var(--line);border-radius:10px;
       padding:12px 16px;background:var(--panel)" id="sysline"></div>
</div>

<script>
"use strict";
const $=id=>document.getElementById(id);
const fmtTs=s=>s?s.replace("T"," ").replace("Z","").slice(5,16):"—";
const num=(v,d=2)=>v==null?"—":Number(v).toFixed(d);

async function j(url){
  try{const r=await fetch(url);if(!r.ok)return null;return await r.json();}
  catch(e){return null;}
}

function kpi(lbl,val,cls="",sub=""){
  return `<div class="kpi"><div class="lbl">${lbl}</div>
    <div class="val ${cls}">${val}</div>
    <div class="sub">${sub}</div></div>`;
}

function renderKpis(perf,status,uni){
  const meta=(status&&status.meta)||{};
  const wr=perf&&perf.win_rate!=null?(perf.win_rate*100).toFixed(1)+"%":"—";
  const tr=perf?perf.total_r_multiple:null;
  const trCls=tr>0?"pos":tr<0?"neg":"";
  const ds=(perf&&perf.dataset)||{};
  $("kpis").innerHTML=
    kpi("Win rate",wr,"",perf?perf.decided_trades+" sonuçlanan":"")+
    kpi("Toplam R",tr==null?"—":(tr>0?"+":"")+num(tr),trCls,"gölge muhasebe")+
    kpi("Açık sinyal",perf?perf.open_signals:"—","amb","takipte")+
    kpi("Evren",uni?uni.count:"—","",uni?uni.mode:"")+
    kpi("Tarama",meta.scan_count??"—","","son: "+fmtTs(meta.last_scan_utc))+
    kpi("Arşiv",ds.candles_archived?(ds.candles_archived/1000).toFixed(1)+"k":"—","",
        (ds.decisions_recorded??0)+" karar");
}

function renderSignals(rows){
  if(!rows||!rows.length){$("signals").innerHTML=
    '<div class="empty">henüz izlenen sinyal yok — motor koşul bekliyor</div>';return;}
  const tr=rows.map(s=>{
    const r=s.r_multiple;
    const rCls=r>0?"pos":r<0?"neg":"";
    return `<tr><td>${s.id}</td><td>${s.pair}</td>
      <td><span class="pill ${s.direction}">${s.direction}</span></td>
      <td>${fmtTs(s.created_utc)}</td>
      <td><span class="pill ${s.outcome||s.status}">${s.outcome||s.status}</span></td>
      <td>${num(s.entry_min,4)}–${num(s.entry_max,4)}</td>
      <td>${num(s.stop_loss,4)}</td><td>${num(s.tp1,4)}</td>
      <td>${num(s.rr,2)}</td>
      <td class="${rCls}">${r==null?"—":(r>0?"+":"")+num(r)}</td></tr>`;}).join("");
  $("signals").className="";
  $("signals").innerHTML=`<table><thead><tr><th>#</th><th>parite</th><th>yön</th>
    <th>oluşturma</th><th>durum</th><th>entry</th><th>stop</th><th>tp1</th>
    <th>plan RR</th><th>R</th></tr></thead><tbody>${tr}</tbody></table>`;
}

function renderScan(status){
  const res=(status&&status.results)||{};
  const vals=Object.values(res);
  const total=vals.length||1;
  const counts={SIGNAL:0,NO_TRADE:0,DATA_MISSING:0};
  const reasons={};
  const active=[];
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
    `<span><b>${counts.SIGNAL}</b> SIGNAL</span>`+
    `<span><b>${counts.NO_TRADE}</b> NO_TRADE</span>`+
    `<span><b>${counts.DATA_MISSING}</b> DATA_MISSING</span>`+
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
    $("active").innerHTML='<div class="empty">son taramada SIGNAL yok — koşullar filtreleri geçmedi</div>';
  }
  const top=Object.entries(reasons).sort((a,b)=>b[1]-a[1]).slice(0,6);
  $("reasons").innerHTML=top.length?
    top.map(([k,v])=>`<li><span>${k}</span><b>${v}</b></li>`).join(""):
    '<li><span>veri bekleniyor</span></li>';
}

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

async function refresh(){
  const [perf,signals,status,uni,backup]=await Promise.all([
    j("/performance"),j("/signals?limit=100"),j("/status"),
    j("/universe"),j("/backup/info")]);
  renderKpis(perf,status,uni);
  renderSignals(signals);
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
