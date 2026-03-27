# TikNote

> Transform your TikTok videos into searchable, shareable text transcripts powered by AI.

TikNote is a Django web application that authenticates users via TikTok OAuth, fetches their videos, and transcribes the audio using AssemblyAI. Transcripts are displayed in a social-feed-style interface where users can like, comment, bookmark, and share content.

**Live demo:** [tiknote.onrender.com](https://tiknote.onrender.com)

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Setup](#local-setup)
  - [Environment Variables](#environment-variables)
- [How It Works](#how-it-works)
- [App Breakdown](#app-breakdown)
- [API & URL Routes](#api--url-routes)
- [Deployment (Render)](#deployment-render)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## Features

- **TikTok OAuth Login** — Secure sign-in via TikTok's OAuth 2.0 flow with one-time CSRF state tokens
- **Video Sync** — Fetch up to 20 of your TikTok videos with thumbnails and metadata
- **AI Transcription** — Audio transcribed via AssemblyAI (switched from Whisper to fit within Render's 512MB RAM limit)
- **Social Feed** — Transcripts displayed in a Twitter/Instagram-style feed with infinite scroll potential
- **Interactions** — Like, comment (with threaded replies), and bookmark transcriptions
- **Transcript Actions** — Copy to clipboard, download as `.txt`, or share a link
- **Dark Mode** — Full dark/light mode toggle with localStorage persistence
- **Rate Limiting** — Per-user and per-IP rate limits on sensitive endpoints via `django-ratelimit`
- **Input Sanitization** — Comment text sanitized with `bleach`; video IDs validated against a regex

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2.7 |
| Task Queue | Celery 5.5.3 |
| Message Broker | Redis (via Render Key Value store) |
| Database | PostgreSQL (Supabase) |
| Video Download | yt-dlp |
| Transcription | AssemblyAI API |
| Frontend | Tailwind CSS (CDN), Vanilla JS |
| Hosting | Render (free tier) |
| Static Files | WhiteNoise |
| Auth | TikTok OAuth 2.0 |

---

## Architecture Overview

```
User (Browser)
     │
     ▼
┌─────────────────────────────────────────┐
│              Django (Gunicorn)          │
│                                         │
│  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │ accounts │  │  feeds   │  │profiles│ │
│  │(OAuth)   │  │(feed UI) │  │(user) │ │
│  └──────────┘  └──────────┘  └───────┘ │
│  ┌──────────┐  ┌────────────────────┐  │
│  │transcripts│  │   interactions    │  │
│  │(tasks/   │  │(likes/comments/   │  │
│  │ models)  │  │ bookmarks)        │  │
│  └──────────┘  └────────────────────┘  │
└─────────────────────────────────────────┘
         │                    │
         ▼                    ▼
    PostgreSQL             Redis
    (Supabase)          (Render KV)
         │
         ▼
    Celery Worker
    (yt-dlp + AssemblyAI)
```

**Note:** On Render's free tier, Celery runs synchronously via `CELERY_TASK_ALWAYS_EAGER=True`. The `render.yaml` includes a separate worker service for paid tiers where true background processing is needed.

---

## Project Structure

```
tiknote/
├── tiknote/                  # Django project config
│   ├── settings.py
│   ├── urls.py
│   ├── celery.py
│   ├── wsgi.py
│   └── asgi.py
│
├── accounts/                 # TikTok OAuth, login/logout, video sync
│   ├── models.py             # OAuthState (CSRF protection)
│   ├── views.py              # tiktok_login, tiktok_callback, sync_videos_page,
│   │                         # enqueue_selected_videos, transcriptions_page
│   ├── tiktok_client.py      # Token refresh, API wrapper, TikTokClient class
│   ├── urls.py
│   └── templates/accounts/
│       ├── login.html
│       ├── sync_videos.html
│       └── transcriptions.html
│
├── profiles/                 # UserProfile model, avatar proxy, settings
│   ├── models.py             # UserProfile (tokens, avatar, sync prefs)
│   ├── views.py              # profile_view, profile_transcriptions, avatar_proxy
│   ├── forms.py
│   ├── urls.py
│   ├── signals.py            # auto_sync_on_login
│   └── templates/profiles/
│       ├── profile.html
│       └── profile_feed.html # User's personal post feed
│
├── transcripts/              # Core transcription logic
│   ├── models.py             # Video (temp), Transcription (persistent)
│   ├── tasks.py              # Celery task: download → transcribe → save
│   ├── utils.py              # Whisper helper (legacy, replaced by AssemblyAI)
│   ├── views.py              # delete_transcription
│   ├── urls.py
│   └── templates/transcripts/
│       ├── feeds.html
│       └── detail.html
│
├── feeds/                    # Public social feed
│   ├── views.py              # main_feeds, delete_transcription
│   ├── urls.py
│   └── templates/feeds/
│       └── feeds.html        # Main discovery feed
│
├── interactions/             # Likes, comments, bookmarks
│   ├── models.py             # Like, Comment (with replies), Bookmark
│   ├── views.py              # toggle_like, add_comment, get_comments,
│   │                         # delete_comment, toggle_bookmark
│   └── urls.py
│
└── templates/
    └── base.html             # Nav, footer, dark mode, flash messages
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- Redis (local or remote)
- PostgreSQL (or SQLite for local dev)
- A [TikTok Developer account](https://developers.tiktok.com/) with an app set up
- An [AssemblyAI API key](https://www.assemblyai.com/)

### Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/your-username/tiknote.git
cd tiknote/tiknote

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and fill in environment variables
cp .env.example .env  # then edit .env

# 5. Run migrations
python manage.py migrate

# 6. (Optional) Create cache table if using DB cache
python manage.py createcachetable

# 7. Start the development server
python manage.py runserver

# 8. (Optional) Start Celery worker in a separate terminal
celery -A tiknote worker --loglevel=info --pool=solo
```

### Environment Variables

Create a `.env` file in the `tiknote/` directory (alongside `manage.py`):

```env
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Database
# Leave blank to use SQLite locally, or provide a Supabase pooler URL:
# DATABASE_URL=postgresql://user:password@host:6543/dbname?sslmode=require

# Redis
REDIS_URL=redis://127.0.0.1:6379/0

# TikTok OAuth
TIKTOK_CLIENT_KEY=your_tiktok_client_key
TIKTOK_CLIENT_SECRET=your_tiktok_client_secret
TIKTOK_REDIRECT_URI=http://localhost:8000/accounts/tiktok/callback/

# AssemblyAI
ASSEMBLYAI_API_KEY=your_assemblyai_key

# Production only
# CSRF_TRUSTED_ORIGINS=https://your-domain.onrender.com
```

> **Supabase note:** Use the **pooler** connection string on port **6543** with `?sslmode=require`. The direct connection (port 5432) uses IPv6 which Render's free tier does not support.

---

## How It Works

### 1. Authentication

The user clicks "Login with TikTok" which triggers the OAuth 2.0 flow:

1. A unique `OAuthState` token is generated and saved to the database.
2. The user is redirected to TikTok's authorization page.
3. TikTok redirects back to `/accounts/tiktok/callback/` with a `code` and `state`.
4. The state is verified (one-time use, expires in 10 minutes) and consumed.
5. The code is exchanged for an access token and refresh token.
6. User info (display name, avatar) is fetched from TikTok's API.
7. A Django `User` and `UserProfile` are created or updated.
8. The user is logged in and redirected to the main feed.

### 2. Video Sync

On the Sync page, the app calls TikTok's `/v2/video/list/` endpoint and displays up to 20 videos as a selectable grid. Users pick videos and click "Transcribe Selected".

### 3. Transcription Pipeline

Selected videos are passed to a Celery task (`create_and_process_from_tiktok_video`):

1. A `Transcription` record is created with `status='pending'`.
2. Video metadata is fetched from TikTok's API.
3. The video is downloaded via `yt-dlp` using the `share_url`.
4. The audio is sent to AssemblyAI for transcription.
5. On success: `Transcription.mark_completed(text)` is called, status → `'completed'`.
6. On failure: status → `'failed'`, temp file is cleaned up.

### 4. Feed & Interactions

Completed transcriptions appear in two feeds:
- **Main Feed** (`/`) — all users' public transcripts, randomised order
- **My Posts** (`/profile/transcriptions/`) — logged-in user's own transcripts

Each transcript card supports:
- ❤️ Like / unlike (AJAX, no page reload)
- 💬 Comments with threaded replies (loaded lazily on click)
- 🔖 Bookmark
- 📋 Copy / ⬇️ Download as `.txt` / 🔗 Share link
- 🗑️ Delete (owner only)

---

## App Breakdown

### `accounts`

Handles all authentication logic. The `OAuthState` model provides CSRF protection for the OAuth flow — each state token is single-use and expires after 10 minutes. `tiktok_client.py` wraps TikTok API calls and handles automatic token refresh.

### `profiles`

Stores extended user data in `UserProfile`: TikTok tokens, avatar URL, display name, sync preferences. The `avatar_proxy` view proxies TikTok avatar images through Django to avoid CORS/hotlinking issues (cached for 24 hours).

**Important field widths:** `profile_image`, `avatar_url`, `share_url`, `cover_image`, and `thumbnail_url` are declared as `URLField(max_length=500)`. PostgreSQL strictly enforces `max_length` (unlike SQLite which silently ignores it), and TikTok CDN URLs regularly exceed Django's default 200-character limit.

### `transcripts`

Contains two models:
- `Video` — temporary record used during sync (deleted after transcription)
- `Transcription` — permanent record with `status`, `transcript` text, `thumbnail_url`, and `slug`

The Celery task lives in `tasks.py`. The legacy `utils.py` (Whisper) is no longer used in production but kept for reference.

### `feeds`

Renders the public discovery feed with annotations for like/bookmark state per user. Uses `Exists()` subqueries for efficient per-user state without N+1 queries.

### `interactions`

Three models: `Like`, `Comment`, `Bookmark`. Comments support one level of replies via a self-referential `parent` FK. All interaction views return JSON and are rate-limited.

---

## API & URL Routes

| Method | URL | Description |
|---|---|---|
| GET | `/` | Main public feed |
| GET | `/accounts/tiktok/login/` | Start TikTok OAuth |
| GET | `/accounts/tiktok/callback/` | OAuth callback handler |
| GET/POST | `/accounts/tiktok/disconnect/` | Logout and clear tokens |
| GET | `/accounts/sync_videos/` | Fetch & display TikTok videos |
| POST | `/accounts/enqueue_selected_videos/` | Queue selected videos for transcription |
| GET | `/accounts/transcriptions/` | Transcription queue/status page |
| GET | `/profile/transcriptions/` | User's personal post feed |
| POST | `/interactions/like/<id>/` | Toggle like |
| POST | `/interactions/comment/<id>/` | Add comment or reply |
| GET | `/interactions/comments/<id>/` | Fetch comments for a transcription |
| DELETE | `/interactions/comment/delete/<id>/` | Delete own comment |
| POST | `/interactions/bookmark/<id>/` | Toggle bookmark |
| POST | `/transcripts/delete/<slug>/` | Delete a transcription |

---

## Deployment (Render)

The project includes a `render.yaml` that provisions:

- **Web Service** — Gunicorn with 2 workers/threads, 120s timeout
- **Worker Service** — Celery worker (requires a paid tier for background workers)
- **Redis** — Render Key Value store (free tier, `noeviction` policy)
- **PostgreSQL** — Render managed database (free tier)

### Build & Deploy

```bash
# render.yaml build command runs build.sh:
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
```

### Required Render Environment Variables (set manually)

| Variable | Value |
|---|---|
| `TIKTOK_CLIENT_KEY` | From TikTok Developer Portal |
| `TIKTOK_CLIENT_SECRET` | From TikTok Developer Portal |
| `TIKTOK_REDIRECT_URI` | `https://your-app.onrender.com/accounts/tiktok/callback/` |
| `ALLOWED_HOSTS` | `your-app.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://your-app.onrender.com` |
| `ASSEMBLYAI_API_KEY` | From AssemblyAI dashboard |

`DATABASE_URL` and `REDIS_URL` are auto-injected by Render from the linked database and Key Value services.

---

## Known Limitations

- **TikTok sandbox mode** — Only public videos work. Private videos return error code `10231` in sandbox/development mode. The app must be approved by TikTok for production access.
- **Render free tier — no background workers** — Celery tasks run synchronously (`CELERY_TASK_ALWAYS_EAGER=True`), meaning transcription blocks the web request. Upgrade to a paid worker service for async processing.
- **Render free tier — 512MB RAM** — Whisper/PyTorch (the original transcription backend) would crash the server. AssemblyAI's API-based approach avoids this entirely.
- **yt-dlp + TikTok** — TikTok actively rate-limits and bot-detects download attempts. Downloads may fail for some videos. The `share_url` from the API is the most reliable download target.
- **Slugs and empty titles** — `Transcription.slug` is generated from `title` at save time. If `title` is blank, the slug will be empty. Affected URLs that use `<slug:slug>` will 404.

---

## Roadmap

- [ ] AssemblyAI webhook for true async transcription status updates
- [ ] Upgrade Celery to use a real background worker (paid Render tier)
- [ ] Retry failed transcriptions from the UI
- [ ] Edit transcript titles
- [ ] Full-text search across transcripts
- [ ] Pagination on feed and transcription list
- [ ] Public/private toggle on transcriptions
- [ ] Complete the delete transcription flow (currently behind `coming soon` alerts in the feed JS)
- [ ] Notifications for likes and comments
