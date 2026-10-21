from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("upload/", views.upload),
    path("files/", views.files),
    path("files/<int:pk>/", views.file_detail),
    path("files/<int:pk>/flagged/", views.file_flagged),
    path("files/<int:pk>/summary/", views.summary),
    path("chat/", views.chat),
    path("sessions/", views.sessions),
    path("sessions/<int:pk>/", views.session_detail),
    path("eval/testset/", views.eval_testset),
    path("eval/run/", views.eval_run),
    path("eval/status/", views.eval_status),
]
