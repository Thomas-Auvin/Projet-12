from pathlib import Path


def find_project_root(start_path: Path | None = None) -> Path:
    """
    Trouve la racine du projet en remontant les dossiers
    jusqu'à trouver pyproject.toml ou .git.
    """
    current = (start_path or Path(__file__)).resolve()

    if current.is_file():
        current = current.parent

    for path in [current, *current.parents]:
        if (path / "pyproject.toml").exists() or (path / ".git").exists():
            return path

    raise FileNotFoundError(
        "Impossible de trouver la racine du projet (aucun pyproject.toml ou .git trouvé)."
    )


ROOT = find_project_root()

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw_local"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

NOTEBOOKS_DIR = ROOT / "notebooks"
SRC_DIR = ROOT / "src"
TESTS_DIR = ROOT / "tests"
APP_DIR = ROOT / "app"
STREAMLIT_DIR = ROOT / "streamlit_app"

ARTIFACTS_DIR = ROOT / "artifacts"

OUTPUTS_DIR = ROOT / "outputs"
FIG_DIR = OUTPUTS_DIR / "figures"
TAB_DIR = OUTPUTS_DIR / "tables"
REPORTS_DIR = OUTPUTS_DIR / "reports"

GITHUB_DIR = ROOT / ".github"
WORKFLOWS_DIR = GITHUB_DIR / "workflows"

DIRS_TO_CREATE = [
    DATA_DIR,
    RAW_DIR,
    INTERIM_DIR,
    PROCESSED_DIR,
    NOTEBOOKS_DIR,
    SRC_DIR,
    TESTS_DIR,
    APP_DIR,
    STREAMLIT_DIR,
    ARTIFACTS_DIR,
    OUTPUTS_DIR,
    FIG_DIR,
    TAB_DIR,
    REPORTS_DIR,
    GITHUB_DIR,
    WORKFLOWS_DIR,
]


def ensure_project_dirs() -> None:
    for directory in DIRS_TO_CREATE:
        directory.mkdir(parents=True, exist_ok=True)


ensure_project_dirs()


if __name__ == "__main__":
    print(f"ROOT: {ROOT}")
    for directory in DIRS_TO_CREATE:
        print(directory)
