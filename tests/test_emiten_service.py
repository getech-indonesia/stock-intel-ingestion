from app.services.emiten_service import _build_prisma_payload


def test_build_prisma_payload_merges_idx_profile():
    symbol = "BBCA"
    ajaib_item = {
        "symbol": "BBCA",
        "name": "Bank Central Asia Tbk.",
        "price": 6100,
        "icon_url": "https://cdn-stock.ajaib.co.id/image/BBCA.png",
        "market_cap": 744458026950000,
        "volume": 147339600,
        "price_1_week": {"pct_change": 2.52},
        "price_1_month": {"pct_change": -7.22},
    }

    # Simulated IDX merged payload (what fetch_idx_company_profile now returns)
    idx_payload = {
        "profile": {
            "NamaEmiten": "PT Bank Central Asia Tbk.",
            "Alamat": "Menara BCA, Grand Indonesia\r\nJalan MH Thamrin No. 1\r\nJakarta 10310",
            "Website": "www.bca.co.id",
            "Sektor": "Keuangan",
            "Industri": "Bank",
            "TanggalPencatatan": "2000-05-31T00:00:00",
            "Logo": "/Portals/0/StaticData/ListedCompanies/LogoEmiten/BBCA.jpg",
        },
        "Direktur": [
            {"Nama": "Gregory Hendra Lembong", "Jabatan": "PRESIDEN DIREKTUR"},
            {"Nama": "Armand Wahyudi Hartono", "Jabatan": "WAKIL PRESIDEN DIREKTUR"},
        ],
        "PemegangSaham": [
            {"Nama": "PT Dwimuria Investama Andalan", "Persentase": 54.942},
            {"Nama": "Masyarakat Non Warkat", "Persentase": 42.159},
        ],
        "Sekretaris": [{"Nama": "Rudy Budiardjo"}],
        "Komisaris": [{"Nama": "Jahja Setiaatmadja", "Jabatan": "PRESIDEN KOMISARIS"}],
        "KomiteAudit": [{"Nama": "Sumantri Slamet", "Jabatan": "KETUA"}],
        "AnakPerusahaan": [],
        "Dividen": [],
        "BondsAndSukuk": [],
        "IssuedBond": [],
    }

    payload = _build_prisma_payload(symbol, ajaib_item, idx_payload)

    company = payload.get("company")
    assert company is not None
    assert company.get("ceo") == "Gregory Hendra Lembong"
    assert "Menara BCA" in (company.get("headquarters") or "")
    assert payload.get("shareholders") and len(payload.get("shareholders")) >= 2
    assert payload.get("sector", {}).get("name") == "Keuangan"
    assert payload.get("listing", {}).get("symbol") == "BBCA"
