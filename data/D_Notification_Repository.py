from models.M_Notification import Notification


class NotificationRepository:
    """Reads and writes notifications (messages for patients and doctors)."""

    def __init__(self, db):
        self.db = db

    def add(self, recipient_id, message, related_request_id=None):
        """Save a new, unread notification. Returns its ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO notifications (recipient_id, message, related_request_id) VALUES (%s, %s, %s)",
                        (recipient_id, message, related_request_id))
            return cur.lastrowid

    def inbox(self, user_id, limit=None):
        """The user's notifications, newest first (at most `limit` of them)."""
        sql = ("SELECT notification_id, recipient_id, message, related_request_id, is_read, created_at "
               "FROM notifications WHERE recipient_id = %s ORDER BY notification_id DESC")
        params = [user_id]
        if limit:
            sql += " LIMIT %s"
            params.append(int(limit))
        with self.db.cursor() as cur:
            cur.execute(sql, params)
            return [Notification(row["notification_id"], row["recipient_id"], row["message"],
                                 row["related_request_id"], bool(row["is_read"]), row["created_at"])
                    for row in cur.fetchall()]

    def mark_read(self, user_id, notification_id):
        """Mark one notification as read, but only if it belongs to this user. Returns it, or None."""
        with self.db.unit_of_work():
            with self.db.cursor() as cur:
                cur.execute("UPDATE notifications SET is_read = 1 WHERE notification_id = %s AND recipient_id = %s",
                            (notification_id, user_id))
                cur.execute("SELECT notification_id, recipient_id, message, related_request_id, is_read, created_at "
                            "FROM notifications WHERE notification_id = %s AND recipient_id = %s",
                            (notification_id, user_id))
                row = cur.fetchone()
        if not row:
            return None
        return Notification(row["notification_id"], row["recipient_id"], row["message"],
                            row["related_request_id"], bool(row["is_read"]), row["created_at"])

    def mark_request_read(self, user_id, request_id):
        """Mark the user's notifications about one access request as read (it has been dealt with)."""
        with self.db.cursor() as cur:
            cur.execute("UPDATE notifications SET is_read = 1 WHERE recipient_id = %s AND related_request_id = %s "
                        "AND is_read = 0", (user_id, request_id))

    def unread_count(self, user_id):
        """How many of the user's notifications are unread."""
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM notifications WHERE recipient_id = %s AND is_read = 0",
                        (user_id,))
            return cur.fetchone()["n"]

    def mark_all_read(self, user_id):
        """Mark every notification of the user as read."""
        with self.db.cursor() as cur:
            cur.execute("UPDATE notifications SET is_read = 1 WHERE recipient_id = %s AND is_read = 0", (user_id,))
