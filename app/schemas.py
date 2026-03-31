from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# =========================
# Requêtes
# =========================


class PredictRequest(BaseModel):
    crop: str = Field(..., description="Culture demandée, ex: Wheat, Rice, Maize")
    area: str | None = Field(
        default=None,
        description="Pays / zone géographique utilisé pour l'autoremplissage éventuel",
    )
    parcel_area_ha: float = Field(
        ...,
        gt=0,
        description="Surface de la parcelle en hectares",
    )
    rainfall_mm: float | None = Field(
        default=None,
        ge=0,
        description="Pluie attendue en mm",
    )
    temperature_celsius: float | None = Field(
        default=None,
        description="Température attendue en °C",
    )
    fertilizer_used: bool | None = Field(
        default=None,
        description="Utilisation de fertilisant",
    )
    irrigation_used: bool | None = Field(
        default=None,
        description="Utilisation d'irrigation",
    )

    @field_validator("crop")
    @classmethod
    def validate_crop(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("crop ne peut pas être vide.")
        return value

    @field_validator("area")
    @classmethod
    def validate_area(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None


class RecommendRequest(BaseModel):
    area: str | None = Field(
        default=None,
        description="Pays / zone géographique utilisé pour l'autoremplissage éventuel",
    )
    parcel_area_ha: float = Field(
        ...,
        gt=0,
        description="Surface de la parcelle en hectares",
    )
    rainfall_mm: float | None = Field(
        default=None,
        ge=0,
        description="Pluie attendue en mm",
    )
    temperature_celsius: float | None = Field(
        default=None,
        description="Température attendue en °C",
    )
    fertilizer_used: bool | None = Field(
        default=None,
        description="Utilisation de fertilisant",
    )
    irrigation_used: bool | None = Field(
        default=None,
        description="Utilisation d'irrigation",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Nombre de cultures recommandées à retourner",
    )

    @field_validator("area")
    @classmethod
    def validate_area(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None


# =========================
# Sous-objets de réponse
# =========================


class InputsUsed(BaseModel):
    area: str | None = None
    parcel_area_ha: float | None = None
    rainfall_mm: float | None = None
    temperature_celsius: float | None = None
    fertilizer_used: bool | None = None
    irrigation_used: bool | None = None

    rainfall_source: Literal["user_input", "country_mean", "not_provided"] = "not_provided"
    temperature_source: Literal["user_input", "country_mean", "not_provided"] = "not_provided"


class PredictResponse(BaseModel):
    crop: str
    predicted_yield_t_ha: float
    error_margin_t_ha: float
    lower_bound_t_ha: float
    upper_bound_t_ha: float

    predicted_yield_total_t: float | None = None
    sale_price_per_tonne: float | None = None
    estimated_revenue: float | None = None
    estimated_revenue_lower: float | None = None
    estimated_revenue_upper: float | None = None
    estimated_variable_costs: float | None = None
    estimated_gross_margin: float | None = None

    source_model: Literal["model_1_crop", "model_2_recommendation"]
    confidence_level: Literal["high", "medium", "low"]

    warning: str | None = None
    inputs_used: InputsUsed

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.lower_bound_t_ha > self.upper_bound_t_ha:
            raise ValueError("lower_bound_t_ha doit être inférieur ou égal à upper_bound_t_ha.")
        return self


class RecommendationItem(BaseModel):
    crop: str
    predicted_yield_t_ha: float
    error_margin_t_ha: float
    lower_bound_t_ha: float
    upper_bound_t_ha: float

    predicted_yield_total_t: float | None = None
    sale_price_per_tonne: float | None = None
    estimated_revenue: float | None = None
    estimated_variable_costs: float | None = None
    estimated_gross_margin: float | None = None

    recommendation_score: float = Field(..., ge=0, le=1)
    confidence_level: Literal["high", "medium", "low"]
    source_model: Literal["model_1_crop", "model_2_recommendation"]
    reason: str
    warning: str | None = None

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.lower_bound_t_ha > self.upper_bound_t_ha:
            raise ValueError("lower_bound_t_ha doit être inférieur ou égal à upper_bound_t_ha.")
        return self


class RecommendResponse(BaseModel):
    recommendations: list[RecommendationItem]
    autofill_used: bool
    missing_economic_data_crops: list[str] = Field(default_factory=list)
    inputs_used: InputsUsed


# =========================
# Réponse santé API
# =========================


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model_1_general_loaded: bool
    model_1_crop_loaded: bool
    model_2_loaded: bool
    crop_profile_loaded: bool
    crop_profile_crops: list[str]
    recommendable_crops_model_1: list[str]
