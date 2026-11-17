# Test günü: 1 master (Baran) + 6 worker

Amaç: Baran'ın bilgisayarı master olur, diğer altı kişinin bilgisayarı worker olur.
Bir gereksinimden uygulama üretilir ve master uygulamayı kendisi test eder.

| Kim | Rol | Model | Model sunucusu |
| --- | --- | --- | --- |
| Baran | **master** (arayüz + API, port 8000) | `gemma4:26b` | Ollama |
| Fatma | worker `agent-fatma` | `qwen3:4b` | Ollama |
| Eray | worker `agent-eray` | `qwen2.5-coder:7b` | Ollama |
| Can | worker `agent-can` | `qwen2.5-coder:7b` | Ollama |
| Abdurrahman | worker `agent-abdurrahman` | `qwen3:4b` | Ollama |
| Okan | worker `agent-okan` | `qwen2.5-coder:7b-instruct-q3_K_M` | Ollama |
| Hamza | worker `agent-hamza` | `gemma-4-26b-a4b-iq2_xxs` | llama.cpp `llama-server`, port 8080 |

## 1. Herkes: önceden

1. **Tailscale** açık ve ekip ağına girilmiş olmalı. Adresini gör: `tailscale ip -4`.
2. **Model hazır** olmalı: Ollama kullananlar Ollama'yı açar ve `ollama pull <model>`
   yapar. Hamza `llama-server`'ı 8080 portunda modeliyle açık tutar.
3. **Kod:**
   ```bash
   git clone https://github.com/Tilhium/dap_test.git   # ilk kez; sonra: git pull
   cd dap_test
   python -m venv .venv
   .venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. **Ayar dosyası:** Okan herkese kendi `.env.for-<ad>` dosyasını **özelden**
   gönderir. Dosya repo köküne `.env` adıyla kaydedilir. İçinde ekip token'ı var:
   gruba yazılmaz, commit'lenmez.

## 2. Baran: master'ı aç

1. `.env.for-baran` dosyasını `.env` olarak kaydet. `ollama pull gemma4:26b`.
2. Arayüz: `frontend/dist` klasörü varsa hazırdır. Yoksa:
   `cd frontend && npm install && npm run build && cd ..`
3. `python -m dap.master`
4. `tailscale ip -4` ile adresini Okan'a gönder, örneğin `100.70.1.2`.
5. Kendi tarayıcında `http://localhost:8000` açılmalı.

## 3. Okan: worker dosyalarını Baran'a çevir

```bash
python scripts/set_master.py http://<Baran'ın IP'si>:8000
```

Bu komut bütün `.env.for-*` dosyalarındaki `MASTER_URL` satırını değiştirir. Sonra
dosyaları herkese özelden gönder.

## 4. Worker'lar: bağlan

```bash
python -m dap.worker.main              # 1. pencere: worker açık kalır
python scripts/check_connection.py     # 2. pencere: altı kontrol de OK olmalı
```

Windows güvenlik duvarı sorarsa Python'a **izin ver**: master görevleri bu
bilgisayarın 9000 portuna gönderir.

**Kontrol:** `http://<Baran'ın IP'si>:8000/agents` sayfasında altı ajan da
**Ready** görünmeli ve her kartta **"✓ master can reach it"** yazmalı.

## 5. Deneme

1. Ana sayfada **New project**: ad ve gereksinim. Örnek:
   `docs/sample_requirements/orta.md` ya da kısa bir metin.
2. Proje sayfasındaki **"Next step"** kutusu sırayla şu düğmeleri gösterir:
   **Decompose** → **Assign agents** → **Run on agents**.
3. Görevler sırayla çalışır: database → backend → frontend → testing. Gerçek
   modellerle her görev birkaç dakika sürebilir.
4. Sonunda master uygulamayı test eder. Sonuç **Master check** tablosunda
   görünür.

## 6. Üretilen uygulamayı açmak (Baran'ın bilgisayarında)

```bash
cd workspace/<project_id>
pip install -r requirements.txt
uvicorn backend.main:app --port 8100
```

Tarayıcıda `http://localhost:8100` açılır. 8000 master'ındır, bu yüzden 8100.

## Sorun olursa

| Belirti | Sebep | Çözüm |
| --- | --- | --- |
| Ajan listede yok | Worker master'a ulaşamıyor | Tailscale açık mı; `.env`'deki `MASTER_URL` Baran'ın IP'si mi; `check_connection.py` |
| Worker "401" diyor | Token farklı | Okan'ın gönderdiği `.env` kullanılmalı |
| Kartta "✗ master cannot reach it" | Master worker'ın 9000 portuna ulaşamıyor | Güvenlik duvarında Python'a izin ver; worker'ı yeniden başlat |
| Ajan **Offline** | 30 sn heartbeat gelmedi | Worker penceresi kapandı mı, Tailscale düştü mü |
| Decompose hata veriyor (502) | Baran'ın modeli cevap vermiyor | Baran'da Ollama açık mı, `gemma4:26b` yüklü mü |
| Görev uzun süre "Running" | Model yavaş | 25 dakikaya kadar normal (`TASK_TIMEOUT_SEC=1500`) |
| Görev "Failed" | Model iki düzeltmeden sonra da hatalı kod yazdı | Proje sayfasında **Task reports** → hata metni; **Run again** |
