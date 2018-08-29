# -*- coding: utf-8 -*-
from django.conf.urls import url

from grandchallenge.serving.views import serve_challenge_file

app_name = "serving"

urlpatterns = [
    url(
        r"^(?P<challenge_short_name>[\w-]+)/(?P<path>.*)$",
        serve_challenge_file,
        name="challenge-file",
    )
]
