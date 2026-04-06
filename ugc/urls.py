from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PollViewSet,
    RegisterView,
    LoginView,
    NextQuestionView,
    SubmitAnswerView,
)


router = DefaultRouter()
router.register(r"polls", PollViewSet, basename="poll")

urlpatterns = [
    path("", include(router.urls)),

    path(
        "register/",
        RegisterView.as_view(),
        name="register"
    ),
    path(
        "login/",
        LoginView.as_view(),
        name="login"
    ),

    path(
        "polls/<int:poll_id>/next-question/",
        NextQuestionView.as_view(),
        name="next-question",
    ),
    path(
        "polls/<int:poll_id>/submit-answer/",
        SubmitAnswerView.as_view(),
        name="submit-answer",
    ),
]
