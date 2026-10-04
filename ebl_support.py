"""Supporter-plan public configuration. Payment verification remains in server.py.
"""
import os

# recurring Supporter subscriptions are configured at deploy time.
# Checkout stays on Stripe-hosted pages; EBL attaches a one-time account reference
# and grants access only after signed Stripe webhooks confirm the subscription.
def _safe_support_url(value):
    value=str(value or "").strip()
    return value if value.startswith(("https://","http://")) else ""








def stripe_support_plans():
    currency=str(os.environ.get("EBL_STRIPE_EXPECTED_CURRENCY","usd") or "usd").strip().lower()
    mode=str(os.environ.get("EBL_STRIPE_MODE","test") or "test").strip().lower()
    monthly={
        "key":"monthly",
        "label":"Monthly",
        "url":_safe_support_url(os.environ.get("EBL_SUPPORT_MONTHLY_URL","")),
        "payment_link_id":str(os.environ.get("EBL_STRIPE_MONTHLY_PAYMENT_LINK_ID","") or "").strip(),
        "price_id":str(os.environ.get("EBL_STRIPE_MONTHLY_PRICE_ID","") or "").strip(),
        "amount":int(os.environ.get("EBL_STRIPE_MONTHLY_AMOUNT","500") or 500),
        "currency":currency,
        "interval":"month"
    }
    yearly={
        "key":"yearly",
        "label":"Yearly",
        "url":_safe_support_url(os.environ.get("EBL_SUPPORT_YEARLY_URL","")),
        "payment_link_id":str(os.environ.get("EBL_STRIPE_YEARLY_PAYMENT_LINK_ID","") or "").strip(),
        "price_id":str(os.environ.get("EBL_STRIPE_YEARLY_PRICE_ID","") or "").strip(),
        "amount":int(os.environ.get("EBL_STRIPE_YEARLY_AMOUNT","5400") or 5400),
        "currency":currency,
        "interval":"year"
    }
    return {"monthly":monthly,"yearly":yearly,"mode":mode}








def support_public_config():
    plans=stripe_support_plans()
    provider=str(os.environ.get("EBL_SUPPORT_PROVIDER","Stripe").strip() or "Stripe")[:40]
    portal_url=_safe_support_url(os.environ.get("EBL_SUPPORT_PORTAL_URL",""))
    available={}
    for key in ("monthly","yearly"):
        p=plans[key]
        if p["url"] and p["payment_link_id"]:
            available[key]={
                "label":p["label"],
                "price_usd":round(max(0,p["amount"])/100,2),
                "interval":p["interval"]
            }
    monthly_amt=int(plans["monthly"]["amount"])
    yearly_amt=int(plans["yearly"]["amount"])
    full_year=monthly_amt*12
    savings=max(0,full_year-yearly_amt)
    savings_pct=round((savings/full_year)*100) if full_year else 0
    return {
        "enabled":bool(available),
        "provider":provider,
        "checkout_path":"/api/support/checkout" if available else "",
        "verified_checkout":bool(available),
        "mode":"test" if plans["mode"]=="test" else ("live" if plans["mode"]=="live" else ""),
        "plans":available,
        "yearly_savings_usd":round(savings/100,2),
        "yearly_savings_pct":savings_pct,
        "portal_url":portal_url,
        "currency":"USD"
    }
