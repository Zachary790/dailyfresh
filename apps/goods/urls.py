from django.urls import path
from django.conf.urls import url, include
from goods.views import IndexView

urlpatterns = [
    url(r'^$', IndexView.as_view(), name='index'),  # 首页
]
