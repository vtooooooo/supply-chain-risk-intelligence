"""End-of-day, pre-order risk scoring with purged chronological evaluation."""
import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                             f1_score, precision_recall_curve, precision_score, recall_score, roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HORIZON = 14
FEATURES = ["site", "category", "on_hand", "pending", "position", "mean_demand", "demand_sd",
            "open_po_units", "due_week_units", "stockout_rate", "supplier_otd", "supplier_sd", "next_promo", "capacity",
            "promised", "days_supply", "season_sin", "season_cos"]


def features(date, site, category, stock, pending, mean, std, frequency, otd, sd,
             promo, capacity, promised, open_po, due_week):
    angle = pd.DatetimeIndex(pd.to_datetime(np.broadcast_to(date, np.shape(stock)))).dayofyear * 2*np.pi/365
    return pd.DataFrame(dict(site=site, category=category, on_hand=stock, pending=pending,
                             position=stock+pending, mean_demand=mean, demand_sd=std,
                             open_po_units=open_po, due_week_units=due_week,
                             stockout_rate=frequency, supplier_otd=otd, supplier_sd=sd,
                             next_promo=np.asarray(promo, int), capacity=capacity, promised=promised,
                             days_supply=stock/np.maximum(mean, .15),
                             season_sin=np.sin(angle), season_cos=np.cos(angle)))[FEATURES]


def prepare(tables):
    d = tables["daily"].sort_values(["site", "sku", "date"]).reset_index(drop=True)
    future = pd.concat([d.groupby(["site", "sku"]).lost.shift(-offset)
                        for offset in range(1, HORIZON+1)], axis=1)
    d["target"] = (future.max(axis=1) > 0).astype("boolean").where(future.notna().all(axis=1))
    d = d.merge(tables["products"][["sku", "category", "supplier"]], on="sku")
    d = d.merge(tables["warehouses"][["site", "capacity"]], on="site")
    d = d.merge(tables["suppliers"][["supplier", "promised"]], on="supplier")
    x = features(d.date, d.site, d.category, d.pre_order_stock, d.pre_order_pending,
                 d.mean_demand, d.demand_sd, d.stockout_rate, d.supplier_otd, d.supplier_sd,
                 d.next_promo, d.capacity, d.promised, d.open_po_units, d.due_week_units)
    return d, x


def partitions(d):
    dates = sorted(d.date.unique())
    train_end, test_start = dates[int(.60*len(dates))], dates[int(.80*len(dates))]
    observed = d.date >= dates[0]+pd.Timedelta(days=27)
    eligible = d.target.notna() & observed
    horizon_end = d.date+pd.Timedelta(days=HORIZON)
    return (eligible & (horizon_end < train_end),
            eligible & (d.date >= train_end) & (horizon_end < test_start),
            eligible & (d.date >= test_start))


def rules(x):
    coverage = (x.on_hand+.35*x.pending)/np.maximum(x.mean_demand, .15)
    return np.exp(-coverage/7).to_numpy()


def evaluate(y, score, threshold):
    prediction = score >= threshold
    top = np.argsort(-score, kind="stable")[:max(1, len(score)//20)]
    tn, fp, fn, tp = confusion_matrix(y, prediction, labels=[0, 1]).ravel()
    diverse = np.unique(y).size > 1
    return dict(pr_auc=average_precision_score(y, score) if np.any(y) else np.nan,
                roc_auc=roc_auc_score(y, score) if diverse else np.nan,
                precision=precision_score(y, prediction, zero_division=0),
                recall=recall_score(y, prediction, zero_division=0),
                f1=f1_score(y, prediction, zero_division=0), brier=brier_score_loss(y, score),
                precision_at_5pct=float(np.mean(y[top])), recall_at_5pct=float(np.sum(y[top])/max(1,np.sum(y))),
                tn=tn, fp=fp, fn=fn, tp=tp, observations=len(y), prevalence=float(np.mean(y)))


def train(tables, output):
    d, x = prepare(tables)
    tr, va, te = partitions(d)
    models = {
        "logistic": make_pipeline(StandardScaler(), LogisticRegression(max_iter=400)),
        "forest": RandomForestClassifier(n_estimators=60, max_depth=10, min_samples_leaf=15, n_jobs=2, random_state=42),
        "lightgbm_15": LGBMClassifier(n_estimators=100, num_leaves=15, n_jobs=2, random_state=42, verbosity=-1),
        "lightgbm_31": LGBMClassifier(n_estimators=100, num_leaves=31, n_jobs=2, random_state=42, verbosity=-1),
    }
    y = d.target.fillna(False).astype(int).to_numpy()
    validation, scorers = {}, {"rules": rules}
    for name, model in models.items():
        model.fit(x[tr], y[tr])
        scorers[name] = lambda values, fitted=model: fitted.predict_proba(values)[:, 1]
    for name, score in scorers.items():
        v = score(x[va])
        p, r, thresholds = precision_recall_curve(y[va], v)
        threshold = thresholds[np.argmax(2*p[:-1]*r[:-1]/np.maximum(p[:-1]+r[:-1], 1e-12))]
        validation[name] = (average_precision_score(y[va], v), threshold)
    selected = max(models, key=lambda name: validation[name][0])
    results, groups = [], []
    holdout = d.loc[te].reset_index(drop=True)
    for name, score in scorers.items():
        ap, threshold = validation[name]
        predictions = score(x[te])
        results.append(dict(model=name, selected=name == selected, validation_ap=ap, threshold=threshold,
                            **evaluate(y[te], predictions, threshold)))
        if name != selected:
            continue
        holdout["risk"] = predictions
        holdout["alert"] = predictions >= threshold
        for column in ["site", "category", "disrupted"]:
            for group, indices in holdout.groupby(column).indices.items():
                groups.append(dict(dimension=column, segment=group,
                                   **evaluate(y[te][indices], predictions[indices], threshold)))
    pd.DataFrame(results).to_csv(output/"metrics.csv", index=False)
    pd.DataFrame(groups).to_csv(output/"segments.csv", index=False)
    holdout.to_parquet(output/"predictions.parquet", index=False)
    calibration = holdout.assign(bin=pd.cut(holdout.risk, np.linspace(0,1,11), include_lowest=True))
    calibration.groupby("bin", observed=True).agg(risk=("risk","mean"), actual=("target","mean"),
                                                  count=("target","size")).to_csv(output/"calibration.csv")
    decisive = x.loc[te].sample(n=min(3500, sum(te)), random_state=42)
    importance = permutation_importance(models[selected], decisive, y[decisive.index],
                                        scoring="average_precision", n_repeats=3, random_state=42)
    pd.DataFrame(dict(feature=FEATURES, ap_drop=importance.importances_mean,
                      sd=importance.importances_std)).sort_values("ap_drop", ascending=False).to_csv(output/"importance.csv", index=False)
    joblib.dump(models[selected], output/"model.joblib")
    return models[selected], pd.Timestamp(holdout.date.min())
