import pandas as pd
import pytest

from app import services


def test_normalize_crop_name_and_bool_to_int():
    assert services.normalize_crop_name(" rice, paddy ") == "Rice"
    assert services.normalize_crop_name("soybeans") == "Soybean"
    assert services.normalize_crop_name("cassava") == "Cassava"
    assert services.normalize_crop_name("unknown crop") == "Unknown Crop"

    assert services.bool_to_int(True) == 1
    assert services.bool_to_int(False) == 0
    assert services.bool_to_int(None) == 0


def test_get_area_climate_reference_from_direct(monkeypatch):
    monkeypatch.setattr(
        services,
        "MODEL_2_META",
        {
            "area_climate_reference": {
                "India": {"rainfall_mm": 900.0, "temperature_celsius": 22.0}
            }
        },
    )

    ref = services.get_area_climate_reference()

    assert ref["India"]["rainfall_mm"] == 900.0
    assert ref["India"]["temperature_celsius"] == 22.0


def test_get_area_climate_reference_from_profiles(monkeypatch):
    monkeypatch.setattr(
        services,
        "MODEL_2_META",
        {
            "area_profiles": [
                {
                    "Area": "India",
                    "average_rain_fall_mm_per_year": 900.0,
                    "avg_temp": 22.0,
                },
                {
                    "Area": "Brazil",
                    "average_rain_fall_mm_per_year": 1200.0,
                    "avg_temp": 25.0,
                },
            ]
        },
    )

    ref = services.get_area_climate_reference()

    assert ref["India"]["rainfall_mm"] == 900.0
    assert ref["Brazil"]["temperature_celsius"] == 25.0


def test_autofill_climate_without_area():
    rainfall, temperature, rainfall_source, temperature_source, autofill_used = (
        services.autofill_climate(
            area=None,
            rainfall_mm=800.0,
            temperature_celsius=None,
        )
    )

    assert rainfall == 800.0
    assert temperature is None
    assert rainfall_source == "user_input"
    assert temperature_source == "not_provided"
    assert autofill_used is False


def test_autofill_climate_with_reference(monkeypatch):
    monkeypatch.setattr(
        services,
        "AREA_CLIMATE_REFERENCE",
        {
            "India": {"rainfall_mm": 900.0, "temperature_celsius": 22.0},
        },
    )

    rainfall, temperature, rainfall_source, temperature_source, autofill_used = (
        services.autofill_climate(
            area="India",
            rainfall_mm=None,
            temperature_celsius=None,
        )
    )

    assert rainfall == 900.0
    assert temperature == 22.0
    assert rainfall_source == "country_mean"
    assert temperature_source == "country_mean"
    assert autofill_used is True


def test_build_confidence_level_and_warning_message():
    assert services.build_confidence_level("model_1_crop", 1500, False) == "high"
    assert services.build_confidence_level("model_1_crop", 300, False) == "medium"
    assert services.build_confidence_level("model_1_crop", 50, False) == "low"

    assert services.build_confidence_level("model_1_general", 9999, False) == "medium"
    assert services.build_confidence_level("model_1_general", 9999, True) == "low"

    assert services.build_confidence_level("model_2_recommendation", 1500, False) == "medium"
    assert services.build_confidence_level("model_2_recommendation", 50, False) == "low"

    warning = services.build_warning_message(
        source_model="model_1_general",
        crop_support_count=100,
        autofill_used=True,
    )
    assert warning is not None
    assert "modèle général" in warning
    assert "peu représentée" in warning
    assert "auto-remplies" in warning

    no_warning = services.build_warning_message(
        source_model="model_1_crop",
        crop_support_count=1500,
        autofill_used=False,
    )
    assert no_warning is None


def test_merge_warnings_deduplicates_messages():
    message = services.merge_warnings(
        "Avertissement 1",
        "Avertissement 1",
        "Avertissement 2",
        None,
        "   ",
    )

    assert message == "Avertissement 1 Avertissement 2"
    assert services.merge_warnings(None, " ", None) is None


def test_get_crop_profile_reference_and_build_model_1_crop_features(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "Crop": "Rice",
                "ext_mean_temp_by_crop": 21.0,
                "ext_mean_rainfall_by_crop": 850.0,
                "ext_mean_pesticides_by_crop": 12.0,
                "ext_n_obs_by_crop": 100.0,
            }
        ]
    )

    monkeypatch.setattr(services, "get_crop_profile_df", lambda: df)

    ref = services.get_crop_profile_reference()
    assert "Rice" in ref
    assert ref["Rice"]["ext_mean_temp_by_crop"] == 21.0

    monkeypatch.setattr(services, "CROP_PROFILE_REFERENCE", ref)
    monkeypatch.setattr(
        services,
        "MODEL_1_CROP_META",
        {
            "feature_names": [
                "Crop",
                "Rainfall_mm",
                "Temperature_Celsius",
                "Fertilizer_Used",
                "Irrigation_Used",
                "ext_mean_temp_by_crop",
                "ext_mean_rainfall_by_crop",
                "ext_mean_pesticides_by_crop",
                "ext_n_obs_by_crop",
                "rainfall_gap_vs_crop_profile",
                "temp_gap_vs_crop_profile",
            ]
        },
    )

    row = services.build_model_1_crop_features(
        crop="Rice",
        rainfall_mm=900.0,
        temperature_celsius=22.0,
        fertilizer_used=True,
        irrigation_used=False,
    )

    assert list(row.columns) == services.MODEL_1_CROP_META["feature_names"]
    assert row.loc[0, "Crop"] == "Rice"
    assert row.loc[0, "Fertilizer_Used"] == 1
    assert row.loc[0, "Irrigation_Used"] == 0
    assert row.loc[0, "rainfall_gap_vs_crop_profile"] == 50.0
    assert row.loc[0, "temp_gap_vs_crop_profile"] == 1.0


def test_build_model_1_crop_features_raises_when_profile_missing(monkeypatch):
    monkeypatch.setattr(services, "CROP_PROFILE_REFERENCE", {})
    monkeypatch.setattr(services, "MODEL_1_CROP_META", None)

    with pytest.raises(ValueError, match="Aucun profil enrichi disponible"):
        services.build_model_1_crop_features(
            crop="Rice",
            rainfall_mm=900.0,
            temperature_celsius=22.0,
            fertilizer_used=True,
            irrigation_used=True,
        )


def test_build_bounds_and_consistency_adjustment():
    lower, upper = services.build_bounds(predicted=0.2, error_margin=0.5)
    assert lower == 0.0
    assert upper == 0.7

    assert services.compute_consistency_adjustment(10.0, None) == 1.0
    assert services.compute_consistency_adjustment(10.0, 10.5) == 1.04
    assert services.compute_consistency_adjustment(10.0, 11.5) == 1.02
    assert services.compute_consistency_adjustment(10.0, 13.0) == 1.00
    assert services.compute_consistency_adjustment(10.0, 14.5) == 0.96
    assert services.compute_consistency_adjustment(10.0, 20.0) == 0.90


def test_normalize_recommendation_scores():
    items = [
        {"crop": "Rice", "_raw_score": 100.0},
        {"crop": "Wheat", "_raw_score": 200.0},
        {"crop": "Cassava", "_raw_score": 300.0},
    ]
    services.normalize_recommendation_scores(items)

    assert items[0]["recommendation_score"] == 0.0
    assert items[1]["recommendation_score"] == 0.5
    assert items[2]["recommendation_score"] == 1.0

    equal_items = [
        {"crop": "Rice", "_raw_score": 10.0},
        {"crop": "Wheat", "_raw_score": 10.0},
    ]
    services.normalize_recommendation_scores(equal_items)
    assert equal_items[0]["recommendation_score"] == 1.0
    assert equal_items[1]["recommendation_score"] == 1.0


def test_reason_builders():
    reason_primary_confirmed = services.build_reason_for_primary_recommendation(
        crop="Rice",
        secondary_used=True,
        consistency_adjustment=1.04,
    )
    assert "modèle secondaire confirme" in reason_primary_confirmed

    reason_primary_prudent = services.build_reason_for_primary_recommendation(
        crop="Rice",
        secondary_used=True,
        consistency_adjustment=0.90,
    )
    assert "plus divergent" in reason_primary_prudent

    reason_general = services.build_reason_for_general_recommendation("Wheat")
    assert "modèle général principal" in reason_general

    reason_secondary = services.build_reason_for_secondary_recommendation("Cassava")
    assert "modèle secondaire" in reason_secondary


def test_convert_price_to_usd_per_tonne():
    assert (
        services.convert_price_to_usd_per_tonne(
            {"price_value": 400.0, "price_unit": "usd_per_tonne"}
        )
        == 400.0
    )
    assert (
        services.convert_price_to_usd_per_tonne(
            {"price_value": 1.2, "price_unit": "usd_per_kg"}
        )
        == 1200.0
    )

    with pytest.raises(ValueError, match="Unsupported price unit"):
        services.convert_price_to_usd_per_tonne(
            {"price_value": 5.0, "price_unit": "eur_per_tonne"}
        )


def test_compute_economic_outputs_without_price(monkeypatch):
    monkeypatch.setattr(services, "get_active_crop_price", lambda crop: None)
    monkeypatch.setattr(services, "get_active_crop_costs", lambda crop: None)

    out = services.compute_economic_outputs(
        crop="Rice",
        parcel_area_ha=10.0,
        predicted_yield_t_ha=7.5,
        lower_bound_t_ha=7.0,
        upper_bound_t_ha=8.0,
    )

    assert out["sale_price_per_tonne"] is None
    assert out["predicted_yield_total_t"] == 75.0
    assert out["estimated_revenue"] is None
    assert out["estimated_gross_margin"] is None


def test_compute_economic_outputs_with_price_and_costs(monkeypatch):
    monkeypatch.setattr(
        services,
        "get_active_crop_price",
        lambda crop: {"price_value": 400.0, "price_unit": "usd_per_tonne"},
    )
    monkeypatch.setattr(
        services,
        "get_active_crop_costs",
        lambda crop: {
            "seed_cost_per_ha": 10.0,
            "pesticide_cost_per_ha": 20.0,
            "fertilizer_cost_per_ha": 30.0,
            "irrigation_cost_per_ha": 40.0,
            "other_cost_per_ha": 5.0,
        },
    )

    out = services.compute_economic_outputs(
        crop="Rice",
        parcel_area_ha=10.0,
        predicted_yield_t_ha=7.5,
        lower_bound_t_ha=7.0,
        upper_bound_t_ha=8.0,
    )

    assert out["sale_price_per_tonne"] == 400.0
    assert out["predicted_yield_total_t"] == 75.0
    assert out["estimated_revenue"] == 30000.0
    assert out["estimated_revenue_lower"] == 28000.0
    assert out["estimated_revenue_upper"] == 32000.0
    assert out["estimated_variable_costs"] == 1050.0
    assert out["estimated_gross_margin"] == 28950.0
