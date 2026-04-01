from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd

ECON_DB_PATH = Path(os.getenv("P12_ECON_DB_PATH", "data/reference/economics.sqlite"))

KNOWN_CROPS = [
    "Barley",
    "Cassava",
    "Cotton",
    "Maize",
    "Plantains And Others",
    "Potatoes",
    "Rice",
    "Sorghum",
    "Soybean",
    "Sweet Potatoes",
    "Wheat",
    "Yams",
]


def normalize_crop_name(crop: str) -> str:
    crop = crop.strip().lower()

    aliases = {
        "rice": "Rice",
        "rice, paddy": "Rice",
        "soybean": "Soybean",
        "soybeans": "Soybean",
        "maize": "Maize",
        "maize (corn)": "Maize",
        "corn": "Maize",
        "wheat": "Wheat",
        "barley": "Barley",
        "cotton": "Cotton",
        "cassava": "Cassava",
        "potatoes": "Potatoes",
        "potato": "Potatoes",
        "sorghum": "Sorghum",
        "sweet potatoes": "Sweet Potatoes",
        "sweet potato": "Sweet Potatoes",
        "plantains and others": "Plantains And Others",
        "plantains & others": "Plantains And Others",
        "plantains": "Plantains And Others",
        "yams": "Yams",
        "yam": "Yams",
    }

    return aliases.get(crop, crop.title())


def get_conn() -> sqlite3.Connection:
    ECON_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ECON_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_prices() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query(
            """
            SELECT
                id,
                crop,
                price_value,
                price_unit,
                currency,
                market_reference,
                source_name,
                source_note,
                observed_at,
                is_default,
                is_user_override,
                is_active,
                updated_at
            FROM crop_prices
            ORDER BY crop ASC, is_user_override DESC, updated_at DESC, id DESC
            """,
            conn,
        )
    return df


def load_costs() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query(
            """
            SELECT
                id,
                crop,
                seed_cost_per_ha,
                pesticide_cost_per_ha,
                fertilizer_cost_per_ha,
                irrigation_cost_per_ha,
                other_cost_per_ha,
                currency,
                source_name,
                source_note,
                observed_at,
                is_default,
                is_user_override,
                is_active,
                updated_at
            FROM crop_costs
            ORDER BY crop ASC, is_user_override DESC, updated_at DESC, id DESC
            """,
            conn,
        )
    return df


def get_active_prices() -> pd.DataFrame:
    df = load_prices()
    if df.empty:
        return df
    df = df.sort_values(
        ["crop", "is_user_override", "updated_at", "id"],
        ascending=[True, False, False, False],
    )
    return df.drop_duplicates(subset=["crop"], keep="first").reset_index(drop=True)


def get_active_costs() -> pd.DataFrame:
    df = load_costs()
    if df.empty:
        return df
    df = df.sort_values(
        ["crop", "is_user_override", "updated_at", "id"],
        ascending=[True, False, False, False],
    )
    return df.drop_duplicates(subset=["crop"], keep="first").reset_index(drop=True)


def get_crop_options() -> list[str]:
    crops = set(KNOWN_CROPS)

    prices = get_active_prices()
    if not prices.empty:
        crops.update(normalize_crop_name(c) for c in prices["crop"].dropna().astype(str).tolist())

    costs = get_active_costs()
    if not costs.empty:
        crops.update(normalize_crop_name(c) for c in costs["crop"].dropna().astype(str).tolist())

    return sorted(crops)


def upsert_user_price(
    crop: str,
    price_value: float,
    price_unit: str,
    currency: str,
    market_reference: str,
    source_name: str,
    source_note: str,
    observed_at: str,
) -> None:
    crop = normalize_crop_name(crop)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO crop_prices (
                crop,
                price_value,
                price_unit,
                currency,
                market_reference,
                source_name,
                source_note,
                observed_at,
                is_default,
                is_user_override,
                is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1, 1)
            """,
            (
                crop,
                price_value,
                price_unit,
                currency,
                market_reference or None,
                source_name or None,
                source_note or None,
                observed_at or None,
            ),
        )


def upsert_user_costs(
    crop: str,
    seed_cost_per_ha: float,
    pesticide_cost_per_ha: float,
    fertilizer_cost_per_ha: float,
    irrigation_cost_per_ha: float,
    other_cost_per_ha: float,
    currency: str,
    source_name: str,
    source_note: str,
    observed_at: str,
) -> None:
    crop = normalize_crop_name(crop)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO crop_costs (
                crop,
                seed_cost_per_ha,
                pesticide_cost_per_ha,
                fertilizer_cost_per_ha,
                irrigation_cost_per_ha,
                other_cost_per_ha,
                currency,
                source_name,
                source_note,
                observed_at,
                is_default,
                is_user_override,
                is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, 1)
            """,
            (
                crop,
                seed_cost_per_ha,
                pesticide_cost_per_ha,
                fertilizer_cost_per_ha,
                irrigation_cost_per_ha,
                other_cost_per_ha,
                currency,
                source_name or None,
                source_note or None,
                observed_at or None,
            ),
        )
