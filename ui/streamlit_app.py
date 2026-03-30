from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st
from economics_ui import (
    get_active_costs,
    get_active_prices,
    upsert_user_costs,
    upsert_user_price,
)

API_BASE_URL_DEFAULT = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


st.set_page_config(
    page_title="Agritech Advisor",
    page_icon="🌾",
    layout="wide",
)

st.title("🌾 Agritech Yield & Crop Advisor")
st.caption("Interface Streamlit connectée à l'API FastAPI du projet 12")


def api_get(base_url: str, path: str) -> dict:
    url = f"{base_url}{path}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(base_url: str, path: str, payload: dict) -> dict:
    url = f"{base_url}{path}"
    resp = requests.post(url, json=payload, timeout=60)
    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise RuntimeError(f"API error {resp.status_code}: {detail}")
    return resp.json()


def show_api_status(base_url: str):
    st.subheader("Statut de l'API")
    try:
        health = api_get(base_url, "/health")
        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Status", health.get("status", "unknown"))
        c2.metric("Model 1 general", str(health.get("model_1_general_loaded", False)))
        c3.metric("Model 1 crop", str(health.get("model_1_crop_loaded", False)))
        c4.metric("Model 2", str(health.get("model_2_loaded", False)))

        st.success("API accessible")
    except Exception as e:
        st.error(f"API inaccessible : {e}")


def format_currency(value):
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def format_number(value, digits=2):
    if value is None:
        return "N/A"
    return f"{value:,.{digits}f}"


def parse_optional_float(value: str):
    value = value.strip()
    if value == "":
        return None
    return float(value)


with st.sidebar:
    st.header("Configuration")
    api_base_url = st.text_input("API base URL", value=API_BASE_URL_DEFAULT)

    st.markdown("---")
    st.write("Lance l'API avant Streamlit :")
    st.code("uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")

show_api_status(api_base_url)

st.markdown("---")

st.subheader("Entrées générales")

c1, c2, c3 = st.columns(3)

with c1:
    area = st.text_input("Pays / zone (area)", value="India")
    parcel_area_ha = st.number_input(
        "Surface de la parcelle (ha)",
        min_value=0.1,
        value=10.0,
        step=0.5,
    )

with c2:
    rainfall_mm_raw = st.text_input(
        "Rainfall (mm) — laisser vide pour autoremplissage",
        value="900",
    )
    temperature_celsius_raw = st.text_input(
        "Température (°C) — laisser vide pour autoremplissage",
        value="22",
    )

with c3:
    fertilizer_used = st.checkbox("Fertilizer used", value=True)
    irrigation_used = st.checkbox("Irrigation used", value=True)

try:
    rainfall_mm = parse_optional_float(rainfall_mm_raw)
    temperature_celsius = parse_optional_float(temperature_celsius_raw)
except ValueError:
    st.error("Rainfall et température doivent être des nombres ou vides.")
    st.stop()

tab_predict, tab_recommend, tab_economics = st.tabs(
    ["🔮 Prédiction", "🏆 Recommandation", "💰 Données économiques"]
)
with tab_predict:
    st.subheader("Prédire le rendement et la marge d'une culture")

    crop = st.selectbox(
        "Culture",
        options=["Rice", "Soybean", "Wheat", "Maize", "Cotton", "Barley", "Cassava"],
        index=0,
    )

    if st.button("Lancer la prédiction", type="primary"):
        payload = {
            "crop": crop,
            "area": area if area.strip() else None,
            "parcel_area_ha": float(parcel_area_ha),
            "rainfall_mm": rainfall_mm,
            "temperature_celsius": temperature_celsius,
            "fertilizer_used": fertilizer_used,
            "irrigation_used": irrigation_used,
        }

        try:
            result = api_post(api_base_url, "/predict", payload)

            st.success("Prédiction réussie")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Yield (t/ha)", format_number(result.get("predicted_yield_t_ha")))
            m2.metric("Yield total (t)", format_number(result.get("predicted_yield_total_t")))
            m3.metric("Revenue", format_currency(result.get("estimated_revenue")))
            m4.metric("Gross margin", format_currency(result.get("estimated_gross_margin")))

            st.markdown("### Détails")
            details = pd.DataFrame(
                [
                    {"champ": "Culture", "valeur": str(result.get("crop"))},
                    {"champ": "Modèle utilisé", "valeur": str(result.get("source_model"))},
                    {"champ": "Confidence", "valeur": str(result.get("confidence_level"))},
                    {
                        "champ": "Error margin (t/ha)",
                        "valeur": format_number(result.get("error_margin_t_ha")),
                    },
                    {
                        "champ": "Lower bound (t/ha)",
                        "valeur": format_number(result.get("lower_bound_t_ha")),
                    },
                    {
                        "champ": "Upper bound (t/ha)",
                        "valeur": format_number(result.get("upper_bound_t_ha")),
                    },
                    {
                        "champ": "Sale price / tonne",
                        "valeur": format_currency(result.get("sale_price_per_tonne")),
                    },
                    {
                        "champ": "Estimated revenue lower",
                        "valeur": format_currency(result.get("estimated_revenue_lower")),
                    },
                    {
                        "champ": "Estimated revenue upper",
                        "valeur": format_currency(result.get("estimated_revenue_upper")),
                    },
                    {
                        "champ": "Estimated variable costs",
                        "valeur": format_currency(result.get("estimated_variable_costs")),
                    },
                ]
            )

            st.dataframe(details, width="stretch", hide_index=True)

            warning = result.get("warning")
            if warning:
                st.warning(warning)

            with st.expander("Entrées utilisées"):
                st.json(result.get("inputs_used", {}))

            with st.expander("Réponse brute JSON"):
                st.json(result)

        except Exception as e:
            st.error(str(e))

with tab_recommend:
    st.subheader("Recommander les cultures les plus intéressantes")

    top_k = st.slider("Nombre de recommandations", min_value=1, max_value=10, value=5)

    if st.button("Lancer la recommandation", type="primary", key="recommend_button"):
        payload = {
            "area": area if area.strip() else None,
            "parcel_area_ha": float(parcel_area_ha),
            "rainfall_mm": rainfall_mm,
            "temperature_celsius": temperature_celsius,
            "fertilizer_used": fertilizer_used,
            "irrigation_used": irrigation_used,
            "top_k": int(top_k),
        }

        try:
            result = api_post(api_base_url, "/recommend", payload)

            st.success("Recommandation réussie")

            recs = result.get("recommendations", [])
            if not recs:
                st.warning("Aucune recommandation retournée.")
            else:
                recs_df = pd.DataFrame(recs)

                ordered_cols = [
                    "crop",
                    "source_model",
                    "confidence_level",
                    "recommendation_score",
                    "predicted_yield_t_ha",
                    "predicted_yield_total_t",
                    "sale_price_per_tonne",
                    "estimated_revenue",
                    "estimated_variable_costs",
                    "estimated_gross_margin",
                    "warning",
                    "reason",
                ]
                available_cols = [c for c in ordered_cols if c in recs_df.columns]
                recs_df = recs_df[available_cols]

                st.markdown("### Top recommandations")
                st.dataframe(recs_df, width="stretch", hide_index=True)

                best = recs[0]
                st.markdown("### Recommandation principale")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Culture", best.get("crop"))
                c2.metric("Gross margin", format_currency(best.get("estimated_gross_margin")))
                c3.metric("Revenue", format_currency(best.get("estimated_revenue")))
                c4.metric("Yield total (t)", format_number(best.get("predicted_yield_total_t")))

                if best.get("warning"):
                    st.warning(best["warning"])

                st.info(best.get("reason", ""))

            missing_economic = result.get("missing_economic_data_crops", [])
            if missing_economic:
                st.markdown("### Cultures sans données économiques actives")
                st.warning(", ".join(missing_economic))

            with st.expander("Entrées utilisées"):
                st.json(result.get("inputs_used", {}))

            with st.expander("Réponse brute JSON"):
                st.json(result)

        except Exception as e:
            st.error(str(e))

with tab_economics:
    st.subheader("Données économiques modifiables")

    st.markdown("### Prix actifs par culture")
    active_prices = get_active_prices()
    if active_prices.empty:
        st.warning("Aucun prix trouvé dans la base.")
    else:
        st.dataframe(active_prices, width="stretch", hide_index=True)

    st.markdown("### Coûts actifs par culture")
    active_costs = get_active_costs()
    if active_costs.empty:
        st.warning("Aucun coût trouvé dans la base.")
    else:
        st.dataframe(active_costs, width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown("## Modifier / ajouter un prix")

    with st.form("price_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            crop_price = st.selectbox(
                "Culture (prix)",
                ["Maize", "Rice", "Soybean", "Wheat", "Cotton", "Barley", "Cassava"],
                key="crop_price",
            )
            price_value = st.number_input("Prix", min_value=0.0, value=100.0, step=1.0)

        with c2:
            price_unit = st.selectbox(
                "Unité",
                ["usd_per_tonne", "usd_per_kg"],
                index=0,
            )
            currency = st.text_input("Devise", value="USD")

        with c3:
            observed_at = st.text_input("Date d'observation", value="2026-03-30")
            market_reference = st.text_input("Marché / référence", value="User override")

        source_name = st.text_input("Source", value="User input")
        source_note = st.text_area("Note source", value="Manual update from Streamlit")

        submitted_price = st.form_submit_button("Enregistrer le prix")

        if submitted_price:
            try:
                upsert_user_price(
                    crop=crop_price,
                    price_value=float(price_value),
                    price_unit=price_unit,
                    currency=currency.strip() or "USD",
                    market_reference=market_reference.strip(),
                    source_name=source_name.strip(),
                    source_note=source_note.strip(),
                    observed_at=observed_at.strip(),
                )
                st.success("Prix enregistré.")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur enregistrement prix : {e}")

    st.markdown("---")
    st.markdown("## Modifier / ajouter des coûts par hectare")

    with st.form("cost_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            crop_cost = st.selectbox(
                "Culture (coûts)",
                ["Maize", "Rice", "Soybean", "Wheat", "Cotton", "Barley", "Cassava"],
                key="crop_cost",
            )
            seed_cost = st.number_input("Semences / ha", min_value=0.0, value=0.0, step=1.0)

        with c2:
            pesticide_cost = st.number_input("Pesticides / ha", min_value=0.0, value=0.0, step=1.0)
            fertilizer_cost = st.number_input(
                "Fertilisants / ha", min_value=0.0, value=0.0, step=1.0
            )

        with c3:
            irrigation_cost = st.number_input("Irrigation / ha", min_value=0.0, value=0.0, step=1.0)
            other_cost = st.number_input("Autres coûts / ha", min_value=0.0, value=0.0, step=1.0)

        cost_currency = st.text_input("Devise coûts", value="USD")
        cost_observed_at = st.text_input("Date coûts", value="2026-03-30")
        cost_source_name = st.text_input("Source coûts", value="User input")
        cost_source_note = st.text_area("Note coûts", value="Manual update from Streamlit")

        submitted_cost = st.form_submit_button("Enregistrer les coûts")

        if submitted_cost:
            try:
                upsert_user_costs(
                    crop=crop_cost,
                    seed_cost_per_ha=float(seed_cost),
                    pesticide_cost_per_ha=float(pesticide_cost),
                    fertilizer_cost_per_ha=float(fertilizer_cost),
                    irrigation_cost_per_ha=float(irrigation_cost),
                    other_cost_per_ha=float(other_cost),
                    currency=cost_currency.strip() or "USD",
                    source_name=cost_source_name.strip(),
                    source_note=cost_source_note.strip(),
                    observed_at=cost_observed_at.strip(),
                )
                st.success("Coûts enregistrés.")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur enregistrement coûts : {e}")
