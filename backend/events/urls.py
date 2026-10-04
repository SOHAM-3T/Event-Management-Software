from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

urlpatterns = [
    path('health/', views.health_check, name='health-check'),
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('events/', views.EventListCreateView.as_view(), name='event-list-create'),
    path('events/<uuid:event_id>/', views.EventDetailView.as_view(), name='event-detail'),
    path('events/<uuid:event_id>/sync/', views.sync_event_registrations, name='event-sync'),
    path('events/<uuid:event_id>/dashboard/', views.event_dashboard, name='event-dashboard'),
    path('events/<uuid:event_id>/participants/', views.ParticipantListView.as_view(), name='participant-list'),
    path('events/<uuid:event_id>/participants/<uuid:participant_id>/attendance/', views.AttendanceUpdateView.as_view(), name='attendance-update'),
]
