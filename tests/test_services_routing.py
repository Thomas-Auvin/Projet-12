import pytest

from app import services


def _fake_economics_for_crop(crop: str):
    mapping = {
        "Rice": {
            "sale_price_per_tonne": 400.0,
            "predicted_yield_total_t": 80.0,
            "estimated_revenue": 32000.0,
            "estimated_revenue_lower": 30000.0,
            "estimated_revenue_upper": 34000.0,
            "estimated_variable_costs": 1000.0,
            "estimated_gross_margin": 31000.0,
        },
        "Wheat": {
            "sale_price_per_tonne": 250.0,
            "predicted_yield_total_t": 60.0,
            "estimated_revenue": 15000.0,
            "estimated_revenue_lower": 14000.0,
            "estimated_revenue_upper": 16000.0,
            "estimated_variable_costs": 1500.0,
            "estimated_gross_margin": 13500.0,
        },
        "Cassava": {
            "sale_price_per_tonne": 300.0,
            "predicted_yield_total_t": 90.0,
            "estimated_revenue": 27000.0,
            "estimated_revenue_lower": 25000.0,
            "estimated_revenue_upper": 29000.0,
            "estimated_variable_costs": 2000.0,
            "estimated_gross_margin": 25000.0,
        },
    }
    return mapping[crop]


def test_predict_crop_yield_routes_to_model_1_crop(monkeypatch):
    monkeypatch.setattr(
        services,
        "autofill_climate",
        lambda area, rainfall_mm, temperature_celsius: (
            rainfall_mm,
            temperature_celsius,
            "user_input",
            "user_input",
            False,
        ),
    )
    monkeypatch.setattr(services, "get_supported_crops_model_1", lambda: ["Rice", "Wheat"])
    monkeypatch.setattr(services, "get_recommendable_crops_model_1", lambda: ["Rice"])
    monkeypatch.setattr(services, "get_supported_crops_model_2", lambda: ["Cassava"])
    monkeypatch.setattr(services, "predict_with_model_1_crop", lambda **kwargs: 7.5)
    monkeypatch.setattr(services, "get_error_margin_model_1_crop", lambda: 0.5)
    monkeypatch.setattr(services, "get_crop_support_count_model_1", lambda crop: 1500)
    monkeypatch.setattr(
        services,
        "compute_economic_outputs",
        lambda **kwargs: _fake_economics_for_crop("Rice"),
    )

    result = services.predict_crop_yield(
        crop="Rice",
        area="India",
        parcel_area_ha=10.0,
        rainfall_mm=900.0,
        temperature_celsius=22.0,
        fertilizer_used=True,
        irrigation_used=True,
    )

    assert result.crop == "Rice"
    assert result.source_model == "model_1_crop"
    assert result.confidence_level == "high"
    assert result.predicted_yield_t_ha == 7.5
    assert result.lower_bound_t_ha == 7.0
    assert result.upper_bound_t_ha == 8.0
    assert result.estimated_gross_margin == 31000.0
    assert result.warning is None


def test_predict_crop_yield_routes_to_model_1_general(monkeypatch):
    monkeypatch.setattr(
        services,
        "autofill_climate",
        lambda area, rainfall_mm, temperature_celsius: (
            rainfall_mm,
            temperature_celsius,
            "user_input",
            "user_input",
            False,
        ),
    )
    monkeypatch.setattr(services, "get_supported_crops_model_1", lambda: ["Rice", "Wheat"])
    monkeypatch.setattr(services, "get_recommendable_crops_model_1", lambda: ["Rice"])
    monkeypatch.setattr(services, "get_supported_crops_model_2", lambda: [])
    monkeypatch.setattr(services, "predict_with_model_1_general", lambda **kwargs: 6.0)
    monkeypatch.setattr(services, "get_error_margin_model_1_crop", lambda: 0.5)
    monkeypatch.setattr(services, "get_crop_support_count_model_1", lambda crop: 100)
    monkeypatch.setattr(
        services,
        "compute_economic_outputs",
        lambda **kwargs: _fake_economics_for_crop("Wheat"),
    )

    result = services.predict_crop_yield(
        crop="Wheat",
        area="India",
        parcel_area_ha=10.0,
        rainfall_mm=900.0,
        temperature_celsius=22.0,
        fertilizer_used=True,
        irrigation_used=False,
    )

    assert result.crop == "Wheat"
    assert result.source_model == "model_1_general"
    assert result.confidence_level == "medium"
    assert result.predicted_yield_t_ha == 6.0
    assert result.warning is not None
    assert "modèle général du dataset principal" in result.warning
    assert "peu représentée" in result.warning


def test_predict_crop_yield_routes_to_model_2(monkeypatch):
    monkeypatch.setattr(
        services,
        "autofill_climate",
        lambda area, rainfall_mm, temperature_celsius: (
            rainfall_mm,
            temperature_celsius,
            "user_input",
            "user_input",
            False,
        ),
    )
    monkeypatch.setattr(services, "get_supported_crops_model_1", lambda: ["Rice"])
    monkeypatch.setattr(services, "get_recommendable_crops_model_1", lambda: ["Rice"])
    monkeypatch.setattr(services, "get_supported_crops_model_2", lambda: ["Rice", "Cassava"])
    monkeypatch.setattr(services, "is_area_supported_for_model_2", lambda area: True)
    monkeypatch.setattr(services, "predict_with_model_2", lambda **kwargs: 9.0)
    monkeypatch.setattr(services, "get_error_margin_model_2", lambda: 1.0)
    monkeypatch.setattr(services, "get_crop_support_count_model_2", lambda crop: 1200)
    monkeypatch.setattr(
        services,
        "compute_economic_outputs",
        lambda **kwargs: _fake_economics_for_crop("Cassava"),
    )

    result = services.predict_crop_yield(
        crop="Cassava",
        area="India",
        parcel_area_ha=10.0,
        rainfall_mm=900.0,
        temperature_celsius=22.0,
        fertilizer_used=None,
        irrigation_used=None,
    )

    assert result.crop == "Cassava"
    assert result.source_model == "model_2_recommendation"
    assert result.confidence_level == "medium"
    assert result.predicted_yield_t_ha == 9.0
    assert result.warning is not None
    assert "modèle secondaire" in result.warning


def test_predict_crop_yield_raises_when_climate_missing_and_no_autofill(monkeypatch):
    monkeypatch.setattr(
        services,
        "autofill_climate",
        lambda area, rainfall_mm, temperature_celsius: (
            None,
            None,
            "not_provided",
            "not_provided",
            False,
        ),
    )

    with pytest.raises(ValueError, match="Impossible de prédire sans rainfall_mm et temperature_celsius"):
        services.predict_crop_yield(
            crop="Rice",
            area="India",
            parcel_area_ha=10.0,
            rainfall_mm=None,
            temperature_celsius=None,
            fertilizer_used=True,
            irrigation_used=True,
        )


def test_recommend_crops_service_returns_tiered_recommendations(monkeypatch):
    monkeypatch.setattr(
        services,
        "autofill_climate",
        lambda area, rainfall_mm, temperature_celsius: (
            rainfall_mm,
            temperature_celsius,
            "user_input",
            "user_input",
            False,
        ),
    )

    monkeypatch.setattr(services, "get_supported_crops_model_1", lambda: ["Rice", "Wheat"])
    monkeypatch.setattr(services, "get_recommendable_crops_model_1", lambda: ["Rice"])
    monkeypatch.setattr(services, "get_supported_crops_model_2", lambda: ["Rice", "Cassava"])
    monkeypatch.setattr(services, "is_area_supported_for_model_2", lambda area: True)

    monkeypatch.setattr(
        services,
        "predict_with_model_1_crop",
        lambda **kwargs: 8.0 if kwargs["crop"] == "Rice" else 0.0,
    )
    monkeypatch.setattr(
        services,
        "predict_with_model_1_general",
        lambda **kwargs: 6.0,
    )
    monkeypatch.setattr(
        services,
        "predict_with_model_2",
        lambda **kwargs: 7.9 if kwargs["crop"] == "Rice" else 9.0,
    )

    monkeypatch.setattr(services, "get_error_margin_model_1_crop", lambda: 0.5)
    monkeypatch.setattr(services, "get_error_margin_model_2", lambda: 1.0)

    monkeypatch.setattr(
        services,
        "get_crop_support_count_model_1",
        lambda crop: 1200 if crop == "Rice" else 100,
    )
    monkeypatch.setattr(
        services,
        "get_crop_support_count_model_2",
        lambda crop: 500,
    )

    def fake_compute_economic_outputs(crop, **kwargs):
        return _fake_economics_for_crop(crop)

    monkeypatch.setattr(services, "compute_economic_outputs", fake_compute_economic_outputs)

    result = services.recommend_crops_service(
        area="India",
        parcel_area_ha=10.0,
        rainfall_mm=900.0,
        temperature_celsius=22.0,
        fertilizer_used=True,
        irrigation_used=True,
        top_k=3,
    )

    assert len(result.recommendations) == 3

    crops = [item.crop for item in result.recommendations]
    assert crops == ["Rice", "Wheat", "Cassava"]

    assert result.recommendations[0].source_model == "model_1_crop"
    assert result.recommendations[1].source_model == "model_1_general"
    assert result.recommendations[2].source_model == "model_2_recommendation"

    assert result.recommendations[0].recommendation_score >= result.recommendations[1].recommendation_score
    assert result.inputs_used.rainfall_source == "user_input"
    assert result.missing_economic_data_crops == []


def test_recommend_crops_service_tracks_missing_economic_data(monkeypatch):
    monkeypatch.setattr(
        services,
        "autofill_climate",
        lambda area, rainfall_mm, temperature_celsius: (
            rainfall_mm,
            temperature_celsius,
            "user_input",
            "user_input",
            False,
        ),
    )

    monkeypatch.setattr(services, "get_supported_crops_model_1", lambda: ["Rice", "Wheat"])
    monkeypatch.setattr(services, "get_recommendable_crops_model_1", lambda: ["Rice"])
    monkeypatch.setattr(services, "get_supported_crops_model_2", lambda: [])
    monkeypatch.setattr(services, "is_area_supported_for_model_2", lambda area: False)

    monkeypatch.setattr(services, "predict_with_model_1_crop", lambda **kwargs: 8.0)
    monkeypatch.setattr(services, "predict_with_model_1_general", lambda **kwargs: 6.0)
    monkeypatch.setattr(services, "get_error_margin_model_1_crop", lambda: 0.5)
    monkeypatch.setattr(services, "get_crop_support_count_model_1", lambda crop: 1000)

    def fake_compute_economic_outputs(crop, **kwargs):
        if crop == "Wheat":
            return {
                "sale_price_per_tonne": None,
                "predicted_yield_total_t": 60.0,
                "estimated_revenue": None,
                "estimated_revenue_lower": None,
                "estimated_revenue_upper": None,
                "estimated_variable_costs": None,
                "estimated_gross_margin": None,
            }
        return _fake_economics_for_crop("Rice")

    monkeypatch.setattr(services, "compute_economic_outputs", fake_compute_economic_outputs)

    result = services.recommend_crops_service(
        area="India",
        parcel_area_ha=10.0,
        rainfall_mm=900.0,
        temperature_celsius=22.0,
        fertilizer_used=True,
        irrigation_used=True,
        top_k=5,
    )

    assert len(result.recommendations) == 1
    assert result.recommendations[0].crop == "Rice"
    assert result.missing_economic_data_crops == ["Wheat"]


def test_recommend_crops_service_raises_when_no_candidate_is_usable(monkeypatch):
    monkeypatch.setattr(
        services,
        "autofill_climate",
        lambda area, rainfall_mm, temperature_celsius: (
            rainfall_mm,
            temperature_celsius,
            "user_input",
            "user_input",
            False,
        ),
    )

    monkeypatch.setattr(services, "get_supported_crops_model_1", lambda: ["Rice"])
    monkeypatch.setattr(services, "get_recommendable_crops_model_1", lambda: ["Rice"])
    monkeypatch.setattr(services, "get_supported_crops_model_2", lambda: [])
    monkeypatch.setattr(services, "is_area_supported_for_model_2", lambda area: False)

    monkeypatch.setattr(services, "predict_with_model_1_crop", lambda **kwargs: 8.0)
    monkeypatch.setattr(services, "get_error_margin_model_1_crop", lambda: 0.5)
    monkeypatch.setattr(services, "get_crop_support_count_model_1", lambda crop: 1000)

    monkeypatch.setattr(
        services,
        "compute_economic_outputs",
        lambda **kwargs: {
            "sale_price_per_tonne": None,
            "predicted_yield_total_t": 80.0,
            "estimated_revenue": None,
            "estimated_revenue_lower": None,
            "estimated_revenue_upper": None,
            "estimated_variable_costs": None,
            "estimated_gross_margin": None,
        },
    )

    with pytest.raises(ValueError, match="Aucune recommandation n'a pu être produite"):
        services.recommend_crops_service(
            area="India",
            parcel_area_ha=10.0,
            rainfall_mm=900.0,
            temperature_celsius=22.0,
            fertilizer_used=True,
            irrigation_used=True,
            top_k=5,
        )
