"""Complement unbound devices only from an explicit stream ownership record."""
from data.exts import db
from model.equipment import Equipment
from model.extra import Zlk_data
from service.recorder_binding_identity import plan_binding_complements


def planned_binding_complements():
    devices = db.session.query(Equipment.id, Equipment.zlk_dat_id).all()
    sources = db.session.query(Zlk_data.id, Zlk_data.equipment_id).all()
    return plan_binding_complements(devices, sources)


def complement_unbound_devices():
    """Keep existing associations and commit explicit, unclaimed owners together."""
    try:
        count = 0
        for equipment_id, source_id in planned_binding_complements():
            count += db.session.query(Equipment).filter(
                Equipment.id == equipment_id,
                Equipment.zlk_dat_id.is_(None)).update(
                    {Equipment.zlk_dat_id: source_id}, synchronize_session=False)
        db.session.commit()
        return count
    except Exception:
        db.session.rollback()
        raise
