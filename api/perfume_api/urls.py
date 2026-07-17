"""perfume_api アプリの URL 設定。"""

from django.urls import path

from .views import HealthView, QueryView

urlpatterns = [
    path("query/", QueryView.as_view(), name="query"),
    path("health/", HealthView.as_view(), name="health"),
]
