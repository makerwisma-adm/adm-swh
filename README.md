# Sistem Pelaporan Keuangan SPPG Wisma Haji Madiun

Web aplikasi internal untuk pelaporan keuangan **Tagihan Mitra** SPPG Wisma Haji Madiun.

> Instalasi terpisah dari `PROJECT/MAKER` — database dan upload file sendiri, port **8001**.

## Fitur

- Login dengan akses terbatas (tidak bisa diakses sembarang orang)
- Dashboard menarik dengan KPI cards, grafik, dan ringkasan
- Input data mengikuti struktur **Tagihan Mitra** dari Excel (NO, PENGAJUAN, JUMLAH, STATUS, REKENING, TANGGAL, ATAS NAMA, NOMOR REKENING, BANK)
- Data table lengkap dengan filter, pencarian, dan edit/hapus
- Export ke CSV dan Excel (.xlsx) mirip struktur "Tagihan Mitra" asli
- Tombol Export Excel langsung di halaman Tagihan
- Logo resmi Badan Gizi Nasional ditampilkan secara profesional di halaman login dan navigasi
- Data awal sudah di-seed sesuai file Excel asli

## Cara Menjalankan

1. Pastikan kamu berada di folder ini:

   ```bash
   cd /Users/adm/PROJECT/WEB
   ```

2. Install dependencies (sekali saja):

   ```bash
   python3 -m pip install -r requirements.txt
   ```

3. Jalankan aplikasi:

   ```bash
   python3 main.py
   ```

   atau

   ```bash
   python3 -m uvicorn main:app --reload --port 8001
   ```

4. Buka browser: **http://localhost:8001**

## Akun Login Default

| Username | Password      | Keterangan     |
|----------|---------------|----------------|
| `swhm`   | `Herman@0281` | Admin Utama (Maker SWH) |
| `admin`  | `sppg123`     | Backup Admin   |

> **Penting**: Ganti password setelah pertama kali login di production.

## Struktur Data (sesuai Excel)

Kolom yang tersedia:

- **NO**
- **PENGAJUAN** (deskripsi)
- **JUMLAH**
- **STATUS** → `DIAJUKAN`, `TERBAYAR`
- **REKENING** → `KAS STAFF`, `PETTY CASH`, `CV IPAL`
- **TANGGAL**
- **ATAS NAMA REK.**
- **NOMOR REKENING**
- **BANK**

## File Penting

- `main.py` — aplikasi FastAPI
- `sppg_keuangan.db` — database SQLite (otomatis dibuat)
- `templates/` — UI halaman

---

Dibuat untuk keperluan internal SPPG Wisma Haji Madiun.
