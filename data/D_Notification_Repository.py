"""Reads and writes notifications."""
from models.M_Notification import Notification


class NotificationRepository:
    """The only place that writes SQL about notifications, the messages shown in the bell. The rest of the program
    asks for Notification objects and never sees a query (abstraction)."""

    def __init__(self, db):
        """Keep the Database that every query goes through."""
        self.db = db

    COLUMNS = "notification_id, recipient_id, message, related_request_id, is_read, created_at, kind"

    @staticmethod
    def _build(row):
        """Make a Notification from one database row."""
        return Notification(row["notification_id"], row["recipient_id"], row["message"], row["related_request_id"],
                            bool(row["is_read"]), row["created_at"], row["kind"])

    def add(self, recipient_id, message, related_request_id=None, kind="info"):
        """Save a new notification, unread. Returns its ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO tb_notifications (recipient_id, message, kind, related_request_id) "
                        "VALUES (%s, %s, %s, %s)", (recipient_id, message, kind, related_request_id))
            return cur.lastrowid

    def inbox(self, user_id, limit=None):
        """The user's notifications, newest first, at most `limit` of them."""
        sql = f"SELECT {self.COLUMNS} FROM tb_notifications WHERE recipient_id = %s ORDER BY notification_id DESC"
        params = [user_id]
        if limit:
            sql += " LIMIT %s"
            params.append(int(limit))
        with self.db.cursor() as cur:
            cur.execute(sql, params)
            return [self._build(row) for row in cur.fetchall()]

    def mark_read(self, user_id, notification_id):
        """Mark one notification as read, but only if it belongs to this user, so nobody can touch someone else's.
        Returns it, or None."""
        with self.db.unit_of_work():
            with self.db.cursor() as cur:
                cur.execute("UPDATE tb_notifications SET is_read = 1 WHERE notification_id = %s AND recipient_id = %s",
                            (notification_id, user_id))
                cur.execute(f"SELECT {self.COLUMNS} FROM tb_notifications WHERE notification_id = %s AND recipient_id = %s",
                            (notification_id, user_id))
                row = cur.fetchone()
        return self._build(row) if row else None

    def mark_request_read(self, user_id, request_id):
        """Mark the user's notifications about one access request as read, because that request has now been dealt
        with."""
        with self.db.cursor() as cur:
            cur.execute("UPDATE tb_notifications SET is_read = 1 WHERE recipient_id = %s AND related_request_id = %s "
                        "AND is_read = 0", (user_id, request_id))

    def unread_count(self, user_id):
        """How many of the user's notifications are still unread. This is the number behind the bell's red mark."""
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM tb_notifications WHERE recipient_id = %s AND is_read = 0",
                        (user_id,))
            return cur.fetchone()["n"]

    def mark_all_read(self, user_id):
        """Mark every notification of the user as read."""
        with self.db.cursor() as cur:
            cur.execute("UPDATE tb_notifications SET is_read = 1 WHERE recipient_id = %s AND is_read = 0", (user_id,))
