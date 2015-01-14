from __future__ import absolute_import, unicode_literals

import json

from django.db import models
from django.forms import Textarea
from django.utils.six import with_metaclass

from wagtail.wagtailcore.rich_text import DbWhitelister, expand_db_html
from wagtail.utils.widgets import WidgetWithScript
from wagtail.wagtailadmin.blocks import StreamBlock  # FIXME: wagtailcore shouldn't be depending on wagtailadmin


class RichTextArea(WidgetWithScript, Textarea):
    def get_panel(self):
        from wagtail.wagtailadmin.edit_handlers import RichTextFieldPanel
        return RichTextFieldPanel

    def render(self, name, value, attrs=None):
        if value is None:
            translated_value = None
        else:
            translated_value = expand_db_html(value, for_editor=True)
        return super(RichTextArea, self).render(name, translated_value, attrs)

    def render_js_init(self, id_, name, value):
        return "makeRichTextEditable({0});".format(json.dumps(id_))

    def value_from_datadict(self, data, files, name):
        original_value = super(RichTextArea, self).value_from_datadict(data, files, name)
        if original_value is None:
            return None
        return DbWhitelister.clean(original_value)


class RichTextField(models.TextField):
    def formfield(self, **kwargs):
        defaults = {'widget': RichTextArea}
        defaults.update(kwargs)
        return super(RichTextField, self).formfield(**defaults)


class StreamField(with_metaclass(models.SubfieldBase, models.TextField)):
    def __init__(self, block_types, **kwargs):
        self.block_types = block_types
        self.stream_block = StreamBlock(block_types)
        super(StreamField, self).__init__(**kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(StreamField, self).deconstruct()
        kwargs['block_types'] = self.block_types
        return name, path, args, kwargs

    def to_python(self, value):
        if value is None:
            return []
        elif isinstance(value, list):
            return value
        else:  # assume string
            return self.stream_block.renderable(json.loads(value))

    def get_prep_value(self, value):
        return json.dumps(value)

