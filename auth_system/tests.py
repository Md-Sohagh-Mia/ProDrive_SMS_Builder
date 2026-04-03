"""
Tests for auth_system: Customer model, forms, views, and authentication backend.

Run with:
    python manage.py test auth_system
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

Customer = get_user_model()


class CustomerModelTests(TestCase):
    def test_create_user(self):
        user = Customer.objects.create_user(
            email='alice@example.com',
            username='alice',
            password='SecurePass1!',
            company_name='Acme Corp',
        )
        self.assertEqual(user.email, 'alice@example.com')
        self.assertTrue(user.check_password('SecurePass1!'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_create_superuser(self):
        admin = Customer.objects.create_superuser(
            email='admin@example.com',
            username='adminuser',
            password='AdminPass1!',
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_email_required(self):
        with self.assertRaises(ValueError):
            Customer.objects.create_user(email='', username='nouser', password='pass')

    def test_username_required(self):
        with self.assertRaises(ValueError):
            Customer.objects.create_user(email='x@x.com', username='', password='pass')

    def test_failed_login_tracking(self):
        user = Customer.objects.create_user(
            email='bob@example.com', username='bob', password='BobPass1!'
        )
        user.record_failed_login()
        user.refresh_from_db()
        self.assertEqual(user.failed_login_attempts, 1)
        user.reset_failed_login()
        user.refresh_from_db()
        self.assertEqual(user.failed_login_attempts, 0)

    def test_get_full_name(self):
        user = Customer(full_name='Jane Doe', username='janedoe')
        self.assertEqual(user.get_full_name(), 'Jane Doe')

    def test_get_short_name_first_word(self):
        user = Customer(full_name='Jane Doe', username='janedoe')
        self.assertEqual(user.get_short_name(), 'Jane')

    def test_get_short_name_falls_back_to_username(self):
        user = Customer(full_name='', username='janedoe')
        self.assertEqual(user.get_short_name(), 'janedoe')

    def test_str(self):
        user = Customer(email='test@t.com', company_name='TestCo', username='testco')
        self.assertIn('test@t.com', str(user))


class LoginFormTests(TestCase):
    def test_valid_with_email(self):
        from auth_system.forms import LoginForm
        form = LoginForm(data={'identifier': 'user@example.com', 'password': 'pass'})
        self.assertTrue(form.is_valid())

    def test_valid_with_username(self):
        from auth_system.forms import LoginForm
        form = LoginForm(data={'identifier': 'myusername', 'password': 'pass'})
        self.assertTrue(form.is_valid())

    def test_invalid_missing_fields(self):
        from auth_system.forms import LoginForm
        form = LoginForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('identifier', form.errors)
        self.assertIn('password', form.errors)


class SignupFormTests(TestCase):
    def _valid_data(self):
        return {
            'company_name': 'Test Corp',
            'abn': '12 345 678 901',
            'address': '1 Test St, Sydney NSW 2000',
            'full_name': 'Test User',
            'role': 'Manager',
            'email': 'newuser@example.com',
            'phone_number': '+61412345678',
            'username': 'newuser',
            'password1': 'SecurePass1!',
            'password2': 'SecurePass1!',
            'terms': True,
        }

    def test_valid_form_creates_user(self):
        from auth_system.forms import SignupForm
        form = SignupForm(data=self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertTrue(user.check_password('SecurePass1!'))

    def test_passwords_must_match(self):
        from auth_system.forms import SignupForm
        data = self._valid_data()
        data['password2'] = 'DifferentPass1!'
        form = SignupForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

    def test_terms_required(self):
        from auth_system.forms import SignupForm
        data = self._valid_data()
        data['terms'] = False
        form = SignupForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('terms', form.errors)

    def test_weak_password_rejected(self):
        from auth_system.forms import SignupForm
        data = self._valid_data()
        data['password1'] = data['password2'] = 'abc'
        form = SignupForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors)


class AuthBackendTests(TestCase):
    def setUp(self):
        self.user = Customer.objects.create_user(
            email='carol@example.com',
            username='caroluser',
            password='CarolPass1!',
        )

    def test_authenticate_by_email(self):
        from auth_system.backends import EmailOrUsernameBackend
        backend = EmailOrUsernameBackend()
        user = backend.authenticate(None, username='carol@example.com', password='CarolPass1!')
        self.assertIsNotNone(user)
        self.assertEqual(user.pk, self.user.pk)

    def test_authenticate_by_username(self):
        from auth_system.backends import EmailOrUsernameBackend
        backend = EmailOrUsernameBackend()
        user = backend.authenticate(None, username='caroluser', password='CarolPass1!')
        self.assertIsNotNone(user)

    def test_wrong_password_returns_none(self):
        from auth_system.backends import EmailOrUsernameBackend
        backend = EmailOrUsernameBackend()
        user = backend.authenticate(None, username='carol@example.com', password='WrongPass!')
        self.assertIsNone(user)

    def test_wrong_password_increments_failed_attempts(self):
        from auth_system.backends import EmailOrUsernameBackend
        backend = EmailOrUsernameBackend()
        backend.authenticate(None, username='carol@example.com', password='WrongPass!')
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 1)

    def test_nonexistent_user_returns_none(self):
        from auth_system.backends import EmailOrUsernameBackend
        backend = EmailOrUsernameBackend()
        user = backend.authenticate(None, username='nobody@example.com', password='pass')
        self.assertIsNone(user)


class LoginViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Customer.objects.create_user(
            email='dave@example.com',
            username='daveuser',
            password='DavePass1!',
            full_name='Dave Test',
        )
        self.login_url = reverse('auth_system:login')
        self.dashboard_url = reverse('auth_system:dashboard')

    def test_get_login_page(self):
        resp = self.client.get(self.login_url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'auth_system/login.html')

    def test_login_with_email(self):
        resp = self.client.post(
            self.login_url,
            {'identifier': 'dave@example.com', 'password': 'DavePass1!'},
        )
        self.assertRedirects(resp, self.dashboard_url)

    def test_login_with_username(self):
        resp = self.client.post(
            self.login_url,
            {'identifier': 'daveuser', 'password': 'DavePass1!'},
        )
        self.assertRedirects(resp, self.dashboard_url)

    def test_login_wrong_password(self):
        resp = self.client.post(
            self.login_url,
            {'identifier': 'dave@example.com', 'password': 'WrongPass!'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid email/username or password')

    def test_authenticated_user_redirected_from_login(self):
        self.client.login(username='dave@example.com', password='DavePass1!')
        resp = self.client.get(self.login_url)
        self.assertRedirects(resp, self.dashboard_url)

    def test_locked_account(self):
        self.user.failed_login_attempts = 5
        self.user.save()
        resp = self.client.post(
            self.login_url,
            {'identifier': 'dave@example.com', 'password': 'DavePass1!'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'temporarily locked')


class LogoutViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Customer.objects.create_user(
            email='eve@example.com', username='eveuser', password='EvePass1!'
        )
        self.logout_url = reverse('auth_system:logout')
        self.login_url = reverse('auth_system:login')

    def test_get_logout_shows_confirmation(self):
        self.client.login(username='eve@example.com', password='EvePass1!')
        resp = self.client.get(self.logout_url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'auth_system/logout_confirm.html')

    def test_post_logout_redirects_to_login(self):
        self.client.login(username='eve@example.com', password='EvePass1!')
        resp = self.client.post(self.logout_url)
        self.assertRedirects(resp, self.login_url)

    def test_post_logout_clears_session(self):
        self.client.login(username='eve@example.com', password='EvePass1!')
        self.client.post(self.logout_url)
        resp = self.client.get(reverse('auth_system:dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp['Location'])


class SignupViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.signup_url = reverse('auth_system:signup')

    def _post_data(self):
        return {
            'company_name': 'New Corp',
            'abn': '98 765 432 109',
            'address': '2 New St, Melbourne VIC 3000',
            'full_name': 'New Person',
            'role': 'Director',
            'email': 'newperson@example.com',
            'phone_number': '+61498765432',
            'username': 'newperson',
            'password1': 'NewPerson1!',
            'password2': 'NewPerson1!',
            'terms': True,
        }

    def test_get_signup_page(self):
        resp = self.client.get(self.signup_url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'auth_system/signup.html')

    def test_successful_signup_creates_user_and_redirects(self):
        resp = self.client.post(self.signup_url, data=self._post_data())
        self.assertRedirects(resp, reverse('auth_system:dashboard'))
        self.assertTrue(Customer.objects.filter(email='newperson@example.com').exists())

    def test_duplicate_email_rejected(self):
        Customer.objects.create_user(
            email='newperson@example.com', username='existing', password='Pass1!'
        )
        resp = self.client.post(self.signup_url, data=self._post_data())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'already exists', msg_prefix='Duplicate email should show error')


class DashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Customer.objects.create_user(
            email='frank@example.com',
            username='frankuser',
            password='FrankPass1!',
            company_name='Frank LLC',
            full_name='Frank User',
        )
        self.dashboard_url = reverse('auth_system:dashboard')

    def test_unauthenticated_redirected(self):
        resp = self.client.get(self.dashboard_url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp['Location'])

    def test_authenticated_can_access(self):
        self.client.login(username='frank@example.com', password='FrankPass1!')
        resp = self.client.get(self.dashboard_url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'auth_system/dashboard.html')
        self.assertContains(resp, 'Frank LLC')
