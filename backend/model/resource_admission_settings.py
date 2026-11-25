"""Persist one administrator-owned scheduling policy across container rebuilds."""
from data.exts import db


class ResourceAdmissionSettings(db.Model):
    __tablename__ = 't_resource_admission_settings'
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    policy_json = db.Column(db.Text, nullable=False)
    revision = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    updated_by = db.Column(db.String(32), nullable=False)
