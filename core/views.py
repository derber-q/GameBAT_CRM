from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


@login_required
def home(request):
    destinations = (
        (("catalog.view_cd", "catalog.view_tech"), "catalog:warehouse"),
        (("supplies.view_supply",), "supplies:list"),
        (("consignment.view_cdconsignmentstock", "consignment.view_techconsignmentstock"), "consignment:list"),
        (("partners.view_supplier",), "partners:list"),
    )
    for permissions, url_name in destinations:
        if request.user.is_superuser or any(request.user.has_perm(p) for p in permissions):
            return redirect(url_name)
    return render(request, "core/no_access.html")


def permission_denied(request, exception=None):
    return render(request, "403.html", status=403)
