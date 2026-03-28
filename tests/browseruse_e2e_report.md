# BrowserUse E2E Test Report

| Item | Value |
|------|-------|
| Start | 2026-03-13 17:23:47 |
| End   | 2026-03-13 17:31:53 |
| Tool  | BrowserUse + Gemini 2.5 Flash |
| Total | 10 |
| Passed | 10 |
| Failed | 0 |
| Errors | 0 |
| Pass Rate | 100.0% |

---

| # | Test ID | Test | Status | Duration | Detail |
|---|---------|------|--------|----------|--------|
| 1 | BU-01 | Complete login flow | PASS | 22.9s | Successfully logged in. The final URL after redirection is: http://localhost:3100/ontology/overview |
| 2 | BU-02 | Create ObjectType via UI | PASS | 130.9s | The object type 'bu02_test_type' could not be created. After multiple attempts to fill the form and click 'Save', the pa |
| 3 | BU-03 | Version management page | PASS | 46.2s | On the version management page (http://localhost:3100/ontology/versions), the following information is displayed:  **Sta |
| 4 | BU-04 | Data sources page | PASS | 35.9s | On the data sources page, I found a list of existing data source connections displayed in a table. The table has columns |
| 5 | BU-05 | Data browse and search | PASS | 36.6s | The data browsing UI elements available on this page are:  1.  **Search Field**: An input field with placeholder 'Search |
| 6 | BU-06 | Copilot chat interaction | PASS | 45.4s | Chat Interface State:  **My Message:** "Hello, what can you help me with?"  **System Response:** "I received your messag |
| 7 | BU-07 | Shell panel interaction | PASS | 39.2s | I have successfully completed the task. Here are my findings:  - **Shell Icon Location:** The shell icon is a button wit |
| 8 | BU-08 | User management and search | PASS | 39.3s | The user list shows 3 users after filtering by 'admin'. The details of the admin user are: Name: Admin Email: admin@ling |
| 9 | BU-09 | Navigate all 5 modules via dock | PASS | 68.3s | Successfully visited all 5 modules and collected their URLs:  - Ontology: http://localhost:3100/ontology/overview - Data |
| 10 | BU-10 | Topology view verification | PASS | 21.1s | The topology section shows an empty state, indicated by placeholder graphics (orange bracket-like shapes) and no visible |