from datetime import datetime


class Notification:
    """A message for one user, with a read/unread flag."""

    def __init__(self, notification_id, recipient_id, message, related_request_id=None,
                 is_read=False, timestamp=None):
        self._notification_id = notification_id
        self._recipient_id = recipient_id
        self._message = message
        self._related_request_id = related_request_id
        self._is_read = is_read
        self._timestamp = timestamp or datetime.now()

    @property
    def notification_id(self):
        """This notification's own ID number."""
        return self._notification_id

    @property
    def recipient_id(self):
        """ID of the user who receives this message."""
        return self._recipient_id

    @property
    def message(self):
        """The message text."""
        return self._message

    @property
    def is_read(self):
        """True once the user has opened it."""
        return self._is_read

    @property
    def timestamp(self):
        """When the notification was created."""
        return self._timestamp

    @property
    def related_request_id(self):
        """The access request this message is about, if any."""
        return self._related_request_id

    def send_notification(self, inbox):
        """Put this notification into the given inbox list."""
        inbox.append(self)

    def mark_as_read(self):
        """Flip the notification from unread to read."""
        self._is_read = True
