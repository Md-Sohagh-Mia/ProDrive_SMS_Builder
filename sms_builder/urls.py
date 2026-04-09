from django.urls import path
from . import views

urlpatterns = [
    path('', views.index),
    path('signin/', views.signin , name='signin'),
    path('signup/', views.signup , name='signup'),
    path('index/', views.index, name='index'),
    path('profile/', views.profile, name='profile'),
    # Add this line:
    path('logout/', views.logout_view, name='logout'),
  ]