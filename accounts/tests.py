from django.test import Client, TestCase
from django.urls import reverse

from .models import Customer


class CustomerModelTest(TestCase):
    def test_create_user(self):
        user = Customer.objects.create_user(
            email='user@example.com',
            password='SecurePass1!',
            username='testuser',
            full_name='Test User',
            company_name='Test Co',
        )
        self.assertEqual(str(user), 'Test User <user@example.com>')
        self.assertTrue(user.check_password('SecurePass1!'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_create_superuser(self):
        admin = Customer.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass1!',
            username='adminuser',
            full_name='Admin User',
            company_name='Admin Co',
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_email_required(self):
        with self.assertRaises(ValueError):
            Customer.objects.create_user(email='', password='pass')

    def test_get_short_name(self):
        user = Customer.objects.create_user(
            email='short@example.com',
            password='pass',
            username='shortuser',
            full_name='Jane Doe',
            company_name='Co',
        )
        self.assertEqual(user.get_short_name(), 'Jane')


class LoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = Customer.objects.create_user(
            email='login@example.com',
            password='LoginPass1!',
            username='loginuser',
            full_name='Login User',
            company_name='Login Co',
        )

    def test_login_page_get(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PRODRIVE')

    def test_login_success(self):
        response = self.client.post(reverse('accounts:login'), {
            'email': 'login@example.com',
            'password': 'LoginPass1!',
        })
        self.assertRedirects(response, reverse('accounts:dashboard'))

    def test_login_invalid_credentials(self):
        response = self.client.post(reverse('accounts:login'), {
            'email': 'login@example.com',
            'password': 'WrongPassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid email')

    def test_login_redirects_if_authenticated(self):
        self.client.login(email='login@example.com', password='LoginPass1!')
        response = self.client.get(reverse('accounts:login'))
        self.assertRedirects(response, reverse('accounts:dashboard'))


class LogoutViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = Customer.objects.create_user(
            email='logout@example.com',
            password='LogoutPass1!',
            username='logoutuser',
            full_name='Logout User',
            company_name='Logout Co',
        )

    def test_logout_confirmation_get(self):
        self.client.login(email='logout@example.com', password='LogoutPass1!')
        response = self.client.get(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign out')

    def test_logout_post(self):
        self.client.login(email='logout@example.com', password='LogoutPass1!')
        response = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('accounts:login'))
        # Verify user is actually logged out
        response2 = self.client.get(reverse('accounts:dashboard'))
        self.assertRedirects(response2, f"{reverse('accounts:login')}?next={reverse('accounts:dashboard')}")


class SignupViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_signup_page_get(self):
        response = self.client.get(reverse('accounts:signup'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'company account')

    def test_signup_success(self):
        response = self.client.post(reverse('accounts:signup'), {
            'company_name': 'New Company Pty Ltd',
            'abn': '12 345 678 901',
            'address': '1 Test St, Sydney NSW 2000',
            'full_name': 'New User',
            'role': 'Fleet Manager',
            'email': 'new@newcompany.com',
            'phone_number': '+61 400 000 000',
            'password': 'NewPass123!',
            'password_confirm': 'NewPass123!',
            'terms': True,
        })
        self.assertRedirects(response, reverse('accounts:dashboard'))
        self.assertTrue(Customer.objects.filter(email='new@newcompany.com').exists())

    def test_signup_duplicate_email(self):
        Customer.objects.create_user(
            email='existing@example.com',
            password='pass',
            username='existinguser',
            full_name='Existing',
            company_name='Co',
        )
        response = self.client.post(reverse('accounts:signup'), {
            'company_name': 'Another Co',
            'full_name': 'Another User',
            'email': 'existing@example.com',
            'password': 'AnotherPass1!',
            'password_confirm': 'AnotherPass1!',
            'terms': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')

    def test_signup_password_mismatch(self):
        response = self.client.post(reverse('accounts:signup'), {
            'company_name': 'Co',
            'full_name': 'User',
            'email': 'mismatch@example.com',
            'password': 'Pass123!',
            'password_confirm': 'Different123!',
            'terms': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'do not match')


class DashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = Customer.objects.create_user(
            email='dash@example.com',
            password='DashPass1!',
            username='dashuser',
            full_name='Dash User',
            company_name='Dash Co',
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:dashboard')}",
        )

    def test_dashboard_accessible_when_logged_in(self):
        self.client.login(email='dash@example.com', password='DashPass1!')
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dash User')
        self.assertContains(response, 'Dash Co')
