from pathlib import Path

import duckdb
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scripts.run import historical
from src.experiment import kpis, replay
from src.model import HORIZON, partitions, prepare
from src.operations import Scenario, simulate
from src.warehouse import build, validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def history():
    return simulate(days=180, skus=25, decision=historical)


def test_inventory_and_events(history):
    validate(history)
    assert len(history["transfers"]) > 0
    assert len(history["receipts"]) > 0
    assert history["daily"].lost.sum() > 0


def test_bad_inventory_rejected(history):
    broken = dict(history, daily=history["daily"].copy())
    broken["daily"].loc[0, "closing"] = -1
    with pytest.raises(ValueError, match="Negative"):
        validate(broken)


def test_sql_reconciliation(history, tmp_path):
    build(history, tmp_path, ROOT/"sql")
    assert len(list(tmp_path.glob("*.csv"))) == 15
    with duckdb.connect(str(tmp_path/"operations.duckdb"), read_only=True) as db:
        assert db.sql("SELECT sum(lost) FROM stockout_events").fetchone()[0] == history["daily"].lost.sum()
        assert db.sql("SELECT count(*) FROM duckdb_constraints() WHERE constraint_type='FOREIGN KEY'").fetchone()[0] >= 10
    assert pd.read_csv(tmp_path/"01_warehouse.csv").lost_cost.sum() == pytest.approx(history["daily"].lost_cost.sum())


def test_horizon_boundaries_and_future_exclusion(history):
    d, x = prepare(history)
    train, validation, holdout = partitions(d)
    gap = pd.Timedelta(days=HORIZON)
    assert d.loc[train, "date"].max() + gap < d.loc[validation, "date"].min()
    assert d.loc[validation, "date"].max() + gap < d.loc[holdout, "date"].min()
    changed = history["daily"].copy()
    changed.loc[changed.date > d.date.min()+pd.Timedelta(days=35), "lost"] = 999
    other, other_x = prepare(dict(history, daily=changed))
    past = d.date <= d.date.min()+pd.Timedelta(days=35)
    pd.testing.assert_frame_equal(x[past], other_x[past])
    assert not d.loc[past, "target"].equals(other.loc[past, "target"])


def test_matched_policy_and_kpis():
    base, proposed = replay(None, "2025-03-01", Scenario(delay=3), days=28, skus=25)
    for dataset in [base, proposed]:
        validate(dataset)
        d = dataset["daily"]
        measures = kpis(dataset)
        assert measures["fill_rate"] == pytest.approx(d.fulfilled.sum()/d.demand.sum())
        assert measures["total_cost"] == pytest.approx(d[["lost_cost","holding_cost","transfer_cost","purchase_fee"]].to_numpy().sum())
    pd.testing.assert_series_equal(base["daily"].demand, proposed["daily"].demand)
    assert len(proposed["transfers"]) > 0


@pytest.mark.parametrize("page", ["Executive overview", "Inventory diagnostics", "Supplier performance",
                                 "Stockout prediction", "Inventory optimization", "Scenario simulator",
                                 "Business impact", "Model diagnostics"])
def test_app_views(page):
    app = AppTest.from_file(str(ROOT/"app/Home.py"), default_timeout=30).run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception
    assert not app.error
    assert app.title[0].value == page
    if page == "Inventory optimization":
        assert "promised_arrival" in app.dataframe[0].value.columns
        assert "arrives" not in app.dataframe[0].value.columns
    if page == "Scenario simulator":
        app.slider[0].set_value(1.2)
        app.button[0].click().run()
        assert not app.exception
        assert not app.error
        assert app.dataframe


def test_saved_prediction_pipeline():
    import os
    import joblib
    import numpy as np
    root = Path(os.environ.get("HARBORFIELD_ARTIFACTS", ROOT/"artifacts"))
    model = joblib.load(root/"model.joblib")
    holdout = pd.read_parquet(root/"predictions.parquet")
    assert holdout.risk.between(0,1).all()
    assert holdout.target.notna().all()
    assert np.unique(holdout.risk).size > 20
    from src.model import FEATURES
    assert model.n_features_in_ == len(FEATURES)
    scores = model.predict_proba(pd.DataFrame(0., index=[0], columns=FEATURES))
    assert scores.shape == (1, 2)
    assert scores[0].sum() == pytest.approx(1.)


def test_short_replay_and_pipeline_reconciliation(tmp_path):
    short = simulate(days=1, skus=5)
    assert short["receipts"].empty and short["transfers"].empty
    build(short, tmp_path, ROOT/"sql")
    d = short["daily"].copy()
    d.loc[d.index[0], ["pending", "position"]] += 1
    with pytest.raises(ValueError, match="commitments"):
        validate(dict(short, daily=d))


def test_extra_receipt_outside_ledger_rejected(history):
    receipts = history["receipts"].copy()
    order_id = history["orders"].loc[~history["orders"].order_id.isin(receipts.order_id), "order_id"].iloc[-1]
    order = history["orders"].set_index("order_id").loc[order_id]
    late_date = max(order.promised, history["daily"].date.max()+pd.Timedelta(days=1))
    invalid = pd.DataFrame([dict(order_id=order_id, received_date=late_date, units=order.units,
                                 lead_days=(late_date-order.ordered).days)])
    with pytest.raises(ValueError, match="outside ledger"):
        validate(dict(history, receipts=pd.concat([receipts, invalid], ignore_index=True)))
