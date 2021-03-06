import collections
from functools import reduce
from typing import AnyStr, Dict, List, Optional, Type

from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.urls import NoReverseMatch, reverse

from backoffice_extensions.helpers import create_csv_from_data
from backoffice_extensions.settings import (
    PRIMARY_BG_COLOR,
    PRIMARY_COLOR,
    TITLE,
    URL_NAMESPACE,
)


class BackOfficeViewMixin:
    uses_temaplate: bool = True
    template_name: AnyStr = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.template_name and self.uses_temaplate:
            raise NotImplementedError("You should specify the template_name attribute.")

    def get_extra_context(self) -> Dict:
        """Adds default context to the backoffice views. Overwrite to add more
        context to the view.
        """
        try:
            index_url = reverse(f"{URL_NAMESPACE}:index")
        except NoReverseMatch:
            index_url = ""
        try:
            sign_out = reverse(f"{URL_NAMESPACE}:sign-out")
        except NoReverseMatch:
            sign_out = ""
        try:
            sign_in = reverse(f"{URL_NAMESPACE}:sign-in")
        except NoReverseMatch:
            sign_in = ""
        return {
            "backoffice_title": TITLE,
            "backoffice_primary_bg_color": PRIMARY_BG_COLOR,
            "backoffice_primary_color": PRIMARY_COLOR,
            "index_url": index_url,
            "sign_out": sign_out,
            "sign_in": sign_in,
        }


class SearchListMixin:
    """Mixin to add search functionality to default ListView
    Django view."""

    search_param: AnyStr = "search"
    search_fields: List = []

    def _search_filter(self, queryset) -> models.QuerySet:
        """Applies search filtering to queryset."""
        search_query = self.request.GET.get(self.search_param)
        if search_query:
            queryset_filter = [
                Q(**{f"{search_field}__icontains": search_query})
                for search_field in self.search_fields
            ]
            if queryset_filter:
                queryset = queryset.filter(reduce(lambda x, y: x | y, queryset_filter))
        return queryset

    def get_queryset(self) -> models.QuerySet:
        """Checks the 'search' variable to allow generic search."""
        queryset = super().get_queryset()
        queryset = self._search_filter(queryset)
        return queryset

    def get_extra_context(self) -> Dict:
        """Adds search data."""
        context: Dict = super().get_extra_context()
        context[self.search_param] = self.request.GET.get(self.search_param, "")
        parameters = self.request.GET.copy()
        parameters = parameters.pop(self.page_kwarg, True) and parameters.urlencode()
        context["parameters"] = parameters
        return context


class ExportMixin:
    """Mixin to allow export CSV data."""

    filename: AnyStr = "data.csv"
    queryset: models.QuerySet = None
    filterset_class = None
    fields: List = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.queryset:
            raise NotImplementedError("You should specify the queryset attribute.")

    def get_csv_response(self, data):
        response = HttpResponse(content_type="text/csv")
        response[
            "Content-Disposition"
        ] = f'attachment; filename="{self.get_filename()}"'
        create_csv_from_data(data, stream=response)
        return response

    def get_filename(self) -> AnyStr:
        return self.filename

    def get_queryset(self) -> models.QuerySet:
        return self.queryset

    def get(self, request, *args, **kwargs):
        items: models.QuerySet = self.get_queryset()
        if self.filterset_class:
            _filter = self.filterset_class(request.GET, queryset=items)
            items = _filter.qs
        fields: List = [
            field[0] if isinstance(field, tuple) else field for field in self.fields
        ]
        if "id" not in fields:
            fields = ["id"] + fields
        data: collections.OrderedDict = collections.OrderedDict()
        for field in fields:
            data[field] = []
        for item in items.iterator():
            for field in fields:
                value = getattr(item, field)
                if hasattr(value, "__call__"):
                    value = value()
                data[field].append(value)
        return self.get_csv_response(data=data)
