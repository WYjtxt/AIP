"""Durable platform preview settings; no camera or algorithm configuration."""
from data.exts import db


class PreviewSettings(db.Model):
    __tablename__ = 't_preview_settings'
    id = db.Column(db.Integer, primary_key=True)
    max_streams = db.Column(db.Integer, nullable=False)
