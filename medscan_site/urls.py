from django.urls import path
from gui import G_Views as views

urlpatterns = [
    # before login
    path("", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("welcome/", views.welcome_view, name="welcome"),
    path("logout/", views.logout_view, name="logout"),
    path("notifications/read/", views.notifications_read, name="notifications_read"),
    # both roles
    path("dashboard/", views.dashboard, name="dashboard"),
    # patient
    path("record/", views.my_record, name="my_record"),
    path("record/edit/", views.update_info, name="update_info"),
    path("profile/", views.profile, name="profile"),
    path("respond/<int:rid>/<str:decision>/", views.respond, name="respond"),
    path("revoke/<int:rid>/", views.revoke, name="revoke"),
    # doctor
    path("search/", views.search_patient, name="search"),
    path("requests/", views.doctor_requests, name="doctor_requests"),
    path("request/<int:pid>/", views.send_request, name="send_request"),
    path("patient/<int:pid>/", views.patient_record, name="record"),
    path("patient/<int:pid>/consult/", views.add_consultation, name="consult"),
    path("patient/<int:pid>/emergency/", views.emergency, name="emergency"),
    path("emergency/", views.emergency, name="emergency_form"),
]
