"""
Full endpoint test: log into Brightspace via Playwright, capture Bearer token,
then exercise every feature endpoint needed for TruStudy.

Usage:
    BS_USER=yourNetID BS_PASS=yourPassword python test_brightspace.py
"""

import asyncio
import os
import httpx
from datetime import datetime, timedelta, timezone
from brightspace_auth import get_brightspace_token


BASE = "https://learn.truman.edu"
LP_VER = "1.57"
LE_VER = "1.92"


def print_resp(label: str, resp: httpx.Response, preview_keys: list[str] | None = None):
    print(f"[{label}] {resp.status_code}")
    if resp.status_code == 200:
        try:
            data = resp.json()
            if preview_keys:
                if isinstance(data, list):
                    for item in data[:3]:
                        print("  ", {k: item.get(k) for k in preview_keys if k in item})
                elif isinstance(data, dict):
                    print("  ", {k: data.get(k) for k in preview_keys if k in data})
            else:
                print("  ", str(data)[:300])
        except Exception:
            print("  (non-JSON response)")
    else:
        print(f"  {resp.text[:200]}")
    print()


async def main():
    username = os.getenv("BS_USER", "")
    password = os.getenv("BS_PASS", "")

    if not username or not password:
        print("ERROR: Set BS_USER and BS_PASS environment variables.")
        return

    # ── Step 1: Login ──────────────────────────────────────────────────────────
    print("=" * 60)
    print("STEP 1: Playwright SSO Login")
    print("=" * 60)
    token = await get_brightspace_token(username, password)

    if not token:
        print("ERROR: No Bearer token captured.")
        return

    print(f"Token: {token[:30]}...\n")

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=15) as c:

        # ── Step 2: Who am I ───────────────────────────────────────────────────
        print("=" * 60)
        print("STEP 2: Who Am I")
        print("=" * 60)
        resp = await c.get(f"/d2l/api/lp/{LP_VER}/users/whoami")
        print_resp("whoami", resp, ["Identifier", "FirstName", "LastName", "UniqueName"])

        # ── Step 3: Current semester courses ──────────────────────────────────
        print("=" * 60)
        print("STEP 3: Current Semester Courses")
        print("=" * 60)

        # Fetch all enrollments (paginated)
        all_enrollments = []
        bookmark = None
        while True:
            params = {"bookmark": bookmark} if bookmark else {}
            resp = await c.get(f"/d2l/api/lp/{LP_VER}/enrollments/myenrollments/", params=params)
            if resp.status_code != 200:
                print(f"[enrollments] {resp.status_code} {resp.text[:200]}")
                break
            page_data = resp.json()
            all_enrollments.extend(page_data.get("Items", []))
            bookmark = page_data.get("PagingInfo", {}).get("Bookmark")
            if not bookmark:
                break

        # Keep only active Course Offerings with a term prefix (SP/SM/FA)
        current_courses = [
            i for i in all_enrollments
            if i.get("Access", {}).get("IsActive")
            and i.get("OrgUnit", {}).get("Type", {}).get("Code") == "Course Offering"
            and i["OrgUnit"]["Name"][:2].upper() in ("SP", "SM", "FA")
        ]

        print(f"  Current semester courses ({len(current_courses)}):")
        for item in current_courses:
            ou = item["OrgUnit"]
            access = item.get("Access", {})
            end = access.get("EndDate", "")
            print(f"  - [{ou['Id']}] {ou['Name']}  (end={end[:10] if end else 'N/A'})")

        org_unit_id = current_courses[0]["OrgUnit"]["Id"] if current_courses else None
        if not org_unit_id:
            print("  No active courses found — skipping per-course tests.\n")
            return
        print(f"\n  Using orgUnitId={org_unit_id} for per-course tests\n")

        # ── Step 4: All student work across current courses ────────────────────
        print("=" * 60)
        print("STEP 4: All Student Work (Assignments, Quizzes, Overdue)")
        print("=" * 60)

        # 4A: Cross-course overdue items (single call)
        resp = await c.get(f"/d2l/api/le/{LE_VER}/overdueItems/myItems")
        print_resp("overdueItems/myItems", resp, ["ItemName", "DueDate", "OrgUnitName"])

        now_utc = datetime.now(timezone.utc)

        def is_future(due_str: str | None) -> bool:
            """True only if due date exists AND is strictly in the future."""
            if not due_str:
                return False  # no due date — exclude (can't determine urgency)
            try:
                return datetime.fromisoformat(due_str.rstrip("Z")).replace(tzinfo=timezone.utc) > now_utc
            except ValueError:
                return False

        def not_submitted(item_resp: httpx.Response) -> bool:
            """True if the student has no submissions for this item."""
            if item_resp.status_code != 200:
                return True  # can't determine — include to be safe
            data = item_resp.json()
            # data may be a list of submissions or a dict with Objects key
            items = data if isinstance(data, list) else data.get("Objects", data.get("Submissions", []))
            return len(items) == 0

        # 4B + 4C: Per-course loop
        for enrollment in current_courses:
            ou = enrollment["OrgUnit"]
            oid = ou["Id"]
            print(f"\n  --- Course: [{oid}] {ou['Name']} ---")

            # Assignments: future due date AND not yet submitted
            resp = await c.get(f"/d2l/api/le/{LE_VER}/{oid}/dropbox/folders/")
            if resp.status_code == 200:
                folders = resp.json() if isinstance(resp.json(), list) else resp.json().get("Objects", [])
                pending = []
                for folder in folders:
                    due = folder.get("DueDate")
                    print(f"    [debug] folder={folder.get('Name')!r}  DueDate={due}")
                    if not is_future(due):
                        print(f"      -> SKIP (not future)")
                        continue
                    fid = folder.get("Id")
                    sub_resp = await c.get(
                        f"/d2l/api/le/{LE_VER}/{oid}/dropbox/folders/{fid}/submissions/mysubmissions/"
                    )
                    submitted = not not_submitted(sub_resp)
                    print(f"      -> sub status={sub_resp.status_code}  submitted={submitted}  raw={sub_resp.text[:120]}")
                    if not submitted:
                        pending.append(folder)
                print(f"  [dropbox/{oid}] {len(pending)} pending assignments")
                for f in pending:
                    due = f.get("DueDate", "")
                    print(f"    - [{f.get('Id')}] {f.get('Name')}  due={due[:10]}")
                print()
            else:
                print(f"  [dropbox/{oid}] {resp.status_code} {resp.text[:100]}\n")

            # Quizzes: future due date AND no attempts submitted
            quiz_bookmark = None
            all_quizzes = []
            while True:
                qparams = {"bookmark": quiz_bookmark} if quiz_bookmark else {}
                resp = await c.get(f"/d2l/api/le/{LE_VER}/{oid}/quizzes/", params=qparams)
                if resp.status_code != 200:
                    print(f"  [quizzes/{oid}] {resp.status_code} {resp.text[:100]}\n")
                    break
                page = resp.json()
                all_quizzes.extend(page.get("Objects", []))
                quiz_bookmark = page.get("Next")
                if not quiz_bookmark:
                    break
            pending_quizzes = []
            for q in all_quizzes:
                due = q.get("DueDate")
                print(f"    [debug] quiz={q.get('Name')!r}  DueDate={due}")
                if not is_future(due):
                    print(f"      -> SKIP (not future)")
                    continue
                qid = q.get("QuizId")
                att_resp = await c.get(
                    f"/d2l/api/le/{LE_VER}/{oid}/quizzes/{qid}/attempts/currentUser"
                )
                submitted = not not_submitted(att_resp)
                print(f"      -> att status={att_resp.status_code}  submitted={submitted}  raw={att_resp.text[:120]}")
                if not submitted:
                    pending_quizzes.append(q)
            if pending_quizzes:
                print(f"  [quizzes/{oid}] {len(pending_quizzes)} pending quizzes/exams")
                for q in pending_quizzes:
                    print(f"    - [{q.get('QuizId')}] {q.get('Name')}  due={q.get('DueDate') or 'N/A'}")
                print()

            # Content items not yet completed with a future due date
            resp = await c.get(f"/d2l/api/le/{LE_VER}/{oid}/content/myItems/due/")
            print_resp(f"content/myItems/due/{oid}", resp, ["ItemName", "DueDate"])

        # ── Step 5: Calendar events (cross-course) ─────────────────────────────
        print("=" * 60)
        print("STEP 5: Calendar Events (all courses)")
        print("=" * 60)
        
        # Calculate time window: now to 30 days from now
        start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        end = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        
        params = {
            "orgUnitIdsCSV": str(org_unit_id),
            "startDateTime": start,
            "endDateTime": end
        }
        
        resp = await c.get(f"/d2l/api/le/{LE_VER}/calendar/events/myEvents/", params=params)
        print_resp("calendar/myEvents", resp, ["Id", "Title", "StartDay"])

        # ── Step 6: Full content tree + file download test ─────────────────────
        print("=" * 60)
        print("STEP 6: Content Tree (all modules/topics/files)")
        print("=" * 60)

        all_file_topics: list[dict] = []

        async def walk_module(oid: int, module_id: int, depth: int = 0) -> None:
            """Recursively walk a module's structure, printing and collecting file topics."""
            resp = await c.get(f"/d2l/api/le/{LE_VER}/{oid}/content/modules/{module_id}/structure/")
            if resp.status_code != 200:
                print(f"{'  ' * depth}[structure {module_id}] {resp.status_code} {resp.text[:80]}")
                return
            children = resp.json()
            if not isinstance(children, list):
                children = children.get("Structure", [])
            for item in children:
                item_type = item.get("Type")       # 0 = module, 1 = topic
                title = item.get("Title", "(untitled)")
                item_id = item.get("Id")
                indent = "  " * depth
                if item_type == 0:
                    # Module — recurse
                    print(f"{indent}[MODULE] {title}  (id={item_id})")
                    await walk_module(oid, item_id, depth + 1)
                elif item_type == 1:
                    topic_type = item.get("TopicType")  # 1=File, 3=Link
                    url = item.get("Url", "")
                    print(f"{indent}[TOPIC type={topic_type}] {title}  (id={item_id})  url={url[:60]}")
                    if topic_type == 1:  # File
                        all_file_topics.append({"id": item_id, "title": title, "oid": oid})
                else:
                    print(f"{indent}[UNKNOWN type={item_type}] {title}  (id={item_id})")

        resp = await c.get(f"/d2l/api/le/{LE_VER}/{org_unit_id}/content/root/")
        print(f"[content/root] {resp.status_code}")
        if resp.status_code == 200:
            root_modules = resp.json()
            if not isinstance(root_modules, list):
                root_modules = root_modules.get("Structure", [])
            print(f"  Root modules: {len(root_modules)}\n")
            for mod in root_modules:
                print(f"[ROOT MODULE] {mod.get('Title')}  (id={mod.get('Id')})")
                await walk_module(org_unit_id, mod.get("Id"), depth=1)
                print()
        else:
            print(f"  {resp.text[:200]}")

        print(f"\n  Total file topics found: {len(all_file_topics)}")
        for f in all_file_topics:
            print(f"  - [{f['id']}] {f['title']}")

        # ── Step 7: File download test (first file topic found) ────────────────
        if all_file_topics:
            first = all_file_topics[0]
            print()
            print("=" * 60)
            print(f"STEP 7: File Download (topicId={first['id']}  '{first['title']}')")
            print("=" * 60)
            resp = await c.get(
                f"/d2l/api/le/{LE_VER}/{first['oid']}/content/topics/{first['id']}/file",
                follow_redirects=True
            )
            size = len(resp.content)
            print(f"[file download] {resp.status_code} — {size} bytes")
            if resp.status_code == 200:
                print(f"  Content-Type: {resp.headers.get('content-type')}")
                print(f"  First 80 bytes: {resp.content[:80]}")
            else:
                print(f"  {resp.text[:200]}")
            print()

    print("=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
