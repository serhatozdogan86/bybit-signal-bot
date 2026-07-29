# LLM Konsey İncelemesi — Temmuz 2026 (özet)
4 bağımsız model değerlendirmesi (tam metinler arşivde). Yakınsayan bulgular:

1. (4/4) Portföy ısı/korelasyon limiti motor seviyesine — en acil eksik.
   "12 eşzamanlı short = tek 12x BTC short."
2. (4/4) Maliyet modeli şart: 2×taker + stop kayması + İŞARETLİ funding
   (ayıda short funding alır → kenar şişmiş olabilir).
3. (4/4) Bağımsızlık kırık: n_eff≈15-30; küme istatistiği + blok-bootstrap
   olmadan anlamlılık iddiası geçersiz.
4. (4/4) Tahsis politikası (FIFO) kapasite krizinin ana suçlusu; slot
   sinyal doğunca değil DOLUNCA atanmalı; güven/EV öncelikli kuyruk test edilmeli.
5. (3/4) Fail-closed gate + TTL; (3/4) histerezis (%0.5-1 + 2×4H teyit).
6. (3/4) Ön-kayıt itirazı: örneklem-içi eşik seçimi ≠ ön-kayıt →
   kilitli konfig + holdout zorunlu.
7. (2/4) AMBIGUOUS→LOSS (muhafazakâr yol kabul edildi, P1'de).
8. Tekil değerli: süreç-vs-sonuç etiketi; evren survivorship/likidite tuzağı;
   hacim mevsimselliği; sweep-vs-breakout rejim uyumsuzluğu; konfig SHA damgası.

Uygulama durumu: v3.5-P0 = maliyet motoru v0, fail-closed+TTL, histerezis,
cluster_id + engine_sha. P1 (ısı motoru, AMBIGUOUS→LOSS, dead-man) sırada.
