from django.urls import path
from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("patient/<int:pid>/", views.patient_record, name="record"),
    path("patient/<int:pid>/consult/", views.add_consultation, name="consult"),
    path("patient/<int:pid>/emergency/", views.emergency, name="emergency"),
    path("request/<int:pid>/", views.send_request, name="send_request"),
    path("respond/<int:rid>/<str:decision>/", views.respond, name="respond"),
    path("history/", views.update_history, name="history"),
]