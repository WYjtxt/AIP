"""Group one media observation by its exact application and stream names."""


def index_media_streams(rows):
    if rows is None:
        return None
    grouped = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        app, stream = row.get('app'), row.get('stream')
        if isinstance(app, str) and isinstance(stream, str):
            grouped.setdefault((app, stream), []).append(row)
    return grouped


def media_stream_rows(grouped, app, stream):
    if grouped is None:
        return None
    return grouped.get((app, stream), [])
