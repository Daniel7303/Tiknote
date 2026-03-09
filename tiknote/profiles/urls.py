from django.urls import path
from . import views

app_name = 'profiles'

urlpatterns = [
    path('', views.profile_view, name='profile'),
    path('/settings/sync/', views.sync_now, name='sync_now'),
    path("transcriptions/", views.profile_transcriptions, name="profile_transcriptions"),
    path('avatar/<int:user_id>/', views.avatar_proxy, name='avatar_proxy'),
    
    
]
