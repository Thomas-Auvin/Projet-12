from pathlib import Path
import sqlite3

import pytest

from app import economics_store as store


@pytest.fixture
def temp_econ_db(tmp_path, monkeypatch) -> Path:
    db_path = tmp_path / "economics_test.sqlite"
    monkeypatch.setattr(store, "DEFAULT_ECON_DB_PATH", db_path)
    return db_path


def test_init_economics_db_creates_tables(temp_econ_db: Path) -> None:
    store.init_economics_db()

    with sqlite3.connect(temp_econ_db) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert "crop_prices" in tables
    assert "crop_costs" in tables


def test_user_price_override_is_returned_as_active(temp_econ_db: Path) -> None:
    store.init_economics_db()

    with store.get_conn() as conn:
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 1)
            """,
            (
                "Rice",
                400.0,
                "usd_per_tonne",
                "USD",
                "default market",
                "default source",
                "default note",
                "2026-03-30",
            ),
        )

    store.upsert_user_price(
        crop="Rice",
        price_value=450.0,
        price_unit="usd_per_tonne",
        currency="USD",
        market_reference="user market",
        source_name="user source",
        source_note="user override",
        observed_at="2026-04-01",
    )

    active = store.get_active_crop_price("Rice")

    assert active is not None
    assert active["crop"] == "Rice"
    assert active["price_value"] == 450.0
    assert active["price_unit"] == "usd_per_tonne"
    assert active["currency"] == "USD"
    assert active["is_user_override"] == 1
    assert active["is_active"] == 1


def test_user_costs_are_saved_and_listed(temp_econ_db: Path) -> None:
    store.init_economics_db()

    store.upsert_user_costs(
        crop="Rice",
        seed_cost_per_ha=10.0,
        pesticide_cost_per_ha=20.0,
        fertilizer_cost_per_ha=30.0,
        irrigation_cost_per_ha=40.0,
        other_cost_per_ha=5.0,
        currency="USD",
        source_name="user source",
        source_note="user costs override",
        observed_at="2026-04-01",
    )

    active = store.get_active_crop_costs("Rice")
    assert active is not None
    assert active["crop"] == "Rice"
    assert active["seed_cost_per_ha"] == 10.0
    assert active["pesticide_cost_per_ha"] == 20.0
    assert active["fertilizer_cost_per_ha"] == 30.0
    assert active["irrigation_cost_per_ha"] == 40.0
    assert active["other_cost_per_ha"] == 5.0
    assert active["is_user_override"] == 1
    assert active["is_active"] == 1

    rows = store.list_active_costs()
    rice_rows = [row for row in rows if row["crop"] == "Rice"]
    assert len(rice_rows) == 1
    assert rice_rows[0]["seed_cost_per_ha"] == 10.0


def test_list_active_prices_returns_user_override_first(temp_econ_db: Path) -> None:
    store.init_economics_db()

    with store.get_conn() as conn:
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 1)
            """,
            (
                "Maize",
                200.0,
                "usd_per_tonne",
                "USD",
                "default market",
                "default source",
                "default note",
                "2026-03-30",
            ),
        )

    store.upsert_user_price(
        crop="Maize",
        price_value=250.0,
        price_unit="usd_per_tonne",
        currency="USD",
        market_reference="user market",
        source_name="user source",
        source_note="user override",
        observed_at="2026-04-01",
    )

    rows = store.list_active_prices()
    maize_rows = [row for row in rows if row["crop"] == "Maize"]

    assert len(maize_rows) == 2
    assert maize_rows[0]["is_user_override"] == 1
    assert maize_rows[0]["price_value"] == 250.0
