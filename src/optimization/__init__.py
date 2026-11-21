"""Bounded marginal-cost dispatch and purchase heuristic."""
import numpy as np
from src.model import features


def recommend(observed, products, sites, vendors, routes, scenario, baseline, model=None, allow_transfers=True):
    stock, pending = observed["on_hand"], observed["pending"]
    mean = observed["mean_demand"]
    promised = vendors.promised.to_numpy()[products.supplier]
    n_sites, n_skus = stock.shape
    site, sku = np.indices(stock.shape)
    capacity = sites.capacity.to_numpy()
    if model is None:
        risk = np.clip(1-stock/np.maximum(1, mean*8), 0, 1)
    else:
        x = features(observed["date"], site.ravel(), products.category.to_numpy()[sku.ravel()],
                     stock.ravel(), pending.ravel(), mean.ravel(), observed["demand_sd"].ravel(),
                     observed["stockout_rate"].ravel(),
                     observed["supplier_otd"][products.supplier.to_numpy()[sku.ravel()]],
                     observed["supplier_sd"][products.supplier.to_numpy()[sku.ravel()]],
                     observed["next_promo"][sku.ravel()], capacity[site.ravel()], promised[sku.ravel()],
                     observed["open_po"].ravel(), observed["due_week"].ravel())
        risk = model.predict_proba(x)[:, 1].reshape(stock.shape)
    room = capacity-(stock+pending).sum(axis=1)
    position = stock+pending
    donor = np.maximum(0, stock-np.ceil(mean*9)).astype(int)
    arriving = np.zeros_like(stock)
    actions = []
    candidates = []
    penalty = products.penalty.to_numpy()*scenario.penalty
    holding = products.holding.to_numpy()*scenario.holding
    for route in routes.itertuples(index=False) if allow_transfers else ():
        a, b, lead = route.source, route.destination, route.transit_days
        benefit = risk[b]*penalty*(1-lead/14)-route.unit_freight*scenario.freight-holding*7
        shortage = np.maximum(0, np.ceil(mean[b]*(lead+5))-position[b]).astype(int)
        viable = np.flatnonzero((benefit > 0) & (donor[a] > 0) & (shortage > 0) & (room[b] > 0))
        candidates.extend((benefit[k], a, b, k, shortage[k]) for k in viable)
    for _, source, destination, sku_id, shortage in sorted(candidates, reverse=True):
        qty = min(donor[source, sku_id], shortage-arriving[destination, sku_id], room[destination], 120)
        if qty > 0:
            actions.append((source, destination, sku_id, int(qty)))
            donor[source, sku_id] -= qty
            room[destination] -= qty
            room[source] += qty
            arriving[destination, sku_id] += qty
    remaining_stock = stock - (np.maximum(0, stock-np.ceil(mean*9)).astype(int)-donor)
    position = remaining_stock+pending+arriving
    target = np.ceil(mean*(promised+6+5*risk+observed["supplier_sd"][products.supplier]))
    needed = np.maximum(0, target-position).astype(int)
    needed[position > mean*(promised+2+3*risk)] = 0
    purchase = np.zeros_like(stock)
    priority = risk*penalty*.5-holding*7-.19
    for location in range(n_sites):
        for item in np.argsort(-priority[location], kind="stable"):
            if priority[location, item] <= 0 or room[location] <= 0:
                break
            qty = min(needed[location, item], room[location], 120)
            purchase[location, item] = qty
            room[location] -= qty
    return actions, purchase
