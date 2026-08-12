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
    # baslik etiketi cizilen satir sayisindan gelir (nRow), elle sayi yok
    assert re.search(r'chalCount.*?\$\{nRow\} aday', DASHBOARD_HTML, re.S)


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
