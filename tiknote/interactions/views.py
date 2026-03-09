from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from transcripts.models import Transcription
from .models import Like, Comment, Bookmark
from django_ratelimit.decorators import ratelimit
import bleach

@require_POST
@login_required
@ratelimit(key='user', rate='60/m', method='POST')
def toggle_like(request, transcription_id):
    """Toggle like on a transcription"""
    transcription = get_object_or_404(Transcription, id=transcription_id)
    
    like, created = Like.objects.get_or_create(
        user=request.user,
        transcription=transcription
    )
    
    if not created:
        # Unlike if already liked
        like.delete()
        liked = False
    else:
        liked = True
    
    likes_count = transcription.likes.count()
    
    return JsonResponse({
        'liked': liked,
        'likes_count': likes_count
    })


@require_POST
@login_required
@ratelimit(key='user', rate='30/m', method='POST')
def add_comment(request, transcription_id):
    """Add a comment to a transcription"""
    transcription = get_object_or_404(Transcription, id=transcription_id)
    text = request.POST.get('text', '').strip()
    parent_id = request.POST.get('parent_id')
    
    if not text:
        return JsonResponse({'error': 'Comment cannot be empty'}, status=400)
    
    if len(text) > 500:
        return JsonResponse({'error': 'Comment is too long (max 500 characters)'}, status=400)
    
    parent_comment = None  # Initialize parent_comment
    if parent_id:
        try:
            parent_comment = Comment.objects.get(id=parent_id, transcription=transcription)
        except Comment.DoesNotExist:
            return JsonResponse({'error': 'Parent comment not found'}, status=404)
            
    text = bleach.clean(text, tags=[], strip=True)
    comment = Comment.objects.create(
        user=request.user,
        transcription=transcription,
        parent=parent_comment,
        text=text
    )
    
    return JsonResponse({
        'success': True,
        'comment': {
            'id': comment.id,
            'text': comment.text,
            'parent_id': parent_comment.id if parent_comment else None,
            'user': {
                'username': comment.user.username,
                'first_name': comment.user.first_name or comment.user.username,
                'avatar_url': getattr(comment.user.profile, 'avatar_url', None) if hasattr(comment.user, 'profile') else None,
            },
            'created_at': comment.created_at.strftime('%b %d, %Y at %I:%M %p'),
            'time_ago': get_time_ago(comment.created_at)
        },
        'comments_count': transcription.comments.count()
    })


def get_comments(request, transcription_id):
    """Get all comments for a transcription"""
    transcription = get_object_or_404(Transcription, id=transcription_id)
    
    # Get only top-level comments (no parent)
    comments = Comment.objects.filter(
        transcription=transcription,
        parent__isnull=True
    ).select_related('user', 'user__profile').prefetch_related('replies').order_by('-created_at')
    
    comments_data = []
    for comment in comments:
        comment_dict = {
            'id': comment.id,
            'text': comment.text,
            'user': {
                'username': comment.user.username,
                'first_name': comment.user.first_name or comment.user.username,
                'avatar_url': getattr(comment.user.profile, 'avatar_url', None) if hasattr(comment.user, 'profile') else None,
            },
            'created_at': comment.created_at.strftime('%b %d, %Y at %I:%M %p'),
            'time_ago': get_time_ago(comment.created_at),
            'is_owner': comment.user == request.user,
            'replies': []
        }
        
        # Add replies
        for reply in comment.replies.all().order_by('created_at'):
            comment_dict['replies'].append({
                'id': reply.id,
                'text': reply.text,
                'user': {
                    'username': reply.user.username,
                    'first_name': reply.user.first_name or reply.user.username,
                    'avatar_url': getattr(reply.user.profile, 'avatar_url', None) if hasattr(reply.user, 'profile') else None,
                },
                'created_at': reply.created_at.strftime('%b %d, %Y at %I:%M %p'),
                'time_ago': get_time_ago(reply.created_at),
                'is_owner': reply.user == request.user,
            })
        
        comments_data.append(comment_dict)
    
    return JsonResponse({'comments': comments_data})





@require_POST
@login_required
@ratelimit(key='user', rate='30/m', method=['DELETE', 'POST'])
def delete_comment(request, comment_id):
    """Delete a comment (only by owner)"""
    comment = get_object_or_404(Comment, id=comment_id)
    
    if comment.user != request.user:
        return JsonResponse({'error': 'You can only delete your own comments'}, status=403)
    
    transcription_id = comment.transcription.id
    comment.delete()
    
    comments_count = Comment.objects.filter(transcription_id=transcription_id).count()
    
    return JsonResponse({
        'success': True,
        'comments_count': comments_count
    })


@require_POST
@login_required
@ratelimit(key='user', rate='30/m', method=['BOOKMARK', 'POST'])
def toggle_bookmark(request, transcription_id):
    """Toggle bookmark on a transcription"""
    transcription = get_object_or_404(Transcription, id=transcription_id)
    
    bookmark, created = Bookmark.objects.get_or_create(
        user=request.user,
        transcription=transcription
    )
    
    if not created:
        bookmark.delete()
        bookmarked = False
    else:
        bookmarked = True
    
    return JsonResponse({
        'bookmarked': bookmarked
    })


def get_time_ago(datetime_obj):
    """Helper function to get human-readable time ago"""
    from django.utils.timesince import timesince
    return timesince(datetime_obj) + ' ago'