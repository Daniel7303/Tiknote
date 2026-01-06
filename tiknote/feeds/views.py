from django.shortcuts import render
from django.db.models import Count, Exists, OuterRef, Value
from transcripts.models import Transcription
from interactions.models import Like, Comment, Bookmark
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import os



# Create your views here.

def main_feeds(request):
    # Get feeds with annotations
    feeds = Transcription.objects.annotate(
        likes_count=Count('likes'),
        comments_count=Count('comments'),
        user_has_liked=Exists(
            Like.objects.filter(
                transcription=OuterRef('pk'),
                user=request.user
            )
        ) if request.user.is_authenticated else Value(False),
        user_has_bookmarked=Exists(
            Bookmark.objects.filter(
                transcription=OuterRef('pk'),
                user=request.user
            )
        ) if request.user.is_authenticated else Value(False)
    ).select_related('user', 'user__profile').order_by('?')  # Random order using database
    
    # Alternative: If you prefer Python's random shuffle
    # feeds = list(feeds)
    # random.shuffle(feeds)
    
    return render(request, "feeds/feeds.html", {
        "feeds": feeds,
    })






@login_required
@require_http_methods(["POST"])
def delete_transcription(request, slug):
    transcription = get_object_or_404(Transcription, slug=slug, user=request.user)
    if request.mehod == "POST":
        transcription.delete()
        return redirect('feeds:main-feeds')