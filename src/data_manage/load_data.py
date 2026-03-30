from pathlib import Path

import pandas as pd

from project_paths import RAW_DIR


def get_raw_path(relative_path: str | Path) -> Path:
    """
    Retourne le chemin complet vers un fichier situé dans data/raw_local.
    """
    file_path = RAW_DIR / relative_path
    if not file_path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {file_path}")
    return file_path


def load_csv(relative_path: str | Path, **kwargs) -> pd.DataFrame:
    """
    Charge un CSV depuis data/raw_local, y compris dans des sous-dossiers.
    Exemple :
        load_csv("agriculture_crop_yield/crop_yield.csv")
    """
    file_path = get_raw_path(relative_path)
    return pd.read_csv(file_path, **kwargs)


def load_excel(relative_path: str | Path, **kwargs) -> pd.DataFrame:
    """
    Charge un fichier Excel depuis data/raw_local.
    """
    file_path = get_raw_path(relative_path)
    return pd.read_excel(file_path, **kwargs)


def list_raw_files(pattern: str = "*") -> list[Path]:
    """
    Liste récursivement les fichiers de data/raw_local.
    Exemple :
        list_raw_files("*.csv")
    """
    return sorted(RAW_DIR.rglob(pattern))
