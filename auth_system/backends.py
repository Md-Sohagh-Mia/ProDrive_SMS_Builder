from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    """
    Authenticate against email OR username with a password.
    Checked before Django's default ModelBackend.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        # Try email first, then username
        try:
            if '@' in username:
                user = User.objects.get(email=username)
            else:
                user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Run the default password hasher to mitigate timing attacks.
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            user.reset_failed_login()
            return user

        # Record failed attempt when user exists but password is wrong
        user.record_failed_login()
        return None
