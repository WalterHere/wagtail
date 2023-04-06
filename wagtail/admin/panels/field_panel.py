import functools

from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from django.db.models import ForeignKey
from django.utils.functional import cached_property

from wagtail.admin import compare
from wagtail.admin.forms.models import registry as model_field_registry
from wagtail.blocks import BlockField

from .base import Panel


class FieldPanel(Panel):
    TEMPLATE_VAR = "field_panel"

    def __init__(
        self, field_name, widget=None, disable_comments=None, permission=None, **kwargs
    ):
        super().__init__(**kwargs)
        self.field_name = field_name
        self.widget = widget
        self.disable_comments = disable_comments
        self.permission = permission

    def clone_kwargs(self):
        kwargs = super().clone_kwargs()
        kwargs.update(
            field_name=self.field_name,
            widget=self.widget,
            disable_comments=self.disable_comments,
            permission=self.permission,
        )
        return kwargs

    def get_form_options(self):
        opts = {
            "fields": [self.field_name],
        }
        if self.widget:
            opts["widgets"] = {self.field_name: self.widget}

        if self.permission:
            opts["field_permissions"] = {self.field_name: self.permission}

        return opts

    def get_comparison_class(self):
        try:
            field = self.db_field

            if field.choices:
                return compare.ChoiceFieldComparison

            comparison_class = compare.comparison_class_registry.get(field)
            if comparison_class:
                return comparison_class

            if field.is_relation:
                if field.many_to_many:
                    return compare.M2MFieldComparison

                return compare.ForeignObjectComparison

        except FieldDoesNotExist:
            pass

        return compare.FieldComparison

    @cached_property
    def db_field(self):
        try:
            model = self.model
        except AttributeError:
            raise ImproperlyConfigured(
                "%r must be bound to a model before calling db_field" % self
            )

        return model._meta.get_field(self.field_name)

    @property
    def clean_name(self):
        return self.field_name

    def __repr__(self):
        return "<%s '%s' with model=%s>" % (
            self.__class__.__name__,
            self.field_name,
            self.model,
        )

    class BoundPanel(Panel.BoundPanel):
        template_name = "wagtailadmin/panels/field_panel.html"
        # Default icons for common model field types,
        # based on the corresponding FieldBlock's icon.
        default_field_icons = {
            "DateField": "date",
            "TimeField": "time",
            "DateTimeField": "date",
            "URLField": "link-external",
            "TaggableManager": "tag",
            "EmailField": "mail",
            "TextField": "pilcrow",
            "RichTextField": "pilcrow",
            "FloatField": "decimal",
            "DecimalField": "decimal",
            "BooleanField": "tick-inverse",
            # Django has no model form field for this, so it won't be used
            # unless a custom field with this name is used, or we also
            # look through the form fields to get the default icon.
            "RegexField": "regex",
        }

        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            if self.form is None:
                self.bound_field = None
                return

            try:
                self.bound_field = self.form[self.field_name]
            except KeyError:
                self.bound_field = None
                return

            if self.panel.heading:
                self.heading = self.bound_field.label = self.panel.heading
            else:
                self.heading = self.bound_field.label

            self.help_text = self.panel.help_text or self.bound_field.help_text

        @property
        def field_name(self):
            return self.panel.field_name

        def is_shown(self):
            if self.form is not None and self.bound_field is None:
                # this field is missing from the form
                return False

            if (
                self.panel.permission
                and self.request
                and not self.request.user.has_perm(self.panel.permission)
            ):
                return False

            return True

        def is_required(self):
            return self.bound_field.field.required

        def classes(self):
            is_streamfield = isinstance(self.bound_field.field, BlockField)
            extra_classes = ["w-panel--nested"] if is_streamfield else []

            return self.panel.classes() + extra_classes

        @property
        def icon(self):
            """
            Display a different icon depending on the field's type.
            """
            # If the panel has an icon, use that
            if self.panel.icon:
                return self.panel.icon

            db_field_type = type(self.panel.db_field)

            # ForeignKey fields can have a custom icon defined in the form field's widget
            # (e.g. page, image, and document choosers). If there's an overridden widget
            # with an icon attribute, use that.
            if issubclass(db_field_type, ForeignKey):
                overrides = model_field_registry.get(self.panel.db_field)
                widget = overrides.get("widget", None)
                return getattr(widget, "icon", None)

            # Otherwise, find a default icon based on the field's class or superclasses
            for field_class in db_field_type.mro():
                field_name = field_class.__name__
                if field_name in self.default_field_icons:
                    return self.default_field_icons[field_name]

            return None

        def id_for_label(self):
            return self.bound_field.id_for_label

        @property
        def comments_enabled(self):
            if self.panel.disable_comments is None:
                # by default, enable comments on all fields except StreamField (which has its own comment handling)
                return not isinstance(self.bound_field.field, BlockField)
            else:
                return not self.panel.disable_comments

        def get_context_data(self, parent_context=None):
            context = super().get_context_data(parent_context)

            widget_described_by_ids = []
            help_text = self.bound_field.help_text
            help_text_id = "%s-helptext" % self.prefix
            error_message_id = "%s-errors" % self.prefix

            if help_text:
                widget_described_by_ids.append(help_text_id)

            if self.bound_field.errors:
                widget = self.bound_field.field.widget
                if hasattr(widget, "render_with_errors"):
                    widget_attrs = {
                        "id": self.bound_field.auto_id,
                    }
                    if widget_described_by_ids:
                        widget_attrs["aria-describedby"] = " ".join(
                            widget_described_by_ids
                        )

                    rendered_field = widget.render_with_errors(
                        self.bound_field.html_name,
                        self.bound_field.value(),
                        attrs=widget_attrs,
                        errors=self.bound_field.errors,
                    )
                else:
                    widget_described_by_ids.append(error_message_id)
                    rendered_field = self.bound_field.as_widget(
                        attrs={
                            "aria-invalid": "true",
                            "aria-describedby": " ".join(widget_described_by_ids),
                        }
                    )
            else:
                widget_attrs = {}
                if widget_described_by_ids:
                    widget_attrs["aria-describedby"] = " ".join(widget_described_by_ids)

                rendered_field = self.bound_field.as_widget(attrs=widget_attrs)

            context.update(
                {
                    "field": self.bound_field,
                    "rendered_field": rendered_field,
                    "help_text": help_text,
                    "help_text_id": help_text_id,
                    "error_message_id": error_message_id,
                    "show_add_comment_button": self.comments_enabled
                    and getattr(
                        self.bound_field.field.widget, "show_add_comment_button", True
                    ),
                }
            )
            return context

        def get_comparison(self):
            comparator_class = self.panel.get_comparison_class()

            if comparator_class and self.is_shown():
                try:
                    return [functools.partial(comparator_class, self.panel.db_field)]
                except FieldDoesNotExist:
                    return []
            return []

        def __repr__(self):
            return "<%s '%s' with model=%s instance=%s request=%s form=%s>" % (
                self.__class__.__name__,
                self.field_name,
                self.panel.model,
                self.instance,
                self.request,
                self.form.__class__.__name__,
            )
