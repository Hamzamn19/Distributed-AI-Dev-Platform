# Kütüphane Yönetim Sistemi Yazılım Gereksinim Dokümanı

## 1. Amaç ve Kapsam
Bu sistem, kütüphane kaynaklarının ve kullanıcı işlemlerinin dijital ortamda düzenli, güvenilir ve izlenebilir bir şekilde yönetilmesini amaçlar.

## 2. Kullanıcı Rolleri
- **Kütüphane Görevlisi:** Kitap ve üye kayıtlarını yöneten, ödünç alma ve iade işlemlerini onaylayan, ceza tahsilatını takip eden yetkili kullanıcıdır.
- **Kütüphane Üyesi:** Kütüphaneye kayıtlı olan, katalogdaki kitapları inceleyebilen, ödünç alan ve iade eden okuyucudur.

## 3. Ana Özellikler
- **Kitap Ekleme:** Görevli sisteme yeni kitap tanımlayabilir; kitap adı, yazar, basım yılı, benzersiz ISBN numarası ve mevcut kopya adedini güncelleyebilir.
- **Üye Kaydı:** Yeni üyelerin ad, soyad, iletişim bilgileri ve kimlik numarası ile sisteme kaydı yapılır; her üyeye benzersiz bir üye numarası atanır.
- **Ödünç Alma ve İade:** Üyeler mevcut kitapları belirli bir süre için ödünç alabilir. Görevli ödünç verme işlemini başlatır ve iade tarihini kaydeder. İade edilen kitapların stok durumu sistem tarafından güncellenir.
- **Gecikme Cezası:** İade tarihi geçen her gün için kitap başına günlük gecikme bedeli hesaplanır. Üyenin toplam borcu sistemde izlenir.

## 4. Kısıtlar ve Kurallar
- Bir üye aynı anda en fazla 3 kitap ödünç alabilir.
- Standart ödünç verme süresi 15 gündür.
- Ödenmemiş gecikme cezası bulunan üyeler borçlarını kapatmadan yeni kitap ödünç alamaz.
- Sistemde kayıtlı olmayan veya stoğu tükenmiş kitaplar ödünç verilemez.
