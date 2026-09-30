from datetime import datetime


class Notification:
    def __init__(self, notification_id, recipient_id, message, related_request_id=None):
        self._notificationID = notification_id
        self._recipientID = recipient_id
        self._message = message
        self._relatedRequestID = related_request_id
        self._isRead = False
        self._timestamp = datetime.now()

    @property
    def recipient_id(self):
        return self._recipientID

    @property
    def message(self):
        return self._message

    @property
    def is_read(self):
        return self._isRead

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def related_request_id(self):
        return self._relatedRequestID

    def sendNotification(self, inbox):
        inbox.append(self)

    def markAsRead(self):
        self._isRead = True