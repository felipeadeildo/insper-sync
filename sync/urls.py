from django.urls import path

from . import views

urlpatterns = [
    # Configurações de sincronização
    path("configuration/", views.sync_configuration, name="sync_configuration"),
    # Sincronização manual
    path("manual-sync/", views.manual_sync, name="manual_sync"),
    # Status da sincronização (API)
    path("status/", views.sync_status, name="sync_status"),
    # Histórico de sincronizações
    path("history/", views.SyncHistoryView.as_view(), name="sync_history"),
    path(
        "session/<int:session_id>/",
        views.sync_session_detail,
        name="sync_session_detail",
    ),
    # Ações de limpeza
    path("clear-history/", views.clear_sync_history, name="clear_sync_history"),
    path("reset-data/", views.reset_sync_data, name="reset_sync_data"),
]
