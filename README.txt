
MBÇ Mühendislik – Kar Yükü Hesap Aracı V2
=========================================

Bu paket profesyonel arayüzlü V2 masaüstü sürümüdür.

Önemli
------
Bu ortamda doğrudan Windows `.exe` derleyemedim. Bunun sebebi burada Windows derleme ortamı bulunmaması.
Ancak bu pakette iki yol hazırdır:

1) Windows'ta Python kurulu bir bilgisayarda tek tıkla `.exe` üretme
2) GitHub Actions ile BULUTTA Windows `.exe` üretme  ← Python kurmadan en pratik yol

--------------------------------------------------
A) PYTHON KURMADAN .EXE ALMAK (ÖNERİLEN)
--------------------------------------------------

GitHub hesabın varsa şu adımları izle:

1. GitHub'da yeni boş bir repo aç
   Örnek isim: `mbc-kar-yuku-v2`

2. Bu zip içindeki TÜM dosyaları repoya yükle

3. GitHub'da:
   Actions > "Build Windows EXE" > Run workflow

4. Derleme bitince:
   Actions ekranında ilgili çalışmanın içine gir
   Artifacts bölümünden:
   `mbc-kar-yuku-v2-windows` dosyasını indir

5. İndirilen zip içinde hazır çalışır dosya olur:
   `mbc_kar_yuku_v2.exe`

Bu exe çalışmak için kullanıcı bilgisayarında Python istemez.

--------------------------------------------------
B) WINDOWS'TA TEK TIKLA BUILD
--------------------------------------------------

Bilgisayarda Python varsa:

1. `install_build_tools.bat` çalıştır
2. Sonra `build_exe.bat` çalıştır
3. Exe şu klasörde oluşur:
   `dist\mbc_kar_yuku_v2.exe`

--------------------------------------------------
UYGULAMA ÖZELLİKLERİ
--------------------------------------------------

- MBÇ Mühendislik marka kimliği
- Profesyonel arayüz
- İl / ilçe bazlı bölge seçimi
- Rakıma göre s_k interpolasyonu
- Tek eğimli, çift eğimli, çok açıklıklı, silindirik, yüksek yapıya bitişik çatı
- Parapet etkisi
- Engel / çıkıntı birikmesi
- İstisnai durum
- Çatı kenarı kar sarkıntısı
- Markdown rapor
- PDF rapor
- Yük şeması önizleme

--------------------------------------------------
DOSYALAR
--------------------------------------------------

- `mbc_kar_yuku_v2.py`          → Ana uygulama
- `regions.json`                → İl/ilçe-kar bölgesi verisi
- `sk_table.json`               → Bölge/rakım-s_k tablosu
- `assets/mbc_logo.png`         → MBÇ Mühendislik logo
- `requirements.txt`            → Paketler
- `build_exe.bat`               → Windows derleme scripti
- `install_build_tools.bat`     → Gerekli paketleri kurar
- `.github/workflows/...`       → GitHub bulut derleme otomasyonu

--------------------------------------------------
NOT
--------------------------------------------------

Bu sürüm hızlı mühendislik değerlendirmesi ve raporlama amaçlıdır.
Nihai projelerde proje özel şartları ayrıca kontrol edilmelidir.
