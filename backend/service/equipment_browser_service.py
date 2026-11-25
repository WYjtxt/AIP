"""Read-only queries for the camera-management browser.

This page needs device metadata, not algorithms, templates or credentialed
playback URLs. Keep its choices small and load descendants by tree level
instead of recursively issuing several queries for every camera.
"""
from sqlalchemy.orm import aliased


LIST_FIELDS = (
    'id', 'equipment_type', 'manufacturer_type', 'equipment_name',
    'equipment_ip', 'equipment_uname', 'equipment_aisles',
    'equipment_codetype', 'user_status', 'create_time', 'parent_id', 'code',
    'flower_frames', 'equipment_width_height', 'online',
    'equipment_constantBitRate', 'equipment_maxFrameRate', 'Hik_indexCode',
    'Ziguang_ape_indexCode',
)


def _positive_int(value, default, maximum=None):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    if value < 1:
        return default
    return min(value, maximum) if maximum else value


def _tree(rows, roots):
    """Attach each row once, tolerating legacy orphaned/cyclic records."""
    by_parent = {}
    for row in rows:
        by_parent.setdefault(row.get('parent_id'), []).append(row)

    def attach(node, ancestors):
        children = []
        for child in by_parent.get(node['id'], ()):
            if child['id'] in ancestors:
                continue
            attach(child, ancestors | {child['id']})
            children.append(child)
        if children:
            node['children'] = children

    for root in roots:
        attach(root, {root['id']})
    return roots


class EquipmentBrowser:
    """Models are passed explicitly so importing this module starts no services."""

    def __init__(self, session, equipment_model, mine_model, options):
        self.session = session
        self.equipment = equipment_model
        self.mine = mine_model
        self.options = options

    def choices(self, params):
        equipment = self.equipment
        query = self.session.query(
            equipment.id, equipment.equipment_name, equipment.equipment_type,
            equipment.parent_id, equipment.Mine_id,
        )
        rows = [dict(row._mapping) for row in query.order_by(equipment.id).all()]
        roots = [row for row in rows if row['parent_id'] is None and (
            not params.get('mine_id') or str(row['Mine_id']) == str(params.get('mine_id')))]
        mines = self.session.query(self.mine.id, self.mine.mine_name).order_by(self.mine.id).all()
        return {
            'code': 200, 'msg': '筛选数据',
            'equipment_list': _tree(rows, roots),
            'equipment_type': self.options.equipment_type,
            'manufacturer_type': self.options.manufacturer_type,
            'mine_list': [dict(row._mapping) for row in mines],
            'equipment_codetype': self.options.equipment_codetype,
        }

    def _metadata_query(self):
        equipment = self.equipment
        parent = aliased(equipment)
        columns = [getattr(equipment, field) for field in LIST_FIELDS]
        # The UI can show a mask without selecting or returning the password.
        columns.append((equipment.equipment_password.isnot(None) &
                        (equipment.equipment_password != '')).label('_password_set'))
        columns.append(parent.equipment_ip.label('parent_ip'))
        return self.session.query(*columns).outerjoin(parent, equipment.parent_id == parent.id)

    @staticmethod
    def _serialize(row):
        result = dict(row._mapping)
        result['equipment_password'] = '********' if result.pop('_password_set') else ''
        result['equipment_code'] = result.get('code')
        return result

    def page(self, params):
        equipment = self.equipment
        page = _positive_int(params.get('page'), 1)
        per_page = _positive_int(params.get('per_page'), 15, 300)
        selected_id = _positive_int(params.get('equipment_name'), None)
        if params.get('equipment_name') and selected_id is None:
            return {'code': 400, 'msg': '设备ID无效'}
        filters = [equipment.id == selected_id] if selected_id else [equipment.parent_id.is_(None)]
        type_ids = {part.strip() for part in str(params.get('equipment_type') or '').split(',') if part.strip()}
        types = [item['value'] for item in self.options.equipment_type if str(item['id']) in type_ids]
        if types:
            filters.append(equipment.equipment_type.in_(types))
        name = params.get('equipment_name1')
        if name:
            filters.append(equipment.equipment_name.contains(str(name), autoescape=True))

        total = self.session.query(equipment.id).filter(*filters).count()
        roots = [self._serialize(row) for row in self._metadata_query().filter(*filters)
                 .order_by(equipment.id).offset((page - 1) * per_page).limit(per_page).all()]
        descendants = []
        seen = {row['id'] for row in roots}
        frontier = list(seen)
        while frontier:
            rows = self._metadata_query().filter(equipment.parent_id.in_(frontier)).order_by(equipment.id).all()
            next_frontier = []
            for row in rows:
                if row.id in seen:
                    continue
                value = self._serialize(row)
                descendants.append(value)
                next_frontier.append(row.id)
                seen.add(row.id)
            frontier = next_frontier
        return {'code': 200, 'msg': '查询成功', 'data_list': {
            'total_items': total,
            'total_pages': (total + per_page - 1) // per_page,
            'current_page': page, 'per_page': per_page,
            'data': _tree(descendants, roots),
        }}
