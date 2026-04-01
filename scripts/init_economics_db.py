import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.economics_store import get_conn, init_economics_db, normalize_crop_name

DEFAULT_PRICE_ROWS = [
    {
        "crop": "Maize",
        "price_value": 209.6,
        "price_unit": "usd_per_tonne",
        "currency": "USD",
        "market_reference": "World Bank Pink Sheet - Maize",
        "source_name": "World Bank Pink Sheet March 2026",
        "source_note": "February 2026 monthly average",
        "observed_at": "2026-02-01",
    },
    {
        "crop": "Rice",
        "price_value": 409.0,
        "price_unit": "usd_per_tonne",
        "currency": "USD",
        "market_reference": "World Bank Pink Sheet - Rice Thailand 5%",
        "source_name": "World Bank Pink Sheet March 2026",
        "source_note": "February 2026 monthly average",
        "observed_at": "2026-02-01",
    },
    {
        "crop": "Soybean",
        "price_value": 455.0,
        "price_unit": "usd_per_tonne",
        "currency": "USD",
        "market_reference": "World Bank Pink Sheet - Soybeans",
        "source_name": "World Bank Pink Sheet March 2026",
        "source_note": "February 2026 monthly average",
        "observed_at": "2026-02-01",
    },
    {
        "crop": "Wheat",
        "price_value": 257.6,
        "price_unit": "usd_per_tonne",
        "currency": "USD",
        "market_reference": "World Bank Pink Sheet - Wheat U.S. HRW",
        "source_name": "World Bank Pink Sheet March 2026",
        "source_note": "February 2026 monthly average",
        "observed_at": "2026-02-01",
    },
    {
        "crop": "Cotton",
        "price_value": 1630.0,
        "price_unit": "usd_per_tonne",
        "currency": "USD",
        "market_reference": "World Bank Pink Sheet - Cotton",
        "source_name": "World Bank Pink Sheet March 2026",
        "source_note": "February 2026 monthly average converted from USD/kg to USD/t",
        "observed_at": "2026-02-01",
    },
    {
        "crop": "Sorghum",
        "price_value": 142.42,
        "price_unit": "usd_per_tonne",
        "currency": "USD",
        "market_reference": "USDA NASS Agricultural Prices - Sorghum Grain",
        "source_name": "USDA NASS Agricultural Prices March 2026",
        "source_note": "February 2026 U.S. average: 6.46 USD/cwt, converted to USD/t",
        "observed_at": "2026-02-01",
    },
    {
        "crop": "Plantains And Others",
        "price_value": 1210.0,
        "price_unit": "usd_per_tonne",
        "currency": "USD",
        "market_reference": "World Bank Pink Sheet - Bananas, U.S.",
        "source_name": "World Bank Pink Sheet March 2026",
        "source_note": (
            "February 2026 monthly average, proxy based on bananas U.S. import price "
            "because no dedicated current plantain benchmark is available in the same source family"
        ),
        "observed_at": "2026-02-01",
    },
]

DEFAULT_COST_ROWS = [
    {"crop": "Maize"},
    {"crop": "Rice"},
    {"crop": "Soybean"},
    {"crop": "Wheat"},
    {"crop": "Cotton"},
    {"crop": "Barley"},
    {"crop": "Cassava"},
    {"crop": "Potatoes"},
    {"crop": "Sorghum"},
    {"crop": "Sweet Potatoes"},
    {"crop": "Plantains And Others"},
    {"crop": "Yams"},
]


def main() -> None:
    init_economics_db()

    with get_conn() as conn:
        conn.execute("DELETE FROM crop_prices WHERE is_default = 1")
        conn.execute("DELETE FROM crop_costs WHERE is_default = 1")

        for row in DEFAULT_PRICE_ROWS:
            conn.execute(
                """
                INSERT INTO crop_prices (
                    crop, price_value, price_unit, currency,
                    market_reference, source_name, source_note,
                    observed_at, is_default, is_user_override, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 1)
                """,
                (
                    normalize_crop_name(row["crop"]),
                    row["price_value"],
                    row["price_unit"],
                    row["currency"],
                    row["market_reference"],
                    row["source_name"],
                    row["source_note"],
                    row["observed_at"],
                ),
            )

        for row in DEFAULT_COST_ROWS:
            conn.execute(
                """
                INSERT INTO crop_costs (
                    crop, seed_cost_per_ha, pesticide_cost_per_ha,
                    fertilizer_cost_per_ha, irrigation_cost_per_ha,
                    other_cost_per_ha, currency, source_name, source_note,
                    observed_at, is_default, is_user_override, is_active
                ) VALUES (?, 0, 0, 0, 0, 0, 'USD',
                          'Default zero costs',
                          'Placeholder values to be edited by the user',
                          '2026-03-30', 1, 0, 1)
                """,
                (normalize_crop_name(row["crop"]),),
            )

    print("Economics DB initialized successfully.")


if __name__ == "__main__":
    main()
