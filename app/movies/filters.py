from django_filters import rest_framework as filters

from .models import Movie


class MovieFilter(filters.FilterSet):
    g = filters.CharFilter(field_name="genre__id", method="filter_genre")
    dmin = filters.CharFilter(method="filter_decade_min")
    dmax = filters.CharFilter(method="filter_decade_max")
    rmin = filters.CharFilter(method="filter_runtime_min")
    rmax = filters.CharFilter(method="filter_runtime_max")

    def __init__(self, data=None, queryset=None, *, request=None, **kwargs):
        """
        If runtimes are the same (and not a boundary value), offset them so
        we can return a larger range of movies (not just that exact runtime).
        """
        runtime_offset_if_equal = 3

        if data and "rmin" in data and "rmax" in data:
            if data["rmin"] == data["rmax"] and not self._is_boundary_runtime(
                data["rmin"]
            ):
                rmin = int(data["rmin"]) - runtime_offset_if_equal
                rmax = int(data["rmax"]) + runtime_offset_if_equal
                data = {**data, "rmin": str(rmin), "rmax": str(rmax)}

        super().__init__(data=data, queryset=queryset, **kwargs)

    def filter_genre(self, queryset, name, value):
        if value:
            return queryset.filter(genre__id__in=value.split(","))
        return queryset

    def filter_decade_min(self, queryset, name, value):
        if value:
            start_decade = "1920" if value == "pre" else value
            return queryset.filter(released__gte=f"{start_decade}-01-01")
        return queryset

    def filter_decade_max(self, queryset, name, value):
        if value:
            end_decade = "1959" if value == "pre" else value
            return queryset.filter(released__lte=f"{end_decade[:3]}9-12-31")
        return queryset

    def filter_runtime_min(self, queryset, name, value):
        if value and not value.startswith("<"):
            if value.startswith(">"):
                value = 151
            return queryset.filter(runtime__gte=value)
        return queryset

    def filter_runtime_max(self, queryset, name, value):
        if value and not value.startswith(">"):
            if value.startswith("<"):
                value = 74
            return queryset.filter(runtime__lte=value)
        return queryset

    def _is_boundary_runtime(self, value: str) -> bool:
        """Check if param is the upper or lower limit, e.g. starts with < or >."""
        if value.startswith("<") or value.startswith(">"):
            return True
        return False

    class Meta:
        model = Movie
        fields = ["g", "dmin", "dmax", "rmin", "rmax"]
