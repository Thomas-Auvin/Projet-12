from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

ECON_DB_PATH = Path("data/reference/economics.sqlite")


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
    df = df.sort_values(["crop", "is_user_override", "updated_at", "id"], ascending=[True, False, False, False])
    return df.drop_duplicates(subset=["crop"], keep="first").reset_index(drop=True)


def get_active_costs() -> pd.DataFrame:
    df = load_costs()
    if df.empty:
        return df
    df = df.sort_values(["crop", "is_user_override", "updated_at", "id"], ascending=[True, False, False, False])
    return df.drop_duplicates(subset=["crop"], keep="first").reset_index(drop=True)


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
