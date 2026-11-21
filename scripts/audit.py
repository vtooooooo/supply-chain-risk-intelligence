"""Reproduce model-dependence and policy economics diagnostics from the full run."""
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from src.model import HORIZON, partitions, prepare, rules
from src.warehouse import KEYS, validate

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT/"artifacts"


def main():
    with duckdb.connect(str(ARTIFACTS/"operations.duckdb"), read_only=True, config={"threads": 2}) as db:
        tables = {name: db.table(name).df() for name in KEYS}
    validate(tables)
    daily, features = prepare(tables)
    train, validation, holdout = partitions(daily)
    for name, mask in zip(["train", "validation", "holdout"], [train, validation, holdout]):
        group = daily.loc[mask]
        print(name, group.date.min().date(), group.date.max().date(), len(group), round(group.target.mean(), 5))
    frame = daily.loc[holdout, ["date", "site", "sku", "target", "lost"]].copy()
    x = features.loc[holdout]
    frame["rules"] = rules(x)
    frame["physical_only"] = -x.days_supply
    frame["ml"] = joblib.load(ARTIFACTS/"model.joblib").predict_proba(x)[:, 1]
    print("history daily lost share", (daily.lost > 0).mean())
    previous = frame.groupby(["site","sku"]).target.shift()
    adjacent = previous.notna()
    print("holdout adjacent label agreement", previous[adjacent].eq(frame.target[adjacent]).mean())
    print("holdout label share by coverage quintile")
    print(frame.groupby(pd.qcut(x.days_supply, 5, duplicates="drop"), observed=True).target.agg(["mean","size"]))
    print("holdout AP", {name: average_precision_score(frame.target, frame[name])
                         for name in ["rules","physical_only","ml"]})
    phases = (frame.date-frame.date.min()).dt.days % HORIZON
    scores = pd.DataFrame([{"prevalence": g.target.mean(), **{
        name: average_precision_score(g.target, g[name]) for name in ["rules","ml"]}}
        for _,g in frame.groupby(phases)])
    print("non-overlap phase sensitivity", scores.agg(["min","mean","max"]).round(4))
    # Each phase uses disjoint label windows within each pair. Phases themselves reuse dates.
    print("incremental AP range across phases", (scores.ml-scores.rules).agg(["min","max"]))
    orders = pd.read_csv(ARTIFACTS/"experiment.csv")
    pair = orders.pivot(index=["scenario","seed"], columns="policy")
    delta = lambda key: pair[key].proposed-pair[key].baseline
    summary = pd.DataFrame(dict(savings=-delta("total_cost"),
                                savings_pct=-delta("total_cost")/pair.total_cost.baseline*100,
                                fill_pp=delta("fill_rate")*100,
                                capital=delta("working_capital")))
    print("all pairs")
    print(summary.round(2).to_string())
    print("scenario summaries")
    print(summary.groupby("scenario").agg(["mean","min","max"]).round(2).to_string())
    print("all-pair summaries", summary.agg(["mean","min","max"]).round(2))
    # Seed is the replication unit across stresses using common seed identifiers.
    print("average improvements by seed", summary.groupby("seed").mean().round(2).to_string())
    print("ratio of total costs", 1-orders.query("policy=='proposed'").total_cost.sum()/orders.query("policy=='baseline'").total_cost.sum())
    cols = ["fill_rate","lost_cost","holding_cost","transfer_cost","purchase_fee","purchase_spend",
            "total_cost","working_capital","terminal_on_hand","terminal_po","terminal_transfer"]
    nominal = orders.query("scenario == 'base'").groupby("policy")[cols].mean()
    controls = pd.read_csv(ARTIFACTS/"ablation.csv").groupby("policy")[cols].mean()
    print("nominal", pd.concat([nominal,controls]).round(3).to_string())
    print("paired transfer-minus-purchase-only")
    baseline = orders.query("scenario == 'base' and policy == 'proposed'").set_index("seed")
    buy = pd.read_csv(ARTIFACTS/"ablation.csv").query("policy == 'ML without transfers'").set_index("seed")
    print((baseline[cols]-buy[cols]).round(3).to_string())
    average_extra = delta("working_capital").loc["base"].mean()
    nominal_savings = summary.savings.loc["base"].mean()
    for rate in [.05,.10,.15,.20,.30]:
        extra_finance = average_extra*rate*56/365
        print(f"additive cost of capital {rate:.0%}: ${extra_finance:,.0f}, net savings ${nominal_savings-extra_finance:,.0f}")
    t = tables["transfers"]
    print("ledger", {key:len(tables[key]) for key in ["daily","orders","receipts","transfers"]})
    print("delayed transfers", int((t.arrives > t.promised_arrival).sum()))
    print("finite horizon transfer pipeline", int((t.arrives > daily.date.max()).sum()))


if __name__ == "__main__":
    main()
