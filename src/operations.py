"""Chronological unit ledger and common-random-number scenario inputs."""
from dataclasses import dataclass
import numpy as np
import pandas as pd

START = pd.Timestamp("2024-01-01")
SITES = 5


@dataclass(frozen=True)
class Scenario:
    growth: float = 1
    delay: int = 0
    freight: float = 1
    capacity: float = 1
    penalty: float = 1
    volatility: float = 1
    holding: float = 1

    def __post_init__(self):
        if min(self.growth, self.freight, self.capacity, self.penalty,
               self.volatility, self.holding) <= 0 or self.delay < 0:
            raise ValueError("Scenario multipliers must be positive and delays nonnegative")


def master(skus: int, suppliers: int = 25):
    rng = np.random.default_rng(902)
    categories = pd.DataFrame({"category": range(5), "name": ["Beverages", "Snacks", "Pantry", "Household", "Personal care"]})
    products = pd.DataFrame({
        "sku": range(skus), "category": np.arange(skus) % 5,
        "supplier": np.arange(skus) % suppliers,
        "unit_cost": rng.uniform(2, 18, skus).round(2),
        "rate": rng.uniform(1, 9, skus).round(2),
        "intermittent": rng.random(skus) < .15,
    })
    products["penalty"] = (products.unit_cost * rng.uniform(.4, 1.8, skus)).round(2)
    products["holding"] = products.unit_cost * .27 / 365
    sites = pd.DataFrame({"site": range(SITES), "name": ["Seattle", "Ontario", "Dallas", "Columbus", "Allentown"]})
    sites["capacity"] = (skus * np.array([115, 155, 170, 140, 130])).astype(int)
    vendors = pd.DataFrame({"supplier": range(suppliers), "promised": rng.integers(4, 12, suppliers),
                            "reliability": rng.uniform(.55, .97, suppliers)})
    routes = pd.DataFrame([(a, b, 1 + abs(a-b), .35 + .23*abs(a-b))
                           for a in range(SITES) for b in range(SITES) if a != b],
                          columns=["source", "destination", "transit_days", "unit_freight"])
    return products, sites, vendors, categories, routes


def inputs(seed, start, days, products, vendors, scenario):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=days)
    size = len(products)
    season = (1 + .23*np.sin(dates.dayofyear.to_numpy()*2*np.pi/365)
              + .16*np.isin(dates.dayofweek, [4, 5]))
    regional = np.array([.78, 1.2, 1.12, .93, 1.04])[None, :, None]
    affinity = np.random.default_rng(251).uniform(.65, 1.38, (1, SITES, size))
    promotions = np.random.default_rng(112).random((days, size)) < .035
    shared = np.exp(rng.normal(0, .20*scenario.volatility, days))
    rates = (season[:, None, None] * regional * affinity * products.rate.to_numpy()
             * (1 + .95*promotions[:, None, :]) * shared[:, None, None] * scenario.growth)
    intermittent = np.where(products.intermittent, rng.random(rates.shape) < .28, True)
    demand = rng.poisson(rates * intermittent)
    disruptions = rng.random((days, len(vendors))) < .045
    late = rng.random(rates.shape) > vendors.reliability.to_numpy()[products.supplier]
    delay = (late*rng.integers(1, 7, rates.shape)
             + disruptions[:, products.supplier][:, None, :]*6 + scenario.delay)
    lane_delays = np.random.default_rng(seed+181).choice([0, 1, 2], (days, SITES, SITES), p=[.91,.07,.02])
    return dates, demand, promotions, disruptions, delay, lane_delays


def simulate(*, seed=42, start=START, days=548, skus=150, suppliers=25,
             scenario=Scenario(), decision=None, initial=None):
    products, sites, vendors, categories, routes = master(skus, suppliers)
    dates, demands, promos, disruptions, late, lane_delays = inputs(seed, start, days, products, vendors, scenario)
    cap = np.maximum(1, (sites.capacity.to_numpy()*scenario.capacity).astype(int))
    sites["capacity"] = cap
    supplier = products.supplier.to_numpy()
    promised = vendors.promised.to_numpy()[supplier]
    rate = products.rate.to_numpy()
    shape = (SITES, skus)
    stock = np.tile(np.ceil(rate*10).astype(int), (SITES, 1)) if initial is None else initial.copy()
    if (stock < 0).any() or (stock.sum(axis=1) > cap).any():
        raise ValueError("Invalid initial stock for scenario capacity")
    pending = np.zeros(shape, dtype=int)
    purchase_queue, transfer_queue = {}, {}
    open_orders = []
    orders, receipts, transfers, daily = [], [], [], []
    demand_history, lost_history = [], []
    vendor_count = np.zeros(suppliers)
    vendor_ontime = np.zeros(suppliers)
    vendor_days = np.zeros(suppliers)
    vendor_days_sq = np.zeros(suppliers)
    site_index, sku_index = np.indices(shape)
    sku_cost = products.unit_cost.to_numpy()
    penalty = products.penalty.to_numpy()*scenario.penalty
    for day, date in enumerate(dates):
        opening = stock.copy()
        received, inbound, outbound = (np.zeros(shape, int) for _ in range(3))
        for order_id, site, sku, qty, order_day, due in purchase_queue.pop(day, ()):
            received[site, sku] += qty
            receipts.append((order_id, date, qty, day-order_day))
            vendor = supplier[sku]
            vendor_count[vendor] += 1
            vendor_ontime[vendor] += day <= due
            vendor_days[vendor] += day-order_day
            vendor_days_sq[vendor] += (day-order_day)**2
        for destination, sku, units in transfer_queue.pop(day, ()):
            inbound[destination, sku] += units
        arrivals = received + inbound
        stock += arrivals
        pending -= arrivals
        actual = demands[day]
        fulfilled = np.minimum(stock, actual)
        stock -= fulfilled
        lost = actual - fulfilled
        demand_history.append(actual)
        lost_history.append(lost > 0)
        mean = np.mean(demand_history[-28:], axis=0)
        std = np.std(demand_history[-28:], axis=0)
        frequency = np.mean(lost_history[-28:], axis=0)
        mean_lt = vendor_days / np.maximum(1, vendor_count)
        sd_lt = np.sqrt(np.maximum(0, vendor_days_sq/np.maximum(1, vendor_count) - mean_lt**2))
        open_orders = [(due, arrival, site, sku, qty) for due, arrival, site, sku, qty in open_orders
                       if arrival > day]
        open_po = np.zeros(shape, dtype=int)
        due_week = np.zeros(shape, dtype=int)
        for due, _, site, sku, qty in open_orders:
            open_po[site, sku] += qty
            if due <= day+7:
                due_week[site, sku] += qty
        observed = {"open_po": open_po, "due_week": due_week,"on_hand": stock.copy(), "pending": pending.copy(), "mean_demand": mean,
                    "demand_sd": std, "stockout_rate": frequency,
                    "supplier_otd": (vendor_ontime+3)/(vendor_count+4),
                    "supplier_sd": sd_lt, "date": date,
                    "next_promo": promos[day+1] if day+1 < days else np.zeros(skus, bool)}
        baseline = np.maximum(0, np.ceil(rate*(promised+8)) - stock - pending).astype(int)
        baseline[(stock + pending) > rate*(promised+2)] = 0
        actions, buy_target = ([], baseline) if decision is None else decision(
            observed, products, sites, vendors, routes, scenario, baseline)
        freight_cost = np.zeros(shape)
        for source, destination, sku, qty in actions:
            route_days = 1 + abs(source-destination)
            if not (source != destination and 0 < qty <= stock[source, sku]
                    and (stock[destination]+pending[destination]).sum()+qty <= cap[destination]):
                raise ValueError("Infeasible transfer")
            outbound[source, sku] += qty
            stock[source, sku] -= qty
            pending[destination, sku] += qty
            arrival = day + route_days + int(lane_delays[day, source, destination])
            transfer_queue.setdefault(arrival, []).append((destination, sku, qty))
            cost = qty*(.35+.23*abs(source-destination))*scenario.freight
            freight_cost[source, sku] += cost
            transfers.append((len(transfers), source, destination, sku, date,
                              date+pd.Timedelta(days=route_days),
                              date+pd.Timedelta(days=int(arrival-day)), qty, cost))
        purchased = np.zeros(shape, int)
        for site in range(SITES):
            room = cap[site] - (stock[site]+pending[site]).sum()
            for sku in np.flatnonzero(buy_target[site] > 0):
                qty = int(min(room, buy_target[site, sku], 120))
                if qty <= 0:
                    break
                due = day+int(promised[sku])
                arrive = due+int(late[day, site, sku])
                order_id = len(orders)
                orders.append((order_id, site, sku, int(supplier[sku]), date,
                               date+pd.Timedelta(days=due-day), qty))
                purchase_queue.setdefault(arrive, []).append((order_id, site, sku, qty, day, due))
                open_orders.append((due, arrive, site, sku, qty))
                purchased[site, sku] = qty
                pending[site, sku] += qty
                room -= qty
        data = dict(date=date, site=site_index.ravel(), sku=sku_index.ravel(),
                    **{name: array.ravel() for name, array in {
                        "opening": opening, "received": received, "inbound": inbound, "outbound": outbound,
                        "demand": actual, "fulfilled": fulfilled, "lost": lost, "closing": stock,
                        "purchased": purchased, "position": stock+pending, "pending": pending,
                        "pre_order_stock": observed["on_hand"], "pre_order_pending": observed["pending"],
                        "open_po_units": open_po, "due_week_units": due_week,
                        "mean_demand": mean, "demand_sd": std, "stockout_rate": frequency,
                        "holding_cost": stock*products.holding.to_numpy()*scenario.holding,
                        "lost_cost": lost*penalty, "transfer_cost": freight_cost,
                        "purchase_fee": purchased*.19, "purchase_spend": purchased*sku_cost,
                        "inventory_value": stock*sku_cost}.items()})
        for name, array in {"supplier_otd": observed["supplier_otd"][supplier],
                            "supplier_sd": sd_lt[supplier], "next_promo": observed["next_promo"],
                            "disrupted": disruptions[day, supplier]}.items():
            data[name] = np.tile(array, SITES)
        daily.append(pd.DataFrame(data))
    cal = pd.DataFrame({"date": np.repeat(dates, skus), "sku": np.tile(np.arange(skus), days),
                        "promotion": promos.ravel()})
    disruption_calendar = pd.DataFrame({"date": np.repeat(dates, suppliers),
                                        "supplier": np.tile(np.arange(suppliers), days),
                                        "disruption": disruptions.ravel()})
    order_frame = pd.DataFrame(orders, columns=["order_id", "site", "sku", "supplier", "ordered", "promised", "units"])
    receipt_frame = pd.DataFrame(receipts, columns=["order_id", "received_date", "units", "lead_days"])
    transfer_frame = pd.DataFrame(transfers, columns=["transfer_id", "source", "destination", "sku",
                                                      "shipped", "promised_arrival", "arrives", "units", "cost"])
    for frame, date_columns in [(order_frame, ["ordered", "promised"]), (receipt_frame, ["received_date"]),
                                (transfer_frame, ["shipped", "promised_arrival", "arrives"])]:
        for column in date_columns:
            frame[column] = pd.to_datetime(frame[column])
        numeric = {column: "float64" if column == "cost" else "int64"
                   for column in frame.columns if column not in date_columns}
        frame[list(numeric)] = frame[list(numeric)].astype(numeric)
    return {"daily": pd.concat(daily, ignore_index=True), "products": products, "warehouses": sites,
            "suppliers": vendors, "categories": categories, "routes": routes,
            "orders": order_frame, "receipts": receipt_frame, "transfers": transfer_frame,
            "promotions": cal, "disruptions": disruption_calendar}
