from django.db import models
from django.http import HttpRequest, HttpResponse


def autocomplete(
    request: HttpRequest,
    tag_model: type[models.Model],
    **kwargs: object,
) -> HttpResponse: ...
