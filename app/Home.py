"""Streamlit decision support using generated operational artifacts."""
import os
import sys
from pathlib import Path

import duckdb
import joblib
import pandas as pd
import plotly.express as px
import streamlit as st

# Community Cloud runs this entry point without installing the local project package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app_data import PREDICTION_COLUMNS, missing_files
from src.experiment import kpis, replay
from src.operations import Scenario

override = os.environ.get("HARBORFIELD_ARTIFACTS")
local_artifacts = ROOT/"artifacts"
if override:
    DATA = Path(override)
elif not missing_files(local_artifacts):
    DATA = local_artifacts
else:
    DATA = ROOT/"deployment"/"snapshot"
st.set_page_config(page_title="Harborfield | Inventory Intelligence", page_icon="📦", layout="wide")
st.sidebar.title("Harborfield")
st.sidebar.caption("Synthetic US distribution network")
PAGES = ["Executive overview", "Inventory diagnostics", "Supplier performance", "Stockout prediction",
         "Inventory optimization", "Scenario simulator", "Business impact", "Model diagnostics"]
page = st.sidebar.radio("View", PAGES)
st.title(page)

missing = missing_files(DATA)
if missing:
    st.error(f"App data is incomplete. Missing files: {', '.join(missing)}.")
    st.code("python -m scripts.run")
    st.stop()


@st.cache_data
def csv(name, version):
    return pd.read_csv(DATA/f"{name}.csv")


def read(name):
    return csv(name, (DATA/f"{name}.csv").stat().st_mtime_ns)


@st.cache_data
def query(statement, version):
    with duckdb.connect(str(DATA/"operations.duckdb"), read_only=True, config={"threads": 2}) as conn:
        return conn.sql(statement).df()


def sql(statement):
    return query(statement, (DATA/"operations.duckdb").stat().st_mtime_ns)


@st.cache_data
def predictions(version):
    return pd.read_parquet(DATA/"predictions.parquet", columns=PREDICTION_COLUMNS)


def table(data, name):
    st.dataframe(data, hide_index=True, use_container_width=True)
    st.download_button("Download CSV", data.to_csv(index=False), f"{name}.csv", "text/csv", key=name)


def dollars(value):
    return f"${value:,.0f}"


def outcomes(data):
    metrics = ["lost_cost", "holding_cost", "transfer_cost", "purchase_fee"]
    costs = data.melt(id_vars=["policy"], value_vars=metrics, var_name="cost", value_name="USD")
    st.plotly_chart(px.bar(costs, x="policy", y="USD", color="cost", title="Recurring cost breakdown"))
    table(data, "policy-results")


def overview():
    totals = sql("""SELECT sum(fulfilled)/sum(demand) fill,
                    sum(lost_cost) loss,last(daily_value ORDER BY date) latest,
                    sum(cogs)/avg(daily_value) turnover,sum(lost_pairs)/sum(pairs) shortage
                    FROM (SELECT date,sum(fulfilled) fulfilled,sum(demand) demand,
                          sum(lost_cost) lost_cost,sum(inventory_value) daily_value,
                          sum(fulfilled*unit_cost) cogs,sum((lost>0)::INT) lost_pairs,count(*) pairs
                          FROM enriched GROUP BY date) daily""")
    r = totals.iloc[0]
    fields = [("Closing inventory", dollars(r.latest)), ("Fill rate", f"{r.fill:.1%}"),
              ("Shortage pair-days", f"{r.shortage:.1%}"), ("Lost contribution", dollars(r.loss)),
              ("Period turnover", f"{r.turnover:.1f}×")]
    for column, (label, value) in zip(st.columns(5), fields):
        column.metric(label, value)
    sites = read("01_warehouse").merge(sql("SELECT site,name FROM warehouses"), on="site")
    st.plotly_chart(px.bar(sites, x="name", y="lost_cost", color="fill_rate", title="Regional lost contribution",
                          labels={"name":"Warehouse","lost_cost":"Lost contribution ($)","fill_rate":"Fill rate"}))
    table(sites, "warehouse-performance")


def inventory():
    sites = sql("SELECT site,name FROM warehouses").set_index("site").name.to_dict()
    site = st.selectbox("Warehouse", list(sites), format_func=sites.get)
    segments = read("03_abc").merge(read("04_xyz"), on="sku")
    d = read("08_excess").query("site == @site").merge(segments, on="sku").merge(read("07_imbalance"), on="sku")
    segment = st.multiselect("ABC segments", sorted(d.abc.unique()))
    if segment:
        d = d[d.abc.isin(segment)]
    st.plotly_chart(px.scatter(d, x="average_coverage", y="average_excess_value", color="abc",
                               symbol="xyz", hover_data=["sku","average_coverage_gap"],
                               title="Coverage versus average excess value"))
    table(d, "inventory-diagnostics")
    if len(d):
        sku = st.selectbox("SKU history", d.sku.tolist())
        history = sql(f"SELECT date,closing,demand,lost FROM daily WHERE site={int(site)} AND sku={int(sku)} ORDER BY date")
        st.plotly_chart(px.line(history, x="date", y=["closing","demand","lost"], title="Daily inventory and demand"))


def suppliers():
    d = read("05_supplier_otd").merge(read("06_lead_variability"), on="supplier")
    st.plotly_chart(px.scatter(d, x="on_time", y="sd_days", size="receipts", hover_data=["supplier"],
                               title="Delivery reliability and lead-time variation"))
    table(d, "supplier-scorecard")
    supplier = st.selectbox("Supplier disruption history", d.supplier.tolist())
    table(sql(f"SELECT date,supplier FROM disruptions WHERE disruption AND supplier={int(supplier)} ORDER BY date"),
          "supplier-disruptions")


def prediction():
    d = predictions((DATA/"predictions.parquet").stat().st_mtime_ns)
    date = st.selectbox("Held-out scoring date", sorted(d.date.dt.date.unique(), reverse=True))
    floor = st.slider("Minimum risk score", 0., 1., .15)
    filtered = d[(d.date.dt.date == date) & (d.risk >= floor)].sort_values("risk", ascending=False)
    st.caption("Risk of any shortage in the 14 days following the observation date.")
    st.plotly_chart(px.histogram(filtered, x="risk", color="alert", title="Risk distribution"))
    table(filtered, "stockout-predictions")
    st.caption("Global explanations use the decline in held-out average precision after feature permutation.")
    table(read("importance"), "prediction-drivers")


def optimization():
    transfers = read("recommendations").drop(columns="arrives")
    buys = read("replenishment")
    st.caption("Nominal replay · seed 101. The simulator accepted these decisions after checking source stock, destination room and transit time. Transfer dates shown are the promises available at dispatch.")
    st.metric("Simulated transfer freight", dollars(transfers.cost.sum()))
    st.caption("Transfers protect nine days of recent demand at donors. Purchase recommendations reserve destination room and rank SKU needs by modeled exposure.")
    tab1, tab2 = st.tabs(["Transfers", "Purchase orders"])
    with tab1:
        table(transfers, "recommended-transfers")
    with tab2:
        table(buys, "recommended-purchases")


def scenario():
    date = predictions((DATA/"predictions.parquet").stat().st_mtime_ns).date.min()
    dimensions = sql("SELECT count(DISTINCT sku) skus,count(DISTINCT supplier) suppliers FROM products").iloc[0]
    with st.form("scenario"):
        a,b,c = st.columns(3)
        growth = a.slider("Demand multiplier", .75, 1.5, 1.)
        delay = a.slider("Additional supplier days", 0, 8, 0)
        freight = b.slider("Freight multiplier", .5, 3., 1.)
        capacity = b.slider("Capacity multiplier", .65, 1.5, 1.)
        penalty = c.slider("Stockout penalty multiplier", .5, 3., 1.)
        run = st.form_submit_button("Run matched scenario")
    if run:
        with st.spinner("Replaying both policies over 28 days"):
            try:
                model = joblib.load(DATA/"model.joblib")
                base, proposed = replay(model, date, Scenario(growth,delay,freight,capacity,penalty), days=28,
                                        skus=int(dimensions.skus), suppliers=int(dimensions.suppliers))
                outcomes(pd.DataFrame([dict(policy="baseline", **kpis(base)), dict(policy="proposed", **kpis(proposed))]))
            except (OSError, ValueError) as error:
                st.error(f"Scenario could not run. {error}")


def impact():
    d = read("experiment")
    selected = st.selectbox("Stress scenario", d.scenario.unique())
    subset = d[d.scenario == selected]
    means = subset.groupby("policy", as_index=False).mean(numeric_only=True).drop(columns="seed")
    st.plotly_chart(px.bar(means, x="policy", y="fill_rate", title="Mean unit fill rate", range_y=[0,1]))
    outcomes(means)
    paired = d.pivot(index=["scenario","seed"], columns="policy", values="total_cost").reset_index()
    paired["cost_change"] = paired.proposed-paired.baseline
    st.plotly_chart(px.strip(paired, x="scenario", y="cost_change", title="Paired cost change by seed"))
    if selected == "base":
        controls = read("ablation").groupby("policy", as_index=False)[["fill_rate", "total_cost", "purchase_spend"]].mean()
        st.subheader("Policy controls")
        table(controls, "policy-controls")
    st.caption("All financial figures reflect synthetic scenarios.")


def model_diagnostics():
    table(read("metrics"), "model-metrics")
    calibration = read("calibration")
    st.plotly_chart(px.scatter(calibration, x="risk", y="actual", size="count", title="Held-out calibration")
                    .add_shape(type="line", x0=0, y0=0, x1=1, y1=1, line_dash="dash"))
    table(read("segments"), "segment-errors")
    table(read("importance"), "feature-importance")
    st.caption("Performance reflects simulated demand and historical decision rules. Recalibrate against field data before operational use.")


try:
    [overview,inventory,suppliers,prediction,optimization,scenario,impact,model_diagnostics][PAGES.index(page)]()
except (OSError, duckdb.Error) as error:
    st.error(f"Could not read generated data. {error}")
