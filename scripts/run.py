"""Run generation, validation, SQL, models and matched policy replay."""
import argparse
import json
import logging

import duckdb
from pathlib import Path

from src.experiment import experiment
from src.model import train
from src.operations import simulate
from src.optimization import recommend
from src.warehouse import KEYS, build

ROOT = Path(__file__).resolve().parents[1]


def historical(observed, products, sites, vendors, routes, scenario, baseline):
    # Weekly transfers are allowed, with the same baseline purchase rule.
    if observed["date"].dayofweek != 0:
        return [], baseline
    actions, _ = recommend(observed, products, sites, vendors, routes, scenario, baseline)
    return actions, baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--stage", choices=["all","warehouse","decisions"], default="all")
    parser.add_argument("--output", type=Path, default=ROOT/"artifacts")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = json.loads((ROOT/"config/default.json").read_text())
    if args.quick:
        config.update(days=215, skus=30)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.stage in {"all","warehouse"}:
        logging.info("event=generate settings=%s", config)
        tables = simulate(**config, decision=historical)
        logging.info("event=warehouse pair_days=%s", len(tables["daily"]))
        build(tables, args.output, ROOT/"sql")
    if args.stage == "warehouse":
        return
    if args.stage == "decisions":
        with duckdb.connect(str(args.output/"operations.duckdb"), read_only=True, config={"threads":2}) as db:
            tables = {name: db.table(name).df() for name in KEYS}
        shape = (len(tables["products"]),len(tables["suppliers"]),tables["daily"].date.nunique())
        if shape != (config["skus"],config["suppliers"],config["days"]):
            parser.error("Warehouse dimensions differ from this run's configuration")
    model, test_start = train(tables, args.output)
    logging.info("event=replay start=%s", test_start.date())
    experiment(model, test_start, args.output, config["skus"], config["suppliers"], args.quick)
    logging.info("event=complete output=%s", args.output)


if __name__ == "__main__":
    main()
