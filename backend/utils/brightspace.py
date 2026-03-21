"""Brightspace content tree walker — recursively builds a flat catalog of all course topics."""

import httpx

BS_BASE = "https://learn.truman.edu"
LE_VER = "1.92"


def get_content_catalog(org_unit_id: int, bs_token: str) -> list[dict]:
    """Walk the course content tree and return a flat list of all topics.

    Returns:
        [{"id": int, "title": str, "topic_type": int, "url": str|None, "module_path": str}]

    topic_type: 1 = downloadable file, 3 = link
    """
    catalog = []

    with httpx.Client(
        base_url=BS_BASE,
        headers={"Authorization": f"Bearer {bs_token}"},
        timeout=30,
        follow_redirects=True,
    ) as client:
        # Get root modules
        resp = client.get(f"/d2l/api/le/{LE_VER}/{org_unit_id}/content/root/")
        if resp.status_code != 200:
            print(f"[brightspace] Failed to get content root: {resp.status_code}")
            return catalog

        modules = resp.json()
        if not isinstance(modules, list):
            modules = modules.get("Structure", [])

        def walk(items: list, path: str = ""):
            for item in items:
                item_type = item.get("Type")
                title = item.get("Title", "")
                current_path = f"{path} > {title}" if path else title

                if item_type == 0:
                    # Module — recurse into children
                    module_id = item.get("Id")
                    if module_id is None:
                        continue
                    child_resp = client.get(
                        f"/d2l/api/le/{LE_VER}/{org_unit_id}/content/modules/{module_id}/structure/"
                    )
                    if child_resp.status_code == 200:
                        children = child_resp.json()
                        if not isinstance(children, list):
                            children = children.get("Structure", [])
                        walk(children, current_path)

                elif item_type == 1:
                    # Topic (leaf node) — extract file extension from title
                    file_ext = ""
                    dot_idx = title.rfind(".")
                    if dot_idx > 0:
                        file_ext = title[dot_idx:].lower()

                    catalog.append({
                        "id": item.get("Id"),
                        "title": title,
                        "topic_type": item.get("TopicType"),
                        "url": item.get("Url"),
                        "module_path": path,
                        "file_extension": file_ext,
                    })

        walk(modules)

    print(f"[brightspace] Content catalog: {len(catalog)} topics found for org_unit {org_unit_id}")
    return catalog
