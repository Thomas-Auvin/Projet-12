from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_ECON_DB_PATH = Path(os.getenv("P12_ECON_DB_PATH", "data/reference/economics.sqlite"))


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


def get_econ_db_path() -> Path:
    path = DEFAULT_ECON_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(get_econ_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_economics_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crop_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop TEXT NOT NULL,
                price_value REAL NOT NULL,
                price_unit TEXT NOT NULL DEFAULT 'usd_per_tonne',
                currency TEXT NOT NULL DEFAULT 'USD',
                market_reference TEXT,
                source_name TEXT,
                source_note TEXT,
                observed_at TEXT,
                is_default INTEGER NOT NULL DEFAULT 1,
                is_user_override INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crop_costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop TEXT NOT NULL,
                seed_cost_per_ha REAL NOT NULL DEFAULT 0,
                pesticide_cost_per_ha REAL NOT NULL DEFAULT 0,
                fertilizer_cost_per_ha REAL NOT NULL DEFAULT 0,
                irrigation_cost_per_ha REAL NOT NULL DEFAULT 0,
                other_cost_per_ha REAL NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'USD',
                source_name TEXT,
                source_note TEXT,
                observed_at TEXT,
                is_default INTEGER NOT NULL DEFAULT 1,
                is_user_override INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def _fetchone_dict(query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def get_active_crop_price(crop: str) -> dict[str, Any] | None:
    return _fetchone_dict(
        """
        SELECT *
        FROM crop_prices
        WHERE lower(crop) = lower(?)
          AND is_active = 1
        ORDER BY is_user_override DESC, updated_at DESC, id DESC
        LIMIT 1
        """,
        (crop,),
    )


def get_active_crop_costs(crop: str) -> dict[str, Any] | None:
    return _fetchone_dict(
        """
        SELECT *
        FROM crop_costs
        WHERE lower(crop) = lower(?)
          AND is_active = 1
        ORDER BY is_user_override DESC, updated_at DESC, id DESC
        LIMIT 1
        """,
        (crop,),
    )


def list_active_prices() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM crop_prices
            WHERE is_active = 1
            ORDER BY crop ASC, is_user_override DESC, updated_at DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def list_active_costs() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM crop_costs
            WHERE is_active = 1
            ORDER BY crop ASC, is_user_override DESC, updated_at DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_user_price(
    crop: str,
    price_value: float,
    price_unit: str = "usd_per_tonne",
    currency: str = "USD",
    market_reference: str | None = None,
    source_name: str | None = None,
    source_note: str | None = None,
    observed_at: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO crop_prices (
                crop, price_value, price_unit, currency,
                market_reference, source_name, source_note, observed_at,
                is_default, is_user_override, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1, 1)
            """,
            (
                crop,
                price_value,
                price_unit,
                currency,
                market_reference,
                source_name,
                source_note,
                observed_at,
            ),
        )


def upsert_user_costs(
    crop: str,
    seed_cost_per_ha: float = 0.0,
    pesticide_cost_per_ha: float = 0.0,
    fertilizer_cost_per_ha: float = 0.0,
    irrigation_cost_per_ha: float = 0.0,
    other_cost_per_ha: float = 0.0,
    currency: str = "USD",
    source_name: str | None = None,
    source_note: str | None = None,
    observed_at: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO crop_costs (
                crop, seed_cost_per_ha, pesticide_cost_per_ha,
                fertilizer_cost_per_ha, irrigation_cost_per_ha,
                other_cost_per_ha, currency, source_name, source_note,
                observed_at, is_default, is_user_override, is_active
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
                source_name,
                source_note,
                observed_at,
            ),
        )
