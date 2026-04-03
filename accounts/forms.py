from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Customer


class LoginForm(forms.Form):
    """Form for customer email/password login."""

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'id': 'loginEmail',
            'placeholder': 'company@email.com',
            'autocomplete': 'email',
        }),
        label='Company Email',
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'loginPassword',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
        }),
        label='Password',
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'id': 'rememberMe'}),
        label='Remember me for 30 days',
    )

    def clean_email(self):
        return self.cleaned_data['email'].lower()


class SignupForm(forms.ModelForm):
    """
    Customer registration form.

    Collects company info, contact person details and a password pair.
    """

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'passField',
            'placeholder': 'Min. 8 characters',
            'autocomplete': 'new-password',
        }),
        label='Create Password',
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'passConfirm',
            'placeholder': 'Repeat password',
            'autocomplete': 'new-password',
        }),
        label='Confirm Password',
    )
    terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the Terms of Service and Privacy Policy.'},
    )

    class Meta:
        model = Customer
        fields = [
            'company_name',
            'abn',
            'address',
            'full_name',
            'role',
            'email',
            'phone_number',
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'companyName',
                'placeholder': 'e.g. Apex Freight Pty Ltd',
                'autocomplete': 'organization',
            }),
            'abn': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'abnField',
                'placeholder': 'XX XXX XXX XXX',
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'addressField',
                'placeholder': '123 Main Street, Sydney NSW 2000',
                'autocomplete': 'street-address',
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'fullName',
                'placeholder': 'Full name',
                'autocomplete': 'name',
            }),
            'role': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'roleField',
                'placeholder': 'e.g. Fleet Manager',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'id': 'emailField',
                'placeholder': 'name@company.com.au',
                'autocomplete': 'email',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'phoneField',
                'placeholder': '+61 4XX XXX XXX',
                'autocomplete': 'tel',
            }),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if Customer.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email address already exists.')
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        password_confirm = cleaned.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', 'Passwords do not match.')
        return cleaned

    def save(self, commit=True):
        customer = super().save(commit=False)
        # Derive a unique username from the email local-part
        base = self.cleaned_data['email'].split('@')[0]
        username = base
        counter = 1
        while Customer.objects.filter(username=username).exists():
            username = f'{base}{counter}'
            counter += 1
        customer.username = username
        customer.set_password(self.cleaned_data['password'])
        if commit:
            customer.save()
        return customer
