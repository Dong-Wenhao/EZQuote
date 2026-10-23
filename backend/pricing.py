"""Explainable historical statistics and decimal pricing, always subject to owner approval."""
import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN

from .business import get_business, historical_rows, number
from .catalog import CatalogError, amount, compact
from .requirements import resolve_area, understand
from .store import dumps, now


def ensure_stock(items, business):
    quantities = {}
    for item in items:
        quantities[item["sku"]] = quantities.get(item["sku"], Decimal(0)) + Decimal(item["quantity"])
    for sku, qty in quantities.items():
        inv = business["inventory"].get(sku)
        if not inv or Decimal(inv["stock"]) < qty:
            raise CatalogError(f"Insufficient or unknown inventory for {sku}; required {qty}")


def totals(recommendation, discount_pct, freight):
    pct = number(discount_pct, "discount_pct", maximum=100)
    fee = number(freight, "freight")
    if -pct.as_tuple().exponent > 2 or -fee.as_tuple().exponent > 2:
        raise CatalogError("Discount and freight accept at most two decimal places")
    if pct > Decimal(recommendation["max_discount_pct"]):
        raise CatalogError("Discount exceeds the shop maximum discount rule")
    original = Decimal(recommendation["original_product_price"])
    discount = Decimal(amount(original * pct / 100))
    final = Decimal(amount(original - discount + fee))
    cost = Decimal(recommendation["estimated_product_cost"]) + Decimal(recommendation["estimated_delivery_cost"])
    minimum = Decimal(recommendation["min_margin_pct"])
    margin = (final - cost) / final * 100 if final > 0 else Decimal(-100)
    if final <= 0 or margin < minimum:
        raise CatalogError("Final price is below the shop minimum gross margin rule")
    return {"discount_pct": amount(pct), "discount_amount": amount(discount), "freight": amount(fee),
            "final_total": amount(final), "estimated_margin_pct": amount(margin)}


def recommend(store, db, items, inquiry, area, fulfilment, exclude_quote=None):
    business = get_business(store, db)
    if not business["configured"]:
        raise CatalogError("Import the complete business workbook before using historical pricing")
    catalog = store.catalog(db)
    if catalog["id"] != business["catalog_id"]:
        raise CatalogError("The catalog changed. Import an aligned complete business workbook first")
    ensure_stock(items, business)
    if fulfilment not in {"delivery", "pickup"}:
        raise CatalogError("Choose delivery or pickup")
    rule = resolve_area(area, business) if fulfilment == "delivery" else None
    if fulfilment == "delivery" and not rule:
        raise CatalogError("A configured delivery area is required; otherwise choose pickup")
    area = rule["area"] if rule else ""
    original = sum(Decimal(i["line_total"]) for i in items)
    if any(not i.get("unit_cost") for i in items):
        raise CatalogError("Unit costs are required to check the minimum margin")
    product_cost = sum(Decimal(i["unit_cost"]) * Decimal(i["quantity"]) for i in items)
    quantity = {}
    for item in items:
        quantity[item["sku"]] = quantity.get(item["sku"], Decimal(0)) + Decimal(item["quantity"])
    history = historical_rows(store, db, exclude_quote)
    grouped = {}
    for row in history:
        grouped.setdefault(row["order_id"], []).append(row)
    def similar(rows):
        # Compare the complete selected basket, never independent line conversions.
        previous = {}
        for row in rows:
            previous[row["sku"]] = previous.get(row["sku"], Decimal(0)) + Decimal(row["quantity"])
        return set(previous) == set(quantity) and all(qty / 2 <= previous[sku] <= qty * 2 for sku, qty in quantity.items())
    similar_orders = [rows for rows in grouped.values() if similar(rows) and rows[0]["outcome"] in {"won", "lost"}]
    local = [rows for rows in similar_orders if compact(rows[0]["area"]) == compact(area)]
    matched = local or similar_orders
    won = [rows for rows in matched if rows[0]["outcome"] == "won"]
    closed_count = len(matched)
    conversion = Decimal(len(won)) / closed_count if closed_count else None
    average_discount = sum(Decimal(rows[0]["discount_pct"]) for rows in won) / len(won) if won else Decimal(0)
    area_orders = [rows for rows in grouped.values() if rows[0]["outcome"] == "won" and rows[0].get("delivery_cost_known", True) and compact(rows[0]["area"]) == compact(area)] if rule else []
    freight_cost = (sum(Decimal(rows[0]["delivery_cost"]) for rows in area_orders) / len(area_orders)) if area_orders else Decimal(rule["cost"] if rule else 0)
    base_fee = Decimal(rule["base_fee"] if rule else 0)
    since = date.today() - timedelta(days=business["rules"]["sales_window_days"])
    sales = {sku: sum(Decimal(h["quantity"]) for h in history if h["sku"] == sku and h["outcome"] == "won" and h["date"] >= since.isoformat()) for sku in quantity}
    high = all(Decimal(business["inventory"][sku]["stock"]) >= Decimal(business["inventory"][sku]["high_stock"]) for sku in quantity)
    low = any(Decimal(business["inventory"][sku]["stock"]) <= Decimal(business["inventory"][sku]["low_stock"]) for sku in quantity)
    enough = closed_count >= business["rules"]["minimum_similar_orders"] and bool(won)
    discount = Decimal(amount(average_discount)) if enough else Decimal(0)
    if enough and high and conversion < Decimal("0.5"):
        discount += 1
    if low:
        discount = Decimal(0)
    discount = min(discount, Decimal(business["rules"]["max_discount_pct"]))
    subsidy = Decimal(business["rules"]["max_delivery_subsidy"]) if rule and high and enough else Decimal(0)
    fee = max(Decimal(0), freight_cost - subsidy) if area_orders else base_fee
    if not rule:
        fee = freight_cost = Decimal(0)
    min_margin = Decimal(business["rules"]["min_margin_pct"])
    # Clip the discount downward before exposing a recommendation that meets policy.
    required_revenue = (product_cost + freight_cost) / (1 - min_margin / 100)
    max_discount_amount = original + fee - required_revenue
    permitted_pct = max(Decimal(0), max_discount_amount / original * 100)
    clipped = min(discount, permitted_pct).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    rec = {"engine": "local_statistics_v1", "business_version": business["id"], "catalog_id": catalog["id"],
           "generated_at": now(), "original_product_price": amount(original), "base_freight": amount(base_fee),
           "original_total": amount(original + base_fee), "suggested_discount_pct": amount(clipped),
           "suggested_freight": amount(fee), "estimated_product_cost": amount(product_cost),
           "estimated_delivery_cost": amount(freight_cost), "min_margin_pct": amount(min_margin),
           "max_discount_pct": business["rules"]["max_discount_pct"], "similar_orders": closed_count,
           "similar_won": len(won), "conversion_rate": str(conversion.quantize(Decimal("0.0001"))) if conversion is not None else None,
           "historical_average_discount_pct": amount(average_discount), "area_cost_orders": len(area_orders),
           "sales_window_days": business["rules"]["sales_window_days"], "recent_sales": {k: str(v) for k, v in sales.items()},
           "stock_levels": {sku: business["inventory"][sku] for sku in quantity},
           "confidence": "medium" if enough and (not rule or len(area_orders) >= 3) else "low",
           "history_scope": "same_basket_quantity_and_area" if local else "same_basket_quantity", "reasons": {"zh": [], "en": [], "ms": []}}
    def reason(zh, en, ms):
        for lang, message in [("zh", zh), ("en", en), ("ms", ms)]:
            rec["reasons"][lang].append(message)
    if enough:
        rate = amount(conversion * 100)
        reason(f"类似订单 {closed_count} 笔，成交 {len(won)} 笔，转化率 {rate}%；成交订单平均折扣 {amount(average_discount)}%。",
               f"{closed_count} similar closed orders, {len(won)} won, conversion {rate}%; average winning discount {amount(average_discount)}%.",
               f"{closed_count} pesanan serupa selesai, {len(won)} berjaya, kadar {rate}%; purata diskaun berjaya {amount(average_discount)}%.")
    else:
        reason("类似成交样本不足，折扣默认 0%，建议置信度低。", "Too few similar wins: default discount is 0%; confidence is low.", "Sampel berjaya tidak mencukupi: diskaun lalai 0%; keyakinan rendah.")
    if not local and similar_orders:
        reason("本地区样本不足，折扣参考其他地区的相同商品组合；运费只参考本地区。", "No local basket sample: discount uses the same basket in other areas; freight uses only this area.", "Tiada sampel setempat: diskaun merujuk bakul sama di kawasan lain; kos penghantaran kekal setempat.")
    for sku, inv in rec["stock_levels"].items():
        reason(f"{sku} 库存 {inv['stock']}；近 {rec['sales_window_days']} 天成交销量 {sales[sku]}。库存" + ("偏高。" if high else "偏低，保留原价。" if low else "正常。"),
               f"{sku}: stock {inv['stock']}; {sales[sku]} units won in {rec['sales_window_days']} days. Stock is " + ("high." if high else "low; retain list price." if low else "normal."),
               f"{sku}: stok {inv['stock']}; {sales[sku]} unit berjaya dalam {rec['sales_window_days']} hari. Stok " + ("tinggi." if high else "rendah; kekalkan harga asal." if low else "biasa."))
    if rule:
        reason(f"{area} 历史配送成本 RM{amount(freight_cost)}（{len(area_orders)} 笔成交）；基础运费 RM{amount(base_fee)}，本次配送补贴 RM{amount(subsidy) if area_orders else '0.00'}。",
               f"{area}: delivery cost RM{amount(freight_cost)} from {len(area_orders)} wins; base fee RM{amount(base_fee)}; subsidy RM{amount(subsidy) if area_orders else '0.00'}.",
               f"{area}: kos RM{amount(freight_cost)} daripada {len(area_orders)} pesanan berjaya; fi asas RM{amount(base_fee)}; subsidi RM{amount(subsidy) if area_orders else '0.00'}.")
    if clipped < discount:
        reason("折扣已按最低毛利规则下调。", "Discount reduced to respect the minimum gross margin.", "Diskaun dikurangkan untuk mematuhi margin kasar minimum.")
    result = totals(rec, rec["suggested_discount_pct"], rec["suggested_freight"])
    rec.update(suggested_discount_amount=result["discount_amount"], recommended_total=result["final_total"], estimated_margin_pct=result["estimated_margin_pct"])
    extracted = understand(inquiry, catalog["products"], business, area, fulfilment)["requirement"]
    extracted["selected_items"] = [{"sku": i["sku"], "quantity": i["quantity"], "unit": i["unit"]} for i in items]
    return {"requirement": extracted, "recommendation": rec, "decision": None}


def save_pricing(store, db, quote, items, inquiry, area, fulfilment, reviewed=None):
    pricing = recommend(store, db, items, inquiry, area, fulfilment, quote["id"])
    if reviewed:
        pricing["requirement"] = {**reviewed["effective"], "selected_items": [{"sku": i["sku"], "quantity": i["quantity"], "unit": i["unit"]} for i in items],
                                  "review_id": reviewed["review_id"], "parser_version": reviewed["parser_version"], "resolutions": reviewed["resolutions"]}
    db.execute("INSERT INTO quote_pricing(quote_id,revision,requirement,recommendation) VALUES(?,?,?,?)",
               (quote["id"], quote["revision"], dumps(pricing["requirement"]), dumps(pricing["recommendation"])))
    return pricing


def get_pricing(db, quote_id, revision):
    row = db.execute("SELECT * FROM quote_pricing WHERE quote_id=? AND revision=?", (quote_id, revision)).fetchone()
    return {"requirement": json.loads(row["requirement"]), "recommendation": json.loads(row["recommendation"]),
            "decision": json.loads(row["decision"]) if row["decision"] else None} if row else None
