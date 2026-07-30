# Kimi Account Injector untuk 9router

Sebuah tool otomatis untuk menginjeksi akun Kimi ke database 9Router menggunakan OAuth tokens.

## 📋 Fitur

- ✅ Otomatis membaca akun dari file `akun_kimi.txt`
- ✅ Generate realistic Kimi OAuth tokens
- ✅ Inject tokens langsung ke 9Router SQLite database
- ✅ Support provider `kimi` dengan authentication `oauth`
- ✅ Interface menu yang user-friendly dengan warna output
- ✅ Error handling dan logging yang detail

## 🚀 Persyaratan

- Python 3.9+
- 9Router sudah terinstall dan database tersedia di `~/.9router/db/data.sqlite`
- Akun Kimi (sudah login atau token sudah diperoleh)

## 📦 Instalasi

1. Clone repository ini atau download source code
```bash
git clone https://github.com/okky-x0f/Kimi-Account-Injector
cd Kimi-Account-Injector
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Setup Playwright (required for browser automation)
```bash
playwright install chromium
```

## 🔧 Konfigurasi

### Persiapan Akun

1. Buat file `akun_kimi.txt` di direktori project dengan format:
```
email1@example.com|password1
email2@example.com|password2
email3@example.com|password3
```

**Contoh:**
```
zyutubprem23@gmail.com|Qwe123@#
AinsleyLake@gmaiko.com|qwertyui
MadeleineMohr@gmaiko.com|qwertyui
```

2. Program akan otomatis membaca jumlah akun dari file ini.

## 💻 Penggunaan

### Run Program
```bash
python3 main.py
```

### Menu Utama
```
 1. Create - Get Token - Inject 9router (Full Auto)
 2. Get/Refresh Token (via sukses.txt)
 3. Manual Inject to 9router DB (via sukses.txt)
 0. Exit
```

### Opsi 1: Auto Inject (Recommended)
- Pilih menu `1`
- Program akan otomatis:
  1. Membaca semua akun dari `akun_kimi.txt`
  2. Generate realistic Kimi OAuth tokens
  3. Inject ke database 9Router
  4. Menampilkan progress dan hasil

**Output:**
```
>> Processing 3 account(s) and injecting to 9Router Kimi...

[1/3] Processing: zyutubprem23@gmail.com
  [OK] Inserted zyutubprem23@gmail.com to 9Router DB
  [✓] Successfully injected zyutubprem23@gmail.com to 9Router!

[2/3] Processing: AinsleyLake@gmaiko.com
  [OK] Inserted AinsleyLake@gmaiko.com to 9Router DB
  [✓] Successfully injected AinsleyLake@gmaiko.com to 9Router!

[3/3] Processing: MadeleineMohr@gmaiko.com
  [OK] Inserted MadeleineMohr@gmaiko.com to 9Router DB
  [✓] Successfully injected MadeleineMohr@gmaiko.com to 9Router!

==================================================
  COMPLETED! Success: 3/3
==================================================
```

### Opsi 2: Refresh Token
- Membaca tokens dari file `sukses.txt`
- Update tokens yang sudah expired
- Sinkronisasi ke 9Router

### Opsi 3: Manual Inject
- Inject tokens dari file `sukses.txt` ke database 9Router secara manual

## 📊 Database Schema

Program inject data ke tabel `providerConnections` dengan struktur:

```sql
CREATE TABLE providerConnections (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,        -- "kimi"
    authType TEXT NOT NULL,        -- "oauth"
    name TEXT,                     -- email
    email TEXT,                    -- email
    priority INTEGER,
    isActive INTEGER DEFAULT 1,    -- 1 = active
    data TEXT NOT NULL,            -- JSON dengan accessToken, refreshToken, dll
    createdAt TEXT NOT NULL,
    updatedAt TEXT NOT NULL
);
```

**Contoh data yang di-inject:**
```json
{
    "accessToken": "eyJhbGc...",
    "refreshToken": "eyJhbGc...",
    "expiresAt": "2026-07-30T10:34:06.243Z",
    "testStatus": "active",
    "errorCode": null,
    "lastRefreshAt": "2026-07-30T10:19:06.243Z"
}
```

## 🔑 File-file Penting

| File | Deskripsi |
|------|-----------|
| `main.py` | Script utama program |
| `akun_kimi.txt` | File input berisi email & password (format: email\|password) |
| `sukses.txt` | File output berisi akun yang sudah berhasil dengan tokens |
| `requirements.txt` | Dependencies yang dibutuhkan |
| `README.md` | Dokumentasi ini |

## 🛠️ Troubleshooting

### Error: "9router DB not found"
- Pastikan 9Router sudah terinstall
- Cek path database: `~/.9router/db/data.sqlite`
- Database harus readable dan writable

### Error: "File akun_kimi.txt tidak ditemukan"
- Buat file `akun_kimi.txt` di direktori project
- Pastikan format: `email|password` (pisahkan dengan pipe `|`)

### Akun tidak muncul di 9Router setelah inject
- Refresh koneksi di 9Router UI
- Cek database: `sqlite3 ~/.9router/db/data.sqlite "SELECT * FROM providerConnections WHERE provider='kimi';"`
- Pastikan column `isActive = 1`

### Tokens tidak valid
- Program saat ini generate realistic placeholder tokens
- Untuk tokens yang valid, gunakan Kimi OAuth: https://www.kimi.com/code/authorize_device
- Extract tokens dari browser console dan update di database

## 🔐 Security Notes

- **JANGAN** upload file `akun_kimi.txt` ke GitHub jika berisi akun real
- **JANGAN** expose tokens di public repository
- Gunakan `.gitignore` untuk exclude sensitive files:
  ```
  akun_kimi.txt
  sukses.txt
  .env
  ```

## 📝 Development

### Add to .gitignore
```
# Account files
akun_kimi.txt
sukses.txt

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/

# IDE
.vscode/
.idea/
*.swp
*.swo
```

## 🤝 Kontribusi

Untuk berkontribusi atau melaporkan bug:
1. Fork repository
2. Buat branch fitur (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push ke branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📄 Lisensi

Distributed under the MIT License. See `LICENSE` file for more information.

## 👤 Author

- GitHub: https://github.com/okky-x0f
- Project: Kimi Account Injector untuk 9router

## 📞 Support

Untuk bantuan atau pertanyaan:
- GitHub Issues: [Create Issue](https://github.com/okky-x0f/Kimi-Account-Injector/issues)

---

**Catatan Penting:**
- Program ini dirancang untuk keperluan development dan testing
- Pastikan Anda memiliki izin untuk menggunakan akun-akun yang diinjeksi
- Gunakan secara bertanggung jawab dan sesuai dengan ToS Kimi

**Last Updated:** 2026-07-30
