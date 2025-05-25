from django.urls import path

from . import views

urlpatterns = [
    path("verify-email/", views.verify_email, name="verify_email"),
    path("verify/<str:token>/", views.verify_token, name="verify_token"),
    path("setup-credentials/", views.setup_credentials, name="setup_credentials"),
    path("dashboard/", views.dashboard, name="dashboard"),
]
