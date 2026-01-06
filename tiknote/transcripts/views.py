from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import os
from .models import Transcription





@login_required
@require_http_methods(["POST"])
def delete_transcription(request, slug):
    transcription = get_object_or_404(Transcription, slug=slug, user=request.user)
    if request.mehod == "POST":
        transcription.delete()
        return redirect('feeds:main-feeds')