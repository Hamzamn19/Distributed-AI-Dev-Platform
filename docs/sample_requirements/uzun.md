# Hastane Randevu ve Hasta Takip Sistemi Yazılım Gereksinim Dokümanı

## 1. Giriş ve Amaç
Bu belgenin amacı, kamu ve özel sağlık kuruluşlarında hasta kabul, poliklinik randevusu oluşturma, muayene takibi, tetkik sonuçlandırma ve reçete yönetimi süreçlerini tek bir çatı altında toplayan entegre bir sağlık yönetim platformunun işlevsel ve operasyonel gereksinimlerini belirlemektir. Sistem, sağlık hizmetlerinin kalitesini artırmayı, bekleme sürelerini en aza indirmeyi ve sağlık verilerinin hatasız, izlenebilir ve güvenli şekilde işlenmesini sağlamayı amaçlamaktadır.

## 2. Kullanıcı Rolleri ve Yetki Tanımları
Sistem hiyerarşik erişim kontrolü prensibine dayanır ve aşağıdaki rolleri içerir:
- **Hasta (Vatandaş):** Sisteme kaydolan, kişisel profilini güncelleyen, uygun poliklinik ve doktorlardan randevu alan, geçmiş muayene ve tahlil sonuçlarını inceleyen ve aktif randevularını yöneten son kullanıcıdır.
- **Poliklinik Doktoru:** Kendi çalışma takvimini görüntüleyen, randevulu hastaları muayene listesinden seçerek kabul eden, muayene bulgularını sisteme kaydeden, laboratuvar ve görüntüleme tetkikleri talep eden ve tıbbi reçete düzenleyen sağlık uzmanıdır.
- **Sağlık Personeli / Danışma Görevlisi:** Hastaneye doğrudan başvuran hastaların kimlik doğrulamalarını yapan, acil durumlarda randevusuz kayıt açan, vezne ve tahlil kabul işlemlerini gerçekleştiren saha personelidir.
- **Hastane Yöneticisi (Başhekimlik):** Polikliniklerin açılması, doktor-poliklinik görevlendirmeleri, çalışma saatlerinin belirlenmesi, sistem kısıtlarının yapılandırılması ve genel performans raporlarının incelenmesinden sorumlu idari roldür.

## 3. Ana Özellikler ve Fonksiyonel Gereksinimler

### 3.1. Hasta Kayıt ve Kimlik Yönetimi
- Yeni hastalar sisteme kayıt olurken Türkiye Cumhuriyeti Kimlik Numarası, ad, soyad, doğum tarihi, cinsiyet, telefon numarası ve e-posta adresi bilgilerini girmek zorundadır.
- Sistem her hastaya benzersiz bir dijital hasta protokol numarası atamalıdır.
- Hastanın acil durum irtibat kişisi ve kan grubu bilgisi profilinde tutulmalıdır.

### 3.2. Doktor Çalışma Çizelgesi ve Poliklinik Yönetimi
- Hastane yöneticisi poliklinik tanımlayabilir ve doktorları ilgili polikliniklerle eşleştirebilir.
- Doktorlar haftalık veya aylık periyotlarda muayene saat aralıklarını tanımlayabilir. Standart muayene aralık süresi 15 dakika olarak belirlenir.
- Doktorların izin, nöbet veya ameliyat günleri çalışma takviminde bloklanarak randevu alımına kapatılabilmelidir.

### 3.3. Randevu Arama, Alma ve İptal Süreci
- Hasta il, hastane, poliklinik uzmanlığı, hekim adı ve tarih kriterlerine göre uygun randevu saatlerini listeleyebilmelidir.
- Hasta seçtiği boş saat aralığı için randevu oluşturduğunda, sistem tarafından onay kodu üretilmeli ve randevu durumu onaylandı olarak güncellenmelidir.
- Hastalar randevu saatine en geç 2 saat kalana kadar sistem üzerinden randevularını gerekçe belirterek iptal edebilmelidir.

### 3.4. Muayene ve Klinik Süreç Yönetimi
- Doktor muayene başladığında randevu durumunu muayenede olarak günceller.
- Doktor hastaya ait şikâyetleri, fiziksel muayene bulgularını ve teşhis kodlarını sisteme girebilir.
- Doktor sistem üzerinden ilaç adı, kullanım dozu, kullanım sıklığı ve kullanım süresi bilgilerini girerek dijital reçete oluşturabilmelidir.

### 3.5. Laboratuvar ve Tetkik Takibi
- Doktor muayene esnasında kan, idrar veya radyolojik tetkik isteği oluşturabilir.
- İlgili laboratuvar personeli numune kabulü yaptığında test durumu çalışılıyor, test tamamlandığında ise sonuçlandı durumuna geçer.
- Tetkik sonuçları onaylandıktan sonra hastanın ve doktorun erişimine açılmalıdır.

### 3.6. Bildirim ve İletişim Servisi
- Randevu oluşturulduğunda, iptal edildiğinde veya yaklaşan randevuya 24 saat kaldığında hastaya otomatik bilgilendirme iletisi gönderilmelidir.
- Tetkik sonuçları çıktığında hastanın sistem bildirim kutusuna otomatik uyarı düşmelidir.

### 3.7. İdari Raporlama ve Analitik
- Yönetici poliklinik doluluk oranlarını, doktor başına düşen günlük hasta sayılarını, ortalama muayene sürelerini ve iptal/gelmeme oranlarını raporlayabilmelidir.

## 4. İş Kuralları ve Sistem Kısıtları
- **Aynı Gün Randevu Sınırı:** Bir hasta aynı gün içerisinde aynı uzmanlık alanından veya aynı poliklinikten birden fazla aktif randevu alamaz.
- **Aktif Randevu Kotası:** Bir hastanın aynı anda sistemde bekleyen aktif randevu sayısı 3 adedi geçemez.
- **Yaptırım Kuralı (Gelmeme Durumu):** Randevusuna mazeretsiz ve iptal etmeksizin gitmeyen hastalar, 15 gün boyunca aynı branştan yeni randevu oluşturamaz.
- **Geçmişe Dönük Randevu Engeli:** Çalışma takviminde geçmiş tarih ve saatlere hiçbir kullanıcı rolü tarafından randevu oluşturulamaz.
- **Tıbbi Kayıt Değiştirilemezliği:** Tamamlanan muayene notları, kesinleşen teşhisler ve onaylanan tahlil sonuçları 24 saat geçtikten sonra sistemden silinemez ve içerikleri değiştirilemez; varsa yalnızca ek açıklama eklenebilir.
- **Kişisel Sağlık Verisi Gizliliği:** Doktorlar yalnızca kendi muayene ettikleri veya konsültasyon talep edilen hastaların tıbbi geçmişine erişebilir; genel hasta listesinde tıbbi ayrıntılar maskelenmelidir.
