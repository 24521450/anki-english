from __future__ import annotations

def pytest_collection_modifyitems(config, items):
    if config.option.markexpr:
        return

    selected = []
    deselected = []
    for item in items:
        if item.get_closest_marker("historical") or item.get_closest_marker("external"):
            deselected.append(item)
        else:
            selected.append(item)

    if deselected:
        items[:] = selected
        config.hook.pytest_deselected(items=deselected)
