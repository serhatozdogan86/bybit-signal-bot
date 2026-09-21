"""Adaylar paneli: masaustu gorunurlugu + durum rozeti mantigi.

Rozet kurallari (2026-08-12 gorev tanimi, aynen):
- ELENDI            : kume >= 20 VE CI ust siniri < 0  (veya emekli)
- SINAV BITTI GECEMEDI: kume >= 50 VE CI alt siniri <= 0
- YARISIYOR         : kume < 50

Rozet metni elle liste degil, chalVerdict() ile koddan turetilir; bu test
fonksiyonu HTML'den cikarip node ile CALISTIRARAK kanitlar.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from app.dashboard import DASHBOARD_HTML


def _desktop_block() -> str:
    m = re.search(r"@media \(min-width:761px\)\{(.*?)\n  \}", DASHBOARD_HTML, re.S)
    assert m, "masaustu (min-width:761px) CSS blogu yok"
    return m.group(1)


def _mobile_block() -> str:
    m = re.search(r"@media \(max-width:760px\)\{(.*)\.tabbar\{", DASHBOARD_HTML, re.S)
    assert m, "mobil (max-width:760px) CSS blogu yok"
    return m.group(1)


# ---------------------------------------------------------------- masaustu CSS
def test_desktop_css_shows_adaylar_panel():
    blk = _desktop_block()
    ad = re.search(r'\.col\[data-tab="adaylar"\]\{([^}]*)\}', blk)
    assert ad, "masaustu blogunda adaylar kurali yok"
    assert "display:flex" in ad.group(1), "adaylar masaustunde gorunur olmali"
    assert "grid-column:2" in ad.group(1), "adaylar orta kolonda olmali"


def test_desktop_css_keeps_three_column_widths():
    # kolon genislikleri degismedi -> sinyal tablosu daralmadi
    assert "grid-template-columns:220px minmax(0,1fr) 300px" in DASHBOARD_HTML
    blk = _desktop_block()
    assert "grid-template-columns" not in blk, \
        "masaustu blogu kolon genisliklerini degistirmemeli"
    # sol ve sag kolon iki satiri kaplar (denge bozulmaz)
    assert re.search(r'\.col\[data-tab="ozet"\]\{[^}]*grid-row:1/span 2', blk)
    assert re.search(r'\.col\[data-tab="piyasa"\]\{[^}]*grid-row:1/span 2', blk)


def test_desktop_css_does_not_show_ayar_panel():
    # ayar sekmesi masaustunde GIZLI kalir (yalniz mobil)
    assert 'data-tab="ayar"' not in _desktop_block()
    assert re.search(
        r'\.col\[data-tab="ayar"\],\.col\[data-tab="adaylar"\]\{display:none\}',
        DASHBOARD_HTML), "temel gizleme kurali (guvenli varsayilan) durmali"


def test_mobile_tab_behavior_untouched():
    mob = _mobile_block()
    assert '.col[data-tab="ayar"].on,.col[data-tab="adaylar"].on{display:flex}' in mob
    assert ".cols{grid-template-columns:1fr}" in mob
    assert ".col[data-tab]{display:none}" in mob


# ---------------------------------------------------------------- bayat metin
def test_stale_five_candidate_text_gone():
    assert "5 aday strateji" not in DASHBOARD_HTML
    assert "Şampiyon Faz-1 sınavını geçemezse" not in DASHBOARD_HTML


def test_candidate_count_is_derived_not_handwritten():
    # baslik etiketi cizilen satir sayisindan gelir (nRow), elle sayi yok.
    # 2026-09-21: etiket "canli aday" oldu (elenenler arsive tasindi);
    # NIYET degismedi - sayi hala nRow'dan turer.
    assert re.search(r'chalCount.*?\$\{nRow\} canlı aday',
                     DASHBOARD_HTML, re.S)
    # sayac YALNIZ canli adaylari saymali: dongu CHAL_CANLI uzerinde doner
    assert "for(const k of canli){" in DASHBOARD_HTML


# ---------------------------------------------------------------- RU cevirisi
def test_badge_texts_have_ru_translations():
    for tr_key, ru_val in [
        ("YARIŞIYOR", "В ГОНКЕ"),
        ("ELENDİ", "ВЫБЫЛ"),
        ("SINAV BİTTİ · GEÇEMEDİ", "ЭКЗАМЕН ЗАВЕРШЁН · НЕ СДАН"),
        ("SINAV BİTTİ · GEÇTİ", "ЭКЗАМЕН ЗАВЕРШЁН · СДАН"),
    ]:
        assert f'"{tr_key}":"{ru_val}"' in DASHBOARD_HTML, f"RU eksik: {tr_key}"
    # yeni panel ipucu metninin RU karsiligi da sozlukte
    assert "Первый экзамен чемпиона НЕ СДАН" in DASHBOARD_HTML
    # canli sayac kalibi
    assert r"[/^(\d+) aday$/" in DASHBOARD_HTML


# ------------------------------------------------------------- rozet mantigi
def _chal_verdict_src() -> str:
    m = re.search(r"function chalVerdict\(s\)\{.*?\n\}", DASHBOARD_HTML, re.S)
    assert m, "chalVerdict fonksiyonu bulunamadi"
    return m.group(0)


CASES = [
    # (girdi, beklenen rozet)
    ({"clusters": 10}, "YARIŞIYOR"),
    ({"clusters": 49, "ci": [-0.4, 0.3]}, "YARIŞIYOR"),
    ({"clusters": 25, "ci": [-0.3, -0.05]}, "ELENDİ"),          # kenar olumu
    ({"clusters": 19, "ci": [-0.3, -0.05]}, "YARIŞIYOR"),       # kume<20: erken
    ({"clusters": 20, "ci": [-0.3, 0.01]}, "YARIŞIYOR"),        # CI ustu >0
    ({"clusters": 55, "ci": [-0.1, 0.2]}, "SINAV BİTTİ · GEÇEMEDİ"),
    ({"clusters": 50, "ci": [0.0, 0.4]}, "SINAV BİTTİ · GEÇEMEDİ"),  # alt<=0
    ({"clusters": 50, "ci": [0.05, 0.4]}, "SINAV BİTTİ · GEÇTİ"),
    ({"clusters": 60, "ci": None}, "SINAV BİTTİ · GEÇEMEDİ"),   # CI yoksa gecmis sayilmaz
    ({"clusters": 5, "retired_utc": "2026-08-12"}, "ELENDİ"),   # emekli (ileri uyum)
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node yok")
def test_chal_verdict_logic_runs_in_node(tmp_path):
    js = (_chal_verdict_src()
          + "\nconst cases=" + json.dumps([c for c, _ in CASES])
          + ";\nconsole.log(JSON.stringify(cases.map(c=>chalVerdict(c).t)));\n")
    f = tmp_path / "verdict.js"
    f.write_text(js, encoding="utf-8")
    # encoding acikca UTF-8: text=True Windows'ta yerel kod sayfasini (cp1252)
    # kullanir ve node'un UTF-8 ciktisindaki Turkce harfleri bozar
    # ("YARIŞIYOR" -> "YARIÅIYOR"), test yalniz o makinelerde kirmizi verir.
    out = subprocess.run(["node", str(f)], capture_output=True, text=True,
                         encoding="utf-8")
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got == [exp for _, exp in CASES]


@pytest.mark.skipif(shutil.which("node") is None, reason="node yok")
def test_dashboard_js_passes_node_check(tmp_path):
    m = re.search(r"<script>(.*?)</script>", DASHBOARD_HTML, re.S)
    f = tmp_path / "dash.js"
    f.write_text(m.group(1), encoding="utf-8")
    out = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def test_verdict_used_in_table_and_modal():
    # ayni kaynak: hem tablo satiri hem detay penceresi chalVerdict cagirir
    rc = re.search(r"function renderChallengers\(ch\)\{.*?\n\}", DASHBOARD_HTML, re.S)
    cd = re.search(r"function chalDetail\(k\)\{.*?openModal", DASHBOARD_HTML, re.S)
    assert rc and "chalVerdict(" in rc.group(0), "tablo rozeti chalVerdict kullanmali"
    assert cd and "chalVerdict(" in cd.group(0), "detay penceresi chalVerdict kullanmali"


# ------------------------------------------- 2026-09-21 pano sadelestirme
def test_eliminated_candidates_are_not_in_main_table():
    """Pano SADELESIR: elenen/emekli adaylar ana tabloda cizilmez.

    Ana dongu CHAL_CANLI uzerinde doner; ayirma chalVerdict'in ILAN
    EDILMIS kuralindan gelir (elle liste YOK - suruklenme yasagi)."""
    assert 'vd-out" ? arsiv : canli' in DASHBOARD_HTML
    assert "for(const k of canli){" in DASHBOARD_HTML
    # eski hali (hepsini cizen dongu) geri gelmemeli
    assert "for(const k of Object.keys(CHAL_ADI)){\n    const s=ch.strategies[k];if(!s)continue;\n    nRow++;" \
        not in DASHBOARD_HTML


def test_archive_opens_only_on_click_and_keeps_records():
    """Arsiv YALNIZ tiklaninca acilir ve kayitlari SILMEZ."""
    assert 'id="arsivBtn"' in DASHBOARD_HTML
    assert "ab.addEventListener(\"click\",openArsiv)" in DASHBOARD_HTML
    assert "function openArsiv(" in DASHBOARD_HTML
    # arsiv metni "silinmedi" guvencesini TASIR (sessiz kayip yok)
    assert "silinmedi" in DASHBOARD_HTML
    # arsiv her motorun NEDEN elendigini yazar
    assert "kenar ölümü (CI üst < 0)" in DASHBOARD_HTML


def test_live_candidate_trades_are_listed_per_candidate():
    """Her canli adayin islemleri AYRI blokta gorunur."""
    assert 'id="chalTrades"' in DASHBOARD_HTML
    assert "function renderChalTrades(" in DASHBOARD_HTML
    assert 'class="chtblock"' in DASHBOARD_HTML
    # ayni ornekleme rejimi suzgeci (rakamlar celismesin - v3.7 dersi)
    assert "(r.regime||1)===rej" in DASHBOARD_HTML


def test_portfolio_card_says_it_is_not_a_verdict():
    """Portfoy karti HUKUM OLMADIGINI yazar - bu uyari SILINEMEZ."""
    assert 'id="pfoCard"' in DASHBOARD_HTML
    assert "function renderPortfolioBook(" in DASHBOARD_HTML
    assert "HÜKÜM DEĞİLDİR" in DASHBOARD_HTML
    # kapi rozeti iki durumu da tasir
    assert "KAPI AÇIK" in DASHBOARD_HTML and "KAPI KAPALI" in DASHBOARD_HTML
    # pano /portfolio ucunu gercekten cagirir
    assert 'j("/portfolio")' in DASHBOARD_HTML
    assert "renderPortfolioBook(pfo)" in DASHBOARD_HTML


def test_new_dashboard_strings_have_ru_translations():
    """Proje kurali: yeni metinlerin RU karsiligi sozlukte olur."""
    for tr_key in ("Portföy · Birleşik Defter", "Canlı Adayların İşlemleri",
                   "Güven aralığı", "KAPI AÇIK", "Bağımsız blok",
                   "Arşiv · elenen ve emekli adaylar"):
        assert f'"{tr_key}":"' in DASHBOARD_HTML, f"RU eksik: {tr_key}"


# ---------------------------------------------- 2026-09-21 AD CAKISMASI
def test_no_duplicate_js_function_names():
    """Panoda AYNI ADDA iki JS fonksiyonu olamaz.

    ARIZA (2026-09-21, bu testin dogum sebebi): yeni portfoy karti icin
    renderPortfolio() yazdim; panoda para-simulasyonu karti icin ZATEN
    ayni adda bir fonksiyon vardi. JS'te sonraki bildirim oncekini EZER -
    yani yeni kart hic calismadi ve eski kart yanlis argumanla cagrilip
    "(signals||[]) is not iterable" ile patladi.
    Metin tabanli testler bunu GOREMEDI (ikisi de string olarak vardi);
    hatayi ancak tarayicida acinca gordum. Bu test o sinifi kapatir."""
    names = re.findall(r"^function\s+([A-Za-z_$][\w$]*)\s*\(",
                       DASHBOARD_HTML, re.M)
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"ayni adda birden fazla fonksiyon: {dupes}"


def test_archive_table_columns_line_up():
    """Arsiv tablosunda baslik sayisi = hucre sayisi.

    ARIZA (2026-09-21, tarayicida gorulda): 7 baslik / 7 hucre vardi ama
    durum rozeti STRATEJI hucresinin ICINDEydi; bu yuzden "durum"
    basliginin altina islem sayisi dusuyor, tum sutunlar bir kayiyordu."""
    blok = DASHBOARD_HTML.split("function openArsiv(")[1].split("openModal(")[0]
    basliklar = blok.count("<th>")
    # satir sablonundaki hucreler (dongu govdesi)
    govde = blok.split("for(const k of CHAL_ARSIV)")[1]
    hucreler = govde.count("<td")
    assert basliklar == hucreler, \
        f"arsiv sutunlari kaymis: {basliklar} baslik / {hucreler} hücre"
