from django.urls import path
from .views import (
    LoginPageView,
    ProfileView,
    SettingsView,
    LogoutView,
    ForgotPasswordView,
    RegisterView,
    UserListView,
    UserUpdateView,
    ManagedUserCreateView,
    PasswordChangeView,
)

app_name = 'accounts'

urlpatterns = [
    path('login/', LoginPageView.as_view(), name='login'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/create/", ManagedUserCreateView.as_view(), name="user-create"),
    path("users/<int:pk>/edit/", UserUpdateView.as_view(), name="user-update"),
    path('register/', RegisterView.as_view(), name='register'),
    path('settings/', SettingsView.as_view(), name='settings'),
    path('change-password/', PasswordChangeView.as_view(), name='change_password'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
