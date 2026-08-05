# CI kurulumu (elle, 1 dakika)

`tests.yml` buraya konuldu çünkü deployda kullanılan GitHub jetonunun
`workflow` yetkisi yok — bu iyi bir şey: otomatik bir süreç, CI'ın kendisini
sessizce değiştirememeli. Kapıyı kuran ile kapıdan geçen aynı el olmamalı.

Etkinleştirmek için (GitHub web arayüzünden, 1 dakika):
1. Depoda **Add file → Create new file**
2. Dosya adı: `.github/workflows/tests.yml`
3. `deploy/ci/tests.yml` içeriğini yapıştır → **Commit**

Sonrasında her push'ta şunlar koşar: değişmezlik testleri
(`tests/test_invariants.py` — hata sınıflarını kapatan testler), tüm test
suite, pano JS sözdizimi kontrolü ve derleme. Kırmızı test = kırmızı commit,
ve bu artık kimsenin hatırlamasına bağlı değil.
