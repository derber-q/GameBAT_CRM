from django.shortcuts import render

from core.decorators import permission_required_any
from .models import Platform, ProductType


@permission_required_any("catalog.view_cd", "catalog.view_tech")
def warehouse(request):
    can_view_cd = request.user.is_superuser or request.user.has_perm("catalog.view_cd")
    can_view_tech = request.user.is_superuser or request.user.has_perm("catalog.view_tech")
    cd_groups = Platform.objects.prefetch_related("cds") if can_view_cd else []
    tech_groups = ProductType.objects.prefetch_related("tech_items__brand") if can_view_tech else []
    return render(request, "catalog/warehouse.html", {"cd_groups": cd_groups, "tech_groups": tech_groups})
