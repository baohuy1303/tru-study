# Brightspace API Endpoints — TruStudy

Base URL: `https://learn.truman.edu`
Auth header: `Authorization: Bearer <token>`

**API Versions (latest stable as of Feb 2026)**
- LP (learning platform): `1.57`
- LE (learning environment): `1.92`

---

## 1. Who Am I

```
GET /d2l/api/lp/1.57/users/whoami
```

Returns: `Identifier` (userId), `FirstName`, `LastName`, `UniqueName` (NetID)

---

## 2. All Enrolled Courses

```
GET /d2l/api/lp/1.57/enrollments/myenrollments/
```

Returns: `Items[]` where each item has:
- `OrgUnit.Id` → the `orgUnitId` used in all LE endpoints
- `OrgUnit.Name`, `OrgUnit.Code`, `OrgUnit.Type.Code`
- `Role.Id`

Filter: keep only `OrgUnit.Type.Code == "Course Offering"` to exclude org/department units.
Pagination: pass `bookmark=<value>` from previous response until no more pages.

---

## 3. Assignments + Due Dates (per course)

```
GET /d2l/api/le/1.92/{orgUnitId}/dropbox/folders/
```

Returns: `Objects[]` where each has:
- `Id` (folderId), `Name`, `DueDate`, `Instructions`

```
# Single assignment details + instructions
GET /d2l/api/le/1.92/{orgUnitId}/dropbox/folders/{folderId}
```

---

## 4. Quizzes + Due Dates (per course)

```
GET /d2l/api/le/1.92/{orgUnitId}/quizzes/
```

Returns: `Objects[]` where each has:
- `QuizId`, `Name`, `DueDate`, `TimeLimit`, `AttemptsAllowed`

```
# Single quiz details
GET /d2l/api/le/1.92/{orgUnitId}/quizzes/{quizId}
```

---

## 5. Calendar Events / Due Dates (cross-course)

```
# All due dates across all enrolled courses
GET /d2l/api/le/1.92/calendar/events/myEvents/

# Due dates for a single course
GET /d2l/api/le/1.92/{orgUnitId}/calendar/events/myEvents/
```

Assignment and quiz due dates appear here when published by the instructor. Best used for the Google Calendar push.

---

## 6. Course Files (for RAG pipeline)

Traverse the content tree to find downloadable files:

```
# Step 1 — top-level modules
GET /d2l/api/le/1.92/{orgUnitId}/content/root/

# Step 2 — contents of a module (recurse for nested modules)
GET /d2l/api/le/1.92/{orgUnitId}/content/modules/{moduleId}/structure/

# Step 3 — topic metadata
GET /d2l/api/le/1.92/{orgUnitId}/content/topics/{topicId}
```

Filter topics where `TopicType == "File"` to get downloadable files.

```
# Step 4 — download raw file bytes (PDF, PPTX, etc.)
GET /d2l/api/le/1.92/{orgUnitId}/content/topics/{topicId}/file
```

---

## Quick Reference

| Feature | Endpoint |
|---|---|
| User identity | `GET /d2l/api/lp/1.57/users/whoami` |
| All courses | `GET /d2l/api/lp/1.57/enrollments/myenrollments/` |
| Assignments | `GET /d2l/api/le/1.92/{orgUnitId}/dropbox/folders/` |
| Assignment detail | `GET /d2l/api/le/1.92/{orgUnitId}/dropbox/folders/{folderId}` |
| Quizzes | `GET /d2l/api/le/1.92/{orgUnitId}/quizzes/` |
| Quiz detail | `GET /d2l/api/le/1.92/{orgUnitId}/quizzes/{quizId}` |
| All due dates (cross-course) | `GET /d2l/api/le/1.92/calendar/events/myEvents/` |
| Due dates (per course) | `GET /d2l/api/le/1.92/{orgUnitId}/calendar/events/myEvents/` |
| Content root | `GET /d2l/api/le/1.92/{orgUnitId}/content/root/` |
| Module structure | `GET /d2l/api/le/1.92/{orgUnitId}/content/modules/{moduleId}/structure/` |
| Topic metadata | `GET /d2l/api/le/1.92/{orgUnitId}/content/topics/{topicId}` |
| File download | `GET /d2l/api/le/1.92/{orgUnitId}/content/topics/{topicId}/file` |

---

## Notes

- **Student visibility**: hidden/unpublished content returns nothing — no errors, just empty lists
- **Pagination**: responses include a `Bookmark` field; pass as query param `?bookmark=<value>` for next page
- **orgUnitId**: obtained from enrollments response (`OrgUnit.Id`)
- **userId**: obtained from whoami response (`Identifier`)
