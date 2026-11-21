"""Load and reconcile the operational warehouse."""
import duckdb
import numpy as np
import pandas as pd


def require(condition, description):
    if not condition:
        raise ValueError(description)


KEYS = {"daily": ["date","site","sku"], "products": ["sku"], "suppliers": ["supplier"],
        "categories": ["category"], "warehouses": ["site"], "routes": ["source","destination"],
        "orders": ["order_id"], "receipts": ["order_id"], "transfers": ["transfer_id"],
        "promotions": ["date","sku"], "disruptions": ["date","supplier"]}


def validate(tables):
    for name, keys in KEYS.items():
        frame = tables[name]
        require(not frame.isna().any().any(), f"Missing {name} fields")
        require(not frame.duplicated(keys).any(), f"Duplicate {name} keys")
    d = tables["daily"].sort_values(["site","sku","date"])
    p, w, orders = (tables[k] for k in ["products","warehouses","orders"])
    require(d.sku.isin(p.sku).all() and d.site.isin(w.site).all(), "Unknown site or SKU")
    require(p.supplier.isin(tables["suppliers"].supplier).all() and
            p.category.isin(tables["categories"].category).all(), "Unknown supplier or category")
    require((d[["opening","closing","pending","demand","fulfilled","lost","received","inbound","outbound"]] >= 0).all().all(),
            "Negative operational quantity")
    require((d.opening+d.received+d.inbound-d.fulfilled-d.outbound == d.closing).all(), "Inventory does not balance")
    require((d.demand == d.fulfilled+d.lost).all() and (d.fulfilled <= d.opening+d.received+d.inbound).all(),
            "Fulfillment does not reconcile")
    require(len(d) > 0 and len(d) == d.date.nunique()*len(p)*len(w), "Incomplete daily inventory grid")
    require((d.fulfilled == np.minimum(d.demand, d.opening+d.received+d.inbound)).all(),
            "Available units were not used to fulfill demand")
    require((d.position == d.closing+d.pending).all(), "Inventory position does not reconcile")
    pairs = d.groupby(["site","sku"])
    incoming = d.received+d.inbound
    pending_before = pairs.pending.shift(fill_value=0)-incoming
    require((pending_before >= 0).all() and d.pre_order_pending.eq(pending_before).all(),
            "Pending pipeline does not reconcile")
    previous = pairs.closing.shift()
    require((d.opening == previous.fillna(d.opening)).all(), "Opening and previous closing diverge")
    require(pairs.date.diff().dropna().eq(pd.Timedelta(days=1)).all(), "Daily ledger contains missing dates")
    utilization = d.assign(peak=d.opening+d.received+d.inbound).groupby(["site","date"])[["peak","position"]].sum()
    require(utilization.le(utilization.index.get_level_values("site").map(w.set_index("site").capacity), axis=0).all().all(),
            "Capacity exceeded")
    require(orders.site.isin(w.site).all() and orders.sku.isin(p.sku).all() and
            (orders.supplier == orders.sku.map(p.set_index("sku").supplier)).all() and
            (orders.promised > orders.ordered).all() and orders.units.between(1,120).all(), "Invalid order")
    receipts = tables["receipts"].merge(orders, how="left", on="order_id", suffixes=("", "_ordered"))
    require(((receipts.received_date >= receipts.promised) & (receipts.units == receipts.units_ordered) &
             ((receipts.received_date-receipts.ordered).dt.days == receipts.lead_days)).all(), "Invalid receipt")
    t = tables["transfers"].merge(tables["routes"], on=["source","destination"], how="left")
    if not t.empty:
        require(t.sku.isin(p.sku).all() and t.units.between(1,120).all() and
                ((t.promised_arrival-t.shipped).dt.days == t.transit_days).all() and
                (t.arrives >= t.promised_arrival).all(), "Invalid transfer")
    start, cutoff = d.date.min(), d.date.max()
    for frame, column in [(orders, "ordered"), (receipts, "received_date"), (t, "shipped")]:
        require(frame[column].between(start, cutoff).all(), f"{column} outside ledger dates")
    arrivals = t.groupby(["shipped","destination","sku"]).units.sum()
    incoming_commitment = arrivals.reindex(pd.MultiIndex.from_frame(d[["date","site","sku"]]), fill_value=0)
    require(d.pending.eq(pending_before+d.purchased+incoming_commitment.to_numpy()).all(),
            "New purchase and transfer commitments do not reconcile")
    for frame, date, site, field in [(orders,"ordered","site","purchased"),
                                      (receipts,"received_date","site","received"),
                                      (t,"shipped","source","outbound"), (t[t.arrives <= cutoff],"arrives","destination","inbound")]:
        expected = frame.groupby([date,site,"sku"]).units.sum()
        actual = d.set_index(["date","site","sku"])[field]
        require(np.array_equal(actual.to_numpy(), expected.reindex(actual.index, fill_value=0).to_numpy()),
                f"Ledger and {field} events disagree")
    require((d.demand <= 1000).all() and (d.lost_cost >= 0).all(), "Unexpected demand or cost outlier")


VIEWS = """
CREATE VIEW supplier_sku AS SELECT supplier, sku FROM products;
CREATE VIEW demand AS SELECT date, site, sku, demand FROM daily;
CREATE VIEW fulfillment AS SELECT date, site, sku, fulfilled, lost FROM daily;
CREATE VIEW supplier_lead_history AS SELECT o.*, r.received_date, r.lead_days FROM orders o JOIN receipts r USING(order_id);
CREATE VIEW stockout_events AS
  SELECT site, sku, min(date) AS started, max(date) AS ended, count(*) AS duration, sum(lost) AS lost
  FROM (SELECT *, date - row_number() OVER(PARTITION BY site,sku ORDER BY date)*INTERVAL 1 DAY AS episode
        FROM daily WHERE lost>0) GROUP BY site,sku,episode;
CREATE VIEW inventory_transactions AS
  SELECT date,site,sku,movement,units FROM daily
  UNPIVOT (units FOR movement IN (received,inbound,fulfilled,outbound)) WHERE units>0;
CREATE VIEW enriched AS
  SELECT d.*, p.category, p.supplier, p.unit_cost, w.capacity,
         sum(closing) OVER(PARTITION BY date,d.sku)-closing AS other_stock,
         greatest(0,closing-28*mean_demand)*p.unit_cost AS excess_value,
         closing/nullif(mean_demand,0) AS days_supply
  FROM daily d JOIN products p USING(sku) JOIN warehouses w USING(site);
"""


def build(tables, output, sql_dir):
    validate(tables)
    database = output/"operations.duckdb"
    if database.exists():
        database.unlink()
    references = {
        "products": ["category REFERENCES categories(category)", "supplier REFERENCES suppliers(supplier)"],
        "routes": ["source REFERENCES warehouses(site)", "destination REFERENCES warehouses(site)"],
        "daily": ["site REFERENCES warehouses(site)", "sku REFERENCES products(sku)"],
        "orders": ["site REFERENCES warehouses(site)", "sku REFERENCES products(sku)",
                   "supplier REFERENCES suppliers(supplier)"],
        "receipts": ["order_id REFERENCES orders(order_id)"],
        "transfers": ["sku REFERENCES products(sku)", "(source,destination) REFERENCES routes(source,destination)"],
        "promotions": ["sku REFERENCES products(sku)"],
        "disruptions": ["supplier REFERENCES suppliers(supplier)"],
    }
    with duckdb.connect(str(database), config={"threads": 2}) as db:
        for name in ["categories","warehouses","suppliers","products","routes","daily","orders",
                     "receipts","transfers","promotions","disruptions"]:
            db.register("incoming", tables[name])
            types = db.execute("DESCRIBE incoming").fetchall()
            fields = [f'"{col}" {dtype} NOT NULL' for col, dtype, *_ in types]
            fields.append(f"PRIMARY KEY ({','.join(KEYS[name])})")
            for reference in references.get(name, []):
                keys, target = reference.split(" REFERENCES ")
                keys = keys.strip("()")
                fields.append(f"FOREIGN KEY ({keys}) REFERENCES {target}")
            db.execute(f"CREATE TABLE {name} ({','.join(fields)})")
            db.execute(f"INSERT INTO {name} SELECT * FROM incoming")
            db.unregister("incoming")
        db.execute(VIEWS)
        for query in sorted(sql_dir.glob("*.sql")):
            db.execute(query.read_text()).df().to_csv(output/f"{query.stem}.csv", index=False)
