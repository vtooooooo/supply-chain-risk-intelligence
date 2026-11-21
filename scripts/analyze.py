"""Execute the analytical notebooks and write findings from their source outputs."""
import argparse
from pathlib import Path

import duckdb
import nbformat as nbf
import numpy as np
import pandas as pd
from nbclient import NotebookClient
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]

NOTEBOOKS = {
"01_data_quality_and_profiling": ("Daily ledger and data quality", """
display(db.sql("SELECT count(*) pair_days, count(DISTINCT date) AS calendar_days, count(DISTINCT sku) skus, count(DISTINCT site) sites FROM daily").df())
display(db.sql("SELECT count_if(closing<0) negative_rows, count_if(opening+received+inbound-fulfilled-outbound<>closing) out_of_balance, count_if(demand<>fulfilled+lost) demand_mismatch FROM daily").df())
display(db.sql("SELECT site,avg(utilization) mean_utilization,max(utilization) maximum_utilization FROM (SELECT date,site,sum(closing)/max(capacity) utilization FROM enriched GROUP BY 1,2) GROUP BY site ORDER BY site").df())
""", "The ledger checks identify unit mismatches directly. Peak receiving capacity and transaction-to-event reconciliation also run in the warehouse builder."),
"02_supply_chain_eda": ("Demand, inventory, and procurement", """
d = db.sql("SELECT date,site,sum(demand) demand,sum(lost_cost) lost_cost FROM daily GROUP BY 1,2 ORDER BY 1,2").df()
fig, axes = plt.subplots(2,2,figsize=(12,7), layout='constrained')
for site, g in d.groupby('site'):
    axes[0,0].plot(g.date,g.demand.rolling(14).mean(),label=str(site))
axes[0,0].set_title('Regional demand, 14-day mean')
axes[0,0].legend(title='Site')
raw = db.sql("SELECT demand,demand_sd FROM daily USING SAMPLE reservoir(2000 ROWS) REPEATABLE(42)").df()
axes[0,1].hist(raw.demand,bins=30)
axes[0,1].set_title('Sampled pair-day demand')
axes[1,0].hist(db.sql('SELECT lead_days FROM receipts').df().lead_days,bins=20)
axes[1,0].set_title('Observed lead times')
costs = read('02_sku_stockouts').lost_cost.sort_values(ascending=False)
axes[1,1].plot(costs.cumsum().to_numpy()/costs.sum())
axes[1,1].set_title('Cumulative lost contribution by ranked SKU')
fig.savefig(figures/'operations.png',dpi=130)
plt.show()
for key in ['01_warehouse','03_abc','04_xyz','05_supplier_otd','06_lead_variability','07_imbalance','13_donor_stock']:
    print(key)
    display(read(key).head())
display(db.sql("SELECT dayname(date) AS weekday, avg(demand) AS mean_units FROM daily GROUP BY 1 ORDER BY mean_units DESC").df())
display(db.sql("SELECT month(date) AS calendar_month, avg(demand) AS mean_units, avg((lost>0)::INT) AS stockout_share FROM daily GROUP BY 1 ORDER BY 1").df())
display(db.sql("SELECT bucket,avg(demand_sd) demand_sd, avg((lost>0)::INT) stockout_share FROM (SELECT *,ntile(4) OVER(ORDER BY demand_sd,site,sku,date) AS bucket FROM daily) GROUP BY 1 ORDER BY 1").df())
""", "Coverage gaps and loss concentration motivate pair-level triage. Supplier receipts describe completed orders and exclude open orders."),
"03_statistical_investigation": ("Supplier delay association and donor-stock prevalence", """
from scripts.analyze import investigation
display(pd.Series(investigation(db),name='estimate').to_frame())
""", "The supplier-level rank association avoids treating repeated pair-days as independent. The moving-block interval retains temporal dependence within four-week blocks. Neither measure identifies a causal effect."),
"04_model_development": ("Chronological stockout prediction", """
display(read('metrics'))
s = read('calibration')
plt.plot([0,1],[0,1],color='gray')
plt.scatter(s.risk,s.actual,s=10+80*s['count']/s['count'].max())
plt.xlabel('Mean predicted risk')
plt.ylabel('Observed stockout share')
plt.title('Held-out calibration')
plt.tight_layout()
plt.savefig(figures/'calibration.png',dpi=130)
plt.show()
""", "The training, validation, and test periods are chronological. Thresholds and the winner are selected using validation only. The top-5% metrics estimate intervention triage quality."),
"05_model_explainability": ("Held-out feature and error diagnostics", """
imp=read('importance').head(10).sort_values('ap_drop')
plt.barh(imp.feature,imp.ap_drop,xerr=imp.sd)
plt.xlabel('Average precision drop')
plt.tight_layout()
plt.savefig(figures/'importance.png',dpi=130)
plt.show()
display(read('segments')[['dimension','segment','observations','prevalence','pr_auc','recall','fp','fn']])
""", "Permutation estimates capture model reliance in a held-out sample. Correlated coverage features can substitute for one another. Subgroup errors may reflect policy and prevalence shifts."),
}


def investigation(db):
    suppliers = db.sql("""
        WITH delivery AS (SELECT supplier,avg((received_date>promised)::INT) late FROM supplier_lead_history GROUP BY supplier),
             sales AS (SELECT supplier,avg((lost>0)::INT) stockouts FROM enriched GROUP BY supplier)
        SELECT * FROM delivery JOIN sales USING(supplier)
    """).df()
    weekly = db.sql("""
        SELECT date_trunc('week',date) AS week_start,count(*) total,count_if(other_stock>=lost) covered
        FROM enriched WHERE lost>0 GROUP BY 1 ORDER BY 1
    """).df()
    rng = np.random.default_rng(55)
    n = len(weekly)
    indices = ((rng.integers(n, size=(1200, (n+3)//4, 1))+np.arange(4)) % n).reshape(1200,-1)[:,:n]
    shares = weekly.covered.to_numpy()[indices].sum(1)/weekly.total.to_numpy()[indices].sum(1)
    low, high = np.quantile(shares, [.025,.975])
    return dict(supplier_rank_correlation=spearmanr(suppliers.late,suppliers.stockouts).statistic,
                suppliers=len(suppliers), donor_share=weekly.covered.sum()/weekly.total.sum(),
                donor_low=low, donor_high=high)


def execute_notebooks(output, destination, figures, eda_only=False):
    destination.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    setup = f"""
from pathlib import Path
import sys
import duckdb, pandas as pd, matplotlib.pyplot as plt
root=next(path for path in [Path.cwd(), *Path.cwd().parents] if (path/'config/default.json').exists())
sys.path.insert(0,str(root))
output=root/{str(output.relative_to(ROOT))!r}
figures=root/{str(figures.relative_to(ROOT))!r}
db=duckdb.connect(str(output/'operations.duckdb'),read_only=True,config={{'threads':2}})
def read(name):
    return pd.read_csv(output/f'{{name}}.csv')
"""
    notebooks = list(NOTEBOOKS.items())[:3] if eda_only else NOTEBOOKS.items()
    for filename, (title, body, note) in notebooks:
        book = nbf.v4.new_notebook(cells=[nbf.v4.new_markdown_cell(f"# {title}"),
                                         nbf.v4.new_code_cell(setup.strip()),
                                         nbf.v4.new_code_cell(body.strip()),
                                         nbf.v4.new_markdown_cell(note)],
                                   metadata={"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"}})
        NotebookClient(book, timeout=180, resources={"metadata":{"path":str(ROOT)}}).execute()
        nbf.write(book, destination/f"{filename}.ipynb")


def reports(output, destination, docs):
    destination.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    def read(name):
        return pd.read_csv(output/f"{name}.csv")
    with duckdb.connect(str(output/"operations.duckdb"), read_only=True, config={"threads":2}) as db:
        stats = investigation(db)
        summary = db.sql("SELECT sum(fulfilled)/sum(demand) fill, count_if(lost>0) events, sum(lost_cost) loss FROM daily").df().iloc[0]
    worst = read("01_warehouse").iloc[0]
    top_sku = read("02_sku_stockouts").iloc[0]
    late = read("05_supplier_otd").iloc[0]
    sku_concentration = read("02_sku_stockouts").lost_cost.head(15).sum()/summary.loss
    analysis = f"""# Exploratory analysis

The historical network filled **{summary.fill:.2%}** of requested units. Its {summary.events:,.0f} shortage pair-days produced ${summary.loss:,.0f} in simulated lost contribution. Site {worst.site:.0f} led regional loss at ${worst.lost_cost:,.0f}, and SKU {top_sku.sku:.0f} led product loss. The 15 most exposed SKUs accounted for {sku_concentration:.1%} of loss.

{stats['donor_share']:.1%} of shortage pair-days had enough closing stock elsewhere to cover the observed shortage. The four-week moving-block 95% interval was {stats['donor_low']:.1%}–{stats['donor_high']:.1%}. This supports investigating rebalancing. Dispatch lead time and donor safety stock reduce the actionable share.

Supplier {late.supplier:.0f} had {late.on_time:.1%} on-time receipts. Supplier-level Spearman correlation between late receipts and shortage frequency was {stats['supplier_rank_correlation']:.2f} across {stats['suppliers']} suppliers. This descriptive estimate is confounded by supplier product mix and covers completed receipts. It cannot establish a supplier-delay effect.

Demand varies by region and over time. Coverage and recent shortfalls warrant point-in-time prediction. The replay measures whether those predictions translate to better decisions.

![Demand, lead times and loss concentration](figures/operations.png)
"""
    (destination/"01_exploratory_analysis_report.md").write_text(analysis)
    metrics = read("metrics")
    winner = metrics.loc[metrics.selected].iloc[0]
    model_table = "\n".join(f"| {r.model} | {r.validation_ap:.3f} | {r.pr_auc:.3f} | {r.roc_auc:.3f} | {r.f1:.3f} | {r.brier:.3f} | {r.precision_at_5pct:.3f} | {r.recall_at_5pct:.3f} |" for r in metrics.itertuples())
    (destination/"02_model_evaluation.md").write_text(f"""# Model evaluation

**{winner.model}** led validation average precision. Its held-out prevalence was {winner.prevalence:.2%} across {winner.observations:,} eligible observations. The validation F1 threshold was {winner.threshold:.3f}. Test precision was {winner.precision:.3f}, recall {winner.recall:.3f}, and the confusion counts were TN {winner.tn:,}, FP {winner.fp:,}, FN {winner.fn:,}, TP {winner.tp:,}.

| Model | Validation AP | Test AP | ROC AUC | F1 | Brier | Precision at 5% | Recall at 5% |
|---|---:|---:|---:|---:|---:|---:|---:|
{model_table}

Scores forecast any shortage in the next 14 calendar days. The model uses 28 days of historical operations, completed supplier receipts, and tomorrow’s known promotion plan. Model comparison uses average precision as PR-AUC convention. Calibration and sliced errors are available in the generated CSVs and notebooks. Scores may shift once a new policy changes on-hand and pipeline distributions.

![Held-out calibration](figures/calibration.png)
![Permutation importance](figures/importance.png)
""")
    replay = read("experiment")
    nominal = replay[replay.scenario == "base"]
    means = nominal.groupby("policy").mean(numeric_only=True)
    base, proposed = means.loc["baseline"], means.loc["proposed"]
    savings = 1-proposed.total_cost/base.total_cost
    paired = replay.pivot(index=["scenario","seed"],columns="policy",values="total_cost")
    paired["delta"] = paired.proposed-paired.baseline
    sensitivity = paired.groupby("scenario").delta.agg(["mean","min","max"])
    controls = read("ablation").groupby("policy").mean(numeric_only=True)
    purchase_control = controls.loc["ML without transfers"]
    transfer_delta = proposed.total_cost-purchase_control.total_cost
    coverage_delta = proposed.total_cost-controls.loc["coverage only"].total_cost
    ablation_rows = "\n".join(f"| {name} | {r.fill_rate:.2%} | ${r.total_cost:,.0f} | ${r.purchase_spend:,.0f} |"
                              for name,r in pd.concat([means, controls]).iterrows())
    rows = "\n".join(f"| {name} | {r['mean']:,.0f} | {r['min']:,.0f} | {r['max']:,.0f} |" for name,r in sensitivity.iterrows())
    money = ["lost_cost","holding_cost","transfer_cost","purchase_fee","purchase_spend","total_cost","working_capital"]
    breakdown = "\n".join(f"| {key.replace('_',' ')} | ${base[key]:,.0f} | ${proposed[key]:,.0f} |" for key in money)
    breakdown += f"\n| Fill rate | {base.fill_rate:.2%} | {proposed.fill_rate:.2%} |\n| Stockout frequency | {base.stockout_rate:.2%} | {proposed.stockout_rate:.2%} |\n| Utilization | {base.utilization:.2%} | {proposed.utilization:.2%} |"
    (destination/"03_business_impact_report.md").write_text(f"""# Executive business impact

The risk-aware policy changed nominal simulated total cost by {-savings:+.1%} and fill by {(proposed.fill_rate-base.fill_rate)*100:+.2f} percentage points. These are synthetic scenario outcomes.

Harborfield can lose sales at a constrained site while inventory sits elsewhere. SQL found donor availability elsewhere on {stats['donor_share']:.1%} of shortage days. The selected 14-day model achieved test AP of {winner.pr_auc:.3f}. The policy combines that score with observed coverage, donor reserves, route time, destination room and marginal cost. A fixed reorder policy supplies the comparator.

## Nominal paired comparison

| Measure | Baseline | Proposed |
|---|---:|---:|
{breakdown}

Purchase spend represents inventory investment. The recurring cost metric includes purchase fees only. The working-capital figure is the mean closing on-hand inventory value. At cutoff, baseline and proposed physical stock were worth ${base.terminal_on_hand:,.0f} and ${proposed.terminal_on_hand:,.0f}. Open purchase commitments were ${base.terminal_po:,.0f} and ${proposed.terminal_po:,.0f}. Transfers in transit were ${base.terminal_transfer:,.0f} and ${proposed.terminal_transfer:,.0f}. These gross standard-cost balances are excluded from recurring cost. Ownership and payment timing are unspecified.

## What changed the result

| Policy | Fill | Recurring cost | Purchase spend |
|---|---:|---:|---:|
{ablation_rows}

The coverage-only control replaces ML scores with an observed-stock coverage score. The ML purchase-only control keeps ML prioritization and disables transfers. The full policy beats the fixed baseline in nominal service, while its higher purchase spend means the experiment does not support improved service without more purchasing. Against coverage-only, the full policy changed recurring cost by {coverage_delta:+,.0f} USD. Adding transfers to the ML purchase policy changed recurring cost by {transfer_delta:+,.0f} USD. The throughput and spend differences prevent attributing the baseline comparison to transfers alone.

## Sensitivity

| Scenario | Mean cost change ($) | Minimum ($) | Maximum ($) |
|---|---:|---:|---:|
{rows}

The range spans paired seeds and is descriptive. The policies share starting inventory, demand, promotion schedules and procurement delay draws. Purchase and transfer decisions change which draws get realized. Capacity reserves all committed arrivals. The horizon does not assign terminal pipeline value, so procurement timing can affect the comparison.

Management should compare the purchase-only and full policies in a shadow pilot. Include lane-specific service floors, transfer labor constraints and a working-capital budget. Validate effective demand, costs, capacity units and lead-time records against commercial data. Monitor calibration and backtest under actual ordering rules before granting operational authority.
""")
    interpretations = [
        "Compare weighted regional fill with mean inventory to identify service gaps.",
        "Rank products by accumulated loss to prioritize the largest exposures.",
        "Apply cumulative 80% and 95% throughput cutoffs for differentiated review cadence.",
        "Use the coefficient of variation of daily network demand to distinguish stable and volatile SKUs.",
        "Compare received orders to promised dates to focus supplier follow-up.",
        "Compare dispersion and the upper tail of realized lead times when setting buffers.",
        "Measure each date's best-versus-worst coverage spread and prioritize persistent gaps.",
        "Value daily positive excess against 28 days of trailing demand, then average exposure.",
        "Track month-by-region unmet units and contribution loss to distinguish cost from volume.",
        "Compare contribution lost and carrying cost by category with observed fill.",
        "Divide cost of fulfilled units by mean closing valuation per month for period turnover.",
        "Use the order cohort and receipt linkage to track open volume as of cutoff.",
        "Compare unmet units to other sites' concurrent closing stock to estimate the upper bound on redistribution.",
        "Join all valid lanes to shipment records to retain unused routes and quantify freight concentration.",
        "Rank pair-level cost over the latest 28 days for planner triage.",
    ]
    sql_report = ["# Executed SQL findings", f"Network fill was {summary.fill:.2%}. The historical ledger reported ${summary.loss:,.0f} in lost contribution.", ""]
    for path, interpretation in zip(sorted((ROOT/"sql").glob("*.sql")), interpretations, strict=True):
        frame = read(path.stem)
        query = path.read_text()
        sql_report.extend([f"## {path.stem.replace('_',' ')}", query.splitlines()[0][3:],
                           f"Executed output has {len(frame):,} rows. Fields are " + ", ".join(frame.columns) + ".",
                           "The first reported row is " + ", ".join(f"{k}={v}" for k,v in frame.iloc[0].items()) + ".",
                           interpretation, f"See `sql/{path.name}` for the query.", ""])
    (docs/"04_sql_analysis_findings.md").write_text("\n\n".join(sql_report))
    (docs/"06_project_case_study.md").write_text(f"""# Harborfield case study

**Problem.** Regional stockouts coexist with network stock. Finance needs to know whether redistribution warrants its cost.

**Data.** A chronological synthetic event ledger connects demand, fulfillment, receipts and transfers across five warehouses.

**Investigation.** Network fill was {summary.fill:.2%}. Other locations held enough closing units on {stats['donor_share']:.1%} of shortage pair-days, before lead times and reserves.

**Modeling.** The selected {winner.model} model reached test average precision of {winner.pr_auc:.3f} in a purged chronological split.

**Decisions.** The heuristic applies finite capacity, priced freight, transit time and donor reserves to transfer and purchase proposals.

**Results and business value.** Nominal synthetic fill moved from {base.fill_rate:.2%} to {proposed.fill_rate:.2%}. Cost changed {-savings:+.1%}. A field pilot should test lane economics and service with independently verified inputs.
""")
    (docs/"07_resume_and_interview_summary.md").write_text(f"""# Résumé and interview notes

## Analyst bullets

- Built a reconciled DuckDB supply-chain warehouse and 15 SQL diagnostics, measuring {summary.fill:.2%} historical fill across a synthetic five-site network.
- Quantified donor inventory coinciding with {stats['donor_share']:.1%} of shortage pair-days and evaluated paired financial and service tradeoffs.

## Data scientist bullets

- Trained a point-in-time 14-day stockout classifier with {winner.pr_auc:.3f} held-out average precision and chronological horizon purging.
- Combined predictions with constrained dispatch and procurement, measuring {-savings:+.1%} nominal synthetic cost change in matched scenario replay.

## 60-second explanation

Harborfield loses sales when product is in the wrong region. I simulated its ledger, reconciled every inventory movement, and used SQL and statistical analysis to quantify the mismatch. I scored future shortages from information available at ordering time and translated scores into inventory decisions. I then replayed both policies on paired demand and delay scenarios and compared service, costs and working capital.

## Technical explanation

Observation is after demand and before ordering. Labels examine days 1 through 14. Split boundaries purge training and validation outcomes that reach the next period. The decision heuristic sorts eligible lane-SKU candidates by expected marginal benefit, then allocates only available donor and capacity units. The experiment varies scenarios and reuses exogenous draws within each pair.

## Interview questions

1. **How did you detect leakage?** Enforce label cutoffs and build features from the snapshot and completed receipts.
2. **Why average precision?** It summarizes precision-recall discrimination on the shortage class.
3. **Can another site's stock always help?** Transit, donor buffers, destination room and freight limit eligibility.
4. **How did you compare policies?** Matched dates, initial stock, constraints and exogenous random seeds.
5. **What would you validate next?** Confirm demand censoring, unit volume, supplier risk and costs before a shadow pilot.
""")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--eda-only", action="store_true")
    args = parser.parse_args()
    base = ROOT/"artifacts"
    if args.quick:
        base = base/"quick"
    destination = base/"reports" if args.quick else ROOT/"reports"
    execute_notebooks(base, base/"notebooks" if args.quick else ROOT/"notebooks", destination/"figures", args.eda_only)
    if not args.eda_only:
        reports(base, destination, base/"docs" if args.quick else ROOT/"docs")


if __name__ == "__main__":
    main()
