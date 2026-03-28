"""
F35 部装/总装厂产线管控 — BrowserUse 自动化端到端测试
=====================================================

业务场景：以 F35 战斗机的部装（Sub-Assembly）和总装（Final Assembly）产线为例，
在 LingShu 平台上构建本体模型，并遍历测试所有已开发功能。
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from dataclasses import dataclass, field

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
Wait for redirect to an authenticated page.
Then proceed with the main task:
"""


# ──────────────────────────── Test Result Tracking ────────────────────────────

@dataclass
class TestResult:
    name: str
    module: str
    status: str = "PENDING"
    duration: float = 0.0
    detail: str = ""


@dataclass
class TestReport:
    scenario: str = "F35 部装/总装厂产线管控"
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
        skipped = sum(1 for r in self.results if r.status == "SKIP")
        return total, passed, failed, errors, skipped

    def to_markdown(self) -> str:
        total, passed, failed, errors, skipped = self.summary()
        pass_rate = (passed / total * 100) if total > 0 else 0

        lines = [
            "# LingShu 平台端到端测试报告",
            "",
            f"## 测试场景：{self.scenario}",
            "",
            "| 项目 | 值 |",
            "|------|-----|",
            f"| 开始时间 | {self.start_time} |",
            f"| 结束时间 | {self.end_time} |",
            "| 测试工具 | BrowserUse 0.12.1 + Gemini 2.5 Flash |",
            f"| 测试总数 | {total} |",
            f"| 通过 | {passed} |",
            f"| 失败 | {failed} |",
            f"| 错误 | {errors} |",
            f"| 跳过 | {skipped} |",
            f"| 通过率 | {pass_rate:.1f}% |",
            "",
            "---",
            "",
        ]

        # Group by module
        modules = {}
        for r in self.results:
            modules.setdefault(r.module, []).append(r)

        for module, results in modules.items():
            mod_passed = sum(1 for r in results if r.status == "PASS")
            mod_total = len(results)
            lines.append(f"## {module} ({mod_passed}/{mod_total})")
            lines.append("")
            lines.append("| # | 测试项 | 状态 | 耗时 | 详情 |")
            lines.append("|---|--------|------|------|------|")
            for i, r in enumerate(results, 1):
                detail = r.detail[:100].replace("|", "/").replace("\n", " ") if r.detail else "-"
                lines.append(f"| {i} | {r.name} | {r.status} | {r.duration:.1f}s | {detail} |")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## 业务场景说明",
            "",
            "### F35 部装/总装厂产线管控本体模型",
            "",
            "本测试以 F-35 Lightning II 战斗机制造产线为业务背景，构建以下本体模型：",
            "",
            "**ObjectType（实体类型）：**",
            "- `F35Aircraft` — F-35 飞机整机",
            "- `SubAssemblyUnit` — 部装单元（机翼、机身段、尾翼等）",
            "- `WorkStation` — 工位",
            "",
            "**LinkType（关系类型）：**",
            "- `AssembledFrom` — 整机由部装单元组装",
            "",
            "**InterfaceType（接口类型）：**",
            "- `Trackable` — 可追溯接口（序列号、批次号）",
            "",
            "**ActionType（动作类型）：**",
            "- `StartAssembly` — 启动装配工序",
            "",
            "**SharedPropertyType（共享属性）：**",
            "- `SerialNumber` — 序列号",
            "",
        ])

        return "\n".join(lines)


# ──────────────────────────── Test Runner ────────────────────────────

async def run_test(
    llm,
    test_name: str,
    module: str,
    task: str,
    report: TestReport,
    max_steps: int = 20,
    needs_login: bool = True,
) -> TestResult:
    """Run a single BrowserUse test case with a fresh browser."""
    result = TestResult(name=test_name, module=module)
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
    print(f"  [{result.status}] {module} > {test_name} ({result.duration:.1f}s)")
    return result


async def main():
    print("=" * 70)
    print("F35 部装/总装厂产线管控 — LingShu 平台 BrowserUse E2E 测试")
    print("=" * 70)

    report = TestReport()
    report.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    llm = ChatGoogle(model="gemini-2.5-flash", temperature=0)

    # ═══════════════════════════════════════════════════════════════
    # 1. SETTING MODULE
    # ═══════════════════════════════════════════════════════════════
    print("\n[1/6] Setting 模块测试")
    print("-" * 40)

    await run_test(llm, "登录系统", "Setting", f"""
    Go to {BASE_URL}/login. Fill email: {ADMIN_EMAIL}, password: {ADMIN_PASSWORD}.
    Click Sign in. Verify redirect to authenticated page. Report landing URL.
    """, report, needs_login=False)

    await run_test(llm, "设置概览页", "Setting", f"""
    Navigate to {BASE_URL}/setting/overview.
    Report overview statistics (user count, tenant count, etc.).
    """, report)

    await run_test(llm, "用户管理", "Setting", f"""
    Navigate to {BASE_URL}/setting/users.
    Look for users table. Find admin@lingshu.dev. Report user list.
    """, report)

    await run_test(llm, "租户管理", "Setting", f"""
    Navigate to {BASE_URL}/setting/tenants.
    Look for tenants table. Find "Default" tenant. Report tenant details.
    """, report)

    await run_test(llm, "审计日志", "Setting", f"""
    Navigate to {BASE_URL}/setting/audit.
    Look for audit log entries. Report events shown.
    """, report)

    # ═══════════════════════════════════════════════════════════════
    # 2. ONTOLOGY MODULE — F35 产线本体模型
    # ═══════════════════════════════════════════════════════════════
    print("\n[2/6] Ontology 模块测试")
    print("-" * 40)

    await run_test(llm, "本体概览页", "Ontology", f"""
    Navigate to {BASE_URL}/ontology/overview.
    Report statistics (object types count, link types count, etc.).
    """, report)

    await run_test(llm, "创建 ObjectType: F35Aircraft", "Ontology", f"""
    Navigate to {BASE_URL}/ontology/object-types.
    Click Create/New/+ button.
    Fill name: F35Aircraft
    Fill description: F-35 Lightning II 战斗机整机
    Submit the form. Verify it appears in the list. Report success or errors.
    """, report, max_steps=25)

    await run_test(llm, "创建 ObjectType: SubAssemblyUnit", "Ontology", f"""
    Navigate to {BASE_URL}/ontology/object-types.
    Click Create/New/+ button.
    Fill name: SubAssemblyUnit
    Fill description: 部装单元（机翼、机身段、尾翼等）
    Submit. Verify in list. Report result.
    """, report, max_steps=25)

    await run_test(llm, "创建 ObjectType: WorkStation", "Ontology", f"""
    Navigate to {BASE_URL}/ontology/object-types.
    Click Create/New/+ button.
    Fill name: WorkStation
    Fill description: 装配工位
    Submit. Verify in list. Report result.
    """, report, max_steps=25)

    await run_test(llm, "查看 Object Types 列表", "Ontology", f"""
    Navigate to {BASE_URL}/ontology/object-types.
    Report ALL object types listed with names and descriptions.
    Check if F35Aircraft, SubAssemblyUnit, WorkStation are present.
    """, report)

    await run_test(llm, "创建 LinkType: AssembledFrom", "Ontology", f"""
    Navigate to {BASE_URL}/ontology/link-types.
    Click Create/New/+ button.
    Fill name: AssembledFrom
    Fill description: 整机由部装单元组装关系
    Submit. Report result.
    """, report, max_steps=25)

    await run_test(llm, "创建 InterfaceType: Trackable", "Ontology", f"""
    Navigate to {BASE_URL}/ontology/interface-types.
    Click Create/New/+ button.
    Fill name: Trackable
    Fill description: 可追溯接口
    Submit. Report result.
    """, report, max_steps=25)

    await run_test(llm, "创建 ActionType: StartAssembly", "Ontology", f"""
    Navigate to {BASE_URL}/ontology/action-types.
    Click Create/New/+ button.
    Fill name: StartAssembly
    Fill description: 启动装配工序
    Submit. Report result.
    """, report, max_steps=25)

    await run_test(llm, "创建 SharedPropertyType: SerialNumber", "Ontology", f"""
    Navigate to {BASE_URL}/ontology/shared-property-types.
    Click Create/New/+ button.
    Fill name: SerialNumber
    Fill description: 序列号
    Submit. Report result.
    """, report, max_steps=25)

    await run_test(llm, "本体版本管理页", "Ontology", f"""
    Navigate to {BASE_URL}/ontology/versions.
    Report version/snapshot information and their status.
    """, report)

    # ═══════════════════════════════════════════════════════════════
    # 3. DATA MODULE
    # ═══════════════════════════════════════════════════════════════
    print("\n[3/6] Data 模块测试")
    print("-" * 40)

    await run_test(llm, "数据概览页", "Data", f"""
    Navigate to {BASE_URL}/data/overview.
    Report data module overview information.
    """, report)

    await run_test(llm, "数据源管理", "Data", f"""
    Navigate to {BASE_URL}/data/sources.
    Report data source connections list and available actions.
    """, report)

    await run_test(llm, "数据浏览", "Data", f"""
    Navigate to {BASE_URL}/data/browse.
    Report data browsing interface and available functionality.
    """, report)

    # ═══════════════════════════════════════════════════════════════
    # 4. FUNCTION MODULE
    # ═══════════════════════════════════════════════════════════════
    print("\n[4/6] Function 模块测试")
    print("-" * 40)

    await run_test(llm, "能力概览页", "Function", f"""
    Navigate to {BASE_URL}/function/overview.
    Report function overview information.
    """, report)

    await run_test(llm, "能力列表", "Function", f"""
    Navigate to {BASE_URL}/function/capabilities.
    Report capabilities listed (actions + global functions).
    """, report)

    await run_test(llm, "全局函数", "Function", f"""
    Navigate to {BASE_URL}/function/capabilities/globals.
    Report global functions list and available actions.
    """, report)

    # ═══════════════════════════════════════════════════════════════
    # 5. AGENT/COPILOT MODULE
    # ═══════════════════════════════════════════════════════════════
    print("\n[5/6] Agent 模块测试")
    print("-" * 40)

    await run_test(llm, "智能体概览页", "Agent", f"""
    Navigate to {BASE_URL}/agent/overview.
    Report agent overview statistics.
    """, report)

    await run_test(llm, "模型管理", "Agent", f"""
    Navigate to {BASE_URL}/agent/models.
    Report AI models listed and available actions.
    """, report)

    await run_test(llm, "技能管理", "Agent", f"""
    Navigate to {BASE_URL}/agent/skills.
    Report skills listed and available actions.
    """, report)

    await run_test(llm, "MCP 连接管理", "Agent", f"""
    Navigate to {BASE_URL}/agent/mcp.
    Report MCP connections listed.
    """, report)

    await run_test(llm, "会话管理", "Agent", f"""
    Navigate to {BASE_URL}/agent/sessions.
    Report chat sessions listed.
    """, report)

    await run_test(llm, "子代理管理", "Agent", f"""
    Navigate to {BASE_URL}/agent/sub-agents.
    Report sub-agent configurations listed.
    """, report)

    await run_test(llm, "监控面板", "Agent", f"""
    Navigate to {BASE_URL}/agent/monitor.
    Report monitoring dashboard information.
    """, report)

    # ═══════════════════════════════════════════════════════════════
    # 6. CROSS-MODULE
    # ═══════════════════════════════════════════════════════════════
    print("\n[6/6] 跨模块导航测试")
    print("-" * 40)

    await run_test(llm, "Dock 导航", "Navigation", f"""
    Navigate to {BASE_URL}/ontology/overview.
    Find navigation dock/sidebar.
    Click Data module → verify Data page loads.
    Click Function module → verify Function page loads.
    Click Agent module → verify Agent page loads.
    Click Setting module → verify Setting page loads.
    Click Ontology → verify return to Ontology.
    Report navigation flow.
    """, report, max_steps=30)

    await run_test(llm, "API 健康检查", "Navigation", f"""
    Navigate to {API_URL}/health.
    Report the JSON health check response.
    """, report, needs_login=False)

    # ═══════════════════════════════════════════════════════════════
    # Generate Report
    # ═══════════════════════════════════════════════════════════════
    report.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "f35_test_report.md"
    )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())

    total, passed, failed, errors, skipped = report.summary()
    print("\n" + "=" * 70)
    print("测试完成！")
    print(f"  总计: {total}  通过: {passed}  失败: {failed}  错误: {errors}  跳过: {skipped}")
    print(f"  通过率: {passed/total*100:.1f}%" if total > 0 else "  无测试")
    print(f"  报告: {report_path}")
    print("=" * 70)

    return report


if __name__ == "__main__":
    report = asyncio.run(main())
    total, passed, failed, errors, skipped = report.summary()
    sys.exit(1 if (failed + errors) > 0 else 0)
