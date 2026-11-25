# Kurulum görevi: Baran - MASTER

Sen bir yapay zeka asistanısın. Bu bilgisayarı CM6453 dersindeki **Distributed AI Dev Platform** projesinin
bugünkü ekip testine hazırlayacaksın.

**Bu bilgisayarın rolü: MASTER.** Web arayüzünü ve API'yi `http://<bu bilgisayarın Tailscale IP'si>:8000` adresinde sunar,
gereksinimi kendi modeliyle görevlere böler, görevleri altı worker bilgisayara Tailscale üzerinden dağıtır, sonuçları toplar
ve üretilen uygulamayı kendisi test eder. **Bu bilgisayarda worker çalışmaz.**

| Bilgi | Değer |
| --- | --- |
| Kullanıcı | Baran |
| Rol | master (port 8000) |
| Master'ın modeli | `gemma4:26b` (Ollama); yalnızca görev bölmek için |
| Kod | https://github.com/Tilhium/dap_test (özel repo) |
| Ayar dosyası | Okan'ın ayrıca gönderdiği `.env.for-baran` |

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
python3 --version     # 3.11 veya daha yeni
git --version
tailscale ip -4       # 100.x.y.z gibi bir adres vermeli
```

- macOS'ta `tailscale` komutu yoksa: `/Applications/Tailscale.app/Contents/MacOS/Tailscale ip -4`
- Tailscale adres vermiyorsa: uygulamayı açıp ekip hesabıyla giriş yapmasını iste.
- Node.js **gerekmez**: web arayüzü repoda derlenmiş olarak geliyor (`frontend/dist`).

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

Kontrol: `frontend/dist/index.html` dosyası olmalı. Yoksa `git pull`; hâlâ yoksa Okan'a haber ver.

## 3. Model: Ollama

```bash
ollama --version
ollama pull gemma4:26b            # büyük bir model, zaman alabilir
ollama list                       # listede tam olarak "gemma4:26b" görünmeli
ollama run gemma4:26b "Say OK"    # modeli belleğe yükler
```

## 4. Ayar dosyasını yerleştir

Okan kullanıcıya ayrıca **`.env.for-baran`** adlı bir dosya gönderdi (WhatsApp vb.).

1. Kullanıcıdan bu dosyanın nerede olduğunu iste. Adı aktarımda değişmiş olabilir
   (örneğin `env.for-baran.txt`); içinde `AGENT_TOKEN=` ve `AGENT_ID=agent-baran` satırları olan dosya odur.
2. Dosyayı `dap_test` klasörünün köküne **`.env`** adıyla kopyala (başında nokta var, uzantı yok).
3. İçeriği yazdırmadan kontrol et. Yalnızca şu satırları göstermek serbest:
   - `LLM_MODEL=gemma4:26b`
   - `LLM_MOCK=0`
   - `MASTER_HOST=0.0.0.0` ve `MASTER_PORT=8000`
   - `DATABASE_URL=sqlite:///./data/test-day.db`
4. `git status` çıktısında `.env` **görünmemeli** (git dışında tutulur).

## 5. Güvenlik duvarı

Worker'lar bu bilgisayarın **8000** portuna bağlanır. Master ilk açıldığında macOS "gelen bağlantılara izin ver" diye sorarsa
**İzin ver**. Sistem Ayarları → Ağ → Güvenlik Duvarı açıksa Python'a gelen bağlantı izni verilmeli.

## 6. Master'ı başlat

**Ayrı bir terminalde** (açık kalacak):

```bash
python -m dap.master
```

`Uvicorn running on http://0.0.0.0:8000` görünmeli. Kontrol (ikinci terminal):

```bash
curl http://localhost:8000/api/v1/health      # {"status":"ok",...}
```

Tarayıcıda `http://localhost:8000` açılmalı: "Distributed AI Dev Platform" arayüzü.

**Bu pencere test boyunca açık kalmalı ve bilgisayar uyumamalı** (macOS: ayrı bir terminalde `caffeinate -d`).

## 7. Adresi Okan'a bildir

```bash
tailscale ip -4
```

Kullanıcıya bu adresi **Okan'a göndermesini** söyle. Okan bu adresle diğer altı kişinin ayar dosyalarını güncelleyip gönderecek.
Worker'lar bağlandıkça `http://localhost:8000/agents` sayfasında kartları görünür. Hedef: altı ajan da **Ready** ve her kartta
**"✓ master can reach it"**.

## 8. Kullanıcıya rapor ver

Kısa bir tablo: Python sürümü, Tailscale adresi, `gemma4:26b` hazır mı, `pytest` sonucu, master açık mı, health cevabı,
arayüz açılıyor mu. Eksik varsa ne yapılması gerektiğini yaz.

## Deneme sırasında (bilgi için)

Arayüzde **New project**, sonra proje sayfasındaki **"Next step"** kutusunun gösterdiği düğmeler: **Decompose** →
**Assign agents** → **Run on agents**. Sonunda master üretilen uygulamayı test eder; sonuç **Master check** tablosunda görünür.
Üretilen uygulamayı açmak için:

```bash
cd workspace/<project_id>
pip install -r requirements.txt
uvicorn backend.main:app --port 8100      # sonra http://localhost:8100
```

## Sorun giderme

| Belirti | Muhtemel sebep | Ne yap |
| --- | --- | --- |
| `Address already in use` (8000) | Başka bir master açık | Eski terminali kapat ya da süreci durdur |
| Arayüz "Frontend not built" diyor | `frontend/dist` eksik | `git pull`; hâlâ yoksa Okan'a haber ver |
| Decompose hata veriyor (502) | Model cevap vermiyor | Ollama açık mı, `ollama list`'te `gemma4:26b` var mı |
| Bir ajan listede görünmüyor | O worker master'a ulaşamıyor | Bu bilgisayarın güvenlik duvarında 8000'e izin; worker'ın `MASTER_URL`'i bu bilgisayarın IP'si mi |
| Kartta "✗ master cannot reach it" | Master worker'ın 9000 portuna ulaşamıyor | O worker'ın güvenlik duvarı (onun tarafında çözülür) |
