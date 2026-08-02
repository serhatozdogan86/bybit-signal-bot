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
<html lang="tr" translate="no">
<head>
<meta charset="utf-8">
<meta name="google" content="notranslate">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="signal-engine">
<meta name="theme-color" content="#6D28D9">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/icon-180.png">
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
  td.c-lv{display:flex;gap:14px;justify-content:flex-end;white-space:nowrap}
  td.c-lv span[data-l]::before{content:attr(data-l) " ";font-family:var(--sans);
    font-size:9.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
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
  /* yan sutunlar tasarsa kendi icinde kaysin (portfoy karti gizlenmesin) */
  .cols > .col:first-child, .cols > .col:last-child{overflow-y:auto;
     scrollbar-width:thin;padding-right:2px}
  .cols > .col:first-child > .card{flex:0 0 auto}
  #pfCard{flex:0 0 auto}
  #pfCard .cbody{max-height:none}
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
  .conf{display:inline-block;margin-left:5px;width:15px;text-align:center;
        border-radius:4px;font-size:9.5px;font-weight:700;font-family:var(--mono)}
  .conf.HIGH{background:var(--green-bg);color:var(--green-ink)}
  .conf.MEDIUM{background:var(--amber-bg);color:var(--amber-ink)}
  .conf.LOW{background:var(--grey-bg);color:#5B5344}
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
  .evid{margin:14px 0 6px;background:var(--card2);border:1px solid var(--line);
     border-radius:12px;padding:12px 14px}
  #modal .sheet{max-width:1000px}
  @media(max-width:760px){#modal .sheet{max-width:96vw}}
  .zoombar{display:flex;gap:6px;align-items:center;margin-bottom:8px}
  .zoombar button{background:var(--card);border:1px solid var(--line);
     color:var(--head);border-radius:7px;padding:4px 11px;cursor:pointer;
     font-family:var(--mono);font-size:11px}
  .zoombar button.on{background:var(--blue);color:#fff;border-color:var(--blue)}
  .zoombar .zl{font-family:var(--mono);font-size:10.5px;color:var(--muted);margin-right:auto}
  .evid svg{width:100%;height:auto;display:block}
  .evid .lgd{display:flex;flex-wrap:wrap;gap:10px;margin-top:8px;
     font-family:var(--mono);font-size:10px;color:var(--muted)}
  .evid .lgd i{display:inline-block;width:9px;height:9px;border-radius:2px;
     margin-right:4px;vertical-align:-1px}
  .evlist{font-size:12.5px;line-height:1.7;margin-top:8px}
  .evlist b{font-family:var(--mono);font-size:11px;letter-spacing:.04em;
     color:var(--head);text-transform:uppercase}
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
  /* ---------- MOBIL (<=760px): sekmeli tek kolon + menekse vurgu ---------- */
  .col[data-tab="ayar"]{display:none}   /* yalniz mobil sekmede gorunur */
  .setrow{display:flex;align-items:center;justify-content:space-between;
     gap:12px;padding:11px 0;border-bottom:1px dashed var(--line)}
  .setrow:last-child{border-bottom:0}
  .setrow .sl{font-size:13.5px;color:var(--head);font-weight:500}
  .setbtn{background:var(--blue);color:#fff;border:0;border-radius:9px;
     padding:8px 14px;font-family:var(--sans);font-size:12.5px;font-weight:600;
     cursor:pointer;text-decoration:none;display:inline-block}
  .setbtn.ghost{background:var(--card2);color:var(--blue);
     border:1px solid var(--line);margin-left:6px;font-family:var(--mono);font-size:11.5px}
  .setrow select{font-size:13px}
  .syslist{font-family:var(--mono);font-size:11.5px;line-height:2}
  .syslist b{color:var(--head);font-weight:600}
  .tabbar{display:none}
  @media (max-width:760px){
    /* Claude Design mobil paleti: menekse vurgu, hafif lila zemin */
    :root{--blue:#6D28D9;--bg:#F6F4FB;--card:#FFFFFF;--card2:#F3F0FB;
          --line:#E6E0F5;--head:#3B2E63;--muted:#7C7396;
          --blue-bg:#EFE9FD;--grey-bg:#EFECF7;--shadow:0 1px 3px rgba(61,46,99,.07)}
    body{overflow:auto;-webkit-text-size-adjust:100%}
    .hdr{border-color:var(--line)}
    .kpi .val{letter-spacing:-.02em}
    .kpi .val:not(.pos):not(.neg){color:var(--blue)}
    .badge.b-SHORT{background:#FBE9F3;color:#BE185D}
    .sigwrap tbody tr{border-left-color:#C4B5FD}
    .sigwrap tbody tr.dir-LONG{border-left-color:#16A34A}
    .sigwrap tbody tr.dir-SHORT{border-left-color:#A855F7}
    .chip.on{background:var(--blue);border-color:var(--blue);color:#fff}
    .tb.active{color:var(--blue)}
    .tabbar{background:rgba(255,255,255,.97)}
    .statusbar{background:rgba(246,244,251,.95)}
    .app{height:auto;min-height:100vh;grid-template-rows:auto minmax(0,1fr) auto;
         gap:8px;padding:8px 10px 76px;max-width:100%;overflow-x:hidden}
    .cols,.col,.card,.kpis{min-width:0;max-width:100%}
    /* mobilde ic kaydirma YOK: tek akis, sayfa kayar */
    .cols > .col:first-child,.cols > .col:last-child{overflow:visible;padding-right:0}
    .col,.card,.cbody,.scroll{overflow:visible!important;max-height:none!important}
    .chead{flex-wrap:wrap;row-gap:2px}
    .chead .tag{margin-left:0;flex-basis:100%}
    .chips{flex-basis:100%;margin-left:0!important;display:flex;flex-wrap:wrap;gap:6px}
    .hdr{flex-wrap:wrap;gap:6px;padding:8px 12px;height:auto}
    .hdr .hsum{flex-basis:100%;min-width:0;text-align:left;font-size:11.5px;
        order:3;white-space:normal;line-height:1.5}
    .hdr .hsum span{white-space:normal}
    .hctl select,#calcBtn,#howtoBtn{display:none}   /* -> Ayar sekmesi */
    #setLang:empty::after{content:"başlıktaki TR/RU düğmesi";font-size:11.5px;
       color:var(--muted)}
    .hdr .icon{font-size:12px}
    .col[data-tab="ayar"]{display:none}
    .col[data-tab="ayar"].on{display:flex}
    .cols{grid-template-columns:1fr}
    /* sekme mantigi: yalniz aktif sutun gorunur */
    .col[data-tab]{display:none}
    .col[data-tab].on{display:flex}
    .kpis{grid-template-columns:1fr 1fr;gap:8px}
    .kpi .val{font-size:24px}
    .midrow{grid-template-columns:1fr;min-height:0}
    .scroll{max-height:none;overflow:visible}
    .card{min-height:0}
    /* sinyal tablosu -> kart listesi */
    .sigwrap table,.sigwrap thead{display:block}
    .sigwrap thead{display:none}
    .sigwrap tbody{display:block}
    .sigwrap tbody tr{display:grid;grid-template-columns:1fr auto;
        gap:2px 10px;background:var(--card);border:1px solid var(--line);
        border-left:3px solid var(--line);border-radius:10px;
        padding:10px 12px;margin-bottom:8px}
    .sigwrap tbody tr.dir-LONG{border-left-color:var(--green)}
    .sigwrap tbody tr.dir-SHORT{border-left-color:var(--red)}
    .sigwrap tbody tr:nth-child(even) td{background:transparent}
    .sigwrap td{border:0;padding:0;font-size:13px}
    .sigwrap td[data-l]::before{content:attr(data-l);display:block;
        font-family:var(--mono);font-size:9px;letter-spacing:.08em;
        text-transform:uppercase;color:var(--muted)}
    .sigwrap td.c-pair{grid-column:1;grid-row:1;font-size:15px}
    .sigwrap td.c-dir{grid-column:1;grid-row:2}
    .sigwrap td.c-px{grid-column:2;grid-row:1;text-align:right;font-size:15px}
    .sigwrap td.c-r{grid-column:2;grid-row:2;text-align:right;font-size:15px;font-weight:700}
    .sigwrap td.c-st{grid-column:1;grid-row:3}
    .sigwrap td.c-time{grid-column:2;grid-row:3;text-align:right;color:var(--muted);font-size:11.5px}
    .sigwrap td.c-lv{grid-column:1/-1;grid-row:4;display:grid;
        grid-template-columns:repeat(4,1fr);gap:6px;margin-top:8px;
        padding-top:8px;border-top:1px dashed var(--line)}
    .sigwrap td.c-id{display:none}
    /* alt sekme cubugu */
    .tabbar{display:grid;grid-template-columns:repeat(4,1fr);
        position:fixed;left:0;right:0;bottom:0;z-index:50;
        background:rgba(255,254,250,.96);backdrop-filter:blur(8px);
        border-top:1px solid var(--line);padding:6px 4px 8px}
    .tb{background:none;border:0;display:flex;flex-direction:column;
        align-items:center;gap:3px;font-family:var(--sans);font-size:10.5px;
        color:var(--muted);cursor:pointer;padding:4px 0}
    .tb span{font-size:16px;line-height:1}
    .tb.active{color:var(--blue);font-weight:600}
    .statusbar{position:fixed;bottom:56px;left:0;right:0;font-size:9.5px;
        padding:3px 10px;background:rgba(245,241,232,.94);z-index:49;
        border-top:1px solid var(--line)}
    .statusbar .right{display:none}
    .ovl .sheet{max-width:94vw;max-height:86vh;overflow:auto}
    #tipbox{max-width:76vw}
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
<body class="notranslate">
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
      <button id="langBtn" class="icon" title="Dil / Язык" data-noi18n>TR</button>
      <a id="bookBtn" class="icon" href="/kitap"
         title="Ders Kitabı: stratejinin tam anlatımı">📗</a>
      <button id="calcBtn" class="icon" title="Pozisyon Hesaplayıcı">🧮</button>
      <button id="howtoBtn" class="icon" title="Nasıl okunur?">⚙</button>
    </div>
  </header>

  <div class="cols">
    <div class="col" data-tab="ozet">
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
      <div class="card fill pf" id="pfCard">
        <div class="chead"><span class="tipwrap" tabindex="0" data-tip="Gölge sinyalleri para yönetimi diline çevirir. Model: her kapanan işlemde bakiyenin, girdiğin Risk % kadarı riske atılır; sonuç bakiye × (1 + risk × R) olarak İŞLEM KAPANIŞ SIRASIYLA bileşik işler (örn. 10.000$ ve %1 riskte +2.2R kazanç = +220$, −1R kayıp = −100$). Bugün / 7 gün / 30 gün satırları, o pencerede kapanan işlemlerin bakiyeye net etkisidir; 'açılan' o gün üretilen sinyal sayısıdır (günler UTC). Başlangıç $ ve Risk % alanlarını buradan değiştirebilirsin — tarayıcında saklanır. Kayma/komisyon yoktur; simülasyondur, gerçek para değildir. KAPASİTE MODU: Slot ve Kaldıraç alanları gerçek sermaye kısıtını modeller — sermaye slotlara bölünür, defter doluyken gelen sinyal atlanır (atlanan sayısı gösterilir); 'sınırsız varsayım' satırı kısıtsız teorik bakiyeyi kıyas için verir.">Portföy Simülasyonu <span class="i">ⓘ</span></span> <span class="tag">gölge · bileşik</span></div>
        <div class="cbody fill scroll" id="pf">
          <div class="inputs">
            <label>Başlangıç $ <input type="number" id="pfCap" min="1" step="100" value="10000"></label>
            <label>Risk % <input type="number" id="pfRisk" min="0.1" max="10" step="0.1" value="1.0" style="width:52px"></label>
            <label>Slot <input type="number" id="pfSlots" min="1" max="30" step="1" value="5" style="width:46px"></label>
            <label>Kald. <input type="number" id="pfLev" min="1" max="25" step="1" value="3" style="width:46px"></label>
          </div>
          <div id="pfBody"><div class="empty">hesaplanıyor…</div></div>
        </div>
      </div>
    </div>

    <div class="col" data-tab="sinyaller">
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
        <div class="cbody fill scroll sigwrap" id="signals" style="padding:0 0 4px"><div class="empty" style="padding:8px 14px">yükleniyor…</div></div>
      </div>
    </div>

    <div class="col" data-tab="ayar">
      <div class="card">
        <div class="chead">Ayarlar <span class="tag">tercihler cihazında saklanır</span></div>
        <div class="cbody">
          <div class="setrow"><span class="sl">Dil / Язык</span><span id="setLang"></span></div>
          <div class="setrow"><span class="sl">Yazı boyutu</span><span id="setFs"></span></div>
          <div class="setrow"><span class="sl">Yenileme</span><span id="setIv"></span></div>
        </div>
      </div>
      <div class="card">
        <div class="chead">Araçlar</div>
        <div class="cbody">
          <div class="setrow"><span class="sl">Pozisyon hesaplayıcı</span>
            <button class="setbtn" id="setCalc">🧮 Aç</button></div>
          <div class="setrow"><span class="sl">Nasıl okunur?</span>
            <button class="setbtn" id="setHowto">Rehberi aç</button></div>
          <div class="setrow"><span class="sl">Ders kitabı</span>
            <span><a class="setbtn" id="setBook" href="/kitap">📗 Oku</a>
                  <a class="setbtn ghost" id="setBookPdf" href="/kitap.pdf">PDF</a></span></div>
        </div>
      </div>
      <div class="card">
        <div class="chead">Sistem</div>
        <div class="cbody" id="setSys"><div class="empty">yükleniyor…</div></div>
      </div>
    </div>

    <div class="col" data-tab="piyasa">
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

  <nav class="tabbar" id="tabbar" role="tablist">
    <button class="tb active" data-go="ozet" role="tab"><span>▤</span>Özet</button>
    <button class="tb" data-go="sinyaller" role="tab"><span>≡</span>Sinyaller</button>
    <button class="tb" data-go="piyasa" role="tab"><span>◈</span>Piyasa</button>
    <button class="tb" data-go="ayar" role="tab"><span>⚙</span>Ayar</button>
  </nav>
  <footer class="statusbar" id="statusbar">yükleniyor…</footer>
</div>

<div id="tipbox"></div>

<div id="langpick" class="ovl" data-noi18n>
  <div class="sheet" style="max-width:420px;text-align:center">
    <h3 style="margin-bottom:4px">Dil / Язык</h3>
    <p style="color:var(--muted);font-size:13px;margin:0 0 18px">
      Panoyu hangi dilde kullanmak istersiniz?<br>
      На каком языке открыть панель?</p>
    <div style="display:flex;gap:12px;justify-content:center">
      <button class="langbtn" data-lang="tr">🇹🇷 Türkçe</button>
      <button class="langbtn" data-lang="ru">🇷🇺 Русский</button>
    </div>
    <p style="color:var(--muted);font-size:11px;margin:16px 0 0">
      Daha sonra başlıktaki TR/RU düğmesinden değiştirebilirsiniz ·
      Позже можно сменить кнопкой TR/RU</p>
  </div>
</div>

<div id="overlay" class="ovl">
  <div class="sheet">
    <h3>Nasıl okunur?</h3>
    <dl>
      <dt>R (risk katsayısı)</dt>
      <dd>Her işlemin sonucu, riske atılan birim cinsinden: kayıp = −1R, kazanç = ödül/risk oranı kadar (+2.2R gibi).</dd>
      <dt>Win rate ve başabaş</dt>
      <dd>Kazançlar kayıplardan büyükse %50 isabet gerekmez. Başabaş = 1 / (1 + ort. kazanç R).</dd>
      <dt>Filtre boru hattı</dt>
      <dd>DATA → REGIME → HTF → LTF → VOLUME → MARKET GATE → RR; herhangi biri geçilemezse NO_TRADE. Aşamaya tıklayınca o aşamada elenen pariteler listelenir, üzerine gelince aşama açıklanır.</dd>
      <dt>PENDING → FILLED → WIN/LOSS</dt>
      <dd>Girişe gelmesi 6 saat beklenir; gelirse 48 saat izlenir. Önce stop = LOSS, önce hedef = WIN. NOT_FILLED orana dahil edilmez (hayalet R'si ayrıca izlenir); aynı mumda stop+hedef görülürse muhafazakâr kuralla LOSS sayılır.</dd>
      <dt>Portföy ısısı</dt>
      <dd>Aynı yönde en fazla 4, aynı kümede 2, toplamda 8 açık sinyal. Limit doluyken gelen sinyal reddedilmez, sıraya alınır ve ayrı kohortta izlenir.</dd>
      <dt>Piyasa Nabzı / Saatlik Değerlendirme</dt>
      <dd>Kural tabanlı otomatik üretimdir (canlı insan/LLM yorumu değildir). Korku &amp; Açgözlülük: alternative.me.</dd>
    </dl>
    <div class="warn">Tüm sonuçlar <b>gölge muhasebedir</b>: varsayımsal giriş, kayma/komisyon yok, gerçek emir yok. Geçmiş performans garanti değildir; yatırım tavsiyesi değildir. Haber başlıkları dış kaynaktan aynen aktarılır.</div>
    <div style="margin-top:12px;text-align:right">
      <button id="howtoClose">Kapat</button>
    </div>
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
/* ================= i18n: TR (kaynak) -> RU cevirisi ================= */
const RU={
/* baslik ve kartlar */
"Strateji":"Стратегия","strateji sözleşmesi":"регламент стратегии",
"Filtre Boru Hattı":"Конвейер фильтров","Kümülatif R (Equity)":"Кумулятивный R (эквити)",
"yeşil WIN · kırmızı LOSS":"зелёный WIN · красный LOSS",
"Yön Bilançosu":"Баланс по направлениям","tıkla → yön filtresi":"клик → фильтр направления",
"Sinyaller · Gölge Takip":"Сигналы · Теневой учёт","satıra tıkla → detay":"клик по строке → детали",
"Piyasa Nabzı":"Пульс рынка","canlı metrikler":"живые метрики",
"Saatlik Değerlendirme":"Часовой обзор","hourly_review · otomatik":"hourly_review · автоматически",
"Haber Akışı":"Лента новостей","kripto haber · dış kaynak":"крипто-новости · внешний источник",
"Portföy Simülasyonu":"Симуляция портфеля","gölge · bileşik":"тень · сложный процент",
/* KPI */
"Win Rate":"Винрейт","Toplam R":"Суммарный R","Açık Pozisyon":"Открытые позиции",
"Giriş İsabeti":"Точность входа","Taranan Evren":"Сканируемая вселенная",
"gölge takipte":"в теневом учёте","top · 1 tarama":"top · 1 скан",
/* strateji karti */
"Zaman dilimi":"Таймфрейм","Hacim teyidi":"Подтверждение объёмом","Risk/ödül bandı":"Диапазон риск/прибыль",
"Yön kapısı":"Ворота направления","Setup":"Сетап","Evren":"Вселенная","BTC 4H rejimi":"режим BTC 4H",
"retest · sweep":"ретест · свип","Conservative swing.":"Conservative swing.",
/* boru hatti */
"Yeterli mum yok (yeni listeleme)":"Недостаточно свечей (новый листинг)",
"ADX<20: yönsüz piyasa":"ADX<20: рынок без направления",
"4H yapı çelişkili":"Структура 4H противоречива",
"Doğrulanmış retest/sweep yok":"Нет подтверждённого ретеста/свипа",
"Tetik hacmi <1.5× ort.":"Объём триггера <1.5× сред.",
"Rejim karşıtı yön bloklandı":"Направление против режима заблокировано",
"Plan RR bandı dışı (<2 / >6)":"RR плана вне диапазона (<2 / >6)",
"Tüm aşamaları geçenler takibe alınır":"Прошедшие все этапы берутся в учёт",
"elenen →":"отсеяно →","tarama bekleniyor…":"ожидание скана…",
/* tablo basliklari */
"Parite":"Пара","Yön":"Направление","Zaman":"Время","Durum":"Статус","Anlık":"Сейчас",
"Giriş / Stop / TP1 / RR":"Вход / Стоп / TP1 / RR","giriş":"вход","stop":"стоп",
/* durum rozetleri ve filtreler */
"Tümü":"Все","Açık":"Открытые","Sonuç":"Результат","Dolmayan":"Не заполнено",
"açık":"откр.","yükleniyor…":"загрузка…","hesaplanıyor…":"расчёт…",
"henüz sonuçlanan sinyal yok":"пока нет завершённых сигналов",
"kayıt yok":"нет записей","bu filtrede sinyal yok":"нет сигналов по этому фильтру",
/* detay modali */
"Kapat":"Закрыть","Yön / Setup":"Направление / Сетап","Giriş bölgesi":"Зона входа",
"Stop":"Стоп","Hedefler":"Цели","Plan RR":"RR плана","Durum / Sonuç":"Статус / Результат",
"Sonuç R":"Результат R","Açılış":"Открытие","Kapanış":"Закрытие","Setup / Güven":"Сетап / Уверенность",
"Net R (maliyet v0)":"Чистый R (издержки v0)","Bu sinyalle pozisyon hesapla":"Рассчитать позицию по сигналу",
/* hesaplayici */
"Pozisyon Hesaplayıcı":"Калькулятор позиции","Sinyal":"Сигнал","— manuel —":"— вручную —",
"Bakiye $":"Баланс $","Risk %":"Риск %","Kaldıraç":"Плечо","Entry":"Вход","TP1":"TP1","TP2":"TP2",
"Riske atılan":"Под риском","Stop mesafesi":"Дистанция до стопа","Miktar":"Количество",
"Pozisyon (notional)":"Позиция (номинал)","Gerekli marjin":"Требуемая маржа","Stop'ta kayıp":"Убыток на стопе",
"TP1 kazanç":"Прибыль TP1","TP2 kazanç":"Прибыль TP2","Tahmini komisyon":"Оценка комиссии",
"Yaklaşık likidasyon":"Примерная ликвидация","Güvenli:":"Безопасно:","⚠ Tehlike:":"⚠ Опасно:",
"bakiye, risk, entry ve stop girin…":"введите баланс, риск, вход и стоп…",
/* portfoy */
"Başlangıç $":"Старт $","Slot":"Слот","Kald.":"Плечо","Bugün":"Сегодня","7 gün":"7 дней","30 gün":"30 дней",
"kapasite-kısıtlı":"с учётом ёмкости","sınırsız varsayım":"допущение без лимита",
"alınan":"принято","atlanan":"пропущено","açık slot":"открытых слотов","açılan":"открыто","kapanan":"закрыто",
/* sekmeler ve durum cubugu */
"Özet":"Обзор","Sinyaller":"Сигналы","Piyasa":"Рынок","Ayar":"Настройки",
"Ayarlar":"Настройки","tercihler cihazında saklanır":"настройки хранятся на устройстве",
"Dil / Язык":"Язык / Dil","Yazı boyutu":"Размер шрифта","Yenileme":"Обновление",
"Araçlar":"Инструменты","Pozisyon hesaplayıcı":"Калькулятор позиции","🧮 Aç":"🧮 Открыть",
"Nasıl okunur?":"Как это читать?","Rehberi aç":"Открыть руководство",
"Ders kitabı":"Учебник","📗 Oku":"📗 Читать","Sistem":"Система",
"durum":"состояние","sürüm":"версия","gist sync":"синх. gist",
"canlı":"онлайн","bağlantı yok":"нет связи","veri":"данные","yanıt":"ответ",
"gist açık":"gist открыт","gist kapalı":"gist выключен","sync":"синх",
"gölge muhasebe · geçmiş performans garanti değildir · yatırım tavsiyesi değildir":
  "теневой учёт · прошлые результаты не гарантия · не инвестиционная рекомендация",
/* rehber modali */
"Nasıl okunur?":"Как это читать?","R (risk katsayısı)":"R (единица риска)",
"Win rate ve başabaş":"Винрейт и точка безубыточности","Filtre boru hattı":"Конвейер фильтров",
"Portföy ısısı":"Теплота портфеля","Ders Kitabı — stratejinin tam anlatımı":"Учебник — полное описание стратегии",
"Piyasa Nabzı / Saatlik Değerlendirme":"Пульс рынка / Часовой обзор",
/* diger */
"yazı boyutu":"размер шрифта","yenileme aralığı":"интервал обновления","Nasıl okunur?":"Как это читать?",
"Yazı: Normal":"Шрифт: обычный","Büyük":"Крупный","Çok Büyük":"Очень крупный",
"Ders Kitabı: stratejinin tam anlatımı":"Учебник: полное описание стратегии",
"devamını gör":"читать далее","daha fazla":"ещё",
"başabaş":"безубыток","doldu":"заполнено","değil":"нет","işlem":"сделка","tarama":"скан",
"sinyal sonuçlandı":"сигналов завершено","isabet":"точность","toplam":"итого",
"eşiğin üzerinde":"выше порога","eşiğin altında":"ниже порога",
"beklenti":"ожидание","maksDD":"макс. просадка","net":"чисто",
"WIN":"WIN","LOSS":"LOSS","PENDING":"PENDING","FILLED":"FILLED",
"gölge muhasebe: varsayımsal giriş, kayma/komisyon yok; yatırım tavsiyesi değildir.":
 "теневой учёт: гипотетический вход, без проскальзывания и комиссий; не инвестиционная рекомендация.",
"yükleniyor":"загрузка","güncelleniyor":"обновление",
"Entry bölgesi":"Зона входа",
"Korku & Açgözlülük":"Индекс страха и жадности","Genişlik":"Ширина",
"likit":"ликвидных","24S YÜKSELEN":"24Ч РОСТ","24S DÜŞEN":"24Ч ПАДЕНИЕ",
"canlı metrikler":"живые метрики","kripto haber · dış kaynak":"крипто-новости · внешний источник",
"durum":"состояние","veri":"данные","yanıt":"ответ","sürüm":"версия",
"gölge muhasebe · geçmiş performans garanti değildir · yatırım tavsiyesi değildir":
 "теневой учёт · прошлые результаты не гарантия · не инвестиционная рекомендация",
"başlıktaki TR/RU düğmesi":"кнопка TR/RU в шапке",
"Şimdi yenile":"Обновить сейчас","≥ 1.5× ort.":"≥ 1.5× сред.",
"Tüm sonuçlar":"Все результаты","gölge muhasebedir":"— теневой учёт",
": varsayımsal giriş, kayma/komisyon yok, gerçek emir yok. Geçmiş performans garanti değildir; yatırım tavsiyesi değildir. Haber başlıkları dış kaynaktan aynen aktarılır.":
 ": гипотетический вход, без проскальзывания и комиссий, без реальных ордеров. Прошлые результаты не гарантия; не инвестиционная рекомендация. Заголовки новостей передаются из внешнего источника без изменений.",
"Yapı önce gelir; indikatörler yalnız teyittir. Kenar net değilse karar":
 "Сначала структура; индикаторы лишь подтверждают. Если преимущество не очевидно — решение",
"Genişlik:":"Ширина:","24s yükselen":"24ч рост","24s düşen":"24ч падение",
"Korku":"Страх","Açgözlülük":"Жадность","Nötr":"Нейтрально",
"Gölge sinyalleri para yönetimi diline çevirir. Model: her kapanan işlemde bakiyenin, girdiğin Risk % kadarı riske atılır; sonuç bakiye × (1 + risk × R) olarak İŞLEM KAPANIŞ SIRASIYLA bileşik işler (örn. 10.000$ ve %1 riskte +2.2R kazanç = +220$, −1R kayıp = −100$). Bugün / 7 gün / 30 gün satırları, o pencerede kapanan işlemlerin bakiyeye net etkisidir; 'açılan' o gün üretilen sinyal sayısıdır (günler UTC). Başlangıç $ ve Risk % alanlarını buradan değiştirebilirsin — tarayıcında saklanır. Kayma/komisyon yoktur; simülasyondur, gerçek para değildir. KAPASİTE MODU: Slot ve Kaldıraç alanları gerçek sermaye kısıtını modeller — sermaye slotlara bölünür, defter doluyken gelen sinyal atlanır (atlanan sayısı gösterilir); 'sınırsız varsayım' satırı kısıtsız teorik bakiyeyi kıyas için verir.":
 "Переводит теневые сигналы на язык управления капиталом. Модель: в каждой закрытой сделке рискуем заданным % от баланса; результат считается сложным процентом В ПОРЯДКЕ ЗАКРЫТИЯ сделок (например, при 10 000$ и риске 1%: +2.2R = +220$, −1R = −100$). Строки Сегодня / 7 дней / 30 дней — чистое влияние закрытых в этом окне сделок; «открыто» — число сигналов, созданных за день (дни по UTC). Поля Старт $ и Риск % редактируются, значения хранятся в браузере. Проскальзывания и комиссий нет; это симуляция, не реальные деньги. РЕЖИМ ЁМКОСТИ: поля Слот и Плечо моделируют реальное ограничение капитала — капитал делится на слоты, при заполненной книге новый сигнал пропускается (счётчик показывает сколько); строка «допущение без лимита» даёт теоретический баланс без ограничений для сравнения.",
"Aynı motorun LONG ve SHORT taraflarının ayrı karnesi. Her yön için: sonuçlanan işlemlerin R toplamı (büyük rakam ve çubuk — 0 ekseninden sağa yeşil kâr, sola kırmızı zarar; ölçek iki yönün mutlak maksimumudur), W/L sayıları ve açık pozisyon adedi. Bir taraf sistematik eksideyse motor rejime ters işlem üretiyor demektir — v3.0 market gate tam olarak bu verinin üzerine inşa edildi. Bloğa tıklayınca sinyal tablosu o yönle filtrelenir.":
 "Отдельная сводка по сторонам LONG и SHORT одного и того же движка. Для каждого направления: сумма R по завершённым сделкам (крупное число и полоса — вправо от нуля зелёная прибыль, влево красный убыток; масштаб — максимум по модулю из двух сторон), счёт W/L и число открытых позиций. Если одна сторона систематически в минусе, движок торгует против режима — ворота рынка v3.0 построены именно на этих данных. Клик по блоку фильтрует таблицу сигналов по направлению.",
"Risk-first hesap: önce kaç $ riske atacağın belirlenir (bakiye × risk %), pozisyon büyüklüğü buradan TÜRETİLİR: miktar = risk$ / |entry − stop|. Kaldıraç kârı değil yalnızca bağlanan marjini değiştirir — stop'taki kayıp her kaldıraçta aynı risk$'dır. Likidasyon kontrolü, seçtiğin kaldıraçta likidasyonun stop'tan ÖNCE gelip gelmeyeceğini sınar (yaklaşık, izole marjin varsayımı). Değerler yaklaşıktır; yatırım tavsiyesi değildir.":
 "Расчёт от риска: сначала определяется сумма под риском (баланс × риск %), а размер позиции ВЫВОДИТСЯ из неё: количество = риск$ / |вход − стоп|. Плечо не меняет прибыль, оно меняет лишь занятую маржу — убыток на стопе при любом плече равен той же сумме риска. Проверка ликвидации показывает, наступит ли ликвидация РАНЬШЕ стопа при выбранном плече (приблизительно, изолированная маржа). Значения ориентировочные; не инвестиционная рекомендация.","TP1 / TP2":"TP1 / TP2","RR planı":"RR плана",
"Risk (fiyat)":"Риск (цена)","Fill fiyatı":"Цена входа","Çıkış fiyatı":"Цена выхода",
"Gerçekleşen R":"Фактический R","Son taramada aktif plan":"Активный план последнего скана",
"İnvalidasyon":"Инвалидация","Likidite":"Ликвидность","Confluence":"Конфлюэнс",
"güven":"уверенность","Gölge muhasebe: varsayımsal giriş, kayma/komisyon yok; yatırım tavsiyesi değildir.":
 "Теневой учёт: гипотетический вход, без проскальзывания и комиссий; не инвестиционная рекомендация.",
"🧮 Bu sinyalle pozisyon hesapla":"🧮 Рассчитать позицию по сигналу",
"Güvenli maks. kaldıraç":"Безопасное макс. плечо","riskin":"от риска",
"Bu paritede yaklaşık güvenli üst sınır":"Примерный безопасный предел по этой паре",
"Stop, yön ile tutarsız: LONG için stop < entry, SHORT için stop > entry olmalı.":
 "Стоп не согласован с направлением: для LONG стоп < входа, для SHORT стоп > входа.",
/* uzun aciklamalar */
"Her işlemin sonucu, riske atılan birim cinsinden: kayıp = −1R, kazanç = ödül/risk oranı kadar (+2.2R gibi).":
 "Результат каждой сделки в единицах риска: убыток = −1R, прибыль = отношение вознаграждения к риску (например +2.2R).",
"Kazançlar kayıplardan büyükse %50 isabet gerekmez. Başabaş = 1 / (1 + ort. kazanç R).":
 "Если выигрыши крупнее убытков, 50% точности не нужны. Безубыток = 1 / (1 + средний выигрыш R).",
"DATA → REGIME → HTF → LTF → VOLUME → MARKET GATE → RR; herhangi biri geçilemezse NO_TRADE. Aşamaya tıklayınca o aşamada elenen pariteler listelenir, üzerine gelince aşama açıklanır.":
 "DATA → REGIME → HTF → LTF → VOLUME → MARKET GATE → RR; если этап не пройден — NO_TRADE. Клик по этапу показывает отсеянные пары, наведение — пояснение.",
"Girişe gelmesi 6 saat beklenir; gelirse 48 saat izlenir. Önce stop = LOSS, önce hedef = WIN. NOT_FILLED orana dahil edilmez (hayalet R'si ayrıca izlenir); aynı mumda stop+hedef görülürse muhafazakâr kuralla LOSS sayılır.":
 "Подхода к зоне входа ждём 6 часов; при входе наблюдаем 48 часов. Сначала стоп = LOSS, сначала цель = WIN. NOT_FILLED в статистику не входит (его «призрачный» R учитывается отдельно); если в одной свече и стоп, и цель — консервативно считаем LOSS.",
"Aynı yönde en fazla 4, aynı kümede 2, toplamda 8 açık sinyal. Limit doluyken gelen sinyal reddedilmez, sıraya alınır ve ayrı kohortta izlenir.":
 "Не более 4 открытых сигналов в одну сторону, 2 в одном кластере, 8 суммарно. При заполненном лимите сигнал не отбрасывается, а ставится в очередь и отслеживается в отдельной когорте.",
"Kural tabanlı otomatik üretimdir (canlı insan/LLM yorumu değildir). Korku & Açgözlülük: alternative.me.":
 "Генерируется автоматически по правилам (не живой комментарий человека или LLM). Индекс страха и жадности: alternative.me.",
"Ders Kitabı — stratejinin tam anlatımı":"Учебник — полное описание стратегии",
"Değerler yaklaşıktır (likidasyon borsanın marjin modeline göre değişir; komisyon taker %0.055×2 varsayımı). Yatırım tavsiyesi değildir.":
 "Значения приблизительные (ликвидация зависит от маржинальной модели биржи; комиссия — допущение taker 0.055%×2). Не инвестиционная рекомендация."
};
/* kalip cevirileri (sayi iceren dinamik cumleler) */
const RU_PAT=[
 [/(\d+) sinyal sonuçlandı/, (m,n)=>`завершено сигналов: ${n}`],
 [/isabet %([\d.]+)/, (m,n)=>`точность ${n}%`],
 [/başabaş ~%([\d.]+)/, (m,n)=>`безубыток ~${n}%`],
 [/toplam ([+\-][\d.]+R)/, (m,n)=>`итого ${n}`],
 [/eşiğin (üzerinde|altında)/, (m,d)=>d==="üzerinde"?"выше порога":"ниже порога"],
 [/n<30, hüküm için erken/, ()=>"n<30, рано делать выводы"],
 [/(\d+) doldu \/ (\d+) değil/, (m,a,b)=>`${a} заполнено / ${b} нет`],
 [/(\d+) WIN · (\d+) LOSS · (\d+) açık/, (m,a,b,c)=>`${a} WIN · ${b} LOSS · ${c} откр.`],
 [/(\d+) sonuçlanan/, (m,n)=>`${n} завершено`],
 [/(\d+) kapanan/, (m,n)=>`${n} закрыто`],
 [/(\d+) açılan/, (m,n)=>`${n} открыто`],
 [/(\d+) dk önce/, (m,n)=>`${n} мин назад`],
 [/(\d+) sa önce/, (m,n)=>`${n} ч назад`],
 [/girişe ([+\-][\d.]+%)/, (m,n)=>`до входа ${n}`],
 [/([+\-][\d.]+)R canlı/, (m,n)=>`${n}R сейчас`],
 [/(\d+) parite/, (m,n)=>`${n} пар`],
 [/(\d+) tarama/, (m,n)=>`${n} сканов`],
 [/^ · likit (\d+)$/, (m,n)=>` · ликвидных ${n}`],
 [/^Tümü (\d+)$/, (m,n)=>`Все ${n}`],
 [/^Açık (\d+)$/, (m,n)=>`Открытые ${n}`],
 [/^Sonuç (\d+)$/, (m,n)=>`Результат ${n}`],
 [/^Dolmayan (\d+)$/, (m,n)=>`Не заполнено ${n}`],
 [/^(\d+) WIN \/ (\d+) LOSS$/, (m,a,b)=>`${a} WIN / ${b} LOSS`],

 [/başabaş ~%([\d.]+)/, (m,n)=>`безубыток ~${n}%`],
 [/hepsi \((\d+)\)/, (m,n)=>`все (${n})`],
 [/güven (HIGH|MEDIUM|LOW)/, (m,g)=>`уверенность ${g}`],
 [/riskin %([\d.]+)'i/, (m,n)=>`${n}% от риска`],
 [/~([\d]+)x/, (m,n)=>`~${n}x`]
];
let LANG="tr";
function trSeg(seg){                       // tek parca: sozluk -> kalip
  const t=seg.trim(); if(!t) return null;
  if(RU[t]!==undefined) return seg.replace(t,RU[t]);
  let out=seg, hit=false;
  for(const [re,fn] of RU_PAT){
    const m=out.match(re);
    if(m){ out=out.replace(m[0], fn(...m)); hit=true; }
  }
  return hit?out:null;
}
function tr1(s){                            // birlesik cumleleri parcalara ayir
  const t=s.trim(); if(!t) return null;
  if(RU[t]!==undefined) return s.replace(t,RU[t]);
  if(s.includes(" · ")){
    const parts=s.split(" · ");
    const done=parts.map(p=>trSeg(p));
    if(done.some(x=>x!==null))
      return parts.map((p,i)=>done[i]===null?p:done[i]).join(" · ");
    return null;
  }
  return trSeg(s);
}
const RU_LONG=[
 [/Tüm sonuçlar <b>gölge muhasebedir<\/b>/, "Все результаты — <b>теневой учёт</b>"],
];
function translateNode(root){
  if(LANG!=="ru") return;
  const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
  const jobs=[];
  while(w.nextNode()){ const n=w.currentNode;
    if(!n.nodeValue||!n.nodeValue.trim()) continue;
    if(n.parentElement&&n.parentElement.closest("[data-noi18n]")) continue;
    const out=tr1(n.nodeValue); if(out!==null) jobs.push([n,out]); }
  jobs.forEach(([n,v])=>{n.nodeValue=v;});
  root.querySelectorAll("[data-tip],[data-tipx],[title],[placeholder]").forEach(el=>{
    ["data-tip","data-tipx","title","placeholder"].forEach(a=>{
      const v=el.getAttribute(a); if(!v) return;
      const out=RU[v.trim()]||null; if(out) el.setAttribute(a,out);
      else{ // uzun tooltip metinleri: cumle cumle dene
        const parts=v.split(" · ").map(p=>RU[p.trim()]||p);
        if(parts.some((p,i)=>p!==v.split(" · ")[i])) el.setAttribute(a,parts.join(" · "));
      }
    });
  });
}
function applyLang(l){
  LANG=l;
  document.documentElement.lang=l;
  try{localStorage.setItem("ui_lang",l);}catch(e){}
  const b=$("bookBtn"); if(b) b.href = l==="ru" ? "/kitap?lang=ru" : "/kitap";
  const sb=$("setBook"), sp=$("setBookPdf");
  if(sb) sb.href = l==="ru" ? "/kitap?lang=ru" : "/kitap";
  if(sp) sp.href = l==="ru" ? "/kitap.pdf?lang=ru" : "/kitap.pdf";
  if(l==="ru") translateNode(document.body);
  else location.reload();
}

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
let PRICES={},PREV_PRICES={},PERF=null;
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
  $("modal").classList.add("show");translateNode($("modal"));
}
["overlay","modal","calc"].forEach(id=>{
  $(id).addEventListener("click",e=>{if(e.target.id===id)$(id).classList.remove("show");});
});
$("modalClose").addEventListener("click",()=>$("modal").classList.remove("show"));
$("calcClose").addEventListener("click",()=>$("calc").classList.remove("show"));
/* ---------- dil secimi ---------- */
(function initLang(){
  let saved=null;
  const urlLang=new URLSearchParams(location.search).get("lang");
  if(urlLang==="ru"||urlLang==="tr"){ saved=urlLang;
    try{localStorage.setItem("ui_lang",saved);}catch(e){} }
  else { try{saved=localStorage.getItem("ui_lang");}catch(e){} }
  if(saved){ LANG=saved; document.documentElement.lang=saved;
    const b=$("bookBtn"); if(b&&saved==="ru") b.href="/kitap?lang=ru";
    if(saved==="ru"){ const sb=$("setBook"), sp=$("setBookPdf");
      if(sb) sb.href="/kitap?lang=ru"; if(sp) sp.href="/kitap.pdf?lang=ru"; }
    $("langBtn").textContent=saved.toUpperCase(); }
  else { $("langpick").classList.add("show"); }
  document.querySelectorAll(".langbtn").forEach(btn=>
    btn.addEventListener("click",()=>{
      const l=btn.dataset.lang;
      try{localStorage.setItem("ui_lang",l);}catch(e){}
      LANG=l; document.documentElement.lang=l;
      $("langBtn").textContent=l.toUpperCase();
      const b=$("bookBtn"); if(b) b.href = l==="ru"?"/kitap?lang=ru":"/kitap";
      const sb=$("setBook"), sp=$("setBookPdf");
      if(sb) sb.href = l==="ru"?"/kitap?lang=ru":"/kitap";
      if(sp) sp.href = l==="ru"?"/kitap.pdf?lang=ru":"/kitap.pdf";
      $("langpick").classList.remove("show");
      location.replace(location.pathname + (l==="ru" ? "?lang=ru" : "?lang=tr"));
    }));
  $("langBtn").addEventListener("click",()=>{
    const next = LANG==="ru" ? "tr" : "ru";
    try{localStorage.setItem("ui_lang",next);}catch(e){}
    location.replace(location.pathname + (next==="ru" ? "?lang=ru" : "?lang=tr"));
  });
})();

/* ---------- mobil sekmeler ---------- */
function setTab(name){
  document.querySelectorAll(".col[data-tab]").forEach(el=>
    el.classList.toggle("on", el.dataset.tab===name));
  document.querySelectorAll(".tb").forEach(b=>
    b.classList.toggle("active", b.dataset.go===name));
  window.scrollTo({top:0,behavior:"smooth"});
  try{localStorage.setItem("ui_tab",name);}catch(e){}
}
document.querySelectorAll(".tb").forEach(b=>
  b.addEventListener("click",()=>setTab(b.dataset.go)));
/* mobilde header kontrollerini Ayar sekmesine tasi (masaustunde geri al) */
function placeControls(){
  const mob=window.matchMedia("(max-width:760px)").matches;
  const move=(el,hostId)=>{ if(!el)return;
    const host=$(hostId), hdr=document.querySelector(".hctl");
    if(mob&&host&&el.parentElement!==host) host.appendChild(el);
    if(!mob&&hdr&&el.parentElement!==hdr) hdr.appendChild(el);
  };
  move($("fs"),"setFs"); move($("iv"),"setIv");   /* dil dugmesi baslikta kalir */
}
window.addEventListener("resize",()=>{clearTimeout(window.__pc);
  window.__pc=setTimeout(placeControls,200);});
$("setCalc").addEventListener("click",()=>openCalc(null));
$("setHowto").addEventListener("click",()=>$("overlay").classList.add("show"));
placeControls();
(function initTab(){
  let t="ozet";
  try{t=localStorage.getItem("ui_tab")||"ozet";}catch(e){}
  if(t==="ayar")t="ozet";
  setTab(t);
})();
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
  const TIPS_RU={
    "Win Rate":"Доля выигрышных среди завершённых (WIN+LOSS) сигналов — NOT_FILLED не учитывается. Строка ниже — точка безубыточности: 1 / (1 + средний выигрыш в R). Если винрейт выше этого порога, система в плюсе. · клик → фильтр завершённых",
    "Toplam R":"Сумма R по всем завершённым сделкам. R = единица риска: убыток −1R, прибыль равна отношению вознаграждения к риску (например +2.2R). Ниже: валовая прибыль / валовой убыток. Считает не деньги, а единицы риска — так сравнимы любые пары. · клик → фильтр завершённых",
    "Açık Pozisyon":"Сигналы в теневом учёте, ещё не завершённые: PENDING (ждём подхода к зоне входа, 6 ч) + FILLED (вход исполнен, наблюдение 48 ч). · клик → фильтр открытых",
    "Giriş İsabeti":"Доля сигналов, у которых цена дошла до зоны входа. NOT_FILLED = за 6 часов цена так и не пришла; в статистику прибыли/убытка не входит. · клик → фильтр незаполненных",
    "Taranan Evren":"Число пар, отбираемых ежедневно по 24-часовому обороту, и счётчик сканов. Каждый цикл (~15 минут) прогоняет всю вселенную через 7 фильтров. · клик → все сигналы"};
  const TIPS_TR={
    "Win Rate":"Sonuçlanan (WIN+LOSS) sinyaller içinde kazananların oranı — NOT_FILLED hesaba katılmaz. Alt satırdaki başabaş, kâra geçiş eşiğidir: 1 / (1 + ortalama kazanç R). Win rate bu eşiğin üzerindeyse sistem artıdadır. · tıkla → sonuçlananları filtrele",
    "Toplam R":"Tüm sonuçlanan işlemlerin R toplamı. R = riske atılan birim: kayıp −1R, kazanç ödül/risk oranı kadar (+2.2R gibi). Alt satır: brüt kazanç / brüt kayıp. Para değil, risk birimi sayar — pariteler böyle karşılaştırılır. · tıkla → sonuçlananları filtrele",
    "Açık Pozisyon":"Gölge takipte hâlâ sonuçlanmamış sinyaller: PENDING (girişe gelmesi bekleniyor, 6 sa) + FILLED (dolu, 48 sa izlemede). · tıkla → açıkları filtrele",
    "Giriş İsabeti":"Üretilen sinyallerden fiyatı giriş bölgesine gelip dolanların oranı. NOT_FILLED = 6 saat içinde fiyat girişe hiç uğramadı; kazanç/kayıp oranına dahil edilmez. · tıkla → dolmayanları filtrele",
    "Taranan Evren":"24s hacme göre her gün yeniden seçilen parite sayısı ve bugüne kadarki tarama turu. Her tur ~15 dakikada bir tüm evreni 7 aşamalı filtreden geçirir. · tıkla → tüm sinyaller"};
  const TIPS = (typeof LANG!=="undefined"&&LANG==="ru") ? TIPS_RU : TIPS_TR;
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
    FILTER=k.dataset.f;renderChips();renderSignals();
    if(window.matchMedia("(max-width:760px)").matches)setTab("sinyaller");}));
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
  const netTxt=(PERF&&PERF.expectancy_net!=null)?` · net <b class="num">${(PERF.expectancy_net>0?"+":"")+num(PERF.expectancy_net,2)}R</b>`:"";
  if(st)st.innerHTML=`PF <b class="num">${pf==null?"∞":num(pf,2)}</b> · beklenti <b class="num">${(exp>0?"+":"")+num(exp,2)}R</b>/${LANG==="ru"?"сделку":"işlem"}${netTxt} · maksDD <b class="num neg">−${num(maxDD,2)}R</b>`;
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
    <div class="dstat">${d.w} WIN · ${d.l} LOSS · ${d.open} ${LANG==="ru"?"откр.":"açık"}</div></div>`;
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
const STEPS_RU={
 "DATA":["Недостаточно свечей (новый листинг)","Достаточно ли истории? Нужны минимум 60 закрытых баров на 4H и 15m. У новых листингов истории нет; вместо догадок движок говорит DATA_MISSING."],
 "REGIME":["ADX<20: рынок без направления","Есть ли направление или это пила? Если ADX (сила тренда) ниже 20, пара считается бесцельной и отсеивается. В такой фазе большинство пробоев — ловушки."],
 "HTF STRUCTURE":["Структура 4H противоречива","Анализ 4-часовой структуры: растущие минимумы-максимумы (HH-HL) или падающие (LH-LL)? Если вместе с положением EMA200 сторона не определяется — отсев. В нерешительном рынке это самый частый фильтр, и это здорово."],
 "LTF SETUP":["Нет подтверждённого ретеста/свипа","На 15m ищется конкретная формация: ретест принятого уровня после пробоя либо возврат уровня после снятия ликвидности (sweep-reclaim). «Красиво выглядит» недостаточно."],
 "VOLUME":["Объём триггера <1.5× сред.","Объём триггерного бара должен быть не ниже 1.5× среднего за 20 баров. Пробой без участия крупного игрока не выносит движение."],
 "MARKET GATE":["Направление против режима заблокировано","Фильтр v3.0: по закрытию BTC 4H относительно EMA200 определяется режим (бык/медведь/нейтраль, гистерезис ±0.5%, подтверждение двумя закрытиями). Сигналы ПРОТИВ режима блокируются: лонги в медвежьем, шорты в бычьем. Если данных BTC нет дольше 2 часов — ворота закрывают оба направления (fail-closed)."],
 "RISK/REWARD":["RR плана вне диапазона (<2 / >6)","Диапазон риск/прибыль 2.0–6.0. Нижняя граница: цель должна быть минимум вдвое дальше риска. Верхняя (v3.0): RR>6 обычно означает стоп, вжатый в цену; рыночный шум выбивает его первой волной. В теневых данных все 4 сигнала с RR≥6 проиграли."],
 "SIGNAL":["Прошедшие все этапы берутся в учёт","Решения, прошедшие все семь этапов. Берутся в теневой учёт: 6 часов ждём подхода цены к зоне входа; при входе — 48 часов наблюдения (сначала стоп = LOSS, сначала цель = WIN)."]};
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
      `<div class="note">${LANG==="ru"
        ?"Решения, прошедшие все этапы; берутся в теневой учёт."
        :"Tüm aşamaları geçen kararlar; gölge takibe alınır."}</div>`);
    return;
  }
  const st=STEPS.find(s=>s[0]===name);
  const _rp = (LANG==="ru");
  const _desc = _rp && typeof STEPS_RU!=="undefined" && STEPS_RU[name]
    ? STEPS_RU[name][0] : (st?st[1]:"");
  openModal(name+" · "+rows.length+(_rp?" пар отсеяно":" parite elendi"),
    `<div class="note"><b>${_desc}</b> — ${_rp
      ? `это фильтр «${name}» движка; не прошедшая пара получает NO_TRADE в этом скане.`
      : `bu aşama motorun "${name}" filtresidir; geçilemeyen parite o taramada NO_TRADE olur.`}</div>
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
  const _ru = (typeof LANG!=="undefined"&&LANG==="ru");
  $("pipe").innerHTML=STEPS.map(([n,d,,col,tip])=>{
    const c=cnt[n]||0;
    if(_ru&&STEPS_RU[n]){ d=STEPS_RU[n][0]; tip=STEPS_RU[n][1]; }
    return `<div class="step" data-s="${n}" data-tipx="${tip}" tabindex="0">
      <div class="h"><span>${n}</span><span class="n num">−${c}</span></div>
      <div class="d">${d}</div>
      <div class="g"><div style="width:${Math.min(100,100*c/total)}%;background:${col}"></div></div></div>`;
  }).join("")+
  `<div class="step" data-s="SIGNAL" data-tipx="${_ru?STEPS_RU.SIGNAL[1]:SIGNAL_TIP}" tabindex="0"><div class="h"><span class="pos">→ SIGNAL</span><span class="n num pos">${sig}</span></div>
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
    g("Kapanış",s.closed_utc?fmtTs(s.closed_utc)+" UTC":"—")+
    g("Setup / Güven",(s.setup_type||"—")+" / "+(s.confidence||"—"))+
    g("Net R (maliyet v0)",s.r_net!=null?((s.r_net>0?"+":"")+num(s.r_net)):"—")+"</div>";
  const live=LAST_STATUS&&LAST_STATUS.results&&LAST_STATUS.results[s.pair];
  if(live&&live.decision==="SIGNAL"){
    html+=`<div class="note"><b>Son taramada aktif plan:</b> ${live.setup_type||""} · güven ${live.confidence||""}<br>
      <b>İnvalidasyon:</b> ${live.invalidation||"—"}<br>
      <b>Likidite:</b> ${live.liquidity_note||"—"}<br>
      <b>Confluence:</b> ${(live.indicator_confluence||[]).join(", ")||"—"}</div>`;
  }
  html+='<div class="note">Gölge muhasebe: varsayımsal giriş, kayma/komisyon yok; yatırım tavsiyesi değildir.</div>';
  html=`<div class="evid" id="evidBox"><div class="empty">${LANG==="ru"?"загрузка графика…":"grafik yükleniyor…"}</div></div>`+html;
  html+=`<div style="margin-top:10px"><button onclick='window.__calcSig(${s.id})'>🧮 ${LANG==="ru"?"Рассчитать позицию по сигналу":"Bu sinyalle pozisyon hesapla"}</button></div>`;
  openModal(s.pair,html);
  loadEvidence(s.id);
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
      pxCell=`<td class="num c-px${tick}"><b>${fmtPx(px)}</b><div class="age ${cls}">${ur==null?"":(ur>0?"+":"")+num(ur)+"R canlı"}</div></td>`;
    }else if(o==="PENDING"){
      const ref=s.direction==="LONG"?s.entry_max:s.entry_min;
      const dist=ref?100*(px-ref)/ref:null;
      pxCell=`<td class="num c-px${tick}"><b>${fmtPx(px)}</b><div class="age">${dist==null?"":"girişe "+(dist>0?"+":"")+num(dist,1)+"%"}</div></td>`;
    }else{
      pxCell=`<td class="num c-px" style="color:var(--muted)">${fmtPx(px)}</td>`;
    }
    return `<tr data-i="${i}" class="dir-${s.direction}${o==="NOT_FILLED"?" dim":""}">
      <td class="num c-id">${s.id}</td>
      <td class="c-pair"><b>${s.pair}</b>${s.confidence?`<span class="conf ${s.confidence}" title="${LANG==="ru"?"уверенность":"güven"}: ${s.confidence}${s.setup_type?" · "+s.setup_type:""}">${s.confidence[0]}</span>`:""}</td>
      <td class="c-dir"><span class="badge b-${s.direction}">${s.direction}</span></td>
      <td class="c-time">${fmtTs(s.created_utc)}${age}</td>
      <td class="c-st"><span class="badge b-${o}">${o}</span></td>
      ${pxCell}
      <td class="num c-lv"><span data-l="giriş">${num(s.entry_min,4)}–${num(s.entry_max,4)}</span><span data-l="stop">${num(s.stop_loss,4)}</span><span data-l="tp1">${num(s.tp1,4)}</span><span data-l="rr">${num(s.rr,2)}</span></td>
      <td class="num c-r ${r>0?"pos":r<0?"neg":""}"><b>${r==null?"—":(r>0?"+":"")+num(r)}</b></td></tr>`;}).join("");
  el.innerHTML=`<table><thead><tr><th>#</th><th>Parite</th><th>Yön</th>
    <th>Zaman</th><th>Durum</th><th class="r">Anlık</th>
    <th class="r lvh">Giriş / Stop / TP1 / RR</th>
    <th class="r">R</th></tr></thead><tbody>${tr}</tbody></table>`;
  el.querySelectorAll("tbody tr").forEach(row=>row.addEventListener("click",
    ()=>signalDetail(rows[Number(row.dataset.i)])));
}

/* ---------- sag panel ---------- */
function renderReview(comments){
  const el=$("review");
  if(!comments||!comments.length){
    el.innerHTML=`<div class="empty">${LANG==="ru"?"первый обзор появится после первого цикла сканирования…":"ilk değerlendirme ilk tarama turundan sonra üretilir…"}</div>`;return;}
  const latest=comments[0];
  const _ct=(LANG==="ru"&&latest.text_ru)?latest.text_ru:latest.text;
  const paras=_ct.split("\n").map(t=>
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
  const br=m.breadth?`<div class="breadth num"><b>${LANG==="ru"?"Ширина:":"Genişlik:"}</b>
    <span class="pos">${m.breadth.advancers}▲</span> /
    <span class="neg">${m.breadth.decliners}▼</span>
    <span> · ${LANG==="ru"?"ликвидных":"likit"} ${m.liquid_universe}</span></div>`:"";
  const link=s=>`https://www.bybit.com/trade/usdt/${s}`;
  const mov=list=>list.map(t=>{
    const cls=t.pct24h>0?"pos":"neg";
    return `<a href="${link(t.symbol)}" target="_blank" rel="noopener" title="Bybit'te aç">
      <span>${t.symbol.replace("USDT","")}</span>
      <span class="num ${cls}">${(t.pct24h>0?"+":"")+num(t.pct24h,1)}%</span></a>`;}).join("");
  const _pl = (LANG==="ru"&&m.pulse_ru)?m.pulse_ru:m.pulse;
  const _pltag = LANG==="ru"?"пульс рынка · чтение по правилам":"market pulse · kural-tabanlı okuma";
  const pulse=_pl?`<div class="pulse"><span class="tg">${_pltag}</span><br>${_pl}</div>`:"";
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
    const sl=localStorage.getItem("pf_slots"),lv=localStorage.getItem("pf_lev");
    if(c)$("pfCap").value=c;
    if(r)$("pfRisk").value=r;
    if(sl)$("pfSlots").value=sl;
    if(lv)$("pfLev").value=lv;
  }catch(e){}
}
function pfSave(){
  try{
    localStorage.setItem("pf_capital",$("pfCap").value);
    localStorage.setItem("pf_risk",$("pfRisk").value);
    localStorage.setItem("pf_slots",$("pfSlots").value);
    localStorage.setItem("pf_lev",$("pfLev").value);
  }catch(e){}
}
function renderPortfolio(signals){
  const cap0=Math.max(1,Number($("pfCap").value)||10000);
  const riskPct=Math.min(10,Math.max(.1,Number($("pfRisk").value)||1))/100;
  const K=Math.min(30,Math.max(1,Math.round(Number($("pfSlots").value)||5)));
  const L=Math.min(25,Math.max(1,Number($("pfLev").value)||3));
  const T0=Date.parse;
  const ts=s=>T0((s||"").endsWith("Z")?s:(s||"")+"Z");
  const now=Date.now();
  const dayStart=new Date();dayStart.setUTCHours(0,0,0,0);
  const T={gun:dayStart.getTime(),hafta:now-7*864e5,ay:now-30*864e5};
  /* olay listesi: dogum + kapanis */
  const evs=[];
  for(const s of (signals||[])){
    if(!s.created_utc)continue;
    evs.push([ts(s.created_utc),0,s]);
    if(s.closed_utc)evs.push([ts(s.closed_utc),1,s]);
  }
  evs.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
  /* kapasite-kisitli yurutme */
  let eq=cap0,taken=0,skipped=0;const book={};
  const at={gun:cap0,hafta:cap0,ay:cap0},cnt={gun:0,hafta:0,ay:0},
        seen={gun:false,hafta:false,ay:false};
  for(const [t,kind,s] of evs){
    if(kind===0){
      if(Object.keys(book).length>=K){skipped++;continue;}
      const e=s.direction==="LONG"?s.entry_max:s.entry_min;
      const d=e?Math.abs(e-s.stop_loss)/e:0;
      if(d<=0)continue;
      let r=eq*riskPct;const n=r/d,capN=eq/K*L;
      if(n>capN)r*=capN/n;
      book[s.id]=r;taken++;
    }else{
      const r=book[s.id];if(r==null)continue;delete book[s.id];
      if(s.outcome==="WIN"||s.outcome==="LOSS"){
        for(const k of ["gun","hafta","ay"]){
          if(!seen[k]&&t>=T[k]){at[k]=eq;seen[k]=true;}
          if(t>=T[k])cnt[k]++;
        }
        eq+=r*(s.r_multiple||0);
      }
    }
  }
  for(const k of ["gun","hafta","ay"])if(!seen[k])at[k]=eq;
  /* sinirsiz referans (eski model) */
  let ref=cap0;
  (signals||[]).filter(s=>(s.outcome==="WIN"||s.outcome==="LOSS")&&s.closed_utc)
    .sort((a,b)=>a.closed_utc.localeCompare(b.closed_utc))
    .forEach(s=>{ref*=1+riskPct*(s.r_multiple||0);});
  const openedToday=(signals||[]).filter(s=>ts(s.created_utc||"")>=T.gun).length;
  const money=v=>"$"+v.toLocaleString("en-US",{maximumFractionDigits:0});
  const totPct=100*(eq-cap0)/cap0, refPct=100*(ref-cap0)/cap0;
  const row=(lbl,base,n,extra)=>{
    const d=eq-base,p=base?100*d/base:0;
    const cls=d>0?"pos":d<0?"neg":"";
    const sign=d>=0?"+":"−";
    return `<div class="prow"><span class="w">${lbl}</span>
      <span class="d num ${cls}">${sign}${money(Math.abs(d))} <span style="font-weight:500">(${(p>0?"+":"")+num(p,2)}%)</span></span>
      <span class="c num">${n} kapanan${extra||""}</span></div>`;
  };
  $("pfBody").innerHTML=
    `<div class="bal"><div style="display:flex;justify-content:space-between;align-items:baseline">
       <span class="b num">${money(eq)}</span>
       <span class="p num ${totPct>0?"pos":totPct<0?"neg":""}">${(totPct>0?"+":"")+num(totPct,2)}%</span></div>
       <div class="c" style="font-size:9.8px;color:var(--muted)">kapasite-kısıtlı · ${taken} ${LANG==="ru"?"принято":"alınan"} / ${skipped} ${LANG==="ru"?"пропущено":"atlanan"} · ${Object.keys(book).length} ${LANG==="ru"?"открытых слотов":"açık slot"}</div></div>`+
    `<div class="prow"><span class="w" style="width:auto">sınırsız varsayım</span>
      <span class="d num ${refPct>0?"pos":refPct<0?"neg":""}" style="font-weight:500">${money(ref)} (${(refPct>0?"+":"")+num(refPct,1)}%)</span><span class="c"></span></div>`+
    row("Bugün",at.gun,cnt.gun," / "+openedToday+" açılan")+
    row("7 gün",at.hafta,cnt.hafta)+
    row("30 gün",at.ay,cnt.ay)+
    `<div class="foot">${LANG==="ru"
      ? `Модель ёмкости: капитал делится на ${K} слотов (маржа слота × потолок плеча ${L}x); при заполненной книге новый сигнал ПРОПУСКАЕТСЯ; риск ${(riskPct*100).toFixed(1)}%, сложный процент в порядке закрытия сделок. Без проскальзывания и комиссий; это симуляция, не реальные деньги. Дни по UTC.</div>`
      : `Kapasite modeli: sermaye ${K} slota bölünür (slot marjini × ${L}x kaldıraç tavanı); defter doluyken gelen sinyal ATLANIR; risk %${(riskPct*100).toFixed(1)}, işlem kapanış sırasıyla bileşik. Kayma/komisyon yok; gölge simülasyondur, gerçek para değildir. Günler UTC.</div>`}`;
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

let EV_ZOOM=24;
async function loadEvidence(id,win){
  const box=$("evidBox"); if(!box) return;
  const ru=(LANG==="ru");
  if(win) EV_ZOOM=win;
  try{
    const d=await j(`/signal/${id}/chart?before=${EV_ZOOM}&after=${EV_ZOOM}`);
    if(!d||d.error){box.innerHTML=`<div class="empty">${ru?"данные графика недоступны":"grafik verisi yok"}</div>`;return;}
    const e=d.evidence||{}, s=d.signal||{};
    const rows=[];
    if(s.setup_type) rows.push(`<b>${ru?"формация":"kurulum"}</b> ${s.setup_type}${s.confidence?` · ${ru?"уверенность":"güven"} ${s.confidence}`:""}`);
    if(e.liquidity) rows.push(`<b>${ru?"ликвидность":"likidite"}</b> ${e.liquidity}`);
    if(e.confluence) rows.push(`<b>${ru?"конфлюэнс":"confluence"}</b> ${e.confluence}`);
    if(e.invalidation) rows.push(`<b>${ru?"инвалидация":"invalidasyon"}</b> ${e.invalidation}`);
    if(e.regime||e.htf_bias) rows.push(`<b>${ru?"режим / 4H":"rejim / 4H"}</b> ${[e.regime,e.htf_bias].filter(Boolean).join(" · ")}`);
    const zb=[[12,ru?"вблизи":"yakın"],[24,ru?"обычно":"normal"],[48,ru?"шире":"geniş"]]
      .map(([v,l])=>`<button class="${EV_ZOOM===v?"on":""}" onclick="loadEvidence(${id},${v})">${l}</button>`).join("");
    box.innerHTML=`<div class="zoombar"><span class="zl">${ru?"окно графика":"grafik penceresi"}: ±${EV_ZOOM} ${ru?"свечей 15m":"mum (15m)"}</span>${zb}</div>`+
      drawEvidence(d)+
      (rows.length?`<div class="evlist">${rows.map(r=>`<div>${r}</div>`).join("")}</div>`:"");
    translateNode(box);
  }catch(err){
    box.innerHTML=`<div class="empty">${ru?"график недоступен":"grafik alınamadı"}</div>`;
  }
}

/* ---------- kanit grafigi (mum + plan + teyitler) ---------- */
function drawEvidence(d){
  const cs=(d.candles||[]).filter(c=>c.high!=null);
  const s=d.signal||{}, ru=(LANG==="ru");
  if(cs.length<5) return `<div class="empty">${ru?"недостаточно свечей для графика":"grafik için yeterli mum yok"}</div>`;
  const W=760,H=460,PADL=8,PADR=70,TOP=12,VOLH=74,GAP=10;
  const CH=H-VOLH-GAP-TOP;
  const lvls=[s.entry_min,s.entry_max,s.stop_loss,s.tp1,s.tp2].filter(v=>v!=null);
  let lo=Math.min(...cs.map(c=>c.low),...lvls), hi=Math.max(...cs.map(c=>c.high),...lvls);
  const pad=(hi-lo)*0.06||hi*0.01; lo-=pad; hi+=pad;
  const X=i=>PADL+i*((W-PADL-PADR)/cs.length);
  const BW=Math.max(3,(W-PADL-PADR)/cs.length*0.66);
  const Y=v=>TOP+CH-((v-lo)/(hi-lo))*CH;
  const vmax=Math.max(...cs.map(c=>c.volume||0))||1;
  const VY=v=>H-(v/vmax)*VOLH;
  const trig=cs.findIndex(c=>c.ts===s.entry_candle_ts);
  // hacim ortalamasi (son 20)
  const vavg=cs.slice(Math.max(0,trig-20),trig).reduce((a,c)=>a+(c.volume||0),0)/Math.max(1,Math.min(20,trig));
  let out=`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-family="JetBrains Mono, monospace" font-size="12">`;
  // plan bantlari
  if(s.entry_min!=null&&s.entry_max!=null){
    const y1=Y(Math.max(s.entry_min,s.entry_max)), y2=Y(Math.min(s.entry_min,s.entry_max));
    out+=`<rect x="0" y="${y1}" width="${W-PADR}" height="${Math.max(2,y2-y1)}" fill="#2563EB" opacity="0.13"/>
      <text x="${W-PADR+4}" y="${(y1+y2)/2+3}" fill="#2563EB">${ru?"вход":"giriş"}</text>`;
  }
  const line=(v,col,lbl,dash)=>v==null?"":`<line x1="0" y1="${Y(v)}" x2="${W-PADR}" y2="${Y(v)}"
      stroke="${col}" stroke-width="1.4" ${dash?'stroke-dasharray="5 4"':""}/>
      <text x="${W-PADR+4}" y="${Y(v)+3}" fill="${col}">${lbl}</text>`;
  out+=line(s.stop_loss,"#DC2626","STOP");
  out+=line(s.tp1,"#16A34A","TP1");
  out+=line(s.tp2,"#16A34A","TP2",true);
  // mumlar + hacim
  cs.forEach((c,i)=>{
    const up=c.close>=c.open, col=up?"#16A34A":"#DC2626";
    const isTrig=(i===trig);
    out+=`<line x1="${X(i)+BW/2}" y1="${Y(c.high)}" x2="${X(i)+BW/2}" y2="${Y(c.low)}" stroke="${col}" stroke-width="1"/>
      <rect x="${X(i)}" y="${Y(Math.max(c.open,c.close))}" width="${BW}"
        height="${Math.max(1,Math.abs(Y(c.open)-Y(c.close)))}" fill="${col}"
        ${isTrig?'stroke="#2563EB" stroke-width="1.6"':""}/>
      <rect x="${X(i)}" y="${VY(c.volume||0)}" width="${BW}" height="${H-VY(c.volume||0)}"
        fill="${isTrig?"#2563EB":col}" opacity="${isTrig?0.85:0.28}"/>`;
  });
  // hacim esigi
  if(vavg>0){const ty=VY(vavg*1.5);
    out+=`<line x1="0" y1="${ty}" x2="${W-PADR}" y2="${ty}" stroke="#B45309" stroke-width="1" stroke-dasharray="4 3"/>
      <text x="${W-PADR+4}" y="${ty+3}" fill="#B45309">1.5×</text>`;}
  // tetik isareti
  if(trig>=0){
    out+=`<line x1="${X(trig)+BW/2}" y1="${TOP}" x2="${X(trig)+BW/2}" y2="${TOP+CH}"
        stroke="#2563EB" stroke-width="1" stroke-dasharray="3 4" opacity="0.7"/>
      <text x="${X(trig)+BW/2+3}" y="${TOP+9}" fill="#2563EB">${ru?"сигнал":"sinyal"}</text>`;}
  // dolus / cikis noktalari
  const mark=(ts,px,col,lbl)=>{
    if(px==null) return "";
    let idx=cs.findIndex(c=>c.ts>=ts); if(idx<0) idx=cs.length-1;
    return `<circle cx="${X(idx)+BW/2}" cy="${Y(px)}" r="4" fill="${col}" stroke="#FFFEFA" stroke-width="1.5"/>
      <text x="${X(idx)+BW/2+7}" y="${Y(px)-6}" fill="${col}">${lbl}</text>`;};
  if(s.fill_price!=null) out+=mark(s.entry_candle_ts,s.fill_price,"#2563EB",ru?"вход":"doluş");
  if(s.exit_price!=null&&s.closed_utc)
    out+=mark(Date.parse(s.closed_utc.replace(" ","T"))||cs[cs.length-1].ts,s.exit_price,
      (s.outcome==="WIN"?"#16A34A":"#DC2626"),s.outcome||"");
  out+="</svg>";
  const lg=(c,t)=>`<span><i style="background:${c}"></i>${t}</span>`;
  out+=`<div class="lgd">${lg("#2563EB",ru?"зона входа / триггер":"giriş bölgesi / tetik")}
    ${lg("#DC2626","STOP")}${lg("#16A34A","TP1/TP2")}
    ${lg("#B45309",ru?"порог объёма 1.5×":"hacim eşiği 1.5×")}</div>`;
  return out;
}
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
  $("calc").classList.add("show");translateNode($("calc"));
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
  const _ru2 = (typeof LANG!=="undefined"&&LANG==="ru");
  rows+=liqSafe?
    (_ru2
      ? `<div class="note" style="border-left:3px solid var(--green)"><b>Безопасно:</b> при плече ${lev}x ликвидация (${fmtPx(liq)}) находится за стопом (${fmtPx(st)}) — сработает стоп из плана. Примерный безопасный предел по этой паре ~${maxLev}x.</div>`
      : `<div class="note" style="border-left:3px solid var(--green)"><b>Güvenli:</b> ${lev}x kaldıraçta likidasyon (${fmtPx(liq)}) stop'un (${fmtPx(st)}) ötesinde — plan stop'u çalışır. Bu paritede yaklaşık güvenli üst sınır ~${maxLev}x.</div>`)
    :
    (_ru2
      ? `<div class="note" style="border-left:3px solid var(--red)"><b>⚠ Опасно:</b> при плече ${lev}x ликвидация (${fmtPx(liq)}) наступит раньше стопа — сработает не стоп из плана, а ликвидация биржи, и убыток превысит сумму риска. Снизьте плечо ниже ~${maxLev}x.</div>`
      : `<div class="note" style="border-left:3px solid var(--red)"><b>⚠ Tehlike:</b> ${lev}x kaldıraçta likidasyon (${fmtPx(liq)}) stop'a ulaşmadan tetiklenir — planın stop'u değil borsa likidasyonu çalışır ve kayıp risk$'ı aşar. Kaldıracı ~${maxLev}x altına çek.</div>`);
  rows+= _ru2 ? '<div class="note">Значения приблизительные (ликвидация зависит от маржинальной модели биржи; комиссия — допущение taker 0.055%×2). Не инвестиционная рекомендация.</div>'
    : '<div class="note">Değerler yaklaşıktır (likidasyon borsanın marjin modeline göre değişir; komisyon taker %0.055×2 varsayımı). Yatırım tavsiyesi değildir.</div>';
  out.innerHTML=rows;translateNode(out);
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
    `<span>v3.5</span>`+
    `<span class="right">gölge muhasebe · geçmiş performans garanti değildir · yatırım tavsiyesi değildir</span>`;
  const ss=$("setSys"), _r=(LANG==="ru");
  if(ss) ss.innerHTML=`<div class="syslist">
    ${healthy?"● ":"○ "}${_r?"состояние":"durum"}: <b>${healthy?(_r?"онлайн":"canlı"):(_r?"нет связи":"bağlantı yok")}</b><br>
    ${_r?"данные":"veri"}: <b>${new Date().toLocaleTimeString(_r?"ru-RU":"tr-TR")}</b><br>
    ${_r?"ответ":"yanıt"}: <b>${ms} ms</b><br>
    ${backup&&backup.last_sync_utc?`${_r?"синх. gist":"gist sync"}: <b>${fmtTs(backup.last_sync_utc)}</b><br>`:""}
    ${_r?"версия":"sürüm"}: <b>v3.5</b></div>
    <div class="note" style="margin-top:10px">${_r
      ?"теневой учёт · прошлые результаты не гарантия · не инвестиционная рекомендация"
      :"gölge muhasebe · geçmiş performans garanti değildir · yatırım tavsiyesi değildir"}</div>`;
  if(perf&&perf.total_r_multiple!=null){
    const tr=perf.total_r_multiple;
    document.title=`${tr>=0?"▲":"▼"} ${(tr>0?"+":"")+num(tr,1)}R · signal-engine`;
  }
}

/* ---------- loop ---------- */
async function refresh(){
  const t0=performance.now();
  const [perf,signals,status,uni,comments,market,news,px,backup]=await Promise.all([
    j("/performance"),j("/signals?limit=500"),j("/status"),j("/universe"),
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
  $("updated").textContent=new Date().toLocaleTimeString(LANG==="ru"?"ru-RU":"tr-TR");
  translateNode(document.body);
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
["pfCap","pfRisk","pfSlots","pfLev"].forEach(id=>$(id).addEventListener("input",()=>{
  pfSave();renderPortfolio(SIGNALS);}));
refresh();schedule();
</script>
</body>
</html>
"""
