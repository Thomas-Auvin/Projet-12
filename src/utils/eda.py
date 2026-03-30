import numpy as np
import pandas as pd
from IPython.display import display


def quick_eda(df: pd.DataFrame, name: str = "dataset") -> None:
    """
    Affiche un diagnostic rapide d'un DataFrame.
    """
    print("=" * 80)
    print(f"{name.upper()}")
    print("=" * 80)
    print(f"Shape: {df.shape}")

    print("\nColonnes :")
    print(df.columns.tolist())

    print("\nTypes :")
    print(df.dtypes)

    print("\nValeurs manquantes :")
    missing = df.isna().sum().sort_values(ascending=False)
    print(missing[missing > 0])

    print("\nDoublons :")
    print(df.duplicated().sum())

    print("\nAperçu :")
    display(df.head())

    print("\nStatistiques numériques :")
    num_cols = df.select_dtypes(include=[np.number])
    if not num_cols.empty:
        display(num_cols.describe().T)
    else:
        print("Aucune colonne numérique détectée.")

    print("\nStatistiques catégorielles :")
    cat_cols = df.select_dtypes(include=["object", "category", "string"])
    if not cat_cols.empty:
        display(cat_cols.describe().T)
    else:
        print("Aucune colonne catégorielle détectée.")


def missing_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Retourne un résumé des valeurs manquantes.
    """
    summary = pd.DataFrame(
        {
            "missing_count": df.isna().sum(),
            "missing_pct": (df.isna().mean() * 100).round(2),
            "dtype": df.dtypes.astype(str),
        }
    )
    return summary.sort_values("missing_count", ascending=False)


def uniqueness_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Retourne un résumé du nombre de valeurs uniques par colonne.
    """
    summary = pd.DataFrame(
        {
            "n_unique": df.nunique(dropna=False),
            "dtype": df.dtypes.astype(str),
        }
    )
    return summary.sort_values("n_unique")
