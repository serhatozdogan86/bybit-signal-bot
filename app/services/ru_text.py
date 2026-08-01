"""Sunucu tarafi TR -> RU metin cevirisi (saatlik yorum + piyasa nabzi).

Yorumlar sinirli sayida sablondan uretildigi icin duzenli ifade tabanli
ceviri guvenilirdir. Motor kararlarina dokunmaz; yalniz sunum katmanidir.
"""
from __future__ import annotations

import re

_WORDS = [
    ("golge muhasebedir", "теневой учёт"),
    ("Tum sonuclar", "Все результаты —"),
    ("varsayimsal giris", "гипотетический вход"),
    ("kayma/komisyon yok", "без проскальзывания и комиссий"),
    ("gercek emir yok", "без реальных ордеров"),
    ("Gecmis performans garanti degildir", "Прошлые результаты не гарантия"),
    ("yatirim tavsiyesi degildir", "не инвестиционная рекомендация"),
    ("basabasin uzerinde", "выше точки безубыточности"),
    ("basabasin altinda", "ниже точки безубыточности"),
    ("Onceki degerlendirmeden bu yana yeni sonuc yok",
     "С прошлого обзора новых результатов нет"),
    ("Bu donemde sonuclananlar", "Завершено за период"),
    ("Guncel rejim: BTC boga", "Текущий режим: BTC бык"),
    ("Guncel rejim: BTC ayi", "Текущий режим: BTC медведь"),
    ("Guncel rejim: BTC notr", "Текущий режим: BTC нейтральный"),
    ("Ayi rejiminde market gate yeni LONG uretimini blokluyor",
     "В медвежьем режиме ворота рынка блокируют новые LONG"),
    ("Boga rejiminde market gate yeni SHORT uretimini blokluyor",
     "В бычьем режиме ворота рынка блокируют новые SHORT"),
    ("bloklanan kararlar karsi-olgu kohortunda ayrica izleniyor",
     "заблокированные решения отслеживаются в контрфактической когорте"),
    ("Henuz sonuclanan sinyal yok; motor kosul bekliyor",
     "Завершённых сигналов пока нет; движок ждёт условий"),
    ("Orneklem hala kucuk", "Выборка всё ещё мала"),
    ("sonuclanmis sinyal esiginden once hukum erken",
     "до порога завершённых сигналов выводы преждевременны"),
    ("Uyari: asiri dar stoplu kayip(lar)",
     "Внимание: убыток(и) со слишком узким стопом"),
    ("Izlemede", "В наблюдении"),
    ("en eskisi", "самый старый"),
    ("acik sinyal", "открытых сигналов"),
    ("Yon bilancosu", "Баланс по направлениям"),
    ("Giris isabeti", "Точность входа"),
    ("Kumulatif", "Кумулятивно"),
    ("Toplam", "Всего"),
    ("sonuclanan sinyal", "завершённых сигналов"),
    ("isabet", "точность"),
    ("basabas", "безубыток"),
    ("doldu", "заполнено"),
    ("dolmadi", "не заполнено"),
    # piyasa nabzi
    ("Likit evrende", "В ликвидной вселенной"),
    ("yukselen", "растущих"),
    ("dusen", "падающих"),
    ("genislik karisik", "ширина смешанная"),
    ("genislik negatif", "ширина отрицательная"),
    ("genislik pozitif", "ширина положительная"),
    ("Korku/Acgozluluk", "Индекс страха и жадности"),
    ("Risk istahi guclu", "Аппетит к риску высокий"),
    ("Risk istahi zayif", "Аппетит к риску слабый"),
    ("Risk istahi notr", "Аппетит к риску нейтральный"),
    ("karsi-trend SHORT kurulumlari dusuk olasilikli bolgede",
     "контртрендовые формации SHORT в зоне низкой вероятности"),
    ("karsi-trend LONG kurulumlari dusuk olasilikli bolgede",
     "контртрендовые формации LONG в зоне низкой вероятности"),
    ("LONG tarafinin kosullari daha temiz", "условия на стороне LONG чище"),
    ("SHORT tarafinin kosullari daha temiz", "условия на стороне SHORT чище"),
    ("kural-tabanli okuma", "чтение по правилам"),
    ("Korku", "Страх"),
    ("Acgozluluk", "Жадность"),
    ("Notr", "Нейтрально"),
    ("devam ediyor", "продолжается"),
    ("bu veriyle", "по этим данным"),
]


def to_ru(text: str | None) -> str | None:
    """TR uretilmis yorum metnini Rusca'ya cevirir (kalip tabanli)."""
    if not text:
        return text
    out = text
    for tr, ru in _WORDS:
        out = out.replace(tr, ru)
    # sayili kaliplar
    out = re.sub(r"(\d+) WIN / (\d+) LOSS", r"\1 WIN / \2 LOSS", out)
    out = re.sub(r"BTC 24s", "BTC 24ч", out)
    out = re.sub(r"ETH ", "ETH ", out)
    out = re.sub(r"(\d+) sa ", r"\1 ч ", out)
    out = re.sub(r"(\d+) dk", r"\1 мин", out)
    return out
