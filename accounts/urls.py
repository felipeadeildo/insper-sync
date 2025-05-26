from django.urls import path

from . import views

urlpatterns = [
    path("verify-email/", views.verify_email, name="verify_email"),
    path("verify/<str:token>/", views.verify_token, name="verify_token"),
    path("setup-credentials/", views.setup_credentials, name="setup_credentials"),
    path("logout/", views.logout_view, name="logout"),
    # Google Calendar OAuth URLs
    path("google-auth/", views.google_auth, name="google_auth"),
    path("google-callback/", views.google_callback, name="google_callback"),
    path("google-disconnect/", views.google_disconnect, name="google_disconnect"),
    path("test-google/", views.test_google_connection, name="test_google_connection"),
]
