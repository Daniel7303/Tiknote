from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # path('login/', views.login_redirect, name='login_redirect'),
    # path('login/', views.login_view, name='login'),

    path('tiktok/login/', views.tiktok_login, name='tiktok_login'),
    path('tiktok/callback/', views.tiktok_callback, name='tiktok_callback'),
    path('tiktok/disconnect/', views.tiktok_disconnect, name='tiktok_disconnect'),
    path('sync_videos/', views.sync_videos_page, name='sync_videos_page'),
    path('enqueue_selected_videos/', views.enqueue_selected_videos, name='enqueue_selected_videos'),
    path('transcriptions/', views.transcriptions_page, name='transcriptions_page'),
]

