from __future__ import absolute_import, unicode_literals

import imghdr
from wsgiref.util import FileWrapper

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.views.generic import View

from wagtail.wagtailimages.exceptions import InvalidFilterSpecError
from wagtail.wagtailimages.models import SourceImageIOError, get_image_model
from wagtail.wagtailimages.utils import verify_signature


class ServeView(View):
    model = get_image_model()

    def get(self, request, signature, image_id, filter_spec):
        image = get_object_or_404(self.model, id=image_id)

        if not verify_signature(signature.encode(), image_id, filter_spec):
            raise PermissionDenied

        try:
            # Get/generate the rendition
            try:
                rendition = image.get_rendition(filter_spec)
            except SourceImageIOError:
                return HttpResponse("Source image file not found", content_type='text/plain', status=410)

            # Serve it
            rendition.file.open('rb')
            image_format = imghdr.what(rendition.file)
            return StreamingHttpResponse(FileWrapper(rendition.file), content_type='image/' + image_format)
        except InvalidFilterSpecError:
            return HttpResponse("Invalid filter spec: " + filter_spec, content_type='text/plain', status=400)


serve = ServeView.as_view()
