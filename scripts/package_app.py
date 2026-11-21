"""Export the read-only Community Cloud snapshot from a full validated run."""
import argparse
import shutil
import tempfile
from pathlib import Path

import duckdb
import pandas as pd

from src.app_data import CSV_FILES, PREDICTION_COLUMNS, missing_files

ROOT = Path(__file__).resolve().parents[1]


def package(source: Path, destination: Path) -> None:
    missing = missing_files(source)
    if missing:
        raise ValueError(f"Missing source artifacts: {', '.join(missing)}")
    if destination.resolve() == source.resolve():
        raise ValueError("Choose a destination separate from the original artifacts")

    predictions = pd.read_parquet(source/"predictions.parquet", columns=PREDICTION_COLUMNS)
    experiment = pd.read_csv(source/"experiment.csv")
    if len(predictions) != 72_000 or len(experiment) != 42:
        raise ValueError("The snapshot requires the full default run, including 21 matched pairs")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary)
        for name in (*CSV_FILES, "model.joblib"):
            shutil.copyfile(source/name, staging/name)
        predictions.to_parquet(staging/"predictions.parquet", index=False)
        with duckdb.connect(str(staging/"operations.duckdb"), config={"threads": 2}) as snapshot:
            source_path = str((source/"operations.duckdb").resolve()).replace("'", "''")
            snapshot.execute(f"ATTACH '{source_path}' AS original (READ_ONLY)")
            snapshot.execute("""
                CREATE TABLE daily AS
                SELECT date, site, sku, closing, demand, lost, fulfilled, lost_cost, inventory_value, unit_cost
                FROM original.enriched ORDER BY date, site, sku;
                CREATE VIEW enriched AS SELECT * FROM daily;
                CREATE TABLE warehouses AS SELECT site, name FROM original.warehouses;
                CREATE TABLE products AS SELECT sku, supplier FROM original.products;
                CREATE TABLE disruptions AS SELECT date, supplier, disruption FROM original.disruptions;
            """)
            snapshot.execute("DETACH original")
        destination.mkdir(exist_ok=True)
        for path in staging.iterdir():
            path.replace(destination/path.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT/"artifacts")
    parser.add_argument("--destination", type=Path, default=ROOT/"deployment"/"snapshot")
    args = parser.parse_args()
    package(args.source, args.destination)


if __name__ == "__main__":
    main()
