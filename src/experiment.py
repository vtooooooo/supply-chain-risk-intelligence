"""Paired replay on independent realizations of the held-out season."""
from functools import partial
import pandas as pd

from src.operations import Scenario, simulate
from src.optimization import recommend
from src.warehouse import validate

SCENARIOS = {
    "base": Scenario(), "volatile": Scenario(volatility=2), "delays": Scenario(delay=4),
    "freight": Scenario(freight=2), "capacity": Scenario(capacity=.68),
    "holding": Scenario(holding=2), "penalty": Scenario(penalty=1.6),
}


def kpis(tables):
    d = tables["daily"]
    capacity = d.site.map(tables["warehouses"].set_index("site").capacity)
    outcomes = dict(fill_rate=d.fulfilled.sum()/max(1,d.demand.sum()), stockout_rate=(d.lost>0).mean(),
                    utilization=d.closing.sum()/capacity.groupby([d.date, d.site]).first().sum(),
                    working_capital=d.groupby("date").inventory_value.sum().mean())
    last = d[d.date == d.date.max()]
    unit_cost = tables["products"].set_index("sku").unit_cost
    open_orders = tables["orders"][~tables["orders"].order_id.isin(tables["receipts"].order_id)]
    in_transit = tables["transfers"][tables["transfers"].arrives > d.date.max()]
    outcomes.update(terminal_on_hand=last.inventory_value.sum(),
                    terminal_po=(open_orders.units*open_orders.sku.map(unit_cost)).sum(),
                    terminal_transfer=(in_transit.units*in_transit.sku.map(unit_cost)).sum())
    for field in ["lost_cost", "holding_cost", "transfer_cost", "purchase_fee", "purchase_spend"]:
        outcomes[field] = d[field].sum()
    outcomes["total_cost"] = sum(outcomes[k] for k in ["lost_cost","holding_cost","transfer_cost","purchase_fee"])
    return outcomes


def replay(model, start, scenario, seed=101, days=56, skus=150, suppliers=25):
    shared = dict(start=start, seed=seed, days=days, skus=skus, suppliers=suppliers, scenario=scenario)
    base = simulate(**shared)
    proposed = simulate(**shared, decision=partial(recommend, model=model))
    if not base["daily"][["date","site","sku","demand"]].equals(proposed["daily"][["date","site","sku","demand"]]):
        raise AssertionError("Replay demand diverged")
    validate(base)
    validate(proposed)
    return base, proposed


def experiment(model, start, output, skus, suppliers, quick=False):
    rows = []
    ablation = []
    for name, scenario in SCENARIOS.items():
        for seed in ([101] if quick else [101, 205, 309]):
            base, proposed = replay(model, start, scenario, seed, 28 if quick else 56, skus, suppliers)
            if name == "base" and seed == 101:
                proposed["transfers"].to_csv(output/"recommendations.csv", index=False)
                proposed["orders"].to_csv(output/"replenishment.csv", index=False)
            if name == "base":
                for control, options in [("coverage only", {}), ("ML without transfers", {"model":model, "allow_transfers":False})]:
                    dataset = simulate(seed=seed, start=start, days=28 if quick else 56, skus=skus,
                                       suppliers=suppliers, scenario=scenario, decision=partial(recommend, **options))
                    validate(dataset)
                    ablation.append(dict(seed=seed, policy=control, **kpis(dataset)))
            for policy, dataset in [("baseline",base), ("proposed",proposed)]:
                rows.append(dict(scenario=name, seed=seed, policy=policy, **kpis(dataset)))
    pd.DataFrame(ablation).to_csv(output/"ablation.csv", index=False)
    pd.DataFrame(rows).to_csv(output/"experiment.csv", index=False)
