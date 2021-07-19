import datetime

from collections import defaultdict

import django_filters

from django import forms
from django.db.models import IntegerField, Value
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _

from wagtail.admin.filters import DateRangePickerWidget, WagtailFilterSet
from wagtail.core.log_actions import registry as log_action_registry
from wagtail.core.models import PageLogEntry

from .base import ReportView


class SiteHistoryReportFilterSet(WagtailFilterSet):
    action = django_filters.ChoiceFilter(choices=log_action_registry.get_choices)
    hide_commenting_actions = django_filters.BooleanFilter(
        label=_('Hide commenting actions'),
        method='filter_hide_commenting_actions',
        widget=forms.CheckboxInput,
    )
    timestamp = django_filters.DateFromToRangeFilter(label=_('Date'), widget=DateRangePickerWidget)
    label = django_filters.CharFilter(label=_('Title'), lookup_expr='icontains')
    user = django_filters.ModelChoiceFilter(
        field_name='user', queryset=lambda request: PageLogEntry.objects.all().get_users()
    )

    def filter_hide_commenting_actions(self, queryset, name, value):
        if value:
            queryset = queryset.exclude(
                action__startswith='wagtail.comments'
            )
        return queryset

    class Meta:
        model = PageLogEntry
        fields = ['label', 'action', 'user', 'timestamp', 'hide_commenting_actions']


class LogEntriesView(ReportView):
    template_name = 'wagtailadmin/reports/site_history.html'
    title = _('Site history')
    header_icon = 'history'
    filterset_class = SiteHistoryReportFilterSet

    export_headings = {
        "object_id": _("ID"),
        "title": _("Title"),
        "object_verbose_name": _("Type"),
        "action": _("Action type"),
        "timestamp": _("Date/Time")
    }
    list_export = [
        "object_id",
        "label",
        "object_verbose_name",
        "action",
        "timestamp"
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.custom_field_preprocess['action'] = {
            self.FORMAT_CSV: self.get_action_label,
            self.FORMAT_XLSX: self.get_action_label
        }

    def get_filename(self):
        return "audit-log-{}".format(
            datetime.datetime.today().strftime("%Y-%m-%d")
        )

    def get_filtered_queryset(self):
        """
        Since this report combines records from multiple log models, the standard pattern of
        returning a queryset from get_queryset() to be filtered by filter_queryset() is not
        possible - the subquery for each log model must be filtered separately before joining
        with union().

        Additionally, a union() on standard model-based querysets will return a queryset based on
        the first model in the union, so instances of the other model(s) would be returned as the
        wrong type. To avoid this, we construct values() querysets as follows:

        1. For each model, construct a values() queryset consisting of id, timestamp and an
           annotation to indicate which model it is, and filter this with filter_queryset
        2. Form a union() queryset from these queries, and order it by -timestamp
           (this is the result returned from get_filtered_queryset)
        3. Apply pagination (done in MultipleObjectMixin.get_context_data)
        4. (In decorate_paginated_queryset:) For each model included in the result set, look up
           the set of model instances by ID. Use these to form a final list of model instances
           in the same order as the query.
        """
        queryset = None
        filters = None

        # Retrieve the set of registered log models, and cast it to a list so that we assign
        # an index number to each one; this index number will be used to distinguish models
        # in the combined results
        self.log_models = list(log_action_registry.get_log_entry_models())

        for log_model_index, log_model in enumerate(self.log_models):
            sub_queryset = log_model.objects.viewable_by_user(self.request.user).values(
                'pk', 'timestamp'
            ).annotate(
                log_model_index=Value(log_model_index, output_field=IntegerField())
            )
            filters, sub_queryset = self.filter_queryset(sub_queryset)
            # disable any native ordering on the queryset; we will re-apply it on the combined result
            sub_queryset = sub_queryset.order_by()
            if queryset is None:
                queryset = sub_queryset
            else:
                queryset = queryset.union(sub_queryset)

        return filters, queryset.order_by('-timestamp')

    def decorate_paginated_queryset(self, queryset):
        # build lists of ids from queryset, grouped by log model index
        pks_by_log_model_index = defaultdict(list)
        for row in queryset:
            pks_by_log_model_index[row['log_model_index']].append(row['pk'])

        # for each log model found in the queryset, look up the set of log entries by id
        # and build a lookup table
        object_lookup = {}
        for log_model_index, pks in pks_by_log_model_index.items():
            log_entries = self.log_models[log_model_index].objects.in_bulk(pks)
            for pk, log_entry in log_entries.items():
                object_lookup[(log_model_index, pk)] = log_entry

        # return items from our lookup table in the order of the original queryset
        return [
            object_lookup[(row['log_model_index'], row['pk'])]
            for row in queryset
        ]

    def get_action_label(self, action):
        return force_str(log_action_registry.get_action_label(action))
