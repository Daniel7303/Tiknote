from django.urls import path
from . import views

app_name = 'feeds'

urlpatterns = [
    path('', views.main_feeds, name='main-feeds'),    
    path('transcriptions/<slug:slug>/delete/', views.delete_transcription, name='delete_transcription'),
]
