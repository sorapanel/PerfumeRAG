"""ルートURL設定。"""

from django.urls import include, path

urlpatterns = [
    path("api/", include("perfume_api.urls")),
]
