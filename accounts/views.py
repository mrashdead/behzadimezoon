from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView, ListView, UpdateView
from .forms import ProfileUpdateForm, SettingsForm, AdminUserUpdateForm
from .models import User

class LoginPageView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True
    redirect_field_name = 'next'

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy('accounts:profile')

    def form_valid(self, form):
        messages.success(self.request, 'ورود شما با موفقیت انجام شد.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'نام کاربری یا رمز عبور نادرست است.')
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'ورود به حساب کاربری'
        return context


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"

    def get_form(self):
        return ProfileUpdateForm(instance=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form", self.get_form())
        context["page_title"] = "نمایه کاربری"

        if self.request.user.is_staff or self.request.user.is_superuser:
            context["managed_users"] = User.objects.exclude(pk=self.request.user.pk).order_by("username")[:10]

        return context

    def post(self, request, *args, **kwargs):
        form = ProfileUpdateForm(request.POST, instance=request.user)

        if form.is_valid():
            form.save()
            messages.success(request, "اطلاعات حساب کاربری با موفقیت بروزرسانی شد.")
            return redirect("accounts:profile")

        messages.error(request, "لطفاً خطاهای فرم را بررسی کنید.")
        return self.render_to_response(self.get_context_data(form=form))

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def handle_no_permission(self):
        messages.error(self.request, "شما دسترسی لازم برای این بخش را ندارید.")
        return redirect("accounts:profile")

class UserListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 20

    def get_queryset(self):
        return User.objects.exclude(pk=self.request.user.pk).order_by("username")

class UserUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = User
    form_class = AdminUserUpdateForm
    template_name = "accounts/user_update.html"
    success_url = reverse_lazy("accounts:user-list")

    def form_valid(self, form):
        messages.success(self.request, "اطلاعات کاربر با موفقیت بروزرسانی شد.")
        return super().form_valid(form)


class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/settings.html'
    login_url = reverse_lazy('accounts:login')
    redirect_field_name = 'next'

    def get_form(self):
        return SettingsForm(instance=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'تنظیمات حساب'
        context['form'] = kwargs.get('form', self.get_form())
        return context

    def post(self, request, *args, **kwargs):
        form = SettingsForm(request.POST, instance=request.user)

        if form.is_valid():
            form.save()
            messages.success(request, 'تنظیمات حساب با موفقیت بروزرسانی شد.')
            return redirect('accounts:settings')

        messages.error(request, 'لطفاً خطاهای فرم را بررسی کنید.')
        return self.render_to_response(self.get_context_data(form=form))


class LogoutView(LoginRequiredMixin, View):
    login_url = reverse_lazy('accounts:login')

    def post(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, 'شما با موفقیت از حساب کاربری خارج شدید.')
        return redirect('accounts:login')

    def get(self, request, *args, **kwargs):
        return redirect('accounts:profile')

class ForgotPasswordView(TemplateView):
    template_name = 'accounts/forgot-password.html'

class RegisterView(TemplateView):
    template_name = 'accounts/register.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'ثبت‌نام'
        return context
