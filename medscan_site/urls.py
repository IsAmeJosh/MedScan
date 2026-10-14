from django.urls import path
from django.views.generic import RedirectView

from gui import G_Views as views

urlpatterns = [
    # before login
    path("", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    # notifications and the idle timer
    path("notifications/poll/", views.notifications_poll, name="notifications_poll"),
    path("notifications/read/", views.notifications_read, name="notifications_read"),
    path("notifications/<int:nid>/open/", views.notification_open, name="notification_open"),
    path("keepalive/", views.keepalive, name="keepalive"),
    # both roles
    path("dashboard/", views.dashboard, name="dashboard"),
    path("qr/", views.qr_page, name="qr"),
    # patient: Home, My Health, Privacy
    path("record/", views.my_record, name="my_record"),
    path("record/edit/", views.update_info, name="update_info"),
    path("privacy/", views.privacy, name="privacy"),
    path("respond/<int:rid>/<str:decision>/", views.respond, name="respond"),
    path("revoke/<int:rid>/", views.revoke, name="revoke"),
    # doctor: Home, Patients (search is in the top bar), Emergency (button in the top bar)
    path("patients/", views.patients, name="patients"),
    path("patients/suggest/", views.patient_suggest, name="patient_suggest"),
    path("request/<int:pid>/", views.send_request, name="send_request"),
    path("patient/<int:pid>/", views.patient_record, name="record"),
    path("patient/<int:pid>/consult/", views.add_consultation, name="consult"),
    path("patient/<int:pid>/emergency/", views.emergency, name="emergency"),
    path("emergency/", views.emergency, name="emergency_form"),
    # addresses from earlier versions keep working (bookmarks), and lead to the page that replaced them
    path("search/", RedirectView.as_view(pattern_name="patients", query_string=True)),
    path("requests/", RedirectView.as_view(url="/patients/?tab=waiting")),
    path("doctors/", RedirectView.as_view(pattern_name="privacy")),
    path("access-log/", RedirectView.as_view(url="/privacy/?tab=activity")),
    path("profile/", RedirectView.as_view(pattern_name="my_record")),
]
