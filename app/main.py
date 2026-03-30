from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.model_loader import (
    MODEL_1_CROP,
    MODEL_1_GENERAL,
    MODEL_2,
    is_model_loaded,
)
from app.schemas import (
    HealthResponse,
    PredictRequest,
    PredictResponse,
    RecommendRequest,
    RecommendResponse,
)
from app.services import (
    predict_crop_yield,
    recommend_crops_service,
)

app = FastAPI(
    title="Agritech Yield Prediction & Crop Recommendation API",
    description=(
        "API de prédiction de rendement agricole et de recommandation de cultures "
        "à partir de plusieurs modèles complémentaires."
    ),
    version="1.1.0",
)


@app.get("/")
def root():
    return {
        "message": "Bienvenue sur l'API Agritech.",
        "endpoints": {
            "health": "/health",
            "predict": "/predict",
            "recommend": "/recommend",
            "docs": "/docs",
        },
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model_1_general_loaded=is_model_loaded(MODEL_1_GENERAL),
        model_1_crop_loaded=is_model_loaded(MODEL_1_CROP),
        model_2_loaded=is_model_loaded(MODEL_2),
    )


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest) -> PredictResponse:
    try:
        return predict_crop_yield(
            crop=payload.crop,
            area=payload.area,
            parcel_area_ha=payload.parcel_area_ha,
            rainfall_mm=payload.rainfall_mm,
            temperature_celsius=payload.temperature_celsius,
            fertilizer_used=payload.fertilizer_used,
            irrigation_used=payload.irrigation_used,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne pendant la prédiction : {str(e)}",
        ) from e


@app.post("/recommend", response_model=RecommendResponse)
def recommend(payload: RecommendRequest) -> RecommendResponse:
    try:
        return recommend_crops_service(
            area=payload.area,
            parcel_area_ha=payload.parcel_area_ha,
            rainfall_mm=payload.rainfall_mm,
            temperature_celsius=payload.temperature_celsius,
            fertilizer_used=payload.fertilizer_used,
            irrigation_used=payload.irrigation_used,
            top_k=payload.top_k,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne pendant la recommandation : {str(e)}",
        ) from e
