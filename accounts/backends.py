from django.contrib.auth.backends import ModelBackend

from .models import Customer


class EmailBackend(ModelBackend):
    """
    Authenticate against the Customer model using email + password.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # Support being called with keyword argument ``email`` as well as
        # the standard ``username`` keyword (which Django passes by default).
        email = kwargs.get('email', username)
        if email is None or password is None:
            return None
        try:
            user = Customer.objects.get(email__iexact=email)
        except Customer.DoesNotExist:
            # Run the hasher anyway to mitigate timing attacks.
            Customer().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return Customer.objects.get(pk=user_id)
        except Customer.DoesNotExist:
            return None
