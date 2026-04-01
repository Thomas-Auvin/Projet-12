from __future__ import annotations

from typing import Any

import pandas as pd

from app.economics_store import get_active_crop_costs, get_active_crop_price
from app.model_loader import (
    MODEL_1_CROP,
    MODEL_1_CROP_META,
    MODEL_1_GENERAL,
    MODEL_2,
    MODEL_2_META,
    get_crop_profile_df,
    get_error_margin_model_1_crop,
    get_error_margin_model_2,
    get_supported_areas_model_2,
    get_supported_crops_model_1,
    get_supported_crops_model_2,
)
from app.schemas import InputsUsed, PredictResponse, RecommendationItem, RecommendResponse

# =========================================================
# Helpers de normalisation
# =========================================================


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
    }

    return aliases.get(crop, crop.title())


def normalize_area_name(area: str) -> str:
    return area.strip()


def bool_to_int(value: bool | None) -> int:
    return int(bool(value))


# =========================================================
# Référentiel géographique pour autofill
# =========================================================


def get_area_climate_reference() -> dict[str, dict[str, float]]:
    if not MODEL_2_META:
        return {}

    direct = MODEL_2_META.get("area_climate_reference")
    if isinstance(direct, dict):
        return direct

    profiles = MODEL_2_META.get("area_profiles")
    if isinstance(profiles, list):
        out: dict[str, dict[str, float]] = {}
        for row in profiles:
            if not isinstance(row, dict):
                continue
            area = row.get("Area")
            if not area:
                continue
            out[str(area)] = {
                "rainfall_mm": float(row.get("average_rain_fall_mm_per_year", 0.0)),
                "temperature_celsius": float(row.get("avg_temp", 0.0)),
            }
        return out

    return {}


AREA_CLIMATE_REFERENCE = get_area_climate_reference()


def autofill_climate(
    area: str | None,
    rainfall_mm: float | None,
    temperature_celsius: float | None,
) -> tuple[float | None, float | None, str, str, bool]:
    rainfall_source = "user_input" if rainfall_mm is not None else "not_provided"
    temperature_source = "user_input" if temperature_celsius is not None else "not_provided"
    autofill_used = False

    if area is None:
        return rainfall_mm, temperature_celsius, rainfall_source, temperature_source, autofill_used

    area = normalize_area_name(area)
    ref = AREA_CLIMATE_REFERENCE.get(area)

    if not ref:
        return rainfall_mm, temperature_celsius, rainfall_source, temperature_source, autofill_used

    if rainfall_mm is None:
        rainfall_mm = ref.get("rainfall_mm")
        if rainfall_mm is not None:
            rainfall_source = "country_mean"
            autofill_used = True

    if temperature_celsius is None:
        temperature_celsius = ref.get("temperature_celsius")
        if temperature_celsius is not None:
            temperature_source = "country_mean"
            autofill_used = True

    return rainfall_mm, temperature_celsius, rainfall_source, temperature_source, autofill_used


# =========================================================
# Support / confiance
# =========================================================


def get_crop_support_count_model_1(crop: str) -> int:
    if not MODEL_1_CROP_META:
        return 0
    counts = MODEL_1_CROP_META.get("crop_support_counts", {})
    return int(counts.get(crop, 0))


def get_crop_support_count_model_2(crop: str) -> int:
    if not MODEL_2_META:
        return 0
    counts = MODEL_2_META.get("item_support_counts", {})
    return int(counts.get(crop, 0))


def is_area_supported_for_model_2(area: str | None) -> bool:
    if area is None:
        return False
    supported_areas = {normalize_area_name(x) for x in get_supported_areas_model_2()}
    return area in supported_areas


def build_confidence_level(
    source_model: str,
    crop_support_count: int,
    autofill_used: bool,
) -> str:
    if source_model == "model_1_crop":
        if crop_support_count >= 1000 and not autofill_used:
            return "high"
        if crop_support_count >= 200:
            return "medium"
        return "low"

    if source_model == "model_1_general":
        if not autofill_used:
            return "medium"
        return "low"

    if crop_support_count >= 1000 and not autofill_used:
        return "medium"
    return "low"


def build_warning_message(
    source_model: str,
    crop_support_count: int,
    autofill_used: bool,
) -> str | None:
    warnings: list[str] = []

    if source_model == "model_1_general":
        warnings.append(
            "Cette prédiction repose sur le modèle général du dataset principal, "
            "car aucun profil enrichi exploitable n'est disponible pour cette culture."
        )

    if source_model == "model_2_recommendation":
        warnings.append(
            "Cette prédiction repose sur le modèle secondaire, avec un niveau de "
            "fiabilité plus faible."
        )

    if crop_support_count < 200:
        warnings.append("La culture est peu représentée dans les données d'entraînement.")

    if autofill_used:
        warnings.append(
            "Certaines variables climatiques ont été auto-remplies à partir des "
            "moyennes du pays."
        )

    if not warnings:
        return None

    return " ".join(warnings)


def merge_warnings(*messages: str | None) -> str | None:
    parts = [msg.strip() for msg in messages if msg and msg.strip()]
    if not parts:
        return None

    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if part not in seen:
            deduped.append(part)
            seen.add(part)
    return " ".join(deduped)


# =========================================================
# Référentiel de profil culture pour model_1_crop enrichi
# =========================================================


def get_crop_profile_reference() -> dict[str, dict[str, float]]:
    df = get_crop_profile_df()
    if df is None or df.empty:
        return {}

    df = df.copy()

    crop_col = None
    for candidate in ["Crop", "Crop_std"]:
        if candidate in df.columns:
            crop_col = candidate
            break

    if crop_col is None:
        return {}

    required_cols = [
        "ext_mean_temp_by_crop",
        "ext_mean_rainfall_by_crop",
        "ext_mean_pesticides_by_crop",
        "ext_n_obs_by_crop",
    ]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        return {}

    ref: dict[str, dict[str, float]] = {}
    for _, row in df.iterrows():
        crop = normalize_crop_name(str(row[crop_col]))
        if not crop:
            continue

        ref[crop] = {
            "ext_mean_temp_by_crop": float(row["ext_mean_temp_by_crop"]),
            "ext_mean_rainfall_by_crop": float(row["ext_mean_rainfall_by_crop"]),
            "ext_mean_pesticides_by_crop": float(row["ext_mean_pesticides_by_crop"]),
            "ext_n_obs_by_crop": float(row["ext_n_obs_by_crop"]),
        }

    return ref


CROP_PROFILE_REFERENCE = get_crop_profile_reference()


def has_crop_profile_for_model_1(crop: str) -> bool:
    crop = normalize_crop_name(crop)
    return crop in CROP_PROFILE_REFERENCE


def get_recommendable_crops_model_1() -> list[str]:
    supported = [normalize_crop_name(c) for c in get_supported_crops_model_1()]
    return sorted([c for c in supported if has_crop_profile_for_model_1(c)])


def get_unusable_crops_model_1() -> list[str]:
    supported = {normalize_crop_name(c) for c in get_supported_crops_model_1()}
    usable = set(get_recommendable_crops_model_1())
    return sorted(supported - usable)


def build_model_1_crop_features(
    crop: str,
    rainfall_mm: float,
    temperature_celsius: float,
    fertilizer_used: bool | None,
    irrigation_used: bool | None,
) -> pd.DataFrame:
    profile = CROP_PROFILE_REFERENCE.get(crop)
    if profile is None:
        raise ValueError(
            f"Aucun profil enrichi disponible pour la culture '{crop}'. "
            "Le modèle principal ne peut pas reconstruire ses features d'entrée."
        )

    ext_mean_temp_by_crop = profile["ext_mean_temp_by_crop"]
    ext_mean_rainfall_by_crop = profile["ext_mean_rainfall_by_crop"]
    ext_mean_pesticides_by_crop = profile["ext_mean_pesticides_by_crop"]
    ext_n_obs_by_crop = profile["ext_n_obs_by_crop"]

    rainfall_gap_vs_crop_profile = rainfall_mm - ext_mean_rainfall_by_crop
    temp_gap_vs_crop_profile = temperature_celsius - ext_mean_temp_by_crop

    row = pd.DataFrame(
        [
            {
                "Crop": crop,
                "Rainfall_mm": rainfall_mm,
                "Temperature_Celsius": temperature_celsius,
                "Fertilizer_Used": bool_to_int(fertilizer_used),
                "Irrigation_Used": bool_to_int(irrigation_used),
                "ext_mean_temp_by_crop": ext_mean_temp_by_crop,
                "ext_mean_rainfall_by_crop": ext_mean_rainfall_by_crop,
                "ext_mean_pesticides_by_crop": ext_mean_pesticides_by_crop,
                "ext_n_obs_by_crop": ext_n_obs_by_crop,
                "rainfall_gap_vs_crop_profile": rainfall_gap_vs_crop_profile,
                "temp_gap_vs_crop_profile": temp_gap_vs_crop_profile,
            }
        ]
    )

    expected_features: list[str] = []
    if MODEL_1_CROP_META:
        expected_features = MODEL_1_CROP_META.get("feature_names", [])

    if expected_features:
        missing = set(expected_features) - set(row.columns)
        if missing:
            raise ValueError(
                "Impossible de construire toutes les colonnes attendues par "
                f"model_1_crop: {missing}"
            )
        row = row[expected_features].copy()

    return row


# =========================================================
# Prédictions unitaires
# =========================================================


def predict_with_model_1_crop(
    crop: str,
    rainfall_mm: float,
    temperature_celsius: float,
    fertilizer_used: bool | None,
    irrigation_used: bool | None,
) -> float:
    if MODEL_1_CROP is None:
        raise ValueError("model_1_crop n'est pas chargé.")

    row = build_model_1_crop_features(
        crop=crop,
        rainfall_mm=rainfall_mm,
        temperature_celsius=temperature_celsius,
        fertilizer_used=fertilizer_used,
        irrigation_used=irrigation_used,
    )
    pred = MODEL_1_CROP.predict(row)[0]
    return float(pred)


def predict_with_model_2(
    crop: str,
    area: str,
    rainfall_mm: float,
    temperature_celsius: float,
) -> float:
    if MODEL_2 is None:
        raise ValueError("model_2_recommendation n'est pas chargé.")

    row = pd.DataFrame(
        [
            {
                "Area": area,
                "Item": crop,
                "average_rain_fall_mm_per_year": rainfall_mm,
                "avg_temp": temperature_celsius,
            }
        ]
    )
    pred = MODEL_2.predict(row)[0]
    return float(pred)


def predict_with_model_1_general(
    rainfall_mm: float,
    temperature_celsius: float,
    fertilizer_used: bool | None,
    irrigation_used: bool | None,
) -> float | None:
    if MODEL_1_GENERAL is None:
        return None

    row = pd.DataFrame(
        [
            {
                "Rainfall_mm": rainfall_mm,
                "Temperature_Celsius": temperature_celsius,
                "Fertilizer_Used": bool_to_int(fertilizer_used),
                "Irrigation_Used": bool_to_int(irrigation_used),
            }
        ]
    )
    pred = MODEL_1_GENERAL.predict(row)[0]
    return float(pred)


# =========================================================
# Helpers métier communs
# =========================================================


def build_bounds(predicted: float, error_margin: float) -> tuple[float, float]:
    lower_bound = max(0.0, predicted - error_margin)
    upper_bound = predicted + error_margin
    return lower_bound, upper_bound


def compute_consistency_adjustment(
    primary_prediction: float,
    secondary_prediction: float | None,
) -> float:
    if secondary_prediction is None:
        return 1.0

    denom = max(abs(primary_prediction), 1.0)
    relative_gap = abs(primary_prediction - secondary_prediction) / denom

    if relative_gap <= 0.10:
        return 1.04
    if relative_gap <= 0.20:
        return 1.02
    if relative_gap <= 0.35:
        return 1.00
    if relative_gap <= 0.50:
        return 0.96
    return 0.90


def normalize_recommendation_scores(items: list[dict[str, Any]]) -> None:
    if not items:
        return

    raw_scores = [float(item["_raw_score"]) for item in items]
    min_score = min(raw_scores)
    max_score = max(raw_scores)

    if max_score == min_score:
        for item in items:
            item["recommendation_score"] = 1.0
        return

    for item in items:
        normalized = (float(item["_raw_score"]) - min_score) / (max_score - min_score)
        item["recommendation_score"] = round(min(max(normalized, 0.0), 1.0), 4)


def build_reason_for_primary_recommendation(
    crop: str,
    secondary_used: bool,
    consistency_adjustment: float,
) -> str:
    reason = (
        f"{crop} est supportée par le modèle principal culture-spécifique, "
        "qui sert de base prioritaire à la recommandation."
    )

    if secondary_used:
        if consistency_adjustment > 1.0:
            reason += " Le modèle secondaire confirme globalement cette estimation."
        elif consistency_adjustment < 1.0:
            reason += (
                " Le modèle secondaire donne un signal plus divergent ; "
                "la recommandation est donc rendue plus prudente."
            )
        else:
            reason += (
                " Le modèle secondaire a été consulté comme second avis "
                "sans modifier fortement la conclusion."
            )

    return reason


def build_reason_for_general_recommendation(crop: str) -> str:
    return (
        f"{crop} est présente dans le dataset principal, mais sans profil enrichi "
        "exploitable. La recommandation utilise donc le modèle général principal."
    )


def build_reason_for_secondary_recommendation(crop: str) -> str:
    return (
        f"{crop} est proposée via le modèle secondaire, car elle n'est couverte "
        "que par le dataset secondaire. Cette recommandation doit être lue comme "
        "une piste complémentaire et plus exploratoire."
    )


# =========================================================
# Economie
# =========================================================


def convert_price_to_usd_per_tonne(price_row: dict[str, Any]) -> float:
    unit = str(price_row["price_unit"]).lower()
    value = float(price_row["price_value"])

    if unit == "usd_per_tonne":
        return value
    if unit == "usd_per_kg":
        return value * 1000.0

    raise ValueError(f"Unsupported price unit: {unit}")


def compute_economic_outputs(
    crop: str,
    parcel_area_ha: float,
    predicted_yield_t_ha: float,
    lower_bound_t_ha: float,
    upper_bound_t_ha: float,
) -> dict[str, float | None]:
    price_row = get_active_crop_price(crop)
    cost_row = get_active_crop_costs(crop)

    predicted_yield_total_t = predicted_yield_t_ha * parcel_area_ha
    lower_total_t = lower_bound_t_ha * parcel_area_ha
    upper_total_t = upper_bound_t_ha * parcel_area_ha

    if price_row is None:
        return {
            "sale_price_per_tonne": None,
            "predicted_yield_total_t": predicted_yield_total_t,
            "estimated_revenue": None,
            "estimated_revenue_lower": None,
            "estimated_revenue_upper": None,
            "estimated_variable_costs": None,
            "estimated_gross_margin": None,
        }

    sale_price_per_tonne = convert_price_to_usd_per_tonne(price_row)

    estimated_revenue = predicted_yield_total_t * sale_price_per_tonne
    estimated_revenue_lower = lower_total_t * sale_price_per_tonne
    estimated_revenue_upper = upper_total_t * sale_price_per_tonne

    if cost_row is None:
        estimated_variable_costs = 0.0
    else:
        estimated_variable_costs = parcel_area_ha * (
            float(cost_row.get("seed_cost_per_ha", 0.0) or 0.0)
            + float(cost_row.get("pesticide_cost_per_ha", 0.0) or 0.0)
            + float(cost_row.get("fertilizer_cost_per_ha", 0.0) or 0.0)
            + float(cost_row.get("irrigation_cost_per_ha", 0.0) or 0.0)
            + float(cost_row.get("other_cost_per_ha", 0.0) or 0.0)
        )

    estimated_gross_margin = estimated_revenue - estimated_variable_costs

    return {
        "sale_price_per_tonne": sale_price_per_tonne,
        "predicted_yield_total_t": predicted_yield_total_t,
        "estimated_revenue": estimated_revenue,
        "estimated_revenue_lower": estimated_revenue_lower,
        "estimated_revenue_upper": estimated_revenue_upper,
        "estimated_variable_costs": estimated_variable_costs,
        "estimated_gross_margin": estimated_gross_margin,
    }


# =========================================================
# Routage principal /predict
# =========================================================


def predict_crop_yield(
    crop: str,
    area: str | None,
    parcel_area_ha: float,
    rainfall_mm: float | None,
    temperature_celsius: float | None,
    fertilizer_used: bool | None,
    irrigation_used: bool | None,
) -> PredictResponse:
    crop = normalize_crop_name(crop)

    if area is not None:
        area = normalize_area_name(area)

    (
        rainfall_mm,
        temperature_celsius,
        rainfall_source,
        temperature_source,
        autofill_used,
    ) = autofill_climate(
        area=area,
        rainfall_mm=rainfall_mm,
        temperature_celsius=temperature_celsius,
    )

    if rainfall_mm is None or temperature_celsius is None:
        raise ValueError(
            "Impossible de prédire sans rainfall_mm et temperature_celsius, sauf si "
            "une area valide permet l'autoremplissage."
        )

    supported_crops_model_1 = {normalize_crop_name(c) for c in get_supported_crops_model_1()}
    recommendable_crops_model_1 = set(get_recommendable_crops_model_1())
    fallback_crops_model_1_general = supported_crops_model_1 - recommendable_crops_model_1

    supported_crops_model_2 = {normalize_crop_name(c) for c in get_supported_crops_model_2()}
    secondary_only_crops = supported_crops_model_2 - supported_crops_model_1

    warning_prefix: str | None = None

    if crop in recommendable_crops_model_1:
        predicted = predict_with_model_1_crop(
            crop=crop,
            rainfall_mm=rainfall_mm,
            temperature_celsius=temperature_celsius,
            fertilizer_used=fertilizer_used,
            irrigation_used=irrigation_used,
        )
        source_model = "model_1_crop"
        error_margin = get_error_margin_model_1_crop() or 0.0
        crop_support_count = get_crop_support_count_model_1(crop)

    elif crop in fallback_crops_model_1_general:
        predicted = predict_with_model_1_general(
            rainfall_mm=rainfall_mm,
            temperature_celsius=temperature_celsius,
            fertilizer_used=fertilizer_used,
            irrigation_used=irrigation_used,
        )
        if predicted is None:
            raise ValueError("model_1_general n'est pas chargé.")

        source_model = "model_1_general"
        error_margin = get_error_margin_model_1_crop() or 0.0
        crop_support_count = get_crop_support_count_model_1(crop)
        warning_prefix = (
            "La culture ne dispose pas d'un profil enrichi exploitable ; "
            "la prédiction repose sur le modèle général du dataset principal, "
            "moins spécifique à la culture. "
        )

    elif crop in secondary_only_crops:
        if area is None:
            raise ValueError(
                "Cette culture n'est disponible que dans le modèle secondaire : "
                "area est obligatoire."
            )
        if not is_area_supported_for_model_2(area):
            raise ValueError(
                "L'area fournie n'est pas supportée par le modèle secondaire pour "
                "cette prédiction."
            )

        predicted = predict_with_model_2(
            crop=crop,
            area=area,
            rainfall_mm=rainfall_mm,
            temperature_celsius=temperature_celsius,
        )
        source_model = "model_2_recommendation"
        error_margin = get_error_margin_model_2() or 0.0
        crop_support_count = get_crop_support_count_model_2(crop)

    else:
        raise ValueError("Culture non supportée par les modèles disponibles.")

    confidence = build_confidence_level(
        source_model=source_model,
        crop_support_count=crop_support_count,
        autofill_used=autofill_used,
    )
    warning = build_warning_message(
        source_model=source_model,
        crop_support_count=crop_support_count,
        autofill_used=autofill_used,
    )
    warning = merge_warnings(warning_prefix, warning)

    lower_bound, upper_bound = build_bounds(predicted, error_margin)

    economics = compute_economic_outputs(
        crop=crop,
        parcel_area_ha=parcel_area_ha,
        predicted_yield_t_ha=predicted,
        lower_bound_t_ha=lower_bound,
        upper_bound_t_ha=upper_bound,
    )

    return PredictResponse(
        crop=crop,
        predicted_yield_t_ha=predicted,
        error_margin_t_ha=error_margin,
        lower_bound_t_ha=lower_bound,
        upper_bound_t_ha=upper_bound,
        predicted_yield_total_t=economics["predicted_yield_total_t"],
        sale_price_per_tonne=economics["sale_price_per_tonne"],
        estimated_revenue=economics["estimated_revenue"],
        estimated_revenue_lower=economics["estimated_revenue_lower"],
        estimated_revenue_upper=economics["estimated_revenue_upper"],
        estimated_variable_costs=economics["estimated_variable_costs"],
        estimated_gross_margin=economics["estimated_gross_margin"],
        source_model=source_model,  # type: ignore[arg-type]
        confidence_level=confidence,  # type: ignore[arg-type]
        warning=warning,
        inputs_used=InputsUsed(
            area=area,
            parcel_area_ha=parcel_area_ha,
            rainfall_mm=rainfall_mm,
            temperature_celsius=temperature_celsius,
            fertilizer_used=fertilizer_used,
            irrigation_used=irrigation_used,
            rainfall_source=rainfall_source,  # type: ignore[arg-type]
            temperature_source=temperature_source,  # type: ignore[arg-type]
        ),
    )


# =========================================================
# Logique de recommandation
# =========================================================


def recommend_crops_service(
    area: str | None,
    parcel_area_ha: float,
    rainfall_mm: float | None,
    temperature_celsius: float | None,
    fertilizer_used: bool | None,
    irrigation_used: bool | None,
    top_k: int = 5,
) -> RecommendResponse:
    if area is not None:
        area = normalize_area_name(area)

    (
        rainfall_mm,
        temperature_celsius,
        rainfall_source,
        temperature_source,
        autofill_used,
    ) = autofill_climate(
        area=area,
        rainfall_mm=rainfall_mm,
        temperature_celsius=temperature_celsius,
    )

    if rainfall_mm is None or temperature_celsius is None:
        raise ValueError(
            "Impossible de recommander sans rainfall_mm et temperature_celsius, sauf si "
            "une area valide permet l'autoremplissage."
        )

    supported_crops_model_1 = {normalize_crop_name(c) for c in get_supported_crops_model_1()}
    recommendable_crops_model_1 = get_recommendable_crops_model_1()
    fallback_crops_model_1_general = sorted(
        supported_crops_model_1 - set(recommendable_crops_model_1)
    )

    supported_crops_model_2 = sorted(
        {normalize_crop_name(c) for c in get_supported_crops_model_2()}
    )
    secondary_only_crops = sorted(set(supported_crops_model_2) - supported_crops_model_1)

    supported_crops_model_2_set = set(supported_crops_model_2)
    area_ok_for_model_2 = is_area_supported_for_model_2(area)

    candidates: list[dict[str, Any]] = []
    missing_economic_data_crops: set[str] = set()

    # -----------------------------------------------------
    # 1) Recommandations principales portées par model_1_crop
    # -----------------------------------------------------
    for crop in recommendable_crops_model_1:
        try:
            predicted_primary = predict_with_model_1_crop(
                crop=crop,
                rainfall_mm=rainfall_mm,
                temperature_celsius=temperature_celsius,
                fertilizer_used=fertilizer_used,
                irrigation_used=irrigation_used,
            )
        except ValueError:
            continue

        error_margin = get_error_margin_model_1_crop() or 0.0
        crop_support_count = get_crop_support_count_model_1(crop)
        confidence = build_confidence_level(
            source_model="model_1_crop",
            crop_support_count=crop_support_count,
            autofill_used=autofill_used,
        )
        base_warning = build_warning_message(
            source_model="model_1_crop",
            crop_support_count=crop_support_count,
            autofill_used=autofill_used,
        )

        secondary_prediction: float | None = None
        secondary_used = False

        if area_ok_for_model_2 and crop in supported_crops_model_2_set:
            secondary_prediction = predict_with_model_2(
                crop=crop,
                area=area,  # type: ignore[arg-type]
                rainfall_mm=rainfall_mm,
                temperature_celsius=temperature_celsius,
            )
            secondary_used = True

        consistency_adjustment = compute_consistency_adjustment(
            primary_prediction=predicted_primary,
            secondary_prediction=secondary_prediction,
        )

        lower_bound, upper_bound = build_bounds(predicted_primary, error_margin)
        economics = compute_economic_outputs(
            crop=crop,
            parcel_area_ha=parcel_area_ha,
            predicted_yield_t_ha=predicted_primary,
            lower_bound_t_ha=lower_bound,
            upper_bound_t_ha=upper_bound,
        )

        if economics["estimated_gross_margin"] is None:
            missing_economic_data_crops.add(crop)
            continue

        raw_score = float(economics["estimated_gross_margin"]) * consistency_adjustment

        warning = merge_warnings(
            base_warning,
            (
                "Le modèle secondaire suggère une estimation sensiblement différente ; "
                "interpréter cette recommandation avec prudence."
                if secondary_used and consistency_adjustment < 1.0
                else None
            ),
        )

        candidates.append(
            {
                "tier": 1,
                "crop": crop,
                "_raw_score": raw_score,
                "predicted_yield_t_ha": predicted_primary,
                "error_margin_t_ha": error_margin,
                "lower_bound_t_ha": lower_bound,
                "upper_bound_t_ha": upper_bound,
                "predicted_yield_total_t": economics["predicted_yield_total_t"],
                "sale_price_per_tonne": economics["sale_price_per_tonne"],
                "estimated_revenue": economics["estimated_revenue"],
                "estimated_variable_costs": economics["estimated_variable_costs"],
                "estimated_gross_margin": economics["estimated_gross_margin"],
                "confidence_level": confidence,
                "source_model": "model_1_crop",
                "reason": build_reason_for_primary_recommendation(
                    crop=crop,
                    secondary_used=secondary_used,
                    consistency_adjustment=consistency_adjustment,
                ),
                "warning": warning,
            }
        )

    # -----------------------------------------------------
    # 2) Recommandations fallback via model_1_general
    # -----------------------------------------------------
    general_prediction = None
    if fallback_crops_model_1_general:
        general_prediction = predict_with_model_1_general(
            rainfall_mm=rainfall_mm,
            temperature_celsius=temperature_celsius,
            fertilizer_used=fertilizer_used,
            irrigation_used=irrigation_used,
        )

    if general_prediction is not None:
        for crop in fallback_crops_model_1_general:
            error_margin = get_error_margin_model_1_crop() or 0.0
            crop_support_count = get_crop_support_count_model_1(crop)

            confidence = build_confidence_level(
                source_model="model_1_general",
                crop_support_count=crop_support_count,
                autofill_used=autofill_used,
            )

            lower_bound, upper_bound = build_bounds(general_prediction, error_margin)
            economics = compute_economic_outputs(
                crop=crop,
                parcel_area_ha=parcel_area_ha,
                predicted_yield_t_ha=general_prediction,
                lower_bound_t_ha=lower_bound,
                upper_bound_t_ha=upper_bound,
            )

            if economics["estimated_gross_margin"] is None:
                missing_economic_data_crops.add(crop)
                continue

            raw_score = float(economics["estimated_gross_margin"])

            warning = merge_warnings(
                "La culture ne dispose pas d'un profil enrichi exploitable ; "
                "la recommandation repose sur le modèle général du dataset principal.",
                build_warning_message(
                    source_model="model_1_general",
                    crop_support_count=crop_support_count,
                    autofill_used=autofill_used,
                ),
            )

            candidates.append(
                {
                    "tier": 2,
                    "crop": crop,
                    "_raw_score": raw_score,
                    "predicted_yield_t_ha": general_prediction,
                    "error_margin_t_ha": error_margin,
                    "lower_bound_t_ha": lower_bound,
                    "upper_bound_t_ha": upper_bound,
                    "predicted_yield_total_t": economics["predicted_yield_total_t"],
                    "sale_price_per_tonne": economics["sale_price_per_tonne"],
                    "estimated_revenue": economics["estimated_revenue"],
                    "estimated_variable_costs": economics["estimated_variable_costs"],
                    "estimated_gross_margin": economics["estimated_gross_margin"],
                    "confidence_level": confidence,
                    "source_model": "model_1_general",
                    "reason": build_reason_for_general_recommendation(crop),
                    "warning": warning,
                }
            )

    # -----------------------------------------------------
    # 3) Recommandations complémentaires via model_2
    # -----------------------------------------------------
    if area_ok_for_model_2:
        for crop in secondary_only_crops:
            predicted_secondary = predict_with_model_2(
                crop=crop,
                area=area,  # type: ignore[arg-type]
                rainfall_mm=rainfall_mm,
                temperature_celsius=temperature_celsius,
            )
            error_margin = get_error_margin_model_2() or 0.0
            crop_support_count = get_crop_support_count_model_2(crop)
            confidence = build_confidence_level(
                source_model="model_2_recommendation",
                crop_support_count=crop_support_count,
                autofill_used=autofill_used,
            )

            lower_bound, upper_bound = build_bounds(predicted_secondary, error_margin)
            economics = compute_economic_outputs(
                crop=crop,
                parcel_area_ha=parcel_area_ha,
                predicted_yield_t_ha=predicted_secondary,
                lower_bound_t_ha=lower_bound,
                upper_bound_t_ha=upper_bound,
            )

            if economics["estimated_gross_margin"] is None:
                missing_economic_data_crops.add(crop)
                continue

            warning = build_warning_message(
                source_model="model_2_recommendation",
                crop_support_count=crop_support_count,
                autofill_used=autofill_used,
            )

            raw_score = float(economics["estimated_gross_margin"])

            candidates.append(
                {
                    "tier": 3,
                    "crop": crop,
                    "_raw_score": raw_score,
                    "predicted_yield_t_ha": predicted_secondary,
                    "error_margin_t_ha": error_margin,
                    "lower_bound_t_ha": lower_bound,
                    "upper_bound_t_ha": upper_bound,
                    "predicted_yield_total_t": economics["predicted_yield_total_t"],
                    "sale_price_per_tonne": economics["sale_price_per_tonne"],
                    "estimated_revenue": economics["estimated_revenue"],
                    "estimated_variable_costs": economics["estimated_variable_costs"],
                    "estimated_gross_margin": economics["estimated_gross_margin"],
                    "confidence_level": confidence,
                    "source_model": "model_2_recommendation",
                    "reason": build_reason_for_secondary_recommendation(crop),
                    "warning": warning,
                }
            )

    if not candidates:
        raise ValueError(
            "Aucune recommandation n'a pu être produite avec les modèles chargés, "
            "les entrées fournies et les données économiques disponibles."
        )

    normalize_recommendation_scores(candidates)

    candidates.sort(
        key=lambda item: (
            int(item["tier"]),
            -float(item["recommendation_score"]),
            -float(item["estimated_gross_margin"]),
            item["crop"],
        )
    )

    recommendations = [
        RecommendationItem(
            crop=str(item["crop"]),
            predicted_yield_t_ha=float(item["predicted_yield_t_ha"]),
            error_margin_t_ha=float(item["error_margin_t_ha"]),
            lower_bound_t_ha=float(item["lower_bound_t_ha"]),
            upper_bound_t_ha=float(item["upper_bound_t_ha"]),
            predicted_yield_total_t=float(item["predicted_yield_total_t"]),
            sale_price_per_tonne=float(item["sale_price_per_tonne"]),
            estimated_revenue=float(item["estimated_revenue"]),
            estimated_variable_costs=float(item["estimated_variable_costs"]),
            estimated_gross_margin=float(item["estimated_gross_margin"]),
            recommendation_score=float(item["recommendation_score"]),
            confidence_level=item["confidence_level"],  # type: ignore[arg-type]
            source_model=item["source_model"],  # type: ignore[arg-type]
            reason=str(item["reason"]),
            warning=item["warning"],
        )
        for item in candidates[:top_k]
    ]

    return RecommendResponse(
        recommendations=recommendations,
        autofill_used=autofill_used,
        missing_economic_data_crops=sorted(missing_economic_data_crops),
        inputs_used=InputsUsed(
            area=area,
            parcel_area_ha=parcel_area_ha,
            rainfall_mm=rainfall_mm,
            temperature_celsius=temperature_celsius,
            fertilizer_used=fertilizer_used,
            irrigation_used=irrigation_used,
            rainfall_source=rainfall_source,  # type: ignore[arg-type]
            temperature_source=temperature_source,  # type: ignore[arg-type]
        ),
    )
