"""
Dashboard v2.8 - sicak tema + derinlikli grafik + tiklanabilir paneller.

v2.7 sartname yerlesimi korunur; uc tasarim karari eklenir:
1) SICAK ZEMIN: bembeyaz yerine "linen" paleti (#F5F1E8 zemin, #FFFEFA kart,
   sicak cizgi/golge tonlari) - uzun bakista goz yormaz.
2) DERINLIK: equity grafigi katmanli gradyan + cizgi altinda yumusak golge
   (canvas shadow plugin) + beyaz halkali WIN/LOSS noktalari -> "yuzen"
   premium his (kitsch 3D degil). SVG fallback ayni derinligi feDropShadow
   ile verir.
3) TIKLANABILIRLIK:
   - KPI kartlari tabloyu filtreler (Win Rate/Toplam R -> Sonuclanan,
     Acik Pozisyon -> Acik, Giris Isabeti -> Dolmayan, Evren -> Tumu)
   - Boru hatti asamasina tiklayinca o asamada elenen paritelerin listesi
     modal olarak acilir (son tarama verisinden)
   - Sinyal satirina tiklayinca detay karti: tum seviyeler (tp2/fill/exit
     dahil), gerceklesen R; parite son taramada aktif SIGNAL ise plan
     detaylari (invalidation, likidite notu, confluence) da eklenir
   - Yon bilancosu bloklari LONG/SHORT yon filtresini acar/kapar
   - Market yukselen/dusenler Bybit islem sayfasina baglanir
"""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>signal-engine // dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%232563EB'/%3E%3Cpath d='M6 22l6-7 4 4 8-10' stroke='%23fff' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root{
    --bg:#F5F1E8; --card:#FFFEFA; --card2:#F9F5EC; --line:#E6DECE;
    --text:#2A241B; --muted:#8A7F6C;
    --green:#16A34A; --green-bg:#E2F2E2; --green-ink:#14532D;
    --red:#DC2626;   --red-bg:#FBE7E2;   --red-ink:#7F1D1D;
    --amber:#D97706; --amber-bg:#FBEFD4; --amber-ink:#78350F;
    --blue:#2563EB;  --blue-bg:#E3EBFA;  --blue-ink:#1E3A8A;
    --grey:#98907F;  --grey-bg:#F0EBDF;
    --head:#4A4132;
    --sans:"Inter",Roboto,-apple-system,"SF Pro Text","Segoe UI",sans-serif;
    --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    --shadow:0 1px 2px rgba(88,70,38,.06),0 5px 14px rgba(88,70,38,.05);
    --shadow-hi:0 2px 4px rgba(88,70,38,.08),0 10px 24px rgba(88,70,38,.09);
    --pad:clamp(8px,1vh,14px);
  }
  *{box-sizing:border-box;margin:0}
  html,body{height:100%}
  body{background:var(--bg);color:var(--text);font-family:var(--sans);
       font-size:13px;line-height:1.45;overflow:hidden;
       font-variant-numeric:tabular-nums}
  .num{font-family:var(--mono);font-variant-numeric:tabular-nums;
       font-size:.94em;letter-spacing:-.01em}
  td.num{text-align:right}
  th.r{text-align:right}
  .app{display:grid;grid-template-rows:56px minmax(0,1fr) 24px;height:100vh;
       gap:10px;padding:10px 12px 6px;max-width:1920px;margin:0 auto}
  .statusbar{display:flex;align-items:center;gap:14px;font-family:var(--mono);
       font-size:10.5px;color:var(--muted);padding:0 6px;white-space:nowrap;
       overflow:hidden}
  .statusbar b{color:var(--text);font-weight:500}
  .statusbar .sep{color:var(--line)}
  .statusbar .right{margin-left:auto;color:var(--muted);
       overflow:hidden;text-overflow:ellipsis}
  .statusbar a{color:var(--info,#2B66C4)}
  .clickable{cursor:pointer;transition:transform .15s ease,box-shadow .15s ease}
  .clickable:hover{transform:translateY(-1px);box-shadow:var(--shadow-hi)}
  /* ============ HEADER ============ */
  .hdr{background:var(--card);border:1px solid var(--line);border-radius:11px;
       box-shadow:var(--shadow);display:flex;align-items:center;gap:16px;
       padding:0 16px}
  .logo{display:flex;align-items:center;gap:8px;font-weight:600;font-size:15px}
  .logo b{color:var(--blue);font-weight:700}
  .dot{width:9px;height:9px;border-radius:50%;background:var(--green)}
  .dot.err{background:var(--red)}
  @media (prefers-reduced-motion:no-preference){
    .dot{animation:pulse 2.4s ease-in-out infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
  }
  .hsum{flex:1;text-align:center;color:var(--muted);font-size:13.5px;
        overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .hsum b{color:var(--text);font-weight:600}
  .hsum .t{font-size:12.5px;margin-right:8px}
  .hctl{display:flex;gap:8px;align-items:center}
  select,button{background:var(--card);color:var(--text);
    border:1px solid var(--line);border-radius:8px;padding:5px 10px;
    font-family:var(--sans);font-size:12.5px;cursor:pointer}
  button:hover,select:hover{border-color:var(--blue)}
  :focus-visible{outline:2px solid var(--blue);outline-offset:2px}
  .icon{width:30px;padding:5px 0;text-align:center}
  /* ============ GRID ============ */
  .cols{display:grid;grid-template-columns:220px minmax(0,1fr) 300px;
        gap:10px;min-height:0}
  .col{display:flex;flex-direction:column;gap:10px;min-height:0}
  .card{background:var(--card);border:1px solid var(--line);border-radius:11px;
        box-shadow:var(--shadow);display:flex;flex-direction:column;min-height:0}
  .chead{padding:var(--pad) 14px 0;font-size:11px;font-weight:700;
         letter-spacing:.04em;text-transform:uppercase;color:var(--head);
         display:flex;align-items:baseline;gap:8px}
  .chead .tag{margin-left:auto;font-weight:400;font-size:10.5px;
              text-transform:none;letter-spacing:0}
  .cbody{padding:6px 14px var(--pad);min-height:0}
  .scroll{overflow-y:auto;scrollbar-width:thin}
  .fill{flex:1}
  .empty{color:var(--muted);font-size:12px;padding:6px 0}
  .pos{color:var(--green)} .neg{color:var(--red)} .amb{color:var(--amber)}
  /* ============ SOL ============ */
  .strat{font-size:12.5px;color:var(--muted)}
  .strat p{margin-bottom:6px}
  .strat b{color:var(--text);font-weight:600}
  .srow{display:flex;justify-content:space-between;padding:2px 0;
        border-bottom:1px dashed var(--line)}
  .srow:last-child{border-bottom:0}
  .srow b{font-weight:600;color:var(--text)}
  .pipe{overflow-y:auto;scrollbar-width:thin}
  .step{padding:5px 6px;margin:0 -6px;border-radius:8px;cursor:pointer;
        transition:background .12s}
  .step:hover{background:var(--card2)}
  .step .h{display:flex;justify-content:space-between;font-size:12px;
           font-weight:600}
  .step .h .n{color:var(--muted);font-weight:500}
  .step .d{font-size:10.5px;color:var(--muted);line-height:1.3}
  .step .g{height:5px;border-radius:3px;background:var(--grey-bg);
           margin-top:3px;overflow:hidden}
  .step .g div{height:100%;border-radius:3px}
  .psummary .bar{display:flex;height:12px;border-radius:6px;overflow:hidden;
                 border:1px solid var(--line)}
  .psummary .bar div{height:100%}
  .psummary .lbl{font-size:10px;color:var(--muted);margin-top:3px;
                 display:flex;justify-content:space-between}
  /* ============ KPI ============ */
  .kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}
  .kpi{background:var(--card);border:1px solid var(--line);border-radius:11px;
       box-shadow:var(--shadow);padding:8px 14px 7px;position:relative}
  .kpi .lbl{font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;
            color:var(--head);font-weight:700}
  .kpi .val{font-size:clamp(19px,2.4vh,24px);font-weight:600;margin-top:1px}
  .kpi .sub{font-size:11px;color:var(--muted);white-space:nowrap;
            overflow:hidden;text-overflow:ellipsis}
  .kpi .tr{position:absolute;top:8px;right:12px;font-size:12px}
  /* KPI tooltip balonu */
  .kpi::after{content:attr(data-tip);position:absolute;top:calc(100% + 8px);
    left:50%;transform:translateX(-50%);background:#2A241B;color:#FBF8F2;
    padding:8px 11px;border-radius:9px;font-size:11.8px;line-height:1.45;
    font-weight:400;width:max-content;max-width:250px;white-space:normal;
    opacity:0;visibility:hidden;pointer-events:none;z-index:40;
    box-shadow:0 8px 24px rgba(42,36,27,.28);
    transition:opacity .15s ease .25s,visibility 0s .4s}
  .kpi::before{content:"";position:absolute;top:calc(100% + 2px);left:50%;
    transform:translateX(-50%);border:6px solid transparent;
    border-bottom-color:#2A241B;opacity:0;visibility:hidden;z-index:41;
    transition:opacity .15s ease .25s,visibility 0s .4s}
  .kpi:hover::after,.kpi:hover::before,
  .kpi:focus-visible::after,.kpi:focus-visible::before{
    opacity:1;visibility:visible;transition-delay:.25s}
  .kpi:last-child::after{left:auto;right:0;transform:none}
  /* kart basligi tooltip'i (sola hizali, genis) */
  .tipwrap{position:relative;cursor:help}
  .tipwrap .i{color:var(--blue);font-size:10px;vertical-align:1px}
  .tipwrap::after{content:attr(data-tip);position:absolute;
    top:calc(100% + 9px);left:0;transform:none;background:#2A241B;
    color:#FBF8F2;padding:9px 12px;border-radius:9px;font-size:11.8px;
    line-height:1.5;font-weight:400;width:max-content;max-width:310px;
    white-space:normal;text-transform:none;letter-spacing:0;
    opacity:0;visibility:hidden;pointer-events:none;z-index:40;
    box-shadow:0 8px 24px rgba(42,36,27,.28);
    transition:opacity .15s ease .25s,visibility 0s .4s}
  .tipwrap::before{content:"";position:absolute;top:calc(100% + 3px);
    left:16px;border:6px solid transparent;border-bottom-color:#2A241B;
    opacity:0;visibility:hidden;z-index:41;
    transition:opacity .15s ease .25s,visibility 0s .4s}
  .tipwrap:hover::after,.tipwrap:hover::before,
  .tipwrap:focus-visible::after,.tipwrap:focus-visible::before{
    opacity:1;visibility:visible;transition-delay:.25s}
  /* ============ orta grafik satiri ============ */
  .midrow{display:grid;grid-template-columns:1.35fr 1fr;gap:10px;
          min-height:clamp(180px,26vh,300px)}
  .chartwrap{position:relative;flex:1;min-height:0}
  .chartwrap canvas{position:absolute;inset:0;width:100%!important;
                    height:100%!important}
  .curve svg{width:100%;height:100%;display:block}
  .duel{display:flex;flex-direction:column;gap:10px;justify-content:center;flex:1}
  .drow{padding:6px 8px;margin:0 -8px;border-radius:9px;cursor:pointer;
        transition:background .12s}
  .drow:hover{background:var(--card2)}
  .drow.on{background:var(--blue-bg)}
  .drow .top{display:flex;justify-content:space-between;font-size:12px;
             margin-bottom:3px}
  .drow .top b{font-weight:700}
  .drow .track{display:flex;height:16px;border-radius:8px;overflow:hidden;
               background:var(--grey-bg);border:1px solid var(--line)}
  .drow .track div{height:100%}
  .dstat{font-size:11.5px;color:var(--muted);margin-top:2px}
  .axis{display:flex;justify-content:space-between;font-size:10.5px;
        color:var(--muted);border-top:1px dashed var(--line);padding-top:4px}
  /* ============ tablo/badge ============ */
  table{width:100%;border-collapse:collapse;font-size:12.5px}
  th{color:var(--head);text-align:left;font-weight:700;font-size:10.5px;
     letter-spacing:.05em;text-transform:uppercase;padding:7px 10px;
     border-bottom:1px solid var(--line);background:var(--card2);
     position:sticky;top:0;z-index:1}
  td{padding:5px 10px;border-bottom:1px solid var(--card2);white-space:nowrap}
  tbody tr{cursor:pointer}
  tbody tr:nth-child(even) td{background:rgba(249,245,236,.55)}
  tbody tr:hover td{background:var(--card2)}
  @keyframes tickU{0%{background:rgba(22,163,74,.28)}100%{background:transparent}}
  @keyframes tickD{0%{background:rgba(220,38,38,.28)}100%{background:transparent}}
  td.tick-up{animation:tickU 1.1s ease-out}
  td.tick-down{animation:tickD 1.1s ease-out}
  tr:last-child td{border-bottom:0}
  tr.dim td{opacity:.55}
  .badge{display:inline-block;padding:1px 9px;border-radius:99px;
         font-size:11px;font-weight:600}
  .b-LONG{background:var(--green-bg);color:var(--green-ink)}
  .b-SHORT{background:var(--red-bg);color:var(--red-ink)}
  .b-WIN{background:var(--green-bg);color:var(--green-ink)}
  .b-LOSS{background:var(--red-bg);color:var(--red-ink)}
  .b-PENDING,.b-FILLED{background:var(--amber-bg);color:var(--amber-ink)}
  .b-NOT_FILLED,.b-EXPIRED{background:var(--grey-bg);color:#5B5344}
  .b-AMBIGUOUS{background:var(--blue-bg);color:var(--blue-ink)}
  .age{font-size:10px;color:var(--muted)}
  .chips{display:flex;gap:6px;align-items:center}
  .chip{background:var(--card2);border:1px solid var(--line);
        color:var(--muted);border-radius:99px;padding:1.5px 10px;
        font-size:11px;cursor:pointer;font-weight:500}
  .chip.on{border-color:var(--blue);color:var(--blue);background:var(--blue-bg)}
  .chip.dir{border-color:var(--amber);color:var(--amber-ink);
            background:var(--amber-bg)}
  /* ============ SAG ============ */
  .majors{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  .mj{background:var(--card2);border:1px solid var(--line);border-radius:9px;
      padding:5px 10px}
  .mj .sym{font-size:11px;color:var(--muted);font-weight:600}
  .mj .px{font-size:16.5px;font-weight:600}
  .mj .row{font-size:11.5px}
  .fng{margin-top:8px}
  .fng .lbl{display:flex;justify-content:space-between;font-size:11.5px;
            color:var(--muted)}
  .fng .lbl b{color:var(--text)}
  .fng .track{position:relative;height:10px;border-radius:5px;margin-top:4px;
    background:linear-gradient(90deg,#DC2626,#F59E0B 40%,#B9B29F 52%,
                               #84CC16 68%,#16A34A);
    border:1px solid var(--line)}
  .fng .mark{position:absolute;top:-3px;width:3px;height:16px;
             background:var(--text);border-radius:2px}
  .breadth{font-size:11.5px;color:var(--muted);margin-top:6px}
  .movers{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:7px;
          font-size:11.5px}
  .movers h4{font-size:10px;color:var(--head);letter-spacing:.05em;
             font-weight:600;margin-bottom:2px;text-transform:uppercase}
  .movers a{display:flex;justify-content:space-between;color:var(--text);
            text-decoration:none;padding:1px 0}
  .movers a:hover{color:var(--blue)}
  .pulse{margin-top:7px;font-size:12px;background:var(--blue-bg);
         border-left:3px solid var(--blue);border-radius:7px;padding:6px 9px}
  .pulse .tg{font-size:10px;color:var(--muted)}
  .review{font-size:12.5px}
  .review .rts{font-size:10.5px;color:var(--muted)}
  .review .txt{display:-webkit-box;-webkit-line-clamp:6;
               -webkit-box-orient:vertical;overflow:hidden;margin:3px 0}
  .review.open .txt{display:block;-webkit-line-clamp:unset;overflow:visible}
  .review .txt p{margin-bottom:5px}
  .review .warnline{border-left:3px solid var(--red);padding-left:7px;
                    background:var(--red-bg);border-radius:4px}
  .more{color:var(--blue);font-size:11.5px;cursor:pointer;font-weight:500}
  /* portfoy simulasyonu */
  .pf .inputs{display:flex;gap:8px;align-items:center;font-size:11.5px;
              color:var(--muted);flex-wrap:wrap}
  .pf input{width:78px;background:var(--card2);border:1px solid var(--line);
            border-radius:7px;padding:3px 7px;font-family:var(--sans);
            font-size:12.5px;color:var(--text);
            font-variant-numeric:tabular-nums}
  .pf input:focus{border-color:var(--blue);outline:none}
  .pf .bal{margin-top:7px;background:var(--card2);border:1px solid var(--line);
           border-radius:9px;padding:6px 10px}
  .pf .bal .b{font-size:20px;font-weight:700}
  .pf .bal .p{font-size:11px;font-weight:600}
  .pf .prow{display:flex;justify-content:space-between;align-items:baseline;
            padding:3.5px 0;border-bottom:1px dashed var(--line);
            font-size:12px}
  .pf .prow:last-of-type{border-bottom:0}
  .pf .prow .w{color:var(--muted);font-weight:600;width:48px}
  .pf .prow .d{font-weight:700}
  .pf .prow .c{color:var(--muted);font-size:9.8px}
  .pf .foot{font-size:10px;color:var(--muted);margin-top:4px}
  .news li{list-style:none;padding:5px 0;border-bottom:1px solid var(--card2)}
  .news li:last-child{border-bottom:0}
  .news a{color:var(--text);text-decoration:none;font-size:12.5px;
          line-height:1.35;display:block}
  .news a:hover{color:var(--blue)}
  .news .src{font-size:10px;color:var(--muted)}
  /* ============ overlay & modal ============ */
  .ovl{position:fixed;inset:0;background:rgba(42,36,27,.45);display:none;
       align-items:center;justify-content:center;z-index:50;padding:20px}
  .ovl.show{display:flex}
  .sheet{background:var(--card);border-radius:14px;max-width:640px;width:100%;
         max-height:82vh;overflow-y:auto;padding:18px 22px;
         box-shadow:0 16px 50px rgba(42,36,27,.3)}
  .sheet h3{font-size:16px;font-weight:600;margin-bottom:8px;color:var(--blue)}
  .sheet dt{font-weight:600;font-size:12.5px;margin-top:9px}
  .sheet dd{margin:1px 0 0;color:var(--muted);font-size:12px}
  .sheet .warn{margin-top:12px;padding:9px 12px;border-left:3px solid var(--red);
               background:var(--red-bg);border-radius:7px;font-size:12px}
  .kvgrid{display:grid;grid-template-columns:1fr 1fr;gap:4px 18px;
          font-size:13px;margin-top:6px}
  .kvgrid .k{color:var(--muted)}
  .kvgrid .v{text-align:right;font-weight:600}
  .taglist{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
  .note{margin-top:10px;font-size:11.5px;background:var(--card2);
        border-radius:7px;padding:7px 10px;color:var(--muted)}
  .note b{color:var(--text)}
  a{color:var(--blue)}
  /* buyuk yazi modu: tek-ekran kilidi kalkar, sayfa kayar; uzun listeler
     yine kendi icinde kayar (55vh tavan) */
  #tipbox{position:fixed;display:none;background:#2A241B;color:#FBF8F2;
    padding:9px 12px;border-radius:9px;font-size:11.8px;line-height:1.5;
    max-width:320px;z-index:60;box-shadow:0 8px 24px rgba(42,36,27,.28);
    pointer-events:none}
  .step{outline:none}
  body.zoomed{overflow:auto}
  body.zoomed .app{height:auto;min-height:100vh}
  body.zoomed .scroll{max-height:55vh}
  body.zoomed .midrow{min-height:280px}
  @media (max-height:940px){
    :root{--pad:7px}
    body{font-size:12.5px}
    .kpi .val{font-size:17px}
    .midrow{min-height:clamp(160px,24vh,240px)}
    .step .d{display:none}
  }
  @media (max-width:1180px){
    body{overflow:auto}
    .app{height:auto}
    .cols{grid-template-columns:1fr}
    .kpis{grid-template-columns:repeat(auto-fit,minmax(140px,1fr))}
    .scroll{max-height:50vh}
  }
</style>
</head>
<body>
<div class="app">
  <header class="hdr">
    <div class="logo"><span class="dot" id="dot"></span>signal<b>-engine</b></div>
    <div class="hsum"><span class="t" id="updated">--:--:--</span><span id="hsum">yükleniyor…</span></div>
    <div class="hctl">
      <select id="fs" title="yazı boyutu">
        <option value="1">Yazı: Normal</option>
        <option value="1.15">Büyük</option>
        <option value="1.3">Çok Büyük</option>
      </select>
      <select id="iv" title="yenileme aralığı">
        <option value="30000">30 sn</option>
        <option value="60000" selected>60 sn</option>
        <option value="300000">5 dk</option>
      </select>
      <button id="refresh" class="icon" title="Şimdi yenile">⟳</button>
      <button id="calcBtn" class="icon" title="Pozisyon Hesaplayıcı">🧮</button>
      <button id="howtoBtn" class="icon" title="Nasıl okunur?">⚙</button>
    </div>
  </header>

  <div class="cols">
    <div class="col">
      <div class="card">
        <div class="chead">Strateji <span class="tag">strateji sözleşmesi</span></div>
        <div class="cbody strat">
          <p><b>Conservative swing.</b> Yapı önce gelir; indikatörler yalnız teyittir. Kenar net değilse karar <b>NO_TRADE</b>.</p>
          <div class="srow"><span>Zaman dilimi</span><b>4H → 15m</b></div>
          <div class="srow"><span>Hacim teyidi</span><b>≥ 1.5× ort.</b></div>
          <div class="srow"><span>Risk/ödül bandı</span><b>2.0 – 6.0</b></div>
          <div class="srow"><span>Yön kapısı</span><b>BTC 4H rejimi</b></div>
          <div class="srow"><span>Setup</span><b>retest · sweep</b></div>
          <div class="srow"><span>Evren</span><b id="stratUni">top-150</b></div>
        </div>
      </div>
      <div class="card">
        <div class="chead">Filtre Boru Hattı <span class="tag" id="pipeMeta"></span></div>
        <div class="cbody pipe fill" id="pipe"><div class="empty">tarama bekleniyor…</div></div>
        <div class="cbody psummary">
          <div class="bar" id="pbar"></div>
          <div class="lbl"><span>elenen →</span><span id="plbl">SIGNAL</span></div>
        </div>
      </div>
      <div class="card fill pf">
        <div class="chead"><span class="tipwrap" tabindex="0" data-tip="Gölge sinyalleri para yönetimi diline çevirir. Model: her kapanan işlemde bakiyenin, girdiğin Risk % kadarı riske atılır; sonuç bakiye × (1 + risk × R) olarak İŞLEM KAPANIŞ SIRASIYLA bileşik işler (örn. 10.000$ ve %1 riskte +2.2R kazanç = +220$, −1R kayıp = −100$). Bugün / 7 gün / 30 gün satırları, o pencerede kapanan işlemlerin bakiyeye net etkisidir; 'açılan' o gün üretilen sinyal sayısıdır (günler UTC). Başlangıç $ ve Risk % alanlarını buradan değiştirebilirsin — tarayıcında saklanır. Kayma/komisyon yoktur; simülasyondur, gerçek para değildir.">Portföy Simülasyonu <span class="i">ⓘ</span></span> <span class="tag">gölge · bileşik</span></div>
        <div class="cbody fill scroll" id="pf">
          <div class="inputs">
            <label>Başlangıç $ <input type="number" id="pfCap" min="1" step="100" value="10000"></label>
            <label>Risk % <input type="number" id="pfRisk" min="0.1" max="10" step="0.1" value="1.0" style="width:52px"></label>
          </div>
          <div id="pfBody"><div class="empty">hesaplanıyor…</div></div>
        </div>
      </div>
    </div>

    <div class="col">
      <div class="kpis" id="kpis"></div>
      <div class="midrow">
        <div class="card">
          <div class="chead">Kümülatif R (Equity) <span class="tag" id="eqStats">yeşil WIN · kırmızı LOSS</span></div>
          <div class="cbody fill chartwrap curve" id="curveWrap"><canvas id="eqChart"></canvas></div>
        </div>
        <div class="card">
          <div class="chead"><span class="tipwrap" tabindex="0" data-tip="Aynı motorun LONG ve SHORT taraflarının ayrı karnesi. Her yön için: sonuçlanan işlemlerin R toplamı (büyük rakam ve çubuk — 0 ekseninden sağa yeşil kâr, sola kırmızı zarar; ölçek iki yönün mutlak maksimumudur), W/L sayıları ve açık pozisyon adedi. Bir taraf sistematik eksideyse motor rejime ters işlem üretiyor demektir — v3.0 market gate tam olarak bu verinin üzerine inşa edildi. Bloğa tıklayınca sinyal tablosu o yönle filtrelenir.">Yön Bilançosu <span class="i">ⓘ</span></span> <span class="tag">tıkla → yön filtresi</span></div>
          <div class="cbody fill duel" id="duel"></div>
        </div>
      </div>
      <div class="card fill">
        <div class="chead">Sinyaller · Gölge Takip <span class="tag" style="margin-left:0">satıra tıkla → detay</span>
          <span class="chips" id="chips" style="margin-left:auto"></span></div>
        <div class="cbody fill scroll" id="signals" style="padding:0 0 4px"><div class="empty" style="padding:8px 14px">yükleniyor…</div></div>
      </div>
    </div>

    <div class="col">
      <div class="card">
        <div class="chead">Piyasa Nabzı <span class="tag" id="mupd">canlı metrikler</span></div>
        <div class="cbody" id="market"><div class="empty">yükleniyor…</div></div>
      </div>
      <div class="card" style="flex:1.05">
        <div class="chead">Saatlik Değerlendirme <span class="tag">hourly_review · otomatik</span></div>
        <div class="cbody fill scroll review" id="review"><div class="empty">ilk değerlendirme bekleniyor…</div></div>
      </div>
      <div class="card fill">
        <div class="chead">Haber Akışı <span class="tag">kripto haber · dış kaynak</span></div>
        <div class="cbody fill scroll"><ul class="news" id="news"><li class="empty">yükleniyor…</li></ul></div>
      </div>
    </div>
  </div>

  <footer class="statusbar" id="statusbar">yükleniyor…</footer>
</div>

<div id="tipbox"></div>

<div id="overlay" class="ovl">
  <div class="sheet">
    <h3>Nasıl okunur?</h3>
    <dl>
      <dt>R (risk katsayısı)</dt>
      <dd>Her işlemin sonucu, riske atılan birim cinsinden: kayıp = −1R, kazanç = ödül/risk oranı kadar (+2.2R gibi).</dd>
      <dt>Win rate ve başabaş</dt>
      <dd>Kazançlar kayıplardan büyükse %50 isabet gerekmez. Başabaş = 1 / (1 + ort. kazanç R).</dd>
      <dt>Filtre boru hattı</dt>
      <dd>DATA → REGIME → HTF → LTF → VOLUME → RR; herhangi biri geçilemezse NO_TRADE. Aşamaya tıklayınca o aşamada elenen pariteler listelenir.</dd>
      <dt>PENDING → FILLED → WIN/LOSS</dt>
      <dd>Girişe gelmesi 6 saat beklenir; gelirse 48 saat izlenir. Önce stop = LOSS, önce hedef = WIN. NOT_FILLED orana dahil edilmez; AMBIGUOUS sayılmaz.</dd>
      <dt>Piyasa Nabzı / Saatlik Değerlendirme</dt>
      <dd>Kural tabanlı otomatik üretimdir (canlı insan/LLM yorumu değildir). Korku &amp; Açgözlülük: alternative.me.</dd>
    </dl>
    <div class="warn">Tüm sonuçlar <b>gölge muhasebedir</b>: varsayımsal giriş, kayma/komisyon yok, gerçek emir yok. Geçmiş performans garanti değildir; yatırım tavsiyesi değildir. Haber başlıkları dış kaynaktan aynen aktarılır.</div>
    <div style="text-align:right;margin-top:12px"><button id="howtoClose">Kapat</button></div>
  </div>
</div>

<div id="calc" class="ovl">
  <div class="sheet" style="max-width:560px">
    <h3><span class="tipwrap" tabindex="0" data-tip="Risk-first hesap: önce kaç $ riske atacağın belirlenir (bakiye × risk %), pozisyon büyüklüğü buradan TÜRETİLİR: miktar = risk$ / |entry − stop|. Kaldıraç kârı değil yalnızca bağlanan marjini değiştirir — stop'taki kayıp her kaldıraçta aynı risk$'dır. Likidasyon kontrolü, seçtiğin kaldıraçta likidasyonun stop'tan ÖNCE gelip gelmeyeceğini sınar (yaklaşık, izole marjin varsayımı). Değerler yaklaşıktır; yatırım tavsiyesi değildir.">Pozisyon Hesaplayıcı <span class="i">ⓘ</span></span></h3>
    <div class="pf" style="font-size:12px">
      <div class="inputs" style="margin-bottom:8px">
        <label>Sinyal <select id="cSig" style="max-width:170px"><option value="">— manuel —</option></select></label>
      </div>
      <div class="inputs">
        <label>Bakiye $ <input type="number" id="cBal" min="1" step="100"></label>
        <label>Risk % <input type="number" id="cRisk" min="0.1" max="10" step="0.1" style="width:52px"></label>
        <label>Kaldıraç <input type="number" id="cLev" min="1" max="50" step="1" value="5" style="width:52px"></label>
        <label>Yön <select id="cDir"><option>LONG</option><option>SHORT</option></select></label>
      </div>
      <div class="inputs" style="margin-top:6px">
        <label>Entry <input type="number" id="cEntry" step="any"></label>
        <label>Stop <input type="number" id="cStop" step="any"></label>
        <label>TP1 <input type="number" id="cTp1" step="any"></label>
        <label>TP2 <input type="number" id="cTp2" step="any"></label>
      </div>
      <div id="cOut" style="margin-top:10px"></div>
    </div>
    <div style="text-align:right;margin-top:12px"><button id="calcClose">Kapat</button></div>
  </div>
</div>

<div id="modal" class="ovl">
  <div class="sheet">
    <h3 id="modalTitle"></h3>
    <div id="modalBody"></div>
    <div style="text-align:right;margin-top:12px"><button id="modalClose">Kapat</button></div>
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
let PRICES={},PREV_PRICES={};
const fmtPx=v=>v==null?"—":Number(v).toLocaleString("en-US",
  {maximumFractionDigits:v>=100?2:v>=1?4:6});
const PREV={};
function arrow(key,val){
  const p=PREV[key];PREV[key]=val;
  if(p==null||val==null||p===val)return '<span class="tr" style="color:var(--grey)">–</span>';
  return val>p?'<span class="tr pos">▲</span>':'<span class="tr neg">▼</span>';
}
let LAST_STATUS=null;

/* ---------- modal ---------- */
function openModal(title,html){
  $("modalTitle").innerHTML=title;$("modalBody").innerHTML=html;
  $("modal").classList.add("show");
}
["overlay","modal","calc"].forEach(id=>{
  $(id).addEventListener("click",e=>{if(e.target.id===id)$(id).classList.remove("show");});
});
$("modalClose").addEventListener("click",()=>$("modal").classList.remove("show"));
$("calcClose").addEventListener("click",()=>$("calc").classList.remove("show"));
$("calcBtn").addEventListener("click",()=>openCalc(null));
["cBal","cRisk","cLev","cDir","cEntry","cStop","cTp1","cTp2"].forEach(id=>
  $(id).addEventListener("input",calcRun));
$("cSig").addEventListener("change",()=>{
  const s=SIGNALS.find(x=>String(x.id)===$("cSig").value);
  if(s)calcFill(s);});
$("howtoBtn").addEventListener("click",()=>$("overlay").classList.add("show"));
$("howtoClose").addEventListener("click",()=>$("overlay").classList.remove("show"));
document.addEventListener("keydown",e=>{
  if(e.key==="Escape"){$("overlay").classList.remove("show");$("modal").classList.remove("show");$("calc").classList.remove("show");}});

/* ---------- header ---------- */
function renderHeader(perf,status){
  const el=$("hsum");
  if(!status){el.innerHTML="⚠ bota ulaşılamıyor — servis uyanıyor olabilir (30-50 sn)";return;}
  if(!perf||!perf.decided_trades){el.innerHTML="<b>Motor çalışıyor</b> · henüz sonuçlanan sinyal yok — filtreler koşul bekliyor";return;}
  const wr=(perf.win_rate*100).toFixed(1),tr=perf.total_r_multiple;
  const w=(perf.closed_by_outcome||{}).WIN||{count:0,sum_r:0};
  const be=w.count?(100/(1+(w.sum_r/w.count))).toFixed(1):null;
  const pos=be&&Number(wr)>Number(be);
  el.innerHTML=`<b>${perf.decided_trades}</b> sinyal sonuçlandı · isabet <b>%${wr}</b>${be?" (başabaş ~%"+be+")":""} · toplam <b class="${tr>=0?"pos":"neg"}">${(tr>0?"+":"")+num(tr)}R</b> · ${pos?'<span class="pos">eşiğin üzerinde</span>':'<span class="neg">eşiğin altında</span>'} · n<30, hüküm için erken`;
}

/* ---------- KPI (tiklanabilir -> tablo filtresi) ---------- */
function renderKpis(perf,status,uni,signals){
  const meta=(status&&status.meta)||{};
  const cbo=(perf&&perf.closed_by_outcome)||{};
  const w=cbo.WIN||{count:0,sum_r:0},l=cbo.LOSS||{count:0,sum_r:0};
  const wrV=perf&&perf.win_rate!=null?perf.win_rate*100:null;
  const be=w.count?(100/(1+(w.sum_r/w.count))).toFixed(1):null;
  const trV=perf?perf.total_r_multiple:null;
  const filled=(signals||[]).filter(s=>["WIN","LOSS","AMBIGUOUS","FILLED"].includes(OUT(s))).length;
  const nf=(signals||[]).filter(s=>OUT(s)==="NOT_FILLED").length;
  const frV=(filled+nf)?100*filled/(filled+nf):null;
  const openV=perf?perf.open_signals:null;
  const TIPS={
    "Win Rate":"Sonuçlanan (WIN+LOSS) sinyaller içinde kazananların oranı — NOT_FILLED hesaba katılmaz. Alt satırdaki başabaş, kâra geçiş eşiğidir: 1 / (1 + ortalama kazanç R). Win rate bu eşiğin üzerindeyse sistem artıdadır. · tıkla → sonuçlananları filtrele",
    "Toplam R":"Tüm sonuçlanan işlemlerin R toplamı. R = riske atılan birim: kayıp −1R, kazanç ödül/risk oranı kadar (+2.2R gibi). Alt satır: brüt kazanç / brüt kayıp. Para değil, risk birimi sayar — pariteler böyle karşılaştırılır. · tıkla → sonuçlananları filtrele",
    "Açık Pozisyon":"Gölge takipte hâlâ sonuçlanmamış sinyaller: PENDING (girişe gelmesi bekleniyor, 6 sa) + FILLED (dolu, 48 sa izlemede). · tıkla → açıkları filtrele",
    "Giriş İsabeti":"Üretilen sinyallerden fiyatı giriş bölgesine gelip dolanların oranı. NOT_FILLED = 6 saat içinde fiyat girişe hiç uğramadı; kazanç/kayıp oranına dahil edilmez. · tıkla → dolmayanları filtrele",
    "Taranan Evren":"24s hacme göre her gün yeniden seçilen parite sayısı ve bugüne kadarki tarama turu. Her tur ~15 dakikada bir tüm evreni 7 aşamalı filtreden geçirir. · tıkla → tüm sinyaller"};
  const kpi=(f,lbl,val,cls,sub,tr)=>`<div class="kpi clickable" data-f="${f}"
    data-tip="${TIPS[lbl]||""}" tabindex="0">${tr||""}
    <div class="lbl">${lbl}</div><div class="val num ${cls||""}">${val}</div>
    <div class="sub">${sub||""}</div></div>`;
  $("kpis").innerHTML=
    kpi("DONE","Win Rate",wrV==null?"—":wrV.toFixed(1)+"%","",
        be?`başabaş ~%${be}`:"",arrow("wr",wrV))+
    kpi("DONE","Toplam R",trV==null?"—":(trV>0?"+":"")+num(trV),
        trV>0?"pos":trV<0?"neg":"",`+${num(w.sum_r)} / −${num(Math.abs(l.sum_r))}`,
        arrow("tr",trV))+
    kpi("OPEN","Açık Pozisyon",openV==null?"—":openV,"amb","gölge takipte",
        arrow("open",openV))+
    kpi("NF","Giriş İsabeti",frV==null?"—":Math.round(frV)+"%","",
        `${filled} doldu / ${nf} değil`,arrow("fr",frV))+
    kpi("ALL","Taranan Evren",uni?uni.count:"—","",
        (uni?uni.mode:"")+" · "+(meta.scan_count??"—")+" tarama",null);
  $("kpis").querySelectorAll(".kpi").forEach(k=>k.addEventListener("click",()=>{
    FILTER=k.dataset.f;renderChips();renderSignals();}));
}

/* ---------- equity: derinlikli Chart.js + SVG fallback ---------- */
let eqChart=null;
const shadowPlugin={id:"lineShadow",
  beforeDatasetDraw(c,args){
    if(args.index!==0)return;
    const x=c.ctx;x.save();
    x.shadowColor="rgba(37,99,235,.30)";x.shadowBlur=10;x.shadowOffsetY=5;},
  afterDatasetDraw(c,args){if(args.index===0)c.ctx.restore();}};
function renderCurve(signals){
  const done=(signals||[]).filter(s=>["WIN","LOSS"].includes(OUT(s)))
    .sort((a,b)=>(a.closed_utc||a.created_utc||"").localeCompare(b.closed_utc||b.created_utc||""));
  const wrap=$("curveWrap");
  if(!done.length){wrap.innerHTML='<div class="empty">henüz sonuçlanan sinyal yok</div>';eqChart=null;return;}
  let c=0;const data=done.map(s=>c+=(s.r_multiple||0));
  // kurumsal metrikler: profit factor, beklenti, maks. drawdown
  const gw=done.filter(s=>s.r_multiple>0).reduce((a,s)=>a+s.r_multiple,0);
  const gl=Math.abs(done.filter(s=>s.r_multiple<0).reduce((a,s)=>a+s.r_multiple,0));
  const pf=gl?gw/gl:null;
  const exp=data[data.length-1]/done.length;
  let peak=0,maxDD=0;
  for(const v of data){peak=Math.max(peak,v);maxDD=Math.max(maxDD,peak-v);}
  const st=$("eqStats");
  if(st)st.innerHTML=`PF <b class="num">${pf==null?"∞":num(pf,2)}</b> · beklenti <b class="num">${(exp>0?"+":"")+num(exp,2)}R</b>/işlem · maksDD <b class="num neg">−${num(maxDD,2)}R</b>`;
  const labels=done.map((s,i)=>i+1);
  const ptCol=done.map(s=>OUT(s)==="WIN"?"#16A34A":"#DC2626");
  const tips=done.map(s=>`${s.pair} ${s.direction} ${OUT(s)} ${(s.r_multiple>0?"+":"")+num(s.r_multiple)}R`);
  if(window.Chart){
    if(!document.getElementById("eqChart")){wrap.innerHTML='<canvas id="eqChart"></canvas>';eqChart=null;}
    const ctx=$("eqChart").getContext("2d");
    const H=wrap.clientHeight||240;
    const grad=ctx.createLinearGradient(0,0,0,H);
    grad.addColorStop(0,"rgba(37,99,235,.26)");
    grad.addColorStop(.55,"rgba(37,99,235,.10)");
    grad.addColorStop(1,"rgba(37,99,235,0)");
    const cfg={type:"line",
      data:{labels,datasets:[
        {data,borderColor:"#2563EB",borderWidth:2.5,fill:true,
         backgroundColor:grad,tension:.35,
         pointRadius:4,pointHoverRadius:6,
         pointBackgroundColor:ptCol,pointBorderColor:"#FFFEFA",
         pointBorderWidth:2},
        {data:labels.map(()=>0),borderColor:"#B7AE9A",borderWidth:1,
         borderDash:[4,4],pointRadius:0,fill:false}]},
      options:{responsive:true,maintainAspectRatio:false,animation:false,
        plugins:{legend:{display:false},
          tooltip:{callbacks:{label:i=>i.datasetIndex===0?tips[i.dataIndex]+
            " · küm "+(data[i.dataIndex]>0?"+":"")+num(data[i.dataIndex])+"R":""}}},
        scales:{x:{display:false},
          y:{grid:{color:"#F0EAD9"},border:{display:false},
             ticks:{font:{size:10},color:"#8A7F6C",
             callback:v=>(v>0?"+":"")+v+"R"}}}},
      plugins:[shadowPlugin]};
    if(eqChart){eqChart.data=cfg.data;eqChart.update("none");}
    else eqChart=new Chart(ctx,cfg);
    return;
  }
  const W=560,H2=220,P=34;
  const pts=[[0,0]].concat(data.map((v,i)=>[i+1,v]));
  const ys=pts.map(p=>p[1]);const ymin=Math.min(0,...ys),ymax=Math.max(0,...ys);
  const yr=(ymax-ymin)||1;
  const X=i=>P+(W-P-8)*i/(pts.length-1||1);
  const Y=v=>10+(H2-24)*(1-(v-ymin)/yr);
  const path=pts.map((p,i)=>(i?"L":"M")+X(p[0]).toFixed(1)+" "+Y(p[1]).toFixed(1)).join(" ");
  const dots=done.map((s,i)=>`<circle cx="${X(i+1)}" cy="${Y(data[i])}" r="4" fill="${ptCol[i]}" stroke="#FFFEFA" stroke-width="2"><title>${tips[i]}</title></circle>`).join("");
  wrap.innerHTML=`<svg viewBox="0 0 ${W} ${H2}" preserveAspectRatio="none">
    <defs><filter id="ds"><feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#2563EB" flood-opacity=".3"/></filter></defs>
    <line x1="${P}" y1="${Y(0)}" x2="${W-8}" y2="${Y(0)}" stroke="#B7AE9A" stroke-dasharray="4 4"/>
    <path d="${path}" fill="none" stroke="#2563EB" stroke-width="2.5" filter="url(#ds)"/>${dots}</svg>`;
}

/* ---------- yon bilancosu (tiklanabilir yon filtresi) ---------- */
let DIRF="ALL";
function renderDuel(signals){
  const side=dir=>{
    const rows=(signals||[]).filter(s=>s.direction===dir);
    const w=rows.filter(s=>OUT(s)==="WIN").length;
    const l=rows.filter(s=>OUT(s)==="LOSS").length;
    const r=rows.filter(s=>["WIN","LOSS"].includes(OUT(s)))
      .reduce((a,s)=>a+(s.r_multiple||0),0);
    const open=rows.filter(s=>["PENDING","FILLED"].includes(OUT(s))).length;
    return {w,l,r,open};
  };
  const L=side("LONG"),S=side("SHORT");
  const mx=Math.max(Math.abs(L.r),Math.abs(S.r),1);
  const track=v=>{
    const w=Math.round(50*Math.abs(v)/mx);
    const left=v<0?`<div style="width:${w}%;background:var(--red);margin-left:${50-w}%"></div>`:
                   `<div style="width:50%"></div>`;
    const right=v>0?`<div style="width:${w}%;background:var(--green)"></div>`:"";
    return `<div class="track">${left}${right}</div>`;
  };
  const row=(name,d)=>`<div class="drow${DIRF===name?" on":""}" data-d="${name}"
    title="tabloyu ${name} ile filtreler">
    <div class="top"><b>${name}</b><b class="num ${d.r>0?"pos":d.r<0?"neg":""}">${(d.r>0?"+":"")+num(d.r)}R</b></div>
    ${track(d.r)}
    <div class="dstat">${d.w} WIN · ${d.l} LOSS · ${d.open} açık</div></div>`;
  $("duel").innerHTML=row("LONG",L)+row("SHORT",S)+
    `<div class="axis"><span>−${num(mx,1)}R</span><span>0</span><span>+${num(mx,1)}R</span></div>`;
  $("duel").querySelectorAll(".drow").forEach(el=>el.addEventListener("click",()=>{
    DIRF=DIRF===el.dataset.d?"ALL":el.dataset.d;
    renderDuel(SIGNALS);renderChips();renderSignals();}));
}

/* ---------- pipeline (tiklanabilir detay) ---------- */
const STEPS=[
  ["DATA","Yeterli mum yok (yeni listeleme)","insufficient data","#DC2626",
   "Analiz için yeterli mum geçmişi var mı? 4H ve 15m serilerde en az 60 kapanmış bar gerekir. Yeni listelenen paritelerin tarihi yoktur; motor tahmin uydurmak yerine DATA_MISSING der. Bu aşamada elenen sayısı çoğunlukla o günkü yeni coin sayısıdır."],
  ["REGIME","ADX<20: yönsüz piyasa","chop regime","#EA580C",
   "Piyasa yönlü mü, testere mi? ADX (trend gücü göstergesi) 20'nin altındaysa parite yönsüz/chop kabul edilir ve elenir. Yönsüz piyasada kırılımların çoğu tuzaktır — motor bu ortamda hiç oynamamayı tercih eder."],
  ["HTF STRUCTURE","4H yapı çelişkili","HTF structure unclear","#F59E0B",
   "4 saatlik yapı analizi: yükselen dipler-tepeler (HH-HL) mi, düşenler (LH-LL) mi? EMA200 konumuyla birlikte net bir taraf seçilemiyorsa yön iddiası yok demektir → elenir. Kararsız piyasada en çok eleyen aşama budur; bu sağlıklıdır."],
  ["LTF SETUP","Doğrulanmış retest/sweep yok","no valid LTF setup","#D3B411",
   "15 dakikalıkta somut giriş kurulumu aranır: kırılım sonrası kabul görmüş seviye retest'i ya da likidite süpürmesi sonrası geri alım (sweep-reclaim). 'Grafik iyi görünüyor' yetmez; doğrulanmış kurulum yoksa elenir."],
  ["VOLUME","Tetik hacmi <1.5× ort.","no volume confirmation","#84CC16",
   "Tetik barın hacmi, son 20 barın ortalamasının en az 1.5 katı olmalı. Katılımsız kırılım güvenilmezdir — büyük oyuncu yoksa hareket taşınmaz. Hacim teyidi olmayan kurulum elenir."],
  ["MARKET GATE","Rejim karşıtı yön bloklandı","counter-regime","#0EA5A4",
   "v3.0 filtresi: her turda BTC 4H kapanışının EMA200'e göre rejimi belirlenir (boğa/ayı/nötr, ±%0.25 bant). Rejime TERS yöndeki sinyaller bloklanır: ayıda LONG, boğada SHORT. İlk 49 sinyalde karşı-trend tarafın sistematik kaybı (−6.99R) üzerine eklendi. BTC verisi alınamazsa kapı açık kalır (fail-open)."],
  ["RISK/REWARD","Plan RR bandı dışı (<2 / >6)","RR ","#16A34A",
   "Plan risk/ödül bandı 2.0–6.0. Alt sınır: hedef, riske edilenin en az 2 katı olmalı — kenar yoksa işlem yok. Üst sınır (v3.0): RR>6 çoğunlukla fiyatın dibine sıkışmış stop demektir; gürültü ilk dalgada stoplar. Gölge veride RR≥6 planlı 4 sinyalin 4'ü de kaybetti — tavan bu kanıtla kondu."],
];
const SIGNAL_TIP="Yedi aşamanın tamamını geçen kararlar. Gölge takibe alınır: fiyatın giriş bölgesine gelmesi 6 saat beklenir; dolarsa 48 saat izlenir (önce stop = LOSS, önce hedef = WIN). Tıklayınca bu taramada geçenlerin setup/RR/güven dökümü açılır.";
function stageOf(d){
  if(d.decision==="SIGNAL")return "SIGNAL";
  const r=(d.decision==="DATA_MISSING")?"insufficient data":(d.reject_reason||"");
  const st=STEPS.find(([, ,p])=>r.startsWith(p)||r.includes(p));
  return st?st[0]:"OTHER";
}
function pipeDetail(name){
  const res=(LAST_STATUS&&LAST_STATUS.results)||{};
  const rows=Object.values(res).filter(d=>stageOf(d)===name);
  if(!rows.length){openModal(name,'<div class="empty">bu aşamada elenen parite yok</div>');return;}
  if(name==="SIGNAL"){
    openModal("→ SIGNAL · "+rows.length+" parite",
      rows.map(d=>`<div class="kvgrid"><span class="k"><b>${d.pair}</b>
        <span class="badge b-${d.direction}">${d.direction}</span> ${d.setup_type||""}</span>
        <span class="v num">RR ${num(d.rr,2)} · ${d.confidence||""}</span></div>`).join("")+
      '<div class="note">Tüm aşamaları geçen kararlar; gölge takibe alınır.</div>');
    return;
  }
  const st=STEPS.find(s=>s[0]===name);
  openModal(name+" · "+rows.length+" parite elendi",
    `<div class="note"><b>${st?st[1]:""}</b> — bu aşama motorun "${name}" filtresidir; geçilemeyen parite o taramada NO_TRADE olur.</div>
     <div class="taglist">`+
    rows.map(d=>`<span class="badge b-NOT_FILLED" title="${(d.reject_reason||"").replace(/"/g,"'")}">${d.pair}</span>`).join("")+
    "</div>");
}
function renderPipeline(status){
  const res=(status&&status.results)||{};
  const vals=Object.values(res);const total=vals.length;
  if(!total){$("pipe").innerHTML='<div class="empty">tarama bekleniyor…</div>';return;}
  const cnt={};let sig=0;
  for(const d of vals){
    const s=stageOf(d);
    if(s==="SIGNAL"){sig++;continue;}
    cnt[s]=(cnt[s]||0)+1;
  }
  $("pipeMeta").textContent=total+" parite";
  $("pipe").innerHTML=STEPS.map(([n,d,,col,tip])=>{
    const c=cnt[n]||0;
    return `<div class="step" data-s="${n}" data-tipx="${tip}" tabindex="0">
      <div class="h"><span>${n}</span><span class="n num">−${c}</span></div>
      <div class="d">${d}</div>
      <div class="g"><div style="width:${Math.min(100,100*c/total)}%;background:${col}"></div></div></div>`;
  }).join("")+
  `<div class="step" data-s="SIGNAL" data-tipx="${SIGNAL_TIP}" tabindex="0"><div class="h"><span class="pos">→ SIGNAL</span><span class="n num pos">${sig}</span></div>
    <div class="d">Tüm aşamaları geçenler takibe alınır</div>
    <div class="g"><div style="width:${Math.min(100,sig/total*1000)}%;background:var(--green)"></div></div></div>`;
  $("pipe").querySelectorAll(".step").forEach(el=>{
    el.addEventListener("click",()=>pipeDetail(el.dataset.s));
    el.addEventListener("mouseenter",()=>showTip(el));
    el.addEventListener("mouseleave",hideTip);
    el.addEventListener("focus",()=>showTip(el));
    el.addEventListener("blur",hideTip);
  });
  $("pbar").innerHTML=STEPS.map(([n,,,col])=>{
    const c=cnt[n]||0;
    return c?`<div style="width:${100*c/total}%;background:${col}" title="${n}: ${c}"></div>`:"";
  }).join("")+(sig?`<div style="width:${100*sig/total}%;background:var(--green)" title="SIGNAL: ${sig}"></div>`:"");
  $("plbl").innerHTML=`SIGNAL <b class="pos num">${sig}</b>`;
}

/* ---------- sinyal tablosu + detay modali ---------- */
let FILTER="ALL",SIGNALS=[];
const FILTERS=[["ALL","Tümü"],["OPEN","Açık"],["DONE","Sonuç"],["NF","Dolmayan"]];
function matches(s){
  if(DIRF!=="ALL"&&s.direction!==DIRF)return false;
  const o=OUT(s);
  if(FILTER==="OPEN")return o==="PENDING"||o==="FILLED";
  if(FILTER==="DONE")return o==="WIN"||o==="LOSS"||o==="AMBIGUOUS";
  if(FILTER==="NF")return o==="NOT_FILLED"||o==="EXPIRED";
  return true;
}
function renderChips(){
  const base=s=>DIRF==="ALL"||s.direction===DIRF;
  const c={ALL:SIGNALS.filter(base).length,
    OPEN:SIGNALS.filter(s=>base(s)&&["PENDING","FILLED"].includes(OUT(s))).length,
    DONE:SIGNALS.filter(s=>base(s)&&["WIN","LOSS","AMBIGUOUS"].includes(OUT(s))).length,
    NF:SIGNALS.filter(s=>base(s)&&["NOT_FILLED","EXPIRED"].includes(OUT(s))).length};
  let html=FILTERS.map(([k,l])=>
    `<button class="chip${FILTER===k?" on":""}" data-f="${k}">${l} ${c[k]||0}</button>`).join("");
  if(DIRF!=="ALL")html+=`<button class="chip dir" data-clr="1">yön: ${DIRF} ✕</button>`;
  $("chips").innerHTML=html;
  $("chips").querySelectorAll(".chip").forEach(b=>b.addEventListener("click",()=>{
    if(b.dataset.clr){DIRF="ALL";renderDuel(SIGNALS);}
    else FILTER=b.dataset.f;
    renderChips();renderSignals();}));
}
function signalDetail(s){
  const o=OUT(s);
  const risk=s.direction==="LONG"?(s.entry_max-s.stop_loss):(s.stop_loss-s.entry_min);
  const g=(k,v,cls)=>`<span class="k">${k}</span><span class="v num ${cls||""}">${v}</span>`;
  let html=`<div style="display:flex;gap:8px;align-items:center">
    <span class="badge b-${s.direction}">${s.direction}</span>
    <span class="badge b-${o}">${o}</span>
    <span class="num" style="color:var(--muted);font-size:11px">#${s.id} · ${fmtTs(s.created_utc)} UTC</span></div>
  <div class="kvgrid">`+
    g("Entry bölgesi",`${num(s.entry_min,4)} – ${num(s.entry_max,4)}`)+
    g("Stop",num(s.stop_loss,4),"neg")+
    g("TP1 / TP2",`${num(s.tp1,4)} / ${num(s.tp2,4)}`,"pos")+
    g("Plan RR",num(s.rr,2))+
    g("Risk (fiyat)",num(risk,4))+
    g("Fill fiyatı",s.fill_price==null?"—":num(s.fill_price,4))+
    g("Çıkış fiyatı",s.exit_price==null?"—":num(s.exit_price,4))+
    g("Gerçekleşen R",s.r_multiple==null?"—":(s.r_multiple>0?"+":"")+num(s.r_multiple),
      s.r_multiple>0?"pos":s.r_multiple<0?"neg":"")+
    g("Kapanış",s.closed_utc?fmtTs(s.closed_utc)+" UTC":"—")+"</div>";
  const live=LAST_STATUS&&LAST_STATUS.results&&LAST_STATUS.results[s.pair];
  if(live&&live.decision==="SIGNAL"){
    html+=`<div class="note"><b>Son taramada aktif plan:</b> ${live.setup_type||""} · güven ${live.confidence||""}<br>
      <b>İnvalidasyon:</b> ${live.invalidation||"—"}<br>
      <b>Likidite:</b> ${live.liquidity_note||"—"}<br>
      <b>Confluence:</b> ${(live.indicator_confluence||[]).join(", ")||"—"}</div>`;
  }
  html+='<div class="note">Gölge muhasebe: varsayımsal giriş, kayma/komisyon yok; yatırım tavsiyesi değildir.</div>';
  html+=`<div style="margin-top:10px"><button onclick='window.__calcSig(${s.id})'>🧮 Bu sinyalle pozisyon hesapla</button></div>`;
  openModal(s.pair,html);
}
function renderSignals(){
  const rows=SIGNALS.filter(matches);
  const el=$("signals");
  if(!rows.length){el.innerHTML='<div class="empty" style="padding:8px 14px">bu filtrede sinyal yok</div>';return;}
  const tr=rows.map((s,i)=>{
    const o=OUT(s),r=s.r_multiple;
    const open=o==="PENDING"||o==="FILLED";
    const age=open?`<div class="age">${fmtAge(s.created_utc)} / ${o==="PENDING"?"6 sa":"48 sa"}</div>`:"";
    const px=PRICES[s.pair];
    const ppx=PREV_PRICES[s.pair];
    const tick=(px!=null&&ppx!=null&&px!==ppx)?(px>ppx?" tick-up":" tick-down"):"";
    let pxCell;
    if(px==null){pxCell='<td class="num" style="color:var(--grey)">—</td>';}
    else if(o==="FILLED"&&s.fill_price!=null){
      const risk=s.direction==="LONG"?(s.fill_price-s.stop_loss):(s.stop_loss-s.fill_price);
      const ur=risk>0?(s.direction==="LONG"?(px-s.fill_price):(s.fill_price-px))/risk:null;
      const cls=ur>0?"pos":ur<0?"neg":"";
      pxCell=`<td class="num${tick}"><b>${fmtPx(px)}</b><div class="age ${cls}">${ur==null?"":(ur>0?"+":"")+num(ur)+"R canlı"}</div></td>`;
    }else if(o==="PENDING"){
      const ref=s.direction==="LONG"?s.entry_max:s.entry_min;
      const dist=ref?100*(px-ref)/ref:null;
      pxCell=`<td class="num${tick}"><b>${fmtPx(px)}</b><div class="age">${dist==null?"":"girişe "+(dist>0?"+":"")+num(dist,1)+"%"}</div></td>`;
    }else{
      pxCell=`<td class="num" style="color:var(--muted)">${fmtPx(px)}</td>`;
    }
    return `<tr data-i="${i}"${o==="NOT_FILLED"?' class="dim"':""}>
      <td class="num">${s.id}</td><td><b>${s.pair}</b></td>
      <td><span class="badge b-${s.direction}">${s.direction}</span></td>
      <td>${fmtTs(s.created_utc)}${age}</td>
      <td><span class="badge b-${o}">${o}</span></td>
      ${pxCell}
      <td class="num">${num(s.entry_min,4)}–${num(s.entry_max,4)}</td>
      <td class="num">${num(s.stop_loss,4)}</td><td class="num">${num(s.tp1,4)}</td>
      <td class="num">${num(s.rr,2)}</td>
      <td class="num ${r>0?"pos":r<0?"neg":""}"><b>${r==null?"—":(r>0?"+":"")+num(r)}</b></td></tr>`;}).join("");
  el.innerHTML=`<table><thead><tr><th>#</th><th>Parite</th><th>Yön</th>
    <th>Zaman</th><th>Durum</th><th class="r">Anlık</th><th class="r">Entry</th>
    <th class="r">Stop</th><th class="r">TP1</th>
    <th class="r">RR</th><th class="r">R</th></tr></thead><tbody>${tr}</tbody></table>`;
  el.querySelectorAll("tbody tr").forEach(row=>row.addEventListener("click",
    ()=>signalDetail(rows[Number(row.dataset.i)])));
}

/* ---------- sag panel ---------- */
function renderReview(comments){
  const el=$("review");
  if(!comments||!comments.length){
    el.innerHTML='<div class="empty">ilk değerlendirme ilk tarama turundan sonra üretilir…</div>';return;}
  const latest=comments[0];
  const paras=latest.text.split("\n").map(t=>
    `<p${t.startsWith("Uyari")?' class="warnline"':""}>${t}</p>`).join("");
  el.innerHTML=`<div class="rts">${fmtTs(latest.ts_utc)} UTC</div>
    <div class="txt">${paras}</div>
    <span class="more" id="moreBtn">devamını gör</span>`;
  const btn=$("moreBtn");
  btn.addEventListener("click",()=>{
    el.classList.toggle("open");
    btn.textContent=el.classList.contains("open")?"daralt":"devamını gör";});
}
function renderMarket(m){
  const el=$("market");
  if(!m){el.innerHTML='<div class="empty">market verisine ulaşılamadı</div>';return;}
  $("mupd").textContent="canlı metrikler · "+(m.updated_utc?fmtTs(m.updated_utc):"");
  const mj=(m.majors||[]).map(t=>{
    const cls=t.pct24h>0?"pos":t.pct24h<0?"neg":"";
    return `<div class="mj"><div class="sym">${t.symbol.replace("USDT","")}</div>
      <div class="px num">${Number(t.last).toLocaleString("en-US",{maximumFractionDigits:2})}</div>
      <div class="row num"><span class="${cls}">${(t.pct24h>0?"+":"")+num(t.pct24h,2)}%</span>
       <span style="color:var(--muted)"> · f ${num(t.funding,3)}%</span></div></div>`;}).join("");
  let fng="";
  if(m.fng&&m.fng.value!=null){
    fng=`<div class="fng"><div class="lbl"><span>Korku &amp; Açgözlülük</span>
      <b class="num">${m.fng.value} · ${m.fng.label_tr}</b></div>
      <div class="track"><div class="mark" style="left:calc(${m.fng.value}% - 1px)"></div></div></div>`;}
  const br=m.breadth?`<div class="breadth num"><b>Genişlik:</b>
    <span class="pos">${m.breadth.advancers}▲</span> /
    <span class="neg">${m.breadth.decliners}▼</span>
    <span> · likit ${m.liquid_universe}</span></div>`:"";
  const link=s=>`https://www.bybit.com/trade/usdt/${s}`;
  const mov=list=>list.map(t=>{
    const cls=t.pct24h>0?"pos":"neg";
    return `<a href="${link(t.symbol)}" target="_blank" rel="noopener" title="Bybit'te aç">
      <span>${t.symbol.replace("USDT","")}</span>
      <span class="num ${cls}">${(t.pct24h>0?"+":"")+num(t.pct24h,1)}%</span></a>`;}).join("");
  const pulse=m.pulse?`<div class="pulse"><span class="tg">market pulse · kural-tabanlı okuma</span><br>${m.pulse}</div>`:"";
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
  el.innerHTML=n.items.slice(0,4).map(it=>
    `<li><a href="${it.url}" target="_blank" rel="noopener">${it.title}</a>
     <span class="src">${it.source}${it.published_utc?" · "+fmtAge(it.published_utc)+" önce":""}</span></li>`).join("");
}
/* ---------- portfoy simulasyonu ---------- */
function pfLoad(){
  try{
    const c=localStorage.getItem("pf_capital"),r=localStorage.getItem("pf_risk");
    if(c)$("pfCap").value=c;
    if(r)$("pfRisk").value=r;
  }catch(e){}
}
function pfSave(){
  try{
    localStorage.setItem("pf_capital",$("pfCap").value);
    localStorage.setItem("pf_risk",$("pfRisk").value);
  }catch(e){}
}
function renderPortfolio(signals){
  const cap0=Math.max(1,Number($("pfCap").value)||10000);
  const riskPct=Math.min(10,Math.max(.1,Number($("pfRisk").value)||1))/100;
  const done=(signals||[]).filter(s=>["WIN","LOSS"].includes(OUT(s))&&s.closed_utc)
    .sort((a,b)=>a.closed_utc.localeCompare(b.closed_utc));
  const now=Date.now();
  const dayStart=new Date();dayStart.setUTCHours(0,0,0,0);
  const T={gun:dayStart.getTime(),hafta:now-7*864e5,ay:now-30*864e5};
  // bilesik yurutme: her kapanista capital *= 1 + riskPct * R
  let cap=cap0;const at={gun:cap0,hafta:cap0,ay:cap0};const cnt={gun:0,hafta:0,ay:0};
  const seen={gun:false,hafta:false,ay:false};
  for(const s of done){
    const t=Date.parse(s.closed_utc.endsWith("Z")?s.closed_utc:s.closed_utc+"Z");
    for(const k of ["gun","hafta","ay"]){
      if(!seen[k]&&t>=T[k]){at[k]=cap;seen[k]=true;}
      if(t>=T[k])cnt[k]++;
    }
    cap=cap*(1+riskPct*(s.r_multiple||0));
  }
  for(const k of ["gun","hafta","ay"])if(!seen[k])at[k]=cap; // pencerede islem yok
  const openedToday=(signals||[]).filter(s=>{
    const t=Date.parse((s.created_utc||"").endsWith("Z")?s.created_utc:(s.created_utc||"")+"Z");
    return t>=T.gun;}).length;
  const money=v=>"$"+v.toLocaleString("en-US",{maximumFractionDigits:0});
  const totPct=100*(cap-cap0)/cap0;
  const row=(lbl,base,n,extra)=>{
    const d=cap-base,p=base?100*d/base:0;
    const cls=d>0?"pos":d<0?"neg":"";
    const sign=d>=0?"+":"−";
    return `<div class="prow"><span class="w">${lbl}</span>
      <span class="d num ${cls}">${sign}${money(Math.abs(d))} <span style="font-weight:500">(${(p>0?"+":"")+num(p,2)}%)</span></span>
      <span class="c num">${n} kapanan${extra||""}</span></div>`;
  };
  $("pfBody").innerHTML=
    `<div class="bal"><div style="display:flex;justify-content:space-between;align-items:baseline">
       <span class="b num">${money(cap)}</span>
       <span class="p num ${totPct>0?"pos":totPct<0?"neg":""}">${(totPct>0?"+":"")+num(totPct,2)}%</span></div>
       <div class="c" style="font-size:9.8px;color:var(--muted)">güncel bakiye · ${done.length} işlem · başlangıç ${money(cap0)}</div></div>`+
    row("Bugün",at.gun,cnt.gun," / "+openedToday+" açılan")+
    row("7 gün",at.hafta,cnt.hafta)+
    row("30 gün",at.ay,cnt.ay)+
    `<div class="foot">Simülasyon: her işlemde bakiyenin %${(riskPct*100).toFixed(1)}'i riske atılır, sonuç R×risk olarak bileşik işler. Kayma/komisyon yok; gölge muhasebedir, gerçek para değildir. Günler UTC'dir.</div>`;
}
let tipTimer=null;
function showTip(el){
  clearTimeout(tipTimer);
  tipTimer=setTimeout(()=>{
    const tb=$("tipbox");
    tb.textContent=el.dataset.tipx||"";
    if(!tb.textContent)return;
    tb.style.display="block";
    const r=el.getBoundingClientRect(), tw=330;
    let left=r.right+12, top=r.top;
    if(left+tw>window.innerWidth){left=r.left;top=r.bottom+8;}
    tb.style.left=left+"px";
    const th=tb.offsetHeight;
    if(top+th>window.innerHeight-8)top=Math.max(8,window.innerHeight-th-8);
    tb.style.top=top+"px";
  },250);
}
function hideTip(){clearTimeout(tipTimer);$("tipbox").style.display="none";}

window.__calcSig=id=>{const s=SIGNALS.find(x=>x.id===id);if(s)openCalc(s);};
/* ---------- pozisyon hesaplayici ---------- */
const money2=v=>"$"+Number(v).toLocaleString("en-US",{maximumFractionDigits:2});
function calcFill(s){
  $("cDir").value=s.direction;
  $("cEntry").value=s.direction==="LONG"?s.entry_max:s.entry_min;
  $("cStop").value=s.stop_loss;
  $("cTp1").value=s.tp1;
  $("cTp2").value=s.tp2??"";
  calcRun();
}
function calcPopulate(){
  const sel=$("cSig");
  const open=SIGNALS.filter(x=>["PENDING","FILLED"].includes(OUT(x)));
  const rest=SIGNALS.filter(x=>!["PENDING","FILLED"].includes(OUT(x))).slice(0,20);
  sel.innerHTML='<option value="">— manuel —</option>'+
    [...open,...rest].map(x=>`<option value="${x.id}">#${x.id} ${x.pair} ${x.direction} (${OUT(x)})</option>`).join("");
}
function openCalc(sig){
  calcPopulate();
  try{
    $("cBal").value=localStorage.getItem("pf_capital")||$("pfCap").value||10000;
    $("cRisk").value=localStorage.getItem("pf_risk")||$("pfRisk").value||1;
    $("cLev").value=localStorage.getItem("calc_lev")||5;
  }catch(e){}
  if(sig){$("cSig").value=String(sig.id);calcFill(sig);}
  else calcRun();
  $("modal").classList.remove("show");
  $("calc").classList.add("show");
}
function calcRun(){
  const bal=Number($("cBal").value)||0, riskP=(Number($("cRisk").value)||0)/100;
  const lev=Math.max(1,Number($("cLev").value)||1);
  const dir=$("cDir").value;
  const e=Number($("cEntry").value), st=Number($("cStop").value);
  const t1=Number($("cTp1").value), t2=Number($("cTp2").value);
  const out=$("cOut");
  try{localStorage.setItem("calc_lev",String(lev));}catch(x){}
  if(!bal||!riskP||!e||!st){out.innerHTML='<div class="empty">bakiye, risk, entry ve stop girin…</div>';return;}
  const dist=dir==="LONG"?e-st:st-e;
  if(dist<=0){out.innerHTML='<div class="note" style="border-left:3px solid var(--red)">Stop, yön ile tutarsız: LONG için stop &lt; entry, SHORT için stop &gt; entry olmalı.</div>';return;}
  const riskUsd=bal*riskP;
  const qty=riskUsd/dist, notional=qty*e, margin=notional/lev;
  const distP=100*dist/e;
  // yaklasik likidasyon (izole; ~%5 bakim payi)
  const liq=dir==="LONG"?e*(1-0.95/lev):e*(1+0.95/lev);
  const liqSafe=dir==="LONG"?liq<st:liq>st;
  const maxLev=Math.max(1,Math.min(50,Math.floor(0.95/(dist/e)*0.8)));
  const fee=notional*0.00055*2, feeR=fee/riskUsd;
  const g=(k,v,cls)=>`<span class="k">${k}</span><span class="v num ${cls||""}">${v}</span>`;
  let rows=`<div class="kvgrid">`+
    g("Riske atılan",money2(riskUsd)+` (${(riskP*100).toFixed(1)}%)`,"neg")+
    g("Stop mesafesi",num(distP,2)+"%")+
    g("Miktar",qty.toLocaleString("en-US",{maximumFractionDigits:4})+" coin")+
    g("Pozisyon (notional)",money2(notional))+
    g("Gerekli marjin",money2(margin)+` (${lev}x)`)+
    g("Stop'ta kayıp","−"+money2(riskUsd),"neg");
  if(t1){const gain=qty*Math.abs(t1-e);rows+=g("TP1 kazanç",`+${money2(gain)} (+${num(gain/riskUsd,2)}R)`,"pos");}
  if(t2){const gain2=qty*Math.abs(t2-e);rows+=g("TP2 kazanç",`+${money2(gain2)} (+${num(gain2/riskUsd,2)}R)`,"pos");}
  rows+=g("Tahmini komisyon","~"+money2(fee)+` (riskin %${num(feeR*100,1)}'i)`)+
    g("Yaklaşık likidasyon",fmtPx(liq),liqSafe?"":"neg")+"</div>";
  rows+=liqSafe?
    `<div class="note" style="border-left:3px solid var(--green)"><b>Güvenli:</b> ${lev}x kaldıraçta likidasyon (${fmtPx(liq)}) stop'un (${fmtPx(st)}) ötesinde — plan stop'u çalışır. Bu paritede yaklaşık güvenli üst sınır ~${maxLev}x.</div>`:
    `<div class="note" style="border-left:3px solid var(--red)"><b>⚠ Tehlike:</b> ${lev}x kaldıraçta likidasyon (${fmtPx(liq)}) stop'a ulaşmadan tetiklenir — planın stop'u değil borsa likidasyonu çalışır ve kayıp risk$'ı aşar. Kaldıracı ~${maxLev}x altına çek.</div>`;
  rows+='<div class="note">Değerler yaklaşıktır (likidasyon borsanın marjin modeline göre değişir; komisyon taker %0.055×2 varsayımı). Yatırım tavsiyesi değildir.</div>';
  out.innerHTML=rows;
}
function renderSys(uni,healthy){
  if(uni)$("stratUni").textContent=(uni.mode||"")+"-"+(uni.count||"");
  $("dot").className="dot"+(healthy?"":" err");
}
function renderFooter(backup,healthy,ms,perf){
  const gist=backup&&backup.gist_url?
    `gist <a href="${backup.gist_url}" target="_blank" rel="noopener">açık</a> · sync <b>${fmtTs(backup.last_sync_utc)}</b>`:
    "gist kapalı";
  $("statusbar").innerHTML=
    `<span>${healthy?"●":"○"} <b>${healthy?"canlı":"bağlantı yok"}</b></span><span class="sep">|</span>`+
    `<span>veri <b>${new Date().toLocaleTimeString("tr-TR")}</b></span><span class="sep">|</span>`+
    `<span>${gist}</span><span class="sep">|</span>`+
    `<span>yanıt <b>${ms} ms</b></span><span class="sep">|</span>`+
    `<span>v3.2</span>`+
    `<span class="right">gölge muhasebe · geçmiş performans garanti değildir · yatırım tavsiyesi değildir</span>`;
  if(perf&&perf.total_r_multiple!=null){
    const tr=perf.total_r_multiple;
    document.title=`${tr>=0?"▲":"▼"} ${(tr>0?"+":"")+num(tr,1)}R · signal-engine`;
  }
}

/* ---------- loop ---------- */
async function refresh(){
  const t0=performance.now();
  const [perf,signals,status,uni,comments,market,news,px,backup]=await Promise.all([
    j("/performance"),j("/signals?limit=200"),j("/status"),j("/universe"),
    j("/commentary?limit=4"),j("/market"),j("/news"),j("/prices"),
    j("/backup/info")]);
  const fetchMs=Math.round(performance.now()-t0);
  PREV_PRICES=PRICES;PRICES=(px&&px.prices)||{};
  LAST_STATUS=status;
  SIGNALS=(signals||[]).slice().sort((a,b)=>(b.id||0)-(a.id||0));
  renderHeader(perf,status);
  renderKpis(perf,status,uni,SIGNALS);
  renderCurve(SIGNALS);
  renderDuel(SIGNALS);
  renderChips();renderSignals();
  renderPipeline(status);
  renderReview(comments);
  renderMarket(market);
  renderNews(news);
  renderPortfolio(SIGNALS);
  renderSys(uni,!!status);
  renderFooter(backup,!!status,fetchMs,perf);
  $("updated").textContent=new Date().toLocaleTimeString("tr-TR");
}
let timer=null;
function schedule(){
  if(timer)clearInterval(timer);
  timer=setInterval(refresh,parseInt($("iv").value,10));
}
$("iv").addEventListener("change",schedule);
$("refresh").addEventListener("click",refresh);
function applyZoom(v){
  document.body.style.zoom=v;
  document.body.classList.toggle("zoomed",Number(v)>1);
}
try{
  const z=localStorage.getItem("ui_zoom")||"1";
  $("fs").value=z;applyZoom(z);
}catch(e){}
$("fs").addEventListener("change",()=>{
  applyZoom($("fs").value);
  try{localStorage.setItem("ui_zoom",$("fs").value);}catch(e){}});
pfLoad();
["pfCap","pfRisk"].forEach(id=>$(id).addEventListener("input",()=>{
  pfSave();renderPortfolio(SIGNALS);}));
refresh();schedule();
</script>
</body>
</html>
"""
