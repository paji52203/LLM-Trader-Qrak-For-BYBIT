# 🤖 Tokocrypto AI Trading Bot - Cara Install

## Langkah Install (Linux/Ubuntu/Pop!_OS)

```bash
# 1. Install & setup otomatis
chmod +x install.sh && ./install.sh

# 2. Isi API Keys
nano keys.env

# 3. Jalankan bot!
./run.sh
```

## Isi keys.env yang WAJIB diisi:

```
TOKOCRYPTO_API_KEY=isi_api_key_tokocrypto_anda
TOKOCRYPTO_API_SECRET=isi_secret_tokocrypto_anda
GOOGLE_STUDIO_API_KEY=isi_google_ai_studio_key_anda
```

## Cara dapat API Key:
- **Tokocrypto** → Login → Profil → API Management → Buat API Key
- **Google AI Studio** → https://aistudio.google.com → Get API Key

## Monitor bot (setelah jalan):
```bash
tail -f logs/Bot/$(date +%Y_%m_%d)/Bot.log
```

## Hentikan bot:
```bash
pkill -f "python3 start.py"
```
