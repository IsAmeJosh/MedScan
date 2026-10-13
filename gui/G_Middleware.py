"""One database transaction per web request."""
from django.conf import settings

from gui import G_Views


class TransactionPerRequest:
    """Opens one transaction for each web request, so every query of a page shares a single database
    connection (much faster than one connection per query). When the page is built without an error
    everything it changed is saved; if anything goes wrong everything it changed is undone.
    The connection is only opened if the page actually asks the database something."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        db = G_Views.db
        if db.in_transaction:  # already inside one (the tests do this): just join it
            return self.get_response(request)
        tx = db.begin()
        try:
            response = self.get_response(request)
        except BaseException:
            tx.rollback()
            raise
        if getattr(request, "medscan_failed", False) or response.status_code >= 500:
            tx.rollback()
        else:
            tx.commit()
        return response

    def process_exception(self, request, exception):
        """Django turns an error in a view into a 500 page before this class sees it, so note it here."""
        request.medscan_failed = True


class KeepSessionAsIs:
    """Some requests are not the user doing something: the page asking every few seconds whether there are new
    notifications. They must not start the idle logout timer again, so the renewed session cookie is taken off
    their answers (a view marks itself with request.medscan_passive). Must come before SessionMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(request, "medscan_passive", False):
            response.cookies.pop(settings.SESSION_COOKIE_NAME, None)
        return response
