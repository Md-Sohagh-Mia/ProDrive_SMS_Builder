from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


class LoginForm(forms.Form):
    """Login form that accepts either email or username."""

    identifier = forms.CharField(
        label='Email or Username',
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'company@email.com or username',
            'autofocus': True,
            'autocomplete': 'username',
        }),
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
        }),
    )
    remember_me = forms.BooleanField(required=False, label='Remember me for 30 days')

    def clean_identifier(self):
        return self.cleaned_data['identifier'].strip()


class SignupForm(forms.ModelForm):
    """Customer registration form."""

    password1 = forms.CharField(
        label='Create Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min. 8 characters',
            'autocomplete': 'new-password',
            'id': 'passField',
        }),
        help_text='Must be at least 8 characters and not entirely numeric.',
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repeat password',
            'autocomplete': 'new-password',
        }),
    )
    terms = forms.BooleanField(
        required=True,
        label='I agree to the Terms of Service and Privacy Policy.',
        error_messages={'required': 'You must agree to continue.'},
    )

    class Meta:
        model = User
        fields = [
            'company_name',
            'abn',
            'address',
            'full_name',
            'role',
            'email',
            'phone_number',
            'username',
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Apex Freight Pty Ltd', 'autocomplete': 'organization'}),
            'abn':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'XX XXX XXX XXX'}),
            'address':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123 Main Street, Sydney NSW 2000', 'autocomplete': 'street-address'}),
            'full_name':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name', 'autocomplete': 'name'}),
            'role':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Fleet Manager'}),
            'email':        forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@company.com.au', 'autocomplete': 'email'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+61 4XX XXX XXX', 'autocomplete': 'tel'}),
            'username':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose a unique username', 'autocomplete': 'username'}),
        }

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if password:
            try:
                validate_password(password)
            except ValidationError as exc:
                raise forms.ValidationError(exc.messages)
        return password

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Passwords do not match.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user
