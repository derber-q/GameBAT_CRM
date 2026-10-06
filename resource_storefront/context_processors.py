from .modes import mode_for


def storefront_context(request):
    retail = mode_for(request) == "retail"
    return {"is_retail": retail, "storefront_mode": "retail" if retail else "wholesale",
            "storefront_draft_owner": request.session.get("retailer_visitor", "") if retail else request.session.get("resource_contact_id", "")}
