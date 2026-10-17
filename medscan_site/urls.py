"""Every web address of MedScan and the view that answers it."""
from django.urls import path
from django.views.generic import RedirectView

from gui import G_Views as views

urlpatterns = [
    # Before login.
    path("", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    # Notifications and the idle timer.
    path("notifications/poll/", views.notifications_poll, name="notifications_poll"),
    path("notifications/read/", views.notifications_read, name="notifications_read"),
    path("notifications/<int:nid>/open/", views.notification_open, name="notification_open"),
    path("keepalive/", views.keepalive, name="keepalive"),
    # Both roles.
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("profile/contact/", views.profile_contact, name="profile_contact"),
    path("qr/", views.qr_page, name="qr"),
    path("qr/code/", views.qr_code, name="qr_code"),
    path("qr/new/", views.qr_new, name="qr_new"),
    path("qr/scan/", views.qr_scan, name="qr_scan"),
    # Patient: Home, My Record, Access.
    path("record/", views.my_record, name="my_record"),
    path("record/edit/", views.update_info, name="update_info"),
    path("access/", views.access, name="access"),
    path("respond/<int:rid>/<str:decision>/", views.respond, name="respond"),
    path("revoke/<int:rid>/", views.revoke, name="revoke"),
    # Doctor: Home, Patients, Search (the top bar and the phone tab), and the Patient page (locked or open).
    path("patients/", views.patients, name="patients"),
    path("patients/suggest/", views.patient_suggest, name="patient_suggest"),
    path("search/", views.search, name="search"),
    path("request/<int:pid>/", views.send_request, name="send_request"),
    path("patient/<int:pid>/", views.patient_record, name="record"),
    path("patient/<int:pid>/consult/", views.add_consultation, name="consult"),
    path("patient/<int:pid>/emergency/", views.emergency, name="emergency"),
    path("emergency/", views.emergency, name="emergency_form"),
    # old addresses still work (bookmarks) and lead to the page that replaced them
    path("requests/", RedirectView.as_view(url="/patients/?show=waiting")),
    path("doctors/", RedirectView.as_view(url="/access/?tab=doctors")),
    path("privacy/", RedirectView.as_view(url="/access/")),
    path("access-log/", RedirectView.as_view(url="/access/?tab=history")),
]
