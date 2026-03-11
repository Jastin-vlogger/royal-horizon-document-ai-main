from src.core.shipment_calculations import _compute_price_reconciliation

lpo = {"unit": "47.5", "packaging": "50 KG"}
pi = {"price_per_mton": "955.0"}
print(_compute_price_reconciliation(lpo, pi))
