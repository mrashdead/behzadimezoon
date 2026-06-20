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


class ManagedUserCreationTestCase(TestCase):
    """Test user creation permissions and form validation."""

    def setUp(self):
        self.client = Client()
        self.superadmin = User.objects.create_user(
            username='superadmin',
            email='superadmin@example.com',
            password='testpass123',
            role=User.Role.SUPER_ADMIN
        )
        self.manager = User.objects.create_user(
            username='manager',
            email='manager@example.com',
            password='testpass123',
            role=User.Role.MANAGER
        )
        self.seller = User.objects.create_user(
            username='seller',
            email='seller@example.com',
            password='testpass123',
            role=User.Role.SELLER
        )

    # A1: Superuser can access user creation page
    def test_superadmin_can_access_user_create_page(self):
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.get(reverse('accounts:user-create'))
        self.assertEqual(response.status_code, 200)

    # A2: Superuser can create manager user
    def test_superadmin_can_create_manager(self):
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.post(reverse('accounts:user-create'), {
            'username': 'newmanager',
            'first_name': 'New',
            'last_name': 'Manager',
            'email': 'newmanager@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': User.Role.MANAGER
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newmanager').exists())
        new_user = User.objects.get(username='newmanager')
        self.assertEqual(new_user.role, User.Role.MANAGER)

    # A3: Superuser can create seller user
    def test_superadmin_can_create_seller(self):
        self.client.login(username='superadmin', password='testpass123')
        response = self.client.post(reverse('accounts:user-create'), {
            'username': 'newseller',
            'first_name': 'New',
            'last_name': 'Seller',
            'email': 'newseller@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': User.Role.SELLER
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newseller').exists())
        new_user = User.objects.get(username='newseller')
        self.assertEqual(new_user.role, User.Role.SELLER)

    # A4: Manager can access user creation page
    def test_manager_can_access_user_create_page(self):
        self.client.login(username='manager', password='testpass123')
        response = self.client.get(reverse('accounts:user-create'))
        self.assertEqual(response.status_code, 200)

    # A5: Manager can create seller user
    def test_manager_can_create_seller(self):
        self.client.login(username='manager', password='testpass123')
        response = self.client.post(reverse('accounts:user-create'), {
            'username': 'managercreatesseller',
            'first_name': 'Created',
            'last_name': 'Seller',
            'email': 'mcseller@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': User.Role.SELLER
        })
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(username='managercreatesseller')
        self.assertEqual(new_user.role, User.Role.SELLER)

    # A6: Manager cannot create manager user, even with tampered POST
    def test_manager_cannot_create_manager_even_with_tampered_post(self):
        self.client.login(username='manager', password='testpass123')
        response = self.client.post(reverse('accounts:user-create'), {
            'username': 'trymanager',
            'first_name': 'Try',
            'last_name': 'Manager',
            'email': 'trymanager@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': User.Role.MANAGER  # Try to sneak this in
        })
        # Form should reject it
        self.assertNotEqual(response.status_code, 302)
        # User should not be created with MANAGER role
        if User.objects.filter(username='trymanager').exists():
            user = User.objects.get(username='trymanager')
            self.assertNotEqual(user.role, User.Role.MANAGER)

    # A7: Manager cannot create superuser
    def test_manager_cannot_create_superuser(self):
        self.client.login(username='manager', password='testpass123')
        response = self.client.post(reverse('accounts:user-create'), {
            'username': 'trysuperadmin',
            'first_name': 'Try',
            'last_name': 'Super',
            'email': 'trysuperadmin@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': User.Role.SUPER_ADMIN
        })
        self.assertNotEqual(response.status_code, 302)
        if User.objects.filter(username='trysuperadmin').exists():
            user = User.objects.get(username='trysuperadmin')
            self.assertNotEqual(user.role, User.Role.SUPER_ADMIN)

    # A8: Seller cannot access user creation page
    def test_seller_cannot_access_user_create_page(self):
        self.client.login(username='seller', password='testpass123')
        response = self.client.get(reverse('accounts:user-create'))
        # UserPassesTestMixin redirects on permission failure, not 403
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/profile/', response.url)

    # A9: Seller cannot submit user creation POST
    def test_seller_cannot_submit_user_creation_post(self):
        self.client.login(username='seller', password='testpass123')
        response = self.client.post(reverse('accounts:user-create'), {
            'username': 'sellertries',
            'first_name': 'Seller',
            'last_name': 'Tries',
            'email': 'sellertries@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'role': User.Role.SELLER
        })
        # UserPassesTestMixin redirects on permission failure
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username='sellertries').exists())

    # A10: Anonymous user is redirected to login
    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('accounts:user-create'))
        # Should be redirected (either to login or profile with redirect)
        self.assertEqual(response.status_code, 302)


class PasswordChangeTestCase(TestCase):
    """Test password change functionality."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='OldPass123!',
            role=User.Role.SELLER
        )

    def test_password_change_page_requires_login(self):
        response = self.client.get(reverse('accounts:change_password'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_authenticated_user_can_access_password_change(self):
        self.client.login(username='testuser', password='OldPass123!')
        response = self.client.get(reverse('accounts:change_password'))
        self.assertEqual(response.status_code, 200)

    # E1: Wrong current password fails
    def test_wrong_current_password_fails(self):
        self.client.login(username='testuser', password='OldPass123!')
        response = self.client.post(reverse('accounts:change_password'), {
            'current_password': 'WrongPass123!',
            'new_password': 'NewPass123!',
            'new_password_confirm': 'NewPass123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())

    # E2: Mismatched new passwords fail
    def test_mismatched_new_passwords_fail(self):
        self.client.login(username='testuser', password='OldPass123!')
        response = self.client.post(reverse('accounts:change_password'), {
            'current_password': 'OldPass123!',
            'new_password': 'NewPass123!',
            'new_password_confirm': 'DifferentPass123!'
        })
        self.assertFalse(response.context['form'].is_valid())

    # E3: Weak password fails
    def test_weak_password_fails(self):
        self.client.login(username='testuser', password='OldPass123!')
        response = self.client.post(reverse('accounts:change_password'), {
            'current_password': 'OldPass123!',
            'new_password': '123',
            'new_password_confirm': '123'
        })
        self.assertFalse(response.context['form'].is_valid())

    # E4: Valid password change succeeds
    def test_valid_password_change_succeeds(self):
        self.client.login(username='testuser', password='OldPass123!')
        response = self.client.post(reverse('accounts:change_password'), {
            'current_password': 'OldPass123!',
            'new_password': 'NewPass123!',
            'new_password_confirm': 'NewPass123!'
        })
        self.assertEqual(response.status_code, 302)

        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass123!'))

    # E5: Session remains authenticated after password change
    def test_session_remains_authenticated_after_password_change(self):
        self.client.login(username='testuser', password='OldPass123!')
        response = self.client.post(reverse('accounts:change_password'), {
            'current_password': 'OldPass123!',
            'new_password': 'NewPass123!',
            'new_password_confirm': 'NewPass123!'
        }, follow=True)
        # User should still be authenticated
        self.assertTrue(response.context['user'].is_authenticated)

    # E6: All roles can access password change functionality
    def test_all_roles_can_change_password(self):
        users_by_role = {
            User.Role.SUPER_ADMIN: User.objects.create_user(
                username='superadmin2',
                email='sa@example.com',
                password='Pass123!',
                role=User.Role.SUPER_ADMIN
            ),
            User.Role.MANAGER: User.objects.create_user(
                username='manager2',
                email='m@example.com',
                password='Pass123!',
                role=User.Role.MANAGER
            ),
            User.Role.SELLER: User.objects.create_user(
                username='seller2',
                email='s@example.com',
                password='Pass123!',
                role=User.Role.SELLER
            )
        }

        for role, user in users_by_role.items():
            client = Client()
            client.login(username=user.username, password='Pass123!')
            response = client.get(reverse('accounts:change_password'))
            self.assertEqual(response.status_code, 200,
                           f"Role {role} should access password change page")


class ProfileTemplateButtonVisibilityTests(TestCase):
    """Template-level tests for presence/absence of Create User button."""

    def setUp(self):
        self.client = Client()
        self.superadmin = User.objects.create_user(
            username='superadmin_tpl',
            email='sa_tpl@example.com',
            password='TplPass123!',
            role=User.Role.SUPER_ADMIN
        )
        self.manager = User.objects.create_user(
            username='manager_tpl',
            email='m_tpl@example.com',
            password='TplPass123!',
            role=User.Role.MANAGER
        )
        self.seller = User.objects.create_user(
            username='seller_tpl',
            email='s_tpl@example.com',
            password='TplPass123!',
            role=User.Role.SELLER
        )

    def _has_create_user_button(self, response):
        content = response.content.decode('utf-8')
        try:
            url = reverse('accounts:user-create')
        except Exception:
            url = '/accounts/users/create/'
        return 'ایجاد کاربر جدید' in content and url in content

    def test_superadmin_sees_create_user_button(self):
        self.client.login(username='superadmin_tpl', password='TplPass123!')
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._has_create_user_button(response))

    def test_manager_sees_create_user_button(self):
        self.client.login(username='manager_tpl', password='TplPass123!')
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._has_create_user_button(response))

    def test_seller_does_not_see_create_user_button(self):
        self.client.login(username='seller_tpl', password='TplPass123!')
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._has_create_user_button(response))
