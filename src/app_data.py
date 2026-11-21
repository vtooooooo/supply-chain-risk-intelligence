"""Files required by the Streamlit views and the deployment snapshot exporter."""

CSV_FILES = (
    "01_warehouse.csv", "03_abc.csv", "04_xyz.csv", "05_supplier_otd.csv",
    "06_lead_variability.csv", "07_imbalance.csv", "08_excess.csv", "ablation.csv",
    "calibration.csv", "experiment.csv", "importance.csv", "metrics.csv",
    "recommendations.csv", "replenishment.csv", "segments.csv",
)
PREDICTION_COLUMNS = ["date", "site", "sku", "category", "risk", "alert", "target"]
RUNTIME_FILES = (*CSV_FILES, "operations.duckdb", "predictions.parquet", "model.joblib")


def missing_files(directory):
    return [name for name in RUNTIME_FILES if not (directory/name).is_file()]
