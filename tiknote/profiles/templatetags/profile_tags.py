from django import template

register = template.Library()

@register.filter
def get_avatar(user):
    """Safely get user's avatar URL"""
    try:
        return user.profile.avatar_url if hasattr(user, 'profile') and user.profile.avatar_url else None
    except:
        return None

@register.filter
def get_display_name(user):
    """Safely get user's display name"""
    try:
        if hasattr(user, 'profile') and user.profile.display_name:
            return user.profile.display_name
        return user.first_name or user.username
    except:
        return user.username