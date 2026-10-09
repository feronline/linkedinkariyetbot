# LinkedIn Otomatik Başvuru Botu

CV'ni yükle, bot CV'ni **yapay zeka kullanmadan, tamamen kendi bilgisayarında** analiz etsin; sana uygun LinkedIn **Kolay Başvuru (Easy Apply)** ilanlarını bulup günlük limite kadar başvursun.

- API anahtarı, yapay zeka aboneliği, sunucu yok. Her şey yerelde çalışır.
- CV'den yetenek, rol ve kıdem çıkarılır; ilanlar 0–100 puanlanır; puanı düşük ilanlara başvurulmaz.
- Bilmediği bir form sorusuna **tahmin yürütmez**, o ilanı atlar.
- Günlük başvuru sınırı **20**'dir (değiştirilebilir). Daha önce denenen ilana ikinci kez başvurmaz.

> ⚠️ **Uyarı:** LinkedIn otomasyonu LinkedIn Kullanım Şartları'na aykırıdır. Hesabın kısıtlanabilir ya da kapatılabilir. Sorumluluk sana aittir. Limiti düşük tut, aşırıya kaçma.
>
> Kariyer.net desteği henüz **yoktur**.

## Gereksinimler

- Windows (Mac/Linux'ta da çalışır, komutları elle çalıştır)
- [Python 3.10+](https://www.python.org/downloads/) (kurulumda "Add to PATH" kutusunu işaretle)

## Hızlı başlangıç (Windows)

1. Projeyi indir, klasörü aç.
2. CV'ni (PDF veya DOCX) **`data/cvs/`** klasörüne koy. Birden fazla CV koyabilirsin (ör. AI, oyun, mobil). Bot her ilan için en uygun olanı seçer.
3. **`baslat.bat`** dosyasına çift tıkla. İlk seferde:
   - gerekli paketleri ve tarayıcıyı kurar,
   - CV'lerini analiz eder ve `data/profile.json` oluşturur,
   - açılan tarayıcıda LinkedIn'e **kendin giriş yaparsın** (2FA dahil). Şifren hiçbir yere kaydedilmez, sadece oturum çerezi `data/` içinde kalır,
   - başvurmaya başlar.
4. `data/profile.json` dosyasını aç ve **`answers`** bölümünü doldur (aşağıya bak), sonra tekrar çalıştır.

## Arayüz (isteğe bağlı)

`arayuz.bat` ya da `python run.py ui` yerel bir web arayüzü açar (`http://127.0.0.1:8765`, sadece bu bilgisayardan erişilir): CV yükle, analiz sonucunu gör, ayarları ve form cevaplarını düzenle, atlanan soruları tek tıkla cevapla, botu başlat/durdur, bugünkü kotayı ve kayıtları izle.

## Elle kullanım

```powershell
pip install -r requirements.txt
playwright install chromium

python run.py setup          # data/cvs içindeki CV'leri analiz et, profile.json oluştur
python run.py login          # tarayıcıda LinkedIn'e giriş yap, oturumu kaydet
python run.py apply --dry    # başvurmadan, hangi ilanlara başvurulacağını göster
python run.py apply          # başvur (günlük limite kadar)
python run.py apply --limit 3 --min-score 70   # bu çalıştırmada en fazla 3, en az 70 puan
python run.py status         # bugünkü kota ve son kayıtlar
```

## Her gün otomatik çalıştırma (isteğe bağlı, Windows)

`scheduled.py`, Görev Zamanlayıcı ile sık aralıklarla çağrılır; her gün 10:00–16:30 arasında **rastgele** bir saat seçer, bilgisayar açıkken o saatten sonra günde bir kez çalıştırır ve o günkü başvuru sayısını da 12–20 arasında rastgele belirler. Kurmak için PowerShell'de `New-ScheduledTaskAction -Execute pythonw.exe -Argument scheduled.py -WorkingDirectory <proje klasörü>` ile 20 dakikada bir tekrarlayan bir görev oluştur. Günlük çıktı `data/scheduled.log` dosyasına yazılır.

## `data/profile.json` ayarları

| Ayar | Anlamı | Varsayılan |
|---|---|---|
| `daily_limits.linkedin` | Günlük en fazla başvuru | `20` |
| `min_score` | Başvuru için en az ilan puanı (0–100) | `50` |
| `any_software` | `true`: yazılımla ilgili her ilana bak. `false`: sadece CV'nin rolüne uyanlar | `true` |
| `work_type` | Liste: `Remote` (uzaktan), `On-site` (ofis), `Hybrid` (hibrit). Birden fazla seçilebilir | hepsi |
| `locations` | Konum listesi, ör. `["İstanbul, Türkiye", "Kocaeli, Türkiye", "Germany", "Canada"]`. Her biri sırayla taranır; boşsa dünya geneli | boş |
| `pages_per_query` | Her aramada kaç sayfa taransın | `2` |
| `delay_seconds` | Başvurular arası bekleme aralığı (sn) | `[6, 14]` |
| `cover_letter` | Kapak yazısı istenirse kullanılacak metin | boş |
| `answers` | Form sorularına cevaplar | aşağıda |

### `answers` — en önemli kısım

Form sorusunun metni, buradaki **anahtarı içeriyorsa** cevap yazılır. Cevabı boş bırakılan ya da hiç eşleşmeyen zorunlu bir soru çıkarsa o ilan **atlanır** (`needs_answer` olarak kaydedilir).

```json
"answers": {
  "years of experience": "2",
  "phone": "5xxxxxxxxx",
  "expected salary": "50000",
  "notice period": "30",
  "website": "siteadresin.com",
  "github": "github.com/kullaniciadin",
  "sponsorship": "no",
  "authorized to work": "yes"
}
```

Atlanan sorulara bakmak için `python run.py status` çıktısındaki not sütununu oku, sık çıkan soruları buraya anahtar olarak ekle. Evet/Hayır sorularına `"yes"` veya `"no"` yaz. Sayı isteyen alanlara sadece sayı gider (`"2 yıl"` → `2`).

## Bot nasıl karar veriyor?

1. **CV analizi:** PDF/DOCX metni okunur; yetenek sözlüğüyle yetenekler, başlık ve yeteneklerden rol, tarih aralıklarından deneyim yılı çıkarılır. Az deneyimde `Senior/Lead` gibi ilanlar elenir.
2. **Arama:** Role uygun anahtar kelimelerle LinkedIn'de Kolay Başvuru ilanları aranır.
3. **Puanlama:** İlan başlığı ve açıklamasındaki yetenekler CV'ninkiyle karşılaştırılır. Birden fazla CV varsa en yüksek puanlı CV seçilir ve LinkedIn'e o gönderilir.
4. **Başvuru:** Form adım adım doldurulur. Cevabı bilinmeyen zorunlu soru varsa ilan atlanır.
5. **Kota:** Her sonuç `data/state.db` dosyasına yazılır; günlük limite gelince durur.

Yetenek ve rol listelerini `botcore/taxonomy.py` içinde kendi alanına göre genişletebilirsin.

## Dosya yapısı

```
baslat.bat            tek tıkla kur + çalıştır (Windows)
run.py                komutlar: setup, login, apply, status, ui
ui.py / ui.html       yerel arayüz
scheduled.py          günlük rastgele saatli çalıştırma
botcore/
  analyzer.py         yapay zekasız CV analizi ve ilan puanlama
  taxonomy.py         yetenek / rol sözlüğü
  linkedin.py         LinkedIn Kolay Başvuru adaptörü (seçiciler en üstte)
  quota.py            günlük kota + denenen ilan kaydı (SQLite)
  profile.py          profile.json okuma/yazma
data/                 SENİN VERİN (git'e girmez): cvs/, profile.json, sessions/, state.db
```

## Gizlilik

`data/` klasörü, tüm PDF/DOCX dosyaları ve log'lar `.gitignore` ile dışarıda tutulur. Projeyi paylaşırken kendi CV'ni, oturum dosyanı (`data/sessions/linkedin.json`, hesabına erişim sağlar) ve `profile.json`'ı **asla** paylaşma.

## Sorun giderme

| Sorun | Çözüm |
|---|---|
| "Oturum geçersiz" | `python run.py login` ile yeniden giriş yap |
| Hiç başvuru olmuyor | `python run.py status` ile notlara bak; çoğu ilan `needs_answer` ise `answers`'ı doldur |
| Çok az ilan geliyor | `min_score` düşür, `work_type` boşalt, `pages_per_query` artır |
| LinkedIn arayüzü değişti, bot buton bulamıyor | `botcore/linkedin.py` en üstündeki seçici/anahtar kelime listelerini güncelle |
| Hesap için doğrulama (captcha) çıktı | Bot'u durdur, tarayıcıda elle çöz, bir süre bekle |
