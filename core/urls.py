from django.urls import path
from . import views

urlpatterns = [
    path('', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('delete/', views.delete_view, name='delete'),
    path('update/', views.update_view, name='update'),
    path('signout/', views.signout_view, name='signout'),
    path('home/', views.home_view, name='home'),
]
