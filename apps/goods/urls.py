from django.urls import path
from django.conf.urls import url, include
from goods import views

urlpatterns = [
    url(r'^$', views.index, name='index'),  # 首页
]
