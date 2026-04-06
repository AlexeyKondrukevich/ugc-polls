from rest_framework import viewsets, generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers

from ugc.models import (
    Poll,
)
from ugc.serializers import (
    PollSerializer,
    PollDetailSerializer,
    QuestionSerializer,
    SubmitAnswerInputSerializer,
    RegisterSerializer,
)
from ugc.services import (
    AnswerService,
    PollSessionService,
)


@extend_schema_view(
    list=extend_schema(
        summary=_("Список опросов"),
        description=_("Возвращает список всех опросов с количеством вопросов.")
    ),
    retrieve=extend_schema(
        summary=_("Детали опроса"),
        description=_(
            "Возвращает опрос со всеми вопросами и вариантами ответов."
        )
    )
)
class PollViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Список опросов и детальная информация.
    """
    queryset = Poll.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PollDetailSerializer
        return PollSerializer


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
                    }
                ),
                "token": serializers.CharField(),
            }
        ),
        400: inline_serializer(
            name="ErrorResponse",
            fields={"detail": serializers.CharField()}
        ),
    }
)
class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
            "token": token.key
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    summary=_("Логин"),
    description=_("Аутентификация по username и password, возвращает токен."),
    request=inline_serializer(
        name="LoginRequest",
        fields={
            "username": serializers.CharField(),
            "password": serializers.CharField(),
        }
    ),
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
                    }
                ),
                "token": serializers.CharField(),
            }
        ),
        401: inline_serializer(
            name="ErrorResponse",
            fields={"error": serializers.CharField()}
        ),
    }
)
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        if user:
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
                "token": token.key
            })
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED
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
            location=OpenApiParameter.PATH
        ),
    ],
    responses={
        200: QuestionSerializer,
        204: OpenApiResponse(description=_("Опрос завершён")),
        401: OpenApiResponse(description=_("Не авторизован")),
        404: OpenApiResponse(description=_("Опрос не найден")),
    }
)
class NextQuestionView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, poll_id):
        poll = get_object_or_404(
            Poll.objects.prefetch_related(
                "questions__options"
            ),
            id=poll_id
        )
        session = PollSessionService.get_or_start_session(
            request.user,
            poll
        )

        if session is None:
            return Response(
                {"detail": _("Вы уже прошли этот опрос.")},
                status=status.HTTP_204_NO_CONTENT
            )

        if session.is_completed() or session.current_question is None:
            return Response(
                {"detail": _("Опрос завершён.")},
                status=status.HTTP_204_NO_CONTENT
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
            name="SubmitResponse",
            fields={"detail": serializers.CharField()}
        ),
        400: inline_serializer(
            name="ErrorResponse",
            fields={"detail": serializers.CharField()}
        ),
        401: OpenApiResponse(description=_("Не авторизован")),
        404: OpenApiResponse(description=_("Опрос не найден")),
    }
)
class SubmitAnswerView(APIView):
    permission_classes = (IsAuthenticated,)

    @transaction.atomic
    def post(self, request, poll_id):
        poll = get_object_or_404(Poll, id=poll_id)
        session = PollSessionService.get_active_session(
            request.user,
            poll
        )
        current_q = session.current_question

        if current_q is None:
            return Response(
                {"detail": _("Опрос завершён.")},
                status=status.HTTP_400_BAD_REQUEST
            )

        question_id = request.data.get("question_id")
        if int(question_id) != current_q.id:
            return Response(
                {"detail": _("Неверный вопрос.")},
                status=status.HTTP_400_BAD_REQUEST
            )

        AnswerService.save_answer(
            session=session,
            question=current_q,
            selected_option=request.data.get("selected_option"),
            custom_text=request.data.get("custom_text"),
        )

        PollSessionService.advance_to_next_question(
            session,
            poll,
            current_q
        )

        return Response(
            {"detail": _("Ответ сохранён.")},
            status=status.HTTP_200_OK
        )
