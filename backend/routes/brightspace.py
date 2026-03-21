from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

from dependencies import get_bs_token
from brightspace_auth import get_brightspace_token

router = APIRouter(prefix="/api")

BS_BASE = "https://learn.truman.edu"
LP_VER = "1.57"
LE_VER = "1.92"


def _bs_client(token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=BS_BASE,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
        follow_redirects=True,
    )


def _is_future(due_str: str | None) -> bool:
    if not due_str:
        return False
    try:
        return datetime.fromisoformat(due_str.rstrip("Z")).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
    except ValueError:
        return False


async def _get_active_courses(c: httpx.AsyncClient) -> list[dict]:
    """Paginate enrollments and return active Course Offerings with SP/SM/FA prefix."""
    all_enrollments = []
    bookmark = None
    while True:
        params = {"bookmark": bookmark} if bookmark else {}
        resp = await c.get(f"/d2l/api/lp/{LP_VER}/enrollments/myenrollments/", params=params)
        if resp.status_code != 200:
            break
        page = resp.json()
        all_enrollments.extend(page.get("Items", []))
        bookmark = page.get("PagingInfo", {}).get("Bookmark")
        if not bookmark:
            break
    return [
        i for i in all_enrollments
        if i.get("Access", {}).get("IsActive")
        and i.get("OrgUnit", {}).get("Type", {}).get("Code") == "Course Offering"
        and i["OrgUnit"]["Name"][:2].upper() in ("SP", "SM", "FA")
    ]


# ── POST /api/auth/login ──────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(body: LoginRequest):
    token = await get_brightspace_token(body.username, body.password)
    if not token:
        raise HTTPException(status_code=401, detail="Login failed — no token captured")

    async with _bs_client(token) as c:
        resp = await c.get(f"/d2l/api/lp/{LP_VER}/users/whoami")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch user info from Brightspace")
        user = resp.json()

    return {
        "token": token,
        "user_id": user.get("Identifier"),
        "first_name": user.get("FirstName"),
        "last_name": user.get("LastName"),
        "username": user.get("UniqueName"),
    }


# ── GET /api/courses ──────────────────────────────────────────────────────────

@router.get("/courses")
async def get_courses(token: str = Depends(get_bs_token)):
    async with _bs_client(token) as c:
        courses = await _get_active_courses(c)
    return [
        {
            "id": i["OrgUnit"]["Id"],
            "name": i["OrgUnit"]["Name"],
            "end_date": i.get("Access", {}).get("EndDate"),
        }
        for i in courses
    ]


# ── GET /api/dashboard/work ───────────────────────────────────────────────────

@router.get("/dashboard/work")
async def get_dashboard_work(token: str = Depends(get_bs_token)):
    async with _bs_client(token) as c:
        courses = await _get_active_courses(c)
        result = []

        for enrollment in courses:
            ou = enrollment["OrgUnit"]
            oid = ou["Id"]
            course_work = {"course_id": oid, "course_name": ou["Name"], "assignments": [], "quizzes": []}

            # Assignments (dropbox folders) — future due date only
            resp = await c.get(f"/d2l/api/le/{LE_VER}/{oid}/dropbox/folders/")
            if resp.status_code == 200:
                folders = resp.json() if isinstance(resp.json(), list) else resp.json().get("Objects", [])
                for f in folders:
                    if _is_future(f.get("DueDate")):
                        course_work["assignments"].append({
                            "id": f.get("Id"),
                            "name": f.get("Name"),
                            "due_date": f.get("DueDate"),
                            "type": "assignment",
                        })

            # Quizzes — paginated, future due date only
            quiz_bookmark = None
            while True:
                qparams = {"bookmark": quiz_bookmark} if quiz_bookmark else {}
                resp = await c.get(f"/d2l/api/le/{LE_VER}/{oid}/quizzes/", params=qparams)
                if resp.status_code != 200:
                    break
                page = resp.json()
                for q in page.get("Objects", []):
                    if _is_future(q.get("DueDate")):
                        course_work["quizzes"].append({
                            "id": q.get("QuizId"),
                            "name": q.get("Name"),
                            "due_date": q.get("DueDate"),
                            "type": "quiz",
                        })
                quiz_bookmark = page.get("Next")
                if not quiz_bookmark:
                    break

            if course_work["assignments"] or course_work["quizzes"]:
                result.append(course_work)

    return result


# ── GET /api/assignments/{org_unit_id}/{folder_id} ────────────────────────────

@router.get("/assignments/{org_unit_id}/{folder_id}")
async def get_assignment_detail(org_unit_id: int, folder_id: int, token: str = Depends(get_bs_token)):
    async with _bs_client(token) as c:
        resp = await c.get(f"/d2l/api/le/{LE_VER}/{org_unit_id}/dropbox/folders/{folder_id}")
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Failed to fetch assignment detail")
        folder = resp.json()

        instructions = folder.get("CustomInstructions") or {}
        attachments = [
            {
                "file_id": a.get("FileId"),
                "file_name": a.get("FileName"),
                "size": a.get("Size"),
            }
            for a in (folder.get("Attachments") or [])
        ]
        link_attachments = [
            {
                "link_id": l.get("LinkId"),
                "link_name": l.get("LinkName"),
                "href": l.get("Href"),
            }
            for l in (folder.get("LinkAttachments") or [])
        ]

    return {
        "id": folder.get("Id"),
        "name": folder.get("Name"),
        "instructions_html": instructions.get("Html", ""),
        "instructions_text": instructions.get("Text", ""),
        "due_date": folder.get("DueDate"),
        "start_date": (folder.get("Availability") or {}).get("StartDate"),
        "end_date": (folder.get("Availability") or {}).get("EndDate"),
        "attachments": attachments,
        "link_attachments": link_attachments,
        "score_denominator": (folder.get("Assessment") or {}).get("ScoreDenominator"),
        "submission_type": folder.get("SubmissionType"),
        "is_hidden": folder.get("IsHidden"),
    }


# ── GET /api/courses/{org_unit_id}/modules ─────────────────────────────────────

@router.get("/courses/{org_unit_id}/modules")
async def get_root_modules(org_unit_id: int, token: str = Depends(get_bs_token)):
    async with _bs_client(token) as c:
        resp = await c.get(f"/d2l/api/le/{LE_VER}/{org_unit_id}/content/root/")
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Failed to fetch content root")
        modules = resp.json()
        if not isinstance(modules, list):
            modules = modules.get("Structure", [])

    return [
        {"id": m.get("Id"), "title": m.get("Title"), "type": 0}
        for m in modules
    ]


# ── GET /api/courses/{org_unit_id}/modules/{module_id} ────────────────────────

@router.get("/courses/{org_unit_id}/modules/{module_id}")
async def get_module_children(org_unit_id: int, module_id: int, token: str = Depends(get_bs_token)):
    async with _bs_client(token) as c:
        resp = await c.get(f"/d2l/api/le/{LE_VER}/{org_unit_id}/content/modules/{module_id}/structure/")
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Failed to fetch module structure")
        children = resp.json()
        if not isinstance(children, list):
            children = children.get("Structure", [])

    return [
        {
            "id": item.get("Id"),
            "title": item.get("Title"),
            "type": item.get("Type"),
            "topic_type": item.get("TopicType"),
            "url": item.get("Url"),
        }
        for item in children
    ]


# ── GET /api/courses/{org_unit_id}/files/{topic_id}/download ──────────────────

@router.get("/courses/{org_unit_id}/files/{topic_id}/download")
async def download_file(org_unit_id: int, topic_id: int, token: str = Depends(get_bs_token)):
    async with _bs_client(token) as c:
        resp = await c.get(f"/d2l/api/le/{LE_VER}/{org_unit_id}/content/topics/{topic_id}/file")
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Failed to download file")

        content_type = resp.headers.get("content-type", "application/octet-stream")
        content_disposition = resp.headers.get("content-disposition", "")

        headers = {}
        if content_disposition:
            headers["Content-Disposition"] = content_disposition

        return StreamingResponse(
            iter([resp.content]),
            media_type=content_type,
            headers=headers,
        )
