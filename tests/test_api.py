from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
    assert "model_1_general_loaded" in data
    assert "model_1_crop_loaded" in data
    assert "model_2_loaded" in data


def test_predict_endpoint(monkeypatch):
    from app import main

    def fake_predict_crop_yield(**kwargs):
        return {
            "crop": "Rice",
            "predicted_yield_t_ha": 7.5,
            "error_margin_t_ha": 0.5,
            "lower_bound_t_ha": 7.0,
            "upper_bound_t_ha": 8.0,
            "predicted_yield_total_t": 75.0,
            "sale_price_per_tonne": 409.0,
            "estimated_revenue": 30675.0,
            "estimated_revenue_lower": 28630.0,
            "estimated_revenue_upper": 32720.0,
            "estimated_variable_costs": 0.0,
            "estimated_gross_margin": 30675.0,
            "source_model": "model_1_crop",
            "confidence_level": "high",
            "warning": None,
            "inputs_used": {
                "area": "India",
                "parcel_area_ha": 10.0,
                "rainfall_mm": 900.0,
                "temperature_celsius": 22.0,
                "fertilizer_used": True,
                "irrigation_used": True,
                "rainfall_source": "user_input",
                "temperature_source": "user_input",
            },
        }

    monkeypatch.setattr(main, "predict_crop_yield", fake_predict_crop_yield)

    payload = {
        "crop": "Rice",
        "area": "India",
        "parcel_area_ha": 10,
        "rainfall_mm": 900,
        "temperature_celsius": 22,
        "fertilizer_used": True,
        "irrigation_used": True,
    }

    response = client.post("/predict", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["crop"] == "Rice"
    assert data["source_model"] == "model_1_crop"
    assert data["predicted_yield_total_t"] == 75.0
    assert "estimated_gross_margin" in data


def test_recommend_endpoint(monkeypatch):
    from app import main

    def fake_recommend_crops_service(**kwargs):
        return {
            "recommendations": [
                {
                    "crop": "Soybean",
                    "predicted_yield_t_ha": 7.6,
                    "error_margin_t_ha": 0.5,
                    "lower_bound_t_ha": 7.1,
                    "upper_bound_t_ha": 8.1,
                    "predicted_yield_total_t": 76.0,
                    "sale_price_per_tonne": 455.0,
                    "estimated_revenue": 34580.0,
                    "estimated_variable_costs": 0.0,
                    "estimated_gross_margin": 34580.0,
                    "recommendation_score": 1.0,
                    "confidence_level": "high",
                    "source_model": "model_1_crop",
                    "reason": "Test reason",
                    "warning": None,
                }
            ],
            "autofill_used": False,
            "missing_economic_data_crops": [],
            "inputs_used": {
                "area": "India",
                "parcel_area_ha": 10.0,
                "rainfall_mm": 900.0,
                "temperature_celsius": 22.0,
                "fertilizer_used": True,
                "irrigation_used": True,
                "rainfall_source": "user_input",
                "temperature_source": "user_input",
            },
        }

    monkeypatch.setattr(main, "recommend_crops_service", fake_recommend_crops_service)

    payload = {
        "area": "India",
        "parcel_area_ha": 10,
        "rainfall_mm": 900,
        "temperature_celsius": 22,
        "fertilizer_used": True,
        "irrigation_used": True,
        "top_k": 5,
    }

    response = client.post("/recommend", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "recommendations" in data
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["crop"] == "Soybean"
