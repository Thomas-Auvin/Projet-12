from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT / "artifacts"
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"


def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_joblib(path: Path) -> Any:
    return joblib.load(path)


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


MODEL_1_GENERAL_PATH = ARTIFACTS_DIR / "model_1_general.joblib"
MODEL_1_GENERAL_META_PATH = ARTIFACTS_DIR / "model_1_general_meta.json"

MODEL_1_CROP_PATH = ARTIFACTS_DIR / "model_1_crop.joblib"
MODEL_1_CROP_META_PATH = ARTIFACTS_DIR / "model_1_crop_meta.json"

MODEL_2_PATH = ARTIFACTS_DIR / "model_2_recommendation.joblib"
MODEL_2_META_PATH = ARTIFACTS_DIR / "model_2_meta.json"

# Référentiel de profil culture pour reconstruire les features enrichies
CROP_PROFILE_CANDIDATE_PATHS = [
    ARTIFACTS_DIR / "crop_profile.csv",
    ARTIFACTS_DIR / "crop_profile_clean.csv",
    PROCESSED_DIR / "crop_profile.csv",
    PROCESSED_DIR / "crop_profile_clean.csv",
]


def artifact_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def find_existing_path(paths: list[Path]) -> Path | None:
    for path in paths:
        if artifact_exists(path):
            return path
    return None


def load_all_models() -> dict[str, Any]:
    loaded: dict[str, Any] = {
        "model_1_general": None,
        "model_1_general_meta": None,
        "model_1_crop": None,
        "model_1_crop_meta": None,
        "model_2": None,
        "model_2_meta": None,
        "crop_profile_df": None,
    }

    if artifact_exists(MODEL_1_GENERAL_PATH):
        loaded["model_1_general"] = load_joblib(MODEL_1_GENERAL_PATH)

    if artifact_exists(MODEL_1_GENERAL_META_PATH):
        loaded["model_1_general_meta"] = load_json(MODEL_1_GENERAL_META_PATH)

    if artifact_exists(MODEL_1_CROP_PATH):
        loaded["model_1_crop"] = load_joblib(MODEL_1_CROP_PATH)

    if artifact_exists(MODEL_1_CROP_META_PATH):
        loaded["model_1_crop_meta"] = load_json(MODEL_1_CROP_META_PATH)

    if artifact_exists(MODEL_2_PATH):
        loaded["model_2"] = load_joblib(MODEL_2_PATH)

    if artifact_exists(MODEL_2_META_PATH):
        loaded["model_2_meta"] = load_json(MODEL_2_META_PATH)

    crop_profile_path = find_existing_path(CROP_PROFILE_CANDIDATE_PATHS)
    if crop_profile_path is not None:
        loaded["crop_profile_df"] = load_csv(crop_profile_path)

    return loaded


LOADED = load_all_models()


MODEL_1_GENERAL = LOADED["model_1_general"]
MODEL_1_GENERAL_META = LOADED["model_1_general_meta"]

MODEL_1_CROP = LOADED["model_1_crop"]
MODEL_1_CROP_META = LOADED["model_1_crop_meta"]

MODEL_2 = LOADED["model_2"]
MODEL_2_META = LOADED["model_2_meta"]

CROP_PROFILE_DF = LOADED["crop_profile_df"]


def is_model_loaded(model: Any) -> bool:
    return model is not None


def get_supported_crops_model_1() -> list[str]:
    if not MODEL_1_CROP_META:
        return []
    return sorted(MODEL_1_CROP_META.get("supported_crops", []))


def get_supported_crops_model_2() -> list[str]:
    if not MODEL_2_META:
        return []
    return sorted(MODEL_2_META.get("supported_items", []))


def get_supported_areas_model_2() -> list[str]:
    if not MODEL_2_META:
        return []
    return sorted(MODEL_2_META.get("supported_areas", []))


def get_error_margin_model_1_crop() -> float | None:
    if not MODEL_1_CROP_META:
        return None
    return MODEL_1_CROP_META.get("error_margin_t_ha")


def get_error_margin_model_2() -> float | None:
    if not MODEL_2_META:
        return None

    if "error_margin_t_ha" in MODEL_2_META:
        return MODEL_2_META["error_margin_t_ha"]

    cv_summary = MODEL_2_META.get("cv_summary", {})
    if "rmse_mean" in cv_summary:
        return cv_summary["rmse_mean"]

    return None


def get_crop_profile_df() -> pd.DataFrame | None:
    return CROP_PROFILE_DF
