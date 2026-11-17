# Kurulum görevi: Can - worker `agent-can`

Sen bir yapay zeka asistanısın. Bu bilgisayarı CM6453 dersindeki **Distributed AI Dev Platform** projesinin
bugünkü ekip testine hazırlayacaksın.

**Bu bilgisayarın rolü: WORKER.** Master'dan (Baran'ın bilgisayarı) Tailscale üzerinden görev alır, yerel modelle
kod yazar ve sonucu geri gönderir. Master ve diğer worker'lar aynı Tailscale ağındadır.

| Bilgi | Değer |
| --- | --- |
| Kullanıcı | Can |
| Ajan kimliği | `agent-can` (Can-PC) |
| Model | `qwen2.5-coder:7b` (Ollama) |
| Tercih ettiği görev | database |
| Yetenek puanları | coding 100, reasoning 50, context 100 |
| Kod | https://github.com/Tilhium/dap_test (özel repo) |
| Ayar dosyası | Okan'ın ayrıca gönderdiği `.env.for-can` |

## Kurallar (önce bunları oku)

- Adımları **sırayla** uygula. Her komutu çalıştırmadan önce kullanıcıya ne yaptığını tek cümleyle söyle.
- Bir adım başarısız olursa **dur**: hatayı açıkla, düzeltmeyi öner, kullanıcı onaylamadan devam etme.
- `.env` dosyasında ekip token'ı var. İçeriğini **asla ekrana yazdırma**, başka yere gönderme, commit'leme.
  Kontrol için yalnızca bu dosyada "gösterilebilir" denen satırları göster.
- Repodaki kodu **değiştirme**; görevin yalnızca kurulum. Kodda bir sorun görürsen kullanıcıya Okan'a sormasını öner.
- `.env` içindeki bir değer yanlış görünüyorsa kendin değiştirme; kullanıcıya Okan'dan yeni dosya istemesini söyle.
- Komutlar Windows (PowerShell), macOS ve Linux için verildi; bu bilgisayarın sistemine uyanı kullan.

## 1. Ön koşulları kontrol et

```bash
python --version      # 3.11 veya daha yeni (macOS/Linux: python3 --version)
git --version
tailscale ip -4       # 100.x.y.z gibi bir adres vermeli
```

- Python veya Git yoksa kullanıcıdan kurmasını iste (python.org, git-scm.com).
- `tailscale ip -4` adres vermiyorsa: Tailscale uygulamasını açıp ekip hesabıyla giriş yapmasını iste.
  Bu adres olmadan master bu bilgisayara ulaşamaz.

## 2. Kodu indir ve Python ortamını kur

Repo özeldir: kullanıcının GitHub hesabıyla erişimi olmalı. Erişim hatası alırsan Okan'dan davet istemesini söyle.

```bash
# Uygun bir klasörde (örneğin Masaüstü). Klasör zaten varsa: cd dap_test, sonra git pull
git clone https://github.com/Tilhium/dap_test.git
cd dap_test
python -m venv .venv          # macOS/Linux: python3 -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest -q                     # hepsi "passed" olmalı (Ollama gerekmez)
```

Bundan sonraki bütün komutlar **`dap_test` klasöründe, sanal ortam açıkken** çalışır.

## 3. Model: Ollama

1. Ollama açık olmalı (`ollama --version`). Kurulu değilse kullanıcıdan https://ollama.com adresinden kurmasını iste.
2. Modeli indir (birkaç GB, zaman alabilir):
   ```bash
   ollama pull qwen2.5-coder:7b
   ollama list        # listede tam olarak "qwen2.5-coder:7b" görünmeli
   ```
3. Modeli belleğe yükle; ilk görev daha hızlı başlar:
   ```bash
   ollama run qwen2.5-coder:7b "Say OK"
   ```

## 4. Ayar dosyasını yerleştir

Okan kullanıcıya ayrıca **`.env.for-can`** adlı bir dosya gönderdi (WhatsApp vb.).

1. Kullanıcıdan bu dosyanın nerede olduğunu iste. Adı aktarımda değişmiş olabilir
   (örneğin `env.for-can.txt`); içinde `AGENT_TOKEN=` ve `AGENT_ID=agent-can` satırları olan dosya odur.
2. Dosyayı `dap_test` klasörünün köküne **`.env`** adıyla kopyala (başında nokta var, uzantı yok).
3. İçeriği yazdırmadan kontrol et. Yalnızca şu satırları göstermek serbest:
   - `AGENT_ID=agent-can`
   - `MASTER_URL=...` (değer `http://100.` ile başlamalı, `:8000` ile bitmeli)
   - `LLM_MODEL=qwen2.5-coder:7b`
   - `LLM_MOCK=0`
4. `git status` çıktısında `.env` **görünmemeli** (git dışında tutulur).

## 5. Güvenlik duvarı: 9000 portu

Master görevleri bu bilgisayarın **9000** portuna gönderir. Kullanıcıdan onay alarak:

- **Windows** (yönetici olarak açılmış PowerShell):
  ```powershell
  New-NetFirewallRule -DisplayName "DAP worker 9000" -Direction Inbound -Protocol TCP -LocalPort 9000 -Action Allow
  ```
  Worker ilk açıldığında Windows Python için izin sorarsa **İzin ver** dedirt (özel ve ortak ağlar).
- **macOS:** worker ilk açıldığında "gelen bağlantılara izin ver" sorusuna **İzin ver**.
- **Linux:** `ufw` açıksa `sudo ufw allow 9000/tcp`.

## 6. Worker'ı başlat (master açıkken)

Önce kullanıcıya Baran'ın master'ının açık olup olmadığını sor. Sonra **ayrı bir terminalde** (açık kalacak):

```bash
python -m dap.worker.main
```

Günlükte şunlar görünmeli:
- `Worker agent-can (...): A2A server on 0.0.0.0:9000, public address http://100.x.y.z:9000, master http://100...:8000`
- `Registered agent-can with http://...:8000`
- birkaç saniyede bir `heartbeat ... 200 OK`

**Bu pencere test boyunca açık kalmalı**, bilgisayar uyku moduna geçmemeli. Pencere kapanırsa ajan 30 saniyede "Offline" olur.

## 7. Bağlantıyı kontrol et

**İkinci bir terminalde** (aynı klasör, sanal ortam açık):

```bash
python scripts/check_connection.py
```

Altı satırın hepsi `OK` olmalı, en sonda `All checks passed.` yazmalı. `FAIL` varsa o satırdaki öneriyi uygula ve tekrar çalıştır.

Son kontrol: tarayıcıda `http://<Baran'ın IP'si>:8000/agents` adresini aç (IP, `.env`'deki `MASTER_URL`'de yazar).
Bu bilgisayarın kartı **Ready** olmalı ve altında **"✓ master can reach it"** yazmalı.

## 8. Kullanıcıya rapor ver

Kısa bir tablo: Python sürümü, Tailscale adresi, model hazır mı, `pytest` sonucu, worker açık mı, `check_connection` sonucu
(6/6 OK mi), agents sayfasında görünüyor mu. Eksik varsa ne yapılması gerektiğini yaz.

## Sorun giderme

| Belirti | Muhtemel sebep | Ne yap |
| --- | --- | --- |
| `Connection refused` / master'a ulaşılamıyor | Master açık değil ya da Tailscale kapalı | Baran'ın master'ı açık mı diye sor; `tailscale status` |
| `401` | Token farklı | Okan'ın gönderdiği dosyanın aynen `.env` olarak kopyalandığından emin ol |
| check_connection'da 5. veya 6. satır FAIL | Master bu bilgisayarın 9000 portuna ulaşamıyor | Güvenlik duvarı adımını tekrarla; worker'ı yeniden başlat |
| `model not found` | Model indirilmemiş ya da adı farklı | Model adımına dön; ad birebir aynı olmalı |
| `ModuleNotFoundError` | Sanal ortam açık değil | `.venv`'i etkinleştir, `pip install -r requirements.txt` |
| Görev çok uzun sürüyor | Model yavaş | Normal; 25 dakikaya kadar beklenir. Worker penceresini kapatma |
