"""Shared constants."""

PORTAL_MODULES = [
    {"href": "/dashboard", "icon": "fa-chart-line", "title": "Dashboard", "desc": "Ringkasan keuangan", "key": "dashboard"},
    {"href": "/transfer-bgn", "icon": "fa-building-columns", "title": "Transfer BGN", "desc": "Uang masuk BGN & integrasi pengeluaran", "key": "transfer_bgn"},
    {"href": "/portal-mitra", "icon": "fa-house-chimney", "title": "Portal Mitra", "desc": "Beranda & ringkasan mitra", "key": "portal_mitra"},
    {"href": "/laporan", "icon": "fa-clipboard-list", "title": "Laporan Keuangan", "desc": "Ringkasan gabungan semua modul", "key": "laporan"},
    {"href": "/tagihan", "icon": "fa-file-invoice-dollar", "title": "Laporan Tagihan", "desc": "Data tagihan mitra", "key": "tagihan"},
    {"href": "/petty-cash", "icon": "fa-wallet", "title": "Petty Cash", "desc": "Buku besar & reimbursement", "key": "petty_cash"},
    {"href": "/insentif-mitra", "icon": "fa-handshake", "title": "Laporan Insentif Mitra", "desc": "Pembayaran insentif mitra", "key": "insentif_mitra"},
    {"href": "/pengembalian-dana", "icon": "fa-rotate-left", "title": "Pengembalian Dana", "desc": "Pengembalian dana / refund", "key": "pengembalian_dana"},
    {"href": "/sewa-kendaraan", "icon": "fa-car", "title": "Sewa Kendaraan", "desc": "Sewa kendaraan operasional dari dana BGN", "key": "sewa_kendaraan"},
    {"href": "/pengajuan-dana-mitra", "icon": "fa-file-invoice", "title": "Pengajuan Dana Mitra", "desc": "Pengajuan dana mitra SPPG", "key": "pengajuan_dana_mitra"},
    {"href": "/pendapatan-mitra", "icon": "fa-sack-dollar", "title": "Pendapatan Mitra", "desc": "Laporan pendapatan insentif mitra", "key": "pendapatan_mitra"},
    {"href": "/pengeluaran-mitra", "icon": "fa-money-bill-transfer", "title": "Pengeluaran Mitra", "desc": "Pencatatan pengeluaran mitra SPPG", "key": "pengeluaran_mitra"},
    {"href": "/gaji-relawan", "icon": "fa-users", "title": "Gaji Relawan", "desc": "Pembayaran relawan", "key": "gaji_relawan"},
    {"href": "/gaji-staff", "icon": "fa-id-badge", "title": "Gaji Staff", "desc": "Pembayaran gaji staff", "key": "gaji_staff"},
    {"href": "/insentif-pic", "icon": "fa-user-tie", "title": "Insentif PIC", "desc": "Pembayaran insentif PIC", "key": "insentif_pic"},
]


ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLE_VIEWER = "viewer"
ROLE_MITRA = "mitra"
ROLE_KA_SPPG = "ka_sppg"
ROLE_MAKER = "maker"

STATUS_DIAJUKAN = "DIAJUKAN"
STATUS_DISETUJUI = "DISETUJUI"
STATUS_LUNAS = "LUNAS"
STATUS_DIBAYARKAN = "DIBAYARKAN"
STATUS_DITOLAK = "DITOLAK"

PAID_STATUS_SQL = "UPPER(COALESCE(status, '')) IN ('LUNAS', 'DIBAYARKAN', 'TERBAYAR')"

APPROVAL_KATEGORI = {
    "tagihan",
    "gaji_relawan",
    "gaji_staff",
    "insentif_pic",
    "insentif_mitra",
    "pengembalian_dana",
    "sewa_kendaraan",
    "pengajuan_dana_mitra",
    "pengeluaran_mitra",
}

KATEGORI_LABELS = {
    "tagihan": "Laporan Tagihan",
    "gaji_relawan": "Gaji Relawan",
    "gaji_staff": "Gaji Staff",
    "insentif_pic": "Insentif PIC",
    "insentif_mitra": "Insentif Mitra",
    "pengembalian_dana": "Pengembalian Dana",
    "sewa_kendaraan": "Sewa Kendaraan",
    "pengajuan_dana_mitra": "Pengajuan Dana Mitra",
    "pengeluaran_mitra": "Pengeluaran Mitra",
}

ROLE_OPTIONS = [
    {"id": ROLE_ADMIN, "label": "Administrator", "desc": "Akses penuh & setup", "icon": "fa-shield-halved", "color": "#071e49"},
    {"id": ROLE_KA_SPPG, "label": "KA SPPG", "desc": "Menyetujui pengajuan DIAJUKAN", "icon": "fa-user-check", "color": "#1e3a5f"},
    {"id": ROLE_MAKER, "label": "Maker Pembayaran", "desc": "Proses pembayaran VA setelah disetujui KA", "icon": "fa-money-bill-transfer", "color": "#166534"},
    {"id": ROLE_MEMBER, "label": "Akuntan / Member", "desc": "Upload & input terbatas", "icon": "fa-calculator", "color": "#0c4a6e"},
    {"id": ROLE_VIEWER, "label": "Viewer", "desc": "Hanya melihat data", "icon": "fa-eye", "color": "#64748b"},
    {"id": ROLE_MITRA, "label": "Mitra", "desc": "Lihat insentif & pengeluaran milik mitra", "icon": "fa-handshake", "color": "#92400e"},
]

MITRA_DEFAULT_PATH = "/portal-mitra"

MODULE_ACCESS_GROUPS = [
    {
        "id": "persetujuan",
        "label": "Persetujuan",
        "modules": [
            {"key": "dashboard_ka", "label": "Dashboard KA SPPG", "href": "/dashboard-ka", "icon": "fa-user-check",
             "path_prefixes": ["/dashboard-ka", "/api/dashboard-ka", "/export/laporan/lunas"]},
            {"key": "dashboard_bayar", "label": "Dashboard Pembayaran", "href": "/dashboard-bayar", "icon": "fa-money-bill-wave",
             "path_prefixes": ["/dashboard-bayar", "/api/dashboard-bayar", "/export/laporan/lunas"]},
        ],
    },
    {
        "id": "beranda",
        "label": "Modul Beranda",
        "modules": [
            {"key": "dashboard", "label": "Dashboard", "href": "/dashboard", "icon": "fa-chart-line",
             "path_prefixes": ["/dashboard", "/api/dashboard", "/api/summary", "/api/dashboard/monthly-chart"]},
            {"key": "transfer_bgn", "label": "Transfer BGN", "href": "/transfer-bgn", "icon": "fa-building-columns",
             "path_prefixes": ["/transfer-bgn", "/api/transfer-bgn", "/export/transfer-bgn"]},
            {"key": "laporan", "label": "Laporan Keuangan", "href": "/laporan", "icon": "fa-clipboard-list",
             "path_prefixes": ["/laporan", "/export/laporan"]},
        ],
    },
    {
        "id": "laporan",
        "label": "Modul Laporan",
        "modules": [
            {"key": "tagihan", "label": "Laporan Tagihan", "href": "/tagihan", "icon": "fa-file-invoice-dollar",
             "path_prefixes": ["/tagihan", "/export/tagihan", "/export/pdf", "/export/csv", "/export/xlsx", "/upload", "/api/tagihan"]},
            {"key": "petty_cash", "label": "Petty Cash", "href": "/petty-cash", "icon": "fa-wallet",
             "path_prefixes": ["/petty-cash", "/api/petty-cash"]},
            {"key": "gaji_relawan", "label": "Gaji Relawan", "href": "/gaji-relawan", "icon": "fa-users",
             "path_prefixes": ["/gaji-relawan", "/export/gaji-relawan", "/api/gaji-relawan"]},
            {"key": "gaji_staff", "label": "Gaji Staff", "href": "/gaji-staff", "icon": "fa-id-badge",
             "path_prefixes": ["/gaji-staff", "/export/gaji-staff", "/api/gaji-staff"]},
            {"key": "insentif_pic", "label": "Insentif PIC", "href": "/insentif-pic", "icon": "fa-user-tie",
             "path_prefixes": ["/insentif-pic", "/export/insentif-pic", "/api/insentif-pic"]},
            {"key": "insentif_mitra", "label": "Insentif Mitra", "href": "/insentif-mitra", "icon": "fa-handshake",
             "path_prefixes": ["/insentif-mitra", "/export/insentif-mitra", "/api/insentif-mitra"]},
            {"key": "pengembalian_dana", "label": "Pengembalian Dana", "href": "/pengembalian-dana", "icon": "fa-rotate-left",
             "path_prefixes": ["/pengembalian-dana", "/export/pengembalian-dana", "/api/pengembalian-dana"]},
            {"key": "sewa_kendaraan", "label": "Sewa Kendaraan", "href": "/sewa-kendaraan", "icon": "fa-car",
             "path_prefixes": ["/sewa-kendaraan", "/export/sewa-kendaraan", "/api/sewa-kendaraan"]},
        ],
    },
    {
        "id": "mitra",
        "label": "Modul Mitra",
        "modules": [
            {"key": "portal_mitra", "label": "Portal Mitra", "href": "/portal-mitra", "icon": "fa-house-chimney",
             "path_prefixes": ["/portal-mitra"]},
            {"key": "pendapatan_mitra", "label": "Pendapatan Mitra", "href": "/pendapatan-mitra", "icon": "fa-sack-dollar",
             "path_prefixes": ["/pendapatan-mitra"]},
            {"key": "pengajuan_dana_mitra", "label": "Pengajuan Dana Mitra", "href": "/pengajuan-dana-mitra", "icon": "fa-file-invoice",
             "path_prefixes": ["/pengajuan-dana-mitra", "/export/pengajuan-dana-mitra", "/api/pengajuan-dana-mitra"]},
            {"key": "pengeluaran_mitra", "label": "Pengeluaran Mitra", "href": "/pengeluaran-mitra", "icon": "fa-money-bill-transfer",
             "path_prefixes": ["/pengeluaran-mitra", "/api/pengeluaran-mitra"]},
        ],
    },
]

MODULE_BY_KEY: dict = {}
for _group in MODULE_ACCESS_GROUPS:
    for _mod in _group["modules"]:
        MODULE_BY_KEY[_mod["key"]] = {**_mod, "group": _group["id"], "group_label": _group["label"]}

MODULE_BY_KEY["setup"] = {
    "key": "setup",
    "label": "Setup",
    "href": "/setup",
    "icon": "fa-sliders",
    "group": "setup",
    "group_label": "Pengaturan",
    "path_prefixes": ["/setup", "/api/setup", "/api/personnel"],
}

MODULE_HOME_PRIORITY = [
    "dashboard_ka",
    "dashboard_bayar",
    "dashboard",
    "portal_mitra",
    "transfer_bgn",
    "laporan",
    "tagihan",
    "petty_cash",
    "gaji_relawan",
    "gaji_staff",
    "insentif_pic",
    "insentif_mitra",
    "pengembalian_dana",
    "sewa_kendaraan",
    "pendapatan_mitra",
    "pengajuan_dana_mitra",
    "pengeluaran_mitra",
    "setup",
]

DEFAULT_THEME = {
    "color_primary": "#071e49",
    "color_accent": "#c9a558",
    "color_secondary": "#55a7d4",
    "color_icon": "#2563eb",
    "icon_style": "rounded",
}

ICON_STYLES = [
    {"id": "rounded", "label": "Rounded", "desc": "Sudut melengkung standar"},
    {"id": "soft", "label": "Soft", "desc": "Lebih bulat & lembut"},
    {"id": "sharp", "label": "Sharp", "desc": "Sudut tajam modern"},
]

THEME_PRESETS = {
    "classic": {
        "label": "Klasik BGN",
        "color_primary": "#071e49",
        "color_accent": "#c9a558",
        "color_secondary": "#55a7d4",
        "color_icon": "#2563eb",
        "icon_style": "rounded",
    },
    "ocean": {
        "label": "Samudra",
        "color_primary": "#0c4a6e",
        "color_accent": "#38bdf8",
        "color_secondary": "#0ea5e9",
        "color_icon": "#0284c7",
        "icon_style": "soft",
    },
    "forest": {
        "label": "Hutan",
        "color_primary": "#14532d",
        "color_accent": "#86efac",
        "color_secondary": "#22c55e",
        "color_icon": "#16a34a",
        "icon_style": "rounded",
    },
    "sunset": {
        "label": "Senja",
        "color_primary": "#7c2d12",
        "color_accent": "#fb923c",
        "color_secondary": "#f97316",
        "color_icon": "#ea580c",
        "icon_style": "soft",
    },
    "midnight": {
        "label": "Tengah Malam",
        "color_primary": "#1e1b4b",
        "color_accent": "#818cf8",
        "color_secondary": "#6366f1",
        "color_icon": "#4f46e5",
        "icon_style": "sharp",
    },
    "rose": {
        "label": "Mawar",
        "color_primary": "#881337",
        "color_accent": "#fb7185",
        "color_secondary": "#f43f5e",
        "color_icon": "#e11d48",
        "icon_style": "soft",
    },
}
AUTH_ONLY_PATHS = {"/masuk", "/login", "/logout"}
MEMBER_WRITE_PATHS = AUTH_ONLY_PATHS | {
    "/upload",
    "/pengajuan-dana-mitra/upload",
    "/petty-cash/upload",
    "/gaji-relawan/upload",
    "/insentif-pic/upload",
    "/insentif-mitra/upload",
}
TAGIHAN_ATTACHMENT_FIELDS = {"pict", "nota", "bukti"}
TAGIHAN_ATTACHMENT_KATEGORI = {"pengajuan_dana_mitra", "insentif_mitra"}
TAGIHAN_CHARGES_AMOUNT = 6500

FEE_PAYROL_PER_ORANG = 2500
INSENTIF_MITRA_PER_HARI = 6_000_000
INSENTIF_MITRA_HARI = 6
INSENTIF_MITRA_JUMLAH = INSENTIF_MITRA_PER_HARI * INSENTIF_MITRA_HARI
PENGEMBALIAN_DANA_PER_HARI = 6_000_000
PENGEMBALIAN_DANA_HARI = 6
PENGEMBALIAN_DANA_JUMLAH = PENGEMBALIAN_DANA_PER_HARI * PENGEMBALIAN_DANA_HARI
ALLOWED_NOTA_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}
TAGIHAN_ATTACHMENT_COLS = {
    "pict": "pict_path",
    "nota": "nota_path",
    "bukti": "bukti_path",
}

ID_MONTH_NAMES = (
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)
