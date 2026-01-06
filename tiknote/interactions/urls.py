from django.urls import path
from . import views

app_name = 'interactions'

urlpatterns = [
    # 👍 Likes
    path('like/<int:transcription_id>/', views.toggle_like, name='toggle_like'),

    # 💬 Comments
    path('comment/<int:transcription_id>/', views.add_comment, name='add_comment'),
    path('comments/<int:transcription_id>/', views.get_comments, name='get_comments'),
    path('comment/delete/<int:comment_id>/', views.delete_comment, name='delete_comment'),

    # 🔖 Bookmarks
    path('bookmark/<int:transcription_id>/', views.toggle_bookmark, name='toggle_bookmark'),
]
