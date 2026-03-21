# Brightspace API: How to Get Current Semester Courses as a Student

This document outlines a step-by-step strategy to retrieve only the courses you are actively studying in the current semester using the Brightspace (Valence) API.

## Overview

The approach combines three pieces of information:
1. **Your Enrollments** – all course offerings you are enrolled in
2. **The Semester Structure** – which courses belong to the current semester's organizational unit
3. **Course Details** – start/end dates to confirm course activity

The key is using the **organization structure** to find the `Semester` org unit, then filtering your enrollments by its children.

---

## Prerequisites

- OAuth 2 authentication with an access token
- Authorization Code Grant flow (as a student user)
- API base URL: `https://yourinstance.brightspace.com`

---

## Step 1: Get Your Enrollments

This call returns all courses you are enrolled in, along with access information.

### API Endpoint
GET /d2l/api/lp/{version}/enrollments/myenrollments/

text

### Example Request
```http
GET /d2l/api/lp/1.50/enrollments/myenrollments/ HTTP/1.1
Host: yourinstance.brightspace.com
Authorization: Bearer eyJ0eXAiOiJKV1Q...
Response Structure (MyOrgUnitInfo)
json
{
  "OrgUnit": {
    "Id": 12345,
    "Type": { "Id": 3, "Name": "Course Offering" },
    "Name": "Introduction to Computer Science",
    "Code": "CS101",
    "HomeUrl": "/d2l/home/12345"
  },
  "Access": {
    "IsActive": true,
    "StartDate": "2026-01-10T00:00:00.000Z",
    "EndDate": "2026-04-25T23:59:59.000Z",
    "CanAccess": true,
    "ClasslistRoleName": "Student",
    "LastAccessed": "2026-03-19T14:30:00.000Z"
  },
  "PinDate": null
}
Key Fields
Field	Description
OrgUnit.Id	Unique course ID – used for all subsequent calls
OrgUnit.Name	Course name
Access.IsActive	true if the course is currently active
Access.StartDate	Official course start date
Access.EndDate	Official course end date
Step 2: Find the Current Semester's Org Unit
You need to identify the OrgUnit that represents the current semester (e.g., "Spring 2026").

2a. Get All Semesters
Retrieve all org units of type "Semester". The built-in semester type ID is 5.

API Endpoint
text
GET /d2l/api/lp/{version}/orgstructure/?orgUnitType=5
Example Request
http
GET /d2l/api/lp/1.50/orgstructure/?orgUnitType=5 HTTP/1.1
Host: yourinstance.brightspace.com
Authorization: Bearer eyJ0eXAiOiJKV1Q...
Response Structure (OrgUnitProperties)
json
{
  "Identifier": 2001,
  "Name": "Fall 2025",
  "Code": "FA25",
  "Path": "/semesters/fa25",
  "Type": { "Id": 5, "Name": "Semester" }
}
2b. Identify the Current Semester
From the list of all semesters, programmatically select the one for the current term. Use one or more of these criteria:

Method	Example Logic
Name matching	Look for "Spring" or "Summer" or "Fall" + current year
Date range	Compare StartDate and EndDate against current date (if available)
Code pattern	Match against institutional semester codes (e.g., "202630" for Spring 2026)
Once identified, store its Identifier as semesterId.

Step 3: Get All Courses Under That Semester
Retrieve all course offerings that are children of the identified semester.

API Endpoint (Paged – Recommended)
text
GET /d2l/api/lp/{version}/orgstructure/{semesterId}/children/paged/
Example Request
http
GET /d2l/api/lp/1.50/orgstructure/2001/children/paged/ HTTP/1.1
Host: yourinstance.brightspace.com
Authorization: Bearer eyJ0eXAiOiJKV1Q...
Response Structure (Paged Result Set)
json
{
  "Items": [
    {
      "Identifier": 12345,
      "Name": "Introduction to Computer Science",
      "Code": "CS101",
      "Path": "/semesters/fa25/cs101",
      "Type": { "Id": 3, "Name": "Course Offering" }
    },
    {
      "Identifier": 12346,
      "Name": "Calculus I",
      "Code": "MATH201",
      "Path": "/semesters/fa25/math201",
      "Type": { "Id": 3, "Name": "Course Offering" }
    }
  ],
  "Next": "https://yourinstance.brightspace.com/d2l/api/lp/1.50/orgstructure/2001/children/paged/?bookmark=12346"
}
Key Fields
Field	Description
Items[].Identifier	Course ID – matches OrgUnit.Id from Step 1
Items[].Name	Course name
Items[].Type.Id	3 indicates a Course Offering
Step 4: Filter Your Enrollments
You now have two lists:

List	Source	Description
A	Step 1	All courses you are enrolled in
B	Step 3	All course offerings that belong to the current semester
Filtering Logic
The final list of courses you are studying this semester is the intersection of these two lists.

Pseudocode:

text
enrolledCourses = response from Step 1
semesterCourses = response from Step 3

currentSemesterCourses = enrolledCourses.filter(course => 
    semesterCourses.some(semesterCourse => 
        semesterCourse.Identifier === course.OrgUnit.Id
    )
)
Result Example
json
[
  {
    "OrgUnit": { "Id": 12345, "Name": "Introduction to Computer Science" },
    "Access": { "IsActive": true, "StartDate": "...", "EndDate": "..." }
  },
  {
    "OrgUnit": { "Id": 12346, "Name": "Calculus I" },
    "Access": { "IsActive": true, "StartDate": "...", "EndDate": "..." }
  }
]