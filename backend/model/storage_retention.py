"""Small durable tables owned by alarm retention, never algorithm configuration."""
from data.exts import db


class StorageRetentionSettings(db.Model):
    __tablename__ = 't_storage_retention_settings'
    __table_args__ = {'mysql_engine': 'InnoDB'}
    id = db.Column(db.Integer, primary_key=True)
    alarm_retention_days = db.Column(db.Integer, nullable=False, default=180)
    last_cleanup = db.Column(db.Text)
    orphan_scan_state = db.Column(db.Text)
    updated_at = db.Column(db.DateTime)


class AlarmMediaDeletion(db.Model):
    """A retry queue committed in the same transaction as alarm row deletion."""
    __tablename__ = 't_alarm_media_deletion'
    __table_args__ = {'mysql_engine': 'InnoDB'}
    path_hash = db.Column(db.String(64), primary_key=True)
    path = db.Column(db.Text, nullable=False)
    file_size = db.Column(db.BigInteger)
    file_mtime_ns = db.Column(db.BigInteger)
    created_at = db.Column(db.DateTime, nullable=False)
    checked_at = db.Column(db.DateTime, index=True)
