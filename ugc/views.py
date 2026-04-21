from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import generics, serializers, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ugc.models import Poll
from ugc.serializers import (
    LoginInputSerializer,
    PollDetailSerializer,
    PollSerializer,
    QuestionSerializer,
    RegisterSerializer,
    SubmitAnswerInputSerializer,
)
from ugc.services import AnswerService, PollSessionService


@extend_schema_view(
    list=extend_schema(
        summary=_("Список опросов"),
        description=_(
            "Возвращает список всех опросов с количеством вопросов."
        ),
    ),
    retrieve=extend_schema(
        summary=_("Детали опроса"),
        description=_(
            "Возвращает опрос со всеми вопросами и вариантами ответов."
        ),
    ),
)
class PollViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Список опросов и детальная информация.
    """

    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return (
            Poll.objects.only("id", "title", "author", "created_at")
            .annotate(questions_count=Count("questions"))
            .prefetch_related("questions__options")
            .order_by("id")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PollDetailSerializer
        return PollSerializer

    @method_decorator(cache_page(60 * 5))
    @method_decorator(vary_on_headers("Authorization"))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


@extend_schema(
    summary=_("Регистрация пользователя"),
    description=_("Создаёт нового пользователя и возвращает токен."),
    request=RegisterSerializer,
    responses={
        201: inline_serializer(
            name="RegisterResponse",
            fields={
                "user": inline_serializer(
                    name="UserData",
                    fields={
                        "id": serializers.IntegerField(),
                        "username": serializers.CharField(),
                        "email": serializers.EmailField(),
                    },
                ),
                "token": serializers.CharField(),
            },
        ),
        400: inline_serializer(
            name="ErrorResponse", fields={"detail": serializers.CharField()}
        ),
    },
)
class RegisterView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)
        return Response(
            {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
                "token": token.key,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    summary=_("Логин"),
    description=_("Аутентификация по username и password, возвращает токен."),
    request=LoginInputSerializer,
    responses={
        200: inline_serializer(
            name="LoginResponse",
            fields={
                "user": inline_serializer(
                    name="UserDataShort",
                    fields={
                        "id": serializers.IntegerField(),
                        "username": serializers.CharField(),
                        "email": serializers.EmailField(),
                    },
                ),
                "token": serializers.CharField(),
            },
        ),
        401: inline_serializer(
            name="ErrorResponse", fields={"error": serializers.CharField()}
        ),
    },
)
class LoginView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = LoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = authenticate(username=username, password=password)
        if user:
            token, _ = Token.objects.get_or_create(user=user)
            return Response(
                {
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                    },
                    "token": token.key,
                }
            )
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )


@extend_schema(
    summary=_("Следующий вопрос"),
    description=_(
        """Возвращает следующий вопрос для указанного опроса. """
        """Требует активной сессии."""
    ),
    parameters=[
        OpenApiParameter(
            name="poll_id",
            description=_("ID опроса"),
            required=True,
            type=int,
            location=OpenApiParameter.PATH,
        ),
    ],
    responses={
        200: QuestionSerializer,
        204: OpenApiResponse(description=_("Опрос завершён")),
        401: OpenApiResponse(description=_("Не авторизован")),
        404: OpenApiResponse(description=_("Опрос не найден")),
    },
)
class NextQuestionView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, poll_id):
        poll = get_object_or_404(
            Poll.objects.prefetch_related("questions__options"), id=poll_id
        )
        session = PollSessionService.get_or_start_session(request.user, poll)

        if session is None:
            return Response(
                {"detail": _("Вы уже прошли этот опрос.")},
                status=status.HTTP_204_NO_CONTENT,
            )

        if session.is_completed() or session.current_question is None:
            return Response(
                {"detail": _("Опрос завершён.")},
                status=status.HTTP_204_NO_CONTENT,
            )

        serializer = QuestionSerializer(session.current_question)
        return Response(serializer.data)


@extend_schema(
    summary=_("Отправить ответ"),
    description=_(
        """Сохраняет ответ пользователя (выбор варианта или свой текст) """
        """и переходит к следующему вопросу."""
    ),
    request=SubmitAnswerInputSerializer,
    responses={
        200: inline_serializer(
            name="SubmitResponse", fields={"detail": serializers.CharField()}
        ),
        400: inline_serializer(
            name="ErrorResponse", fields={"detail": serializers.CharField()}
        ),
        401: OpenApiResponse(description=_("Не авторизован")),
        404: OpenApiResponse(description=_("Опрос не найден")),
    },
)
class SubmitAnswerView(APIView):
    permission_classes = (IsAuthenticated,)

    @transaction.atomic
    def post(self, request, poll_id):
        poll = get_object_or_404(Poll, id=poll_id)
        input_serializer = SubmitAnswerInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        validated_data = input_serializer.validated_data

        session = PollSessionService.get_active_session(request.user, poll)
        current_q = session.current_question

        if current_q is None:
            return Response(
                {"detail": _("Опрос завершён.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if validated_data["question_id"] != current_q.id:
            return Response(
                {"detail": _("Неверный вопрос.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            AnswerService.save_answer(
                session=session,
                question=current_q,
                selected_option=validated_data.get("selected_option"),
                custom_text=validated_data.get("custom_text"),
            )
        except IntegrityError:
            return Response(
                {"detail": _("Ответ на этот вопрос уже был сохранён.")},
                status=status.HTTP_409_CONFLICT,
            )

        PollSessionService.advance_to_next_question(session, poll, current_q)

        return Response(
            {"detail": _("Ответ сохранён.")}, status=status.HTTP_200_OK
        )
