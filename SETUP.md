# Distributed AI Dev Platform - Setup Guide

## 1. Tailscale Mesh Network Setup
Bu proje, makineler arası güvenli haberleşme için Tailscale mesh ağını kullanır.

* **Shared Account:** Ortak Tailscale hesabına tüm geliştirici makineleri dahil edilir.
* **IP Adresi Öğrenme:** Terminalde aşağıdaki komutu çalıştırarak makinenizin Tailscale IPv4 adresini öğrenebilirsiniz:
  ```bash
  tailscale ip -4
export MASTER_URL="http://<MASTER_TAILSCALE_IP>:5000"
### Adım 3: Diğer Dosyaları Oluşturmaya Devam Et
`SETUP.md` tamamlandıktan sonra, sıradaki diğer dosyaları (`docs/network-test.md`, `docs/agents.json`, `scripts/seed_agents.py` ve `scripts/smoke_test.py`) tek seferde hatasız oluşturmak için şu blokların tümünü kopyalayıp terminale yapıştırabilirsin:

```bash
mkdir -p docs config scripts

cat << 'EOF' > docs/network-test.md
# Network Test Matrix & 7-Machine Sequence

Aşağıdaki tablo, dağıtık yapıdaki 7 makinenin Tailscale ağı üzerindeki test ve kayıt sırasını belirtir:

| Sıra | Makine Adı | Rol | Tailscale IP | Test Durumu |
|---|---|---|---|---|
| 1 | Master-Node-1 | Orchestrator | 100.64.0.1 | Aktif (Master) |
| 2 | Worker-Node-WSL | Worker (Linux) | 100.64.0.2 | Beklemede |
| 3 | Partner-PC-Windows | Worker (Windows) | 100.64.0.3 | Beklemede |
| 4 | Edge-Node-4 | Worker | 100.64.0.4 | Beklemede |
| 5 | Edge-Node-5 | Worker | 100.64.0.5 | Beklemede |
| 6 | Worker-Node-6 | Worker | 100.64.0.6 | Beklemede |
| 7 | Verification-Node | Tester / CI | 100.64.0.7 | Beklemede |
