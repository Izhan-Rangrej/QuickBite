from django.middleware.csrf import get_token


class EnsureCsrfCookieMiddleware:
    """Guarantee the `csrftoken` cookie exists on every page.

    Guest pages like the homepage contain no {% csrf_token %} form, so Django
    would never set the cookie — and cart.js (fetch + X-CSRFToken header)
    would get a 403 on the first add-to-cart. Calling get_token() marks the
    cookie for sending on every response.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        get_token(request)
        return self.get_response(request)
