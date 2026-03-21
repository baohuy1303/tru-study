# Brightspace API Endpoints for Student Data Access

This document lists the Brightspace API endpoints needed to retrieve:
- All courses a student is enrolled in
- Assignments, quizzes, and due dates per course
- Uploaded course files per course

All requests require OAuth 2 authentication with an access token in the header: `Authorization: Bearer <token>`

---

## 1. Pull All Courses (Enrollments)

As a student, you can only retrieve courses you are actually enrolled in.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/d2l/api/lp/{version}/enrollments/myenrollments/` | GET | Returns all org units (courses) the current user is enrolled in, with role information. |
| `/d2l/api/lp/{version}/users/{userId}/enrollments/` | GET | Alternative – requires your own user ID, also returns enrollments. |

**Response includes**: `OrgUnitId`, `Name`, `Code`, `RoleId`, `StartDate`, `EndDate`

---

## 2. Pull Assignments, Quizzes, and Due Dates

These endpoints are called per course (using `{orgUnitId}` from the enrollments response).

### Assignments

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/d2l/api/le/{version}/{orgUnitId}/content/folders/` | GET | Lists all assignment folders, including due dates and grade item linkage. |
| `/d2l/api/le/{version}/{orgUnitId}/content/folderData/{folderId}` | GET | Detailed assignment info: instructions, due date, submission info. |
| `/d2l/api/le/{version}/{orgUnitId}/content/folderData/{folderId}/mySubmissions` | GET | Your own submissions for a specific assignment folder. |

### Quizzes

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/d2l/api/le/{version}/{orgUnitId}/quizzes/` | GET | Lists all quizzes in the course. |
| `/d2l/api/le/{version}/{orgUnitId}/quizzes/{quizId}` | GET | Full quiz details: due date, time limit, attempts allowed, availability. |
| `/d2l/api/le/{version}/{orgUnitId}/quizzes/{quizId}/attempts/currentUser` | GET | Your attempts for a specific quiz. |

### Due Dates (General)

Due dates are embedded in assignment and quiz endpoints. For a consolidated view:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/d2l/api/le/{version}/{orgUnitId}/calendar/events/` | GET | Calendar events for a course (includes assignment/quiz due dates if published). |
| `/d2l/api/le/{version}/timeline/user/{userId}` | GET | (If available) Upcoming events and deadlines across all courses. |

---

## 3. Pull All Uploaded Course Files per Course

Course files are typically accessed through the Content (LOR) system.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/d2l/api/le/{version}/{orgUnitId}/content/root/` | GET | Returns the root structure of course content (modules and topics). |
| `/d2l/api/le/{version}/{orgUnitId}/content/structure/` | GET | Complete content tree – recommended for finding all file topics. |
| `/d2l/api/le/{version}/{orgUnitId}/content/topics/{topicId}/file` | GET | Direct download of a file attached to a topic. |

### Student Workflow for Files

1. Call `/content/structure/` to get the full course content tree.
2. Filter topics where `TopicType` = `"File"`.
3. Use the topic's `Url` or fetch via the file endpoint to access the file.

> ⚠️ **Note**: The legacy endpoint `/d2l/api/lp/{version}/courses/{orgUnitId}/files/` may not be available to students due to permissions.

---

## Quick Reference Summary

| Data Needed | Primary Endpoints |
|-------------|-------------------|
| **All courses** | `/d2l/api/lp/{version}/enrollments/myenrollments/` |
| **Assignments** | `/d2l/api/le/{version}/{orgUnitId}/content/folders/` |
| **Quizzes** | `/d2l/api/le/{version}/{orgUnitId}/quizzes/` |
| **Due dates** | Assignment/quiz endpoints; plus `/calendar/events/` per course |
| **Course files** | `/d2l/api/le/{version}/{orgUnitId}/content/structure/` → filter file topics |

---

## Important Notes

### API Versions
- **`lp` API** (learning platform): Use `1.50` or latest stable
- **`le` API** (learning environment): Use `1.42` or latest stable

### Authentication
- All requests require `Authorization: Bearer <access_token>`
- Use OAuth 2 **Authorization Code Grant** flow to obtain tokens as a student

### Permission Limits
- As a student, you only see what your role allows
- Hidden assignments, quizzes, or restricted files are **not accessible**
- Due dates for unavailable items will not be returned

### Pagination
- Large responses may require pagination using `bookmark` parameters
- Check response headers for next page links

---

## Example Request

```http
GET /d2l/api/lp/1.50/enrollments/myenrollments/ HTTP/1.1
Host: yourinstance.brightspace.com
Authorization: Bearer eyJ0eXAiOiJKV1Q...
http
GET /d2l/api/le/1.42/12345/quizzes/ HTTP/1.1
Host: yourinstance.brightspace.com
Authorization: Bearer eyJ0eXAiOiJKV1Q...```