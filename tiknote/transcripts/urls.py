from django.urls import path
from . import views

app_name = 'transcripts'

urlpatterns = [
    path('delete/<slug:slug>/', views.delete_transcription, name='delete'),
    
]