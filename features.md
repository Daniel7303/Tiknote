tiknote/
│
├── accounts/ # Handles authentication & TikTok OAuth
│ ├── models.py # OAuthState, TikTok token models
│ ├── views.py # TikTok login/callback views
│ └── tiktok_client.py # Handles API calls, token refresh
│
├── profiles/ # New app for user data, settings, and preferences
│ ├── models.py # UserProfile, Preferences
│ ├── views.py # Profile view, edit view, sync toggle
│ ├── urls.py # URLs for profile management
│ ├── forms.py # Edit forms, settings form
│ └── templates/profiles/ # HTML templates for settings, profile, etc.
│

└── tiknote/
├── settings.py
├── urls.py
└── ...

#feeds
#interactions
