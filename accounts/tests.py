from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from accounts.forms import ProfileUpdateForm, SettingsForm, AdminUserUpdateForm

User = get_user_model()


class AccountsFormsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )

    def test_profile_form_fields(self):
        form = ProfileUpdateForm(instance=self.user)
        self.assertIn('first_name', form.fields)
        self.assertIn('last_name', form.fields)
        self.assertIn('email', form.fields)
        self.assertEqual(len(form.fields), 3)

    def test_settings_form_fields(self):
        form = SettingsForm(instance=self.user)
        self.assertIn('first_name', form.fields)
        self.assertIn('last_name', form.fields)
        self.assertIn('email', form.fields)
        self.assertEqual(len(form.fields), 3)

    def test_settings_form_has_labels(self):
        form = SettingsForm()
        self.assertIsNotNone(form.fields['first_name'].label)
        self.assertIsNotNone(form.fields['last_name'].label)
        self.assertIsNotNone(form.fields['email'].label)

    def test_form_widgets_have_form_control_class(self):
        form = SettingsForm()
        for field_name in form.fields:
            attrs = form.fields[field_name].widget.attrs
            self.assertIn('class', attrs)
            self.assertIn('form-control', attrs['class'])

    def test_form_has_placeholders(self):
        form = SettingsForm()
        for field_name in form.fields:
            attrs = form.fields[field_name].widget.attrs
            self.assertIn('placeholder', attrs)

    def test_admin_user_form_fields(self):
        form = AdminUserUpdateForm(instance=self.user)
        self.assertIn('first_name', form.fields)
        self.assertIn('last_name', form.fields)
        self.assertIn('email', form.fields)
        self.assertIn('is_active', form.fields)
        self.assertEqual(len(form.fields), 4)

    def test_profile_form_saves_data(self):
        form = ProfileUpdateForm(
            {
                'first_name': 'Updated',
                'last_name': 'Name',
                'email': 'updated@example.com'
            },
            instance=self.user
        )
        self.assertTrue(form.is_valid())
        form.save()

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')
        self.assertEqual(self.user.email, 'updated@example.com')

    def test_settings_form_saves_data(self):
        form = SettingsForm(
            {
                'first_name': 'New',
                'last_name': 'Value',
                'email': 'new@example.com'
            },
            instance=self.user
        )
        self.assertTrue(form.is_valid())
        form.save()

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'New')
        self.assertEqual(self.user.last_name, 'Value')
        self.assertEqual(self.user.email, 'new@example.com')

    def test_form_validation_email(self):
        form = SettingsForm(
            {
                'first_name': 'Test',
                'last_name': 'User',
                'email': 'invalid-email'
            },
            instance=self.user
        )
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class ProfileViewTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

    def test_profile_view_requires_login(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_profile_view_get(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('page_title', response.context)

    def test_profile_view_form_is_profile_update_form(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:profile'))
        form = response.context['form']
        self.assertIsInstance(form, ProfileUpdateForm)

    def test_profile_view_user_data_in_context(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.context['user'].username, 'testuser')
        self.assertEqual(response.context['user'].email, 'test@example.com')

    def test_profile_view_admin_sees_managed_users(self):
        self.client.login(username='adminuser', password='testpass123')
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('managed_users', response.context)

    def test_profile_view_regular_user_no_managed_users(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:profile'))
        self.assertNotIn('managed_users', response.context)

    def test_profile_view_post_updates_user(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('accounts:profile'), {
            'first_name': 'Updated',
            'last_name': 'Name',
            'email': 'updated@example.com'
        })
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')
        self.assertEqual(self.user.email, 'updated@example.com')

    def test_profile_view_post_invalid_email(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('accounts:profile'), {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'invalid'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertFalse(response.context['form'].is_valid())
        self.assertIn('email', response.context['form'].errors)


class SettingsViewTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )

    def test_settings_view_requires_login(self):
        response = self.client.get(reverse('accounts:settings'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_settings_view_get(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:settings'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('page_title', response.context)

    def test_settings_view_form_is_settings_form(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:settings'))
        form = response.context['form']
        self.assertIsInstance(form, SettingsForm)

    def test_settings_view_user_data_in_context(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:settings'))
        self.assertEqual(response.context['user'].username, 'testuser')
        self.assertEqual(response.context['user'].email, 'test@example.com')

    def test_settings_view_post_updates_user(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('accounts:settings'), {
            'first_name': 'NewFirst',
            'last_name': 'NewLast',
            'email': 'newemail@example.com'
        })
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'NewFirst')
        self.assertEqual(self.user.last_name, 'NewLast')
        self.assertEqual(self.user.email, 'newemail@example.com')

    def test_settings_view_post_invalid_email(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('accounts:settings'), {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'not-an-email'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertFalse(response.context['form'].is_valid())
        self.assertIn('email', response.context['form'].errors)

    def test_settings_view_post_missing_required_field(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('accounts:settings'), {
            'first_name': '',
            'last_name': 'User',
            'email': 'test@example.com'
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, '')

    def test_settings_view_redirects_on_success(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('accounts:settings'), {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com'
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/settings/', response.url)
