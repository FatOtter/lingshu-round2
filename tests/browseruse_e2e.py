"""
BrowserUse E2E Tests (BU-01 to BU-10)
======================================

Headed browser tests using browser-use LLM agent for visual verification
of real user interactions on the LingShu platform.

Usage:
    python tests/browseruse_e2e.py

Requires:
    - browser-use >= 0.12
    - GOOGLE_API_KEY or GEMINI_API_KEY env var
    - LingShu running at localhost:3100 (frontend) / localhost:8100 (backend)
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime

from browser_use import Agent, Browser
from browser_use.llm.google import ChatGoogle


# ──────────────────────────── Config ────────────────────────────

BASE_URL = "http://localhost:3100"
API_URL = "http://localhost:8100"
ADMIN_EMAIL = "admin@lingshu.dev"
ADMIN_PASSWORD = "admin123"

LOGIN_PREFIX = f"""
First, go to {BASE_URL}/login
Fill email with: {ADMIN_EMAIL}
Fill password with: {ADMIN_PASSWORD}
Click the Sign in button.
Wait for redirect to an authenticated page (URL should no longer contain /login).
Then proceed with the main task:
"""


# ──────────────────────────── Test Result Tracking ────────────────────────────

@dataclass
class TestResult:
    name: str
    test_id: str
    status: str = "PENDING"
    duration: float = 0.0
    detail: str = ""


@dataclass
class TestReport:
    scenario: str = "BrowserUse E2E Tests (BU-01 to BU-10)"
    start_time: str = ""
    end_time: str = ""
    results: list = field(default_factory=list)

    def add(self, result: TestResult):
        self.results.append(result)

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        errors = sum(1 for r in self.results if r.status == "ERROR")
        return total, passed, failed, errors

    def to_markdown(self) -> str:
        total, passed, failed, errors = self.summary()
        pass_rate = (passed / total * 100) if total > 0 else 0

        lines = [
            "# BrowserUse E2E Test Report",
            "",
            f"| Item | Value |",
            "|------|-------|",
            f"| Start | {self.start_time} |",
            f"| End   | {self.end_time} |",
            f"| Tool  | BrowserUse + Gemini 2.5 Flash |",
            f"| Total | {total} |",
            f"| Passed | {passed} |",
            f"| Failed | {failed} |",
            f"| Errors | {errors} |",
            f"| Pass Rate | {pass_rate:.1f}% |",
            "",
            "---",
            "",
            "| # | Test ID | Test | Status | Duration | Detail |",
            "|---|---------|------|--------|----------|--------|",
        ]

        for i, r in enumerate(self.results, 1):
            detail = r.detail[:120].replace("|", "/").replace("\n", " ") if r.detail else "-"
            lines.append(
                f"| {i} | {r.test_id} | {r.name} | {r.status} | {r.duration:.1f}s | {detail} |"
            )

        return "\n".join(lines)


# ──────────────────────────── Test Runner ────────────────────────────

async def run_test(
    llm,
    test_id: str,
    test_name: str,
    task: str,
    report: TestReport,
    max_steps: int = 20,
    needs_login: bool = True,
) -> TestResult:
    """Run a single BrowserUse test case with a fresh browser."""
    result = TestResult(name=test_name, test_id=test_id)
    start = time.time()
    browser = None

    full_task = (LOGIN_PREFIX + task) if needs_login else task

    try:
        browser = Browser(headless=False, disable_security=True)
        agent = Agent(
            task=full_task,
            llm=llm,
            browser=browser,
            use_vision=True,
            max_actions_per_step=5,
            generate_gif=False,
        )

        history = await agent.run(max_steps=max_steps)

        if history.is_done():
            result.status = "PASS"
            result.detail = history.final_result() or "Completed"
        else:
            result.status = "FAIL"
            result.detail = f"Did not complete within {max_steps} steps"

    except Exception as e:
        result.status = "ERROR"
        result.detail = str(e)[:200]
        print(f"    ERROR: {result.detail}")
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    result.duration = time.time() - start
    report.add(result)
    status_icon = {"PASS": "+", "FAIL": "x", "ERROR": "!"}[result.status]
    print(f"  [{status_icon}] {test_id}: {test_name} ({result.duration:.1f}s)")
    return result


# ──────────────────────────── Test Definitions ────────────────────────────

async def main():
    print("=" * 70)
    print("BrowserUse E2E Tests — BU-01 to BU-10")
    print("=" * 70)

    report = TestReport()
    report.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    llm = ChatGoogle(model="gemini-2.5-flash", temperature=0)

    # ── BU-01: Login Flow ──────────────────────────────────────────
    print("\n[BU-01] Login Flow")
    await run_test(llm, "BU-01", "Complete login flow", f"""
    Go to {BASE_URL}/login.
    Verify the login page is displayed with email and password fields.
    Fill email with: {ADMIN_EMAIL}
    Fill password with: {ADMIN_PASSWORD}
    Click the "Sign in" button.
    Wait for the page to redirect away from /login.
    Verify the URL no longer contains "/login" (you should be on an authenticated page).
    Report the final URL you landed on.
    """, report, needs_login=False, max_steps=15)

    # ── BU-02: Create ObjectType ───────────────────────────────────
    print("\n[BU-02] Create ObjectType")
    await run_test(llm, "BU-02", "Create ObjectType via UI", f"""
    Navigate to {BASE_URL}/ontology/object-types.
    Wait for the page to load.
    Look for a "New" or "Create" or "+" button and click it.
    If there's a form, fill in:
      - api_name or API Name: "bu02_test_type"
      - display_name or Display Name: "BU02 Test Type"
      - description: "Created by BrowserUse test"
    Click Save or Submit.
    Wait for the page to update.
    Verify that "bu02_test_type" or "BU02 Test Type" appears on the page or in the list.
    Report what you see.
    """, report, max_steps=25)

    # ── BU-03: Version Lifecycle ───────────────────────────────────
    print("\n[BU-03] Version Lifecycle")
    await run_test(llm, "BU-03", "Version management page", f"""
    Navigate to {BASE_URL}/ontology/versions.
    Wait for the page to load.
    Look for any version history, staging summary, or snapshot information.
    If there are staging entities, look for a "Publish" or "Commit" button.
    Report what version/staging information is displayed on the page.
    """, report, max_steps=15)

    # ── BU-04: Data Source Connection ──────────────────────────────
    print("\n[BU-04] Data Source Connection")
    await run_test(llm, "BU-04", "Data sources page", f"""
    Navigate to {BASE_URL}/data/sources.
    Wait for the page to load.
    Look for a list of data source connections or an empty state message.
    If there's a "New Connection" or "Add" button, note its presence.
    Report what you see on the data sources page (connections list, empty state, etc.).
    """, report, max_steps=15)

    # ── BU-05: Data Browse + Search ────────────────────────────────
    print("\n[BU-05] Data Browse + Search")
    await run_test(llm, "BU-05", "Data browse and search", f"""
    Navigate to {BASE_URL}/data/browse.
    Wait for the page to load.
    Look for entity type selectors, search fields, or data tables.
    If there's a search box, try typing "test" in it.
    Report what data browsing UI elements are available on this page.
    """, report, max_steps=15)

    # ── BU-06: Copilot Chat ────────────────────────────────────────
    print("\n[BU-06] Copilot Chat")
    await run_test(llm, "BU-06", "Copilot chat interaction", f"""
    Navigate to {BASE_URL}/agent/chat.
    Wait for the page to load.
    Look for a chat input area or message box.
    If there is a text input, type "Hello, what can you help me with?" and press Enter or click Send.
    Wait a few seconds for any response.
    Report what you see: chat interface, messages, input area, etc.
    """, report, max_steps=20)

    # ── BU-07: Shell Panel ─────────────────────────────────────────
    print("\n[BU-07] Shell Panel")
    await run_test(llm, "BU-07", "Shell panel interaction", f"""
    Navigate to {BASE_URL}/ontology/overview.
    Wait for the page to load.
    Look for a terminal/shell icon in the header or toolbar area.
    If you find it, click it to open the shell panel.
    If a shell panel opens, look for an input area.
    Report what you found: shell icon location, panel behavior, input field.
    If no shell icon is visible, report that too.
    """, report, max_steps=15)

    # ── BU-08: User Management ─────────────────────────────────────
    print("\n[BU-08] User Management")
    await run_test(llm, "BU-08", "User management and search", f"""
    Navigate to {BASE_URL}/setting/users.
    Wait for the page to load.
    Look for a table or list of users.
    Find the admin user (admin@lingshu.dev or similar) in the list.
    If there's a search box, try searching for "admin".
    Report how many users are shown and their details.
    """, report, max_steps=15)

    # ── BU-09: Cross-Module Navigation ─────────────────────────────
    print("\n[BU-09] Cross-Module Navigation")
    await run_test(llm, "BU-09", "Navigate all 5 modules via dock", f"""
    Start at {BASE_URL}/ontology/overview.
    Wait for it to load.

    Now navigate through all 5 modules using the left sidebar/dock:
    1. Click on "Ontology" or the first icon in the dock. Wait for page load. Note the URL.
    2. Click on "Data" or the second icon in the dock. Wait for page load. Note the URL.
    3. Click on "Function" or the third icon. Wait for page load. Note the URL.
    4. Click on "Agent" or the fourth icon. Wait for page load. Note the URL.
    5. Click on "Setting" or the fifth icon. Wait for page load. Note the URL.

    Report all 5 URLs you visited and confirm each page loaded successfully.
    """, report, max_steps=25)

    # ── BU-10: Topology Visualization ──────────────────────────────
    print("\n[BU-10] Topology Visualization")
    await run_test(llm, "BU-10", "Topology view verification", f"""
    Navigate to {BASE_URL}/ontology/overview.
    Wait for the page to load.
    Look for a topology graph section or visualization area.
    Check if there are:
    - SVG elements or canvas elements showing a graph
    - Or an empty state message like "Your ontology is empty"
    - Or a "Create ObjectType" button
    Report what the topology section shows: graph with nodes, empty state, or something else.
    """, report, max_steps=15)

    # ── Report ─────────────────────────────────────────────────────
    report.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total, passed, failed, errors = report.summary()

    print("\n" + "=" * 70)
    print(f"Results: {passed}/{total} passed, {failed} failed, {errors} errors")
    print("=" * 70)

    # Write report
    report_path = "tests/browseruse_e2e_report.md"
    with open(report_path, "w") as f:
        f.write(report.to_markdown())
    print(f"\nReport written to: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
