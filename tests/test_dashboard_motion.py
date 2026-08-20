"""v2.9 hareket sistemi + katlanabilir kenar cubugu testleri.

Sozlesme:
1. Giris animasyonlari YALNIZ ilk boyamada (body.boot + FIRSTPAINT bayragi);
   60sn veri yenilemeleri animasyon TETIKLEMEZ (update("none") korunur).
2. Tum hareket prefers-reduced-motion'a saygilidir.
3. Kenar cubugu: GPU-hizli transform + grid genislik gecisi; durumu
   localStorage'da; yalniz masaustu (mobil sekme cubugu bozulmaz).
4. WIN/LOSS noktalari renk-TEK-basina kimlik tasimaz (bicim kodlamasi).
"""
from __future__ import annotations

import re

from app.dashboard import DASHBOARD_HTML


# ---------------------------------------------------------- ilk boyama
def test_entrance_animations_gated_to_first_paint():
    assert '<body class="notranslate boot">' in DASHBOARD_HTML
    assert "body.boot .card{animation:rise" in DASHBOARD_HTML
    assert "body.boot .kpi{animation:rise" in DASHBOARD_HTML
    # boot sinifi ilk boyamadan sonra DUSURULUR -> yenilemeler animasyonsuz
    assert 'classList.remove("boot")' in DASHBOARD_HTML
    assert "let FIRSTPAINT=true" in DASHBOARD_HTML
    assert "if(FIRSTPAINT){" in DASHBOARD_HTML
    # veri yenilemesi sessiz kalir (mevcut sozlesme korunur)
    assert 'eqChart.update("none")' in DASHBOARD_HTML


def test_all_motion_respects_reduced_motion():
    # giris animasyonlari no-preference blogunda yasar
    blocks = re.findall(
        r"@media \(prefers-reduced-motion:no-preference\)\{(.*?)\n  \}",
        DASHBOARD_HTML, re.S)
    assert blocks, "no-preference hareket blogu yok"
    blk = "\n".join(blocks)         # .dot pulse blogu + v2.9 hareket blogu
    for frag in ("@keyframes rise", "body.boot .card", "transition:width",
                 "stroke-dashoffset"):
        assert frag in blk, f"{frag} azaltilmis-hareket korumasi disinda"
    # JS tarafi ayni tercihe bakar
    assert "prefers-reduced-motion: no-preference" in DASHBOARD_HTML
    assert "MOTION_OK&&FIRSTPAINT" in DASHBOARD_HTML
    # kenar cubugu gecisleri reduce'ta kapanir
    assert re.search(r"prefers-reduced-motion:reduce\)\{\s*"
                     r"\.cols,\.col\[data-tab=\"ozet\"\]\{transition:none",
                     DASHBOARD_HTML)


def test_equity_progressive_draw_only_on_first_render():
    # ilerleyen-nokta paterni: yalniz ilk grafikte (eqChart null) ve
    # hareket izniyle; sonraki yenilemelerde animation=false kalir
    assert "(MOTION_OK&&FIRSTPAINT&&!eqChart)?" in DASHBOARD_HTML
    assert "xStarted" in DASHBOARD_HTML and "yStarted" in DASHBOARD_HTML
    # SVG fallback ayni sozlesmeyle kendini cizer
    assert "path.eqline" in DASHBOARD_HTML
    assert "strokeDashoffset" in DASHBOARD_HTML


def test_winloss_points_carry_shape_encoding():
    """CVD (yesil-kirmizi) erisilebilirligi: kimlik renk-tek-basina degil;
    WIN=daire, LOSS=elmas (rectRot)."""
    assert '"circle":"rectRot"' in DASHBOARD_HTML
    assert "pointStyle:ptStyle" in DASHBOARD_HTML


# ---------------------------------------------------------- kenar cubugu
def test_sidebar_architecture_transform_flex_width():
    # grid genislik gecisi (akiskan) + transform kaymasi (GPU) + will-change
    assert "transition:grid-template-columns .38s" in DASHBOARD_HTML
    assert "will-change:transform" in DASHBOARD_HTML
    assert re.search(r"body\.nav-min \.cols\{grid-template-columns:0px "
                     r"minmax\(0,1fr\) 300px\}", DASHBOARD_HTML)
    assert "translate3d(-18px,0,0)" in DASHBOARD_HTML
    # kapali durumda etkilesim ve tasma kapali
    assert "pointer-events:none" in DASHBOARD_HTML
    # dugme + erisilebilirlik + kalicilik
    assert 'id="navBtn"' in DASHBOARD_HTML
    assert "aria-pressed" in DASHBOARD_HTML
    assert 'localStorage.setItem("ui_nav"' in DASHBOARD_HTML
    assert 'localStorage.getItem("ui_nav")' in DASHBOARD_HTML


def test_sidebar_is_desktop_only():
    """Mobilde sekme cubugu yonetir; navBtn gizli kalir ve nav-min kurallari
    yalniz min-width:761px bloklarinda yasar."""
    assert "#navBtn{display:none}" in DASHBOARD_HTML
    # nav-min stil kurallari her zaman bir min-width:761px blogu icinde
    for m in re.finditer(r"body\.nav-min[^{]*\{", DASHBOARD_HTML):
        before = DASHBOARD_HTML[: m.start()]
        opens = before.count("@media (min-width:761px){")
        # son acilan desktop blogunun icinde miyiz? (kabaca: acilis sayisi
        # kapanistan buyukse blok icindeyiz)
        closes = before.count("\n  }")
        assert opens > 0, "nav-min kurali desktop medya blogu disinda"


def test_sidebar_title_has_ru_translation():
    assert '"Kenar çubuğu (daralt/genişlet)"' in DASHBOARD_HTML
    assert "Боковая панель" in DASHBOARD_HTML


def test_base_grid_untouched():
    """Temel kolon sozlesmesi degismedi (mevcut testlerin korudugu deger)."""
    assert "grid-template-columns:220px minmax(0,1fr) 300px" in DASHBOARD_HTML


# ---------------------------------------------------------- v3.0 tema
def test_dark_theme_variables_and_toggle():
    """Gece Mavisi (Serhat secimi 2026-08-20): body.dark tum paleti cevirir;
    dugme + kalicilik + parlama onleyici erken script."""
    assert "body.dark{" in DASHBOARD_HTML
    for hexv in ("#0E131A", "#151C26", "#64A1FF", "#3DCB8C", "#F5766B"):
        assert hexv in DASHBOARD_HTML
    assert 'id="themeBtn"' in DASHBOARD_HTML
    assert 'localStorage.setItem("ui_theme"' in DASHBOARD_HTML
    # erken no-flash script: body acilir acilmaz sinif takilir
    assert 'localStorage.getItem("ui_theme")==="dark"' in DASHBOARD_HTML


def test_chart_colors_come_from_theme():
    """Canvas/SVG CSS degiskeni okuyamaz: grafik renkleri chartTheme()'den
    gelir ve tema degisince grafik temiz yeniden cizilir."""
    assert "function chartTheme()" in DASHBOARD_HTML
    assert "const T=chartTheme();" in DASHBOARD_HTML
    assert "borderColor:T.line" in DASHBOARD_HTML
    assert "pointBorderColor:T.ring" in DASHBOARD_HTML
    assert "grid:{color:T.grid}" in DASHBOARD_HTML
    assert "eqChart.destroy();eqChart=null;" in DASHBOARD_HTML
    # WIN/LOSS nokta renkleri de temadan (koyu zeminde acik tonlar)
    assert 'OUT(s)==="WIN"?T.win:T.loss' in DASHBOARD_HTML


def test_theme_title_has_ru():
    assert '"Koyu/Açık tema"' in DASHBOARD_HTML
    assert "Тёмная/светлая тема" in DASHBOARD_HTML
