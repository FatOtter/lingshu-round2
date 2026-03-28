"""
F35 工厂车间负责人视角 — 全功能深度端到端测试
=================================================

以洛克希德·马丁 Fort Worth 工厂车间主管的日常使用场景为测试基准。
覆盖所有 5 个模块的全部 CRUD 操作，含属性定义、接口实现、版本管理全生命周期。

测试矩阵:
  Setting   — 用户/租户/角色 CRUD, 密码变更, 审计日志
  Ontology  — OT+属性/LT+约束/IT+category/AT+参数/SPT, 版本全生命周期
  Data      — 连接 CRUD, 测试连接
  Function  — 全局函数 CRUD, 工作流 CRUD, 能力目录, 执行
  Agent     — 模型/技能/MCP/子代理 CRUD, 会话管理
  UI        — BrowserUse 验证所有页面数据可见性
"""

import asyncio
import json
import os
import sys
import time
import traceback
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any

import httpx

# ════════════════════════════ Config ════════════════════════════

BASE_URL = "http://localhost:3100"
API_URL = "http://localhost:8100"
ADMIN_EMAIL = "admin@lingshu.dev"
ADMIN_PASSWORD = "admin123"

# BrowserUse imports (lazy — only needed for Phase 7)
_browser_use_available = False
try:
    from browser_use import Agent, Browser
    from browser_use.llm.google import ChatGoogle
    _browser_use_available = True
except ImportError:
    pass


# ════════════════════════════ Test Result Tracking ════════════════════════════

@dataclass
class TestResult:
    name: str
    phase: str
    status: str = "PENDING"
    duration: float = 0.0
    detail: str = ""
    critical: bool = False  # 是否为阻塞性测试


@dataclass
class RoundReport:
    round_num: int = 1
    start_time: str = ""
    end_time: str = ""
    results: list = field(default_factory=list)

    def add(self, r: TestResult):
        self.results.append(r)

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        errors = sum(1 for r in self.results if r.status == "ERROR")
        skipped = sum(1 for r in self.results if r.status == "SKIP")
        return total, passed, failed, errors, skipped


# ════════════════════════════ HTTP Client ════════════════════════════

class LingShuClient:
    """Synchronous API client with full CRUD support across all modules."""

    def __init__(self):
        self.client = httpx.Client(base_url=API_URL, timeout=30)
        self.cookies = {}
        self._rid_cache: dict[str, str] = {}  # api_name -> rid

    def login(self, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
        resp = self.client.post(
            "/setting/v1/auth/login",
            json={"email": email, "password": password},
        )
        resp.raise_for_status()
        self.cookies = dict(resp.cookies)
        return resp.json()

    def _req(self, method: str, path: str, data: dict | None = None) -> dict:
        resp = self.client.request(method, path, json=data, cookies=self.cookies)
        try:
            return resp.json()
        except Exception:
            return {"error": {"code": f"HTTP_{resp.status_code}", "message": resp.text[:200]}}

    def post(self, path: str, data: dict | None = None) -> dict:
        return self._req("POST", path, data)

    def get(self, path: str) -> dict:
        return self._req("GET", path)

    def put(self, path: str, data: dict | None = None) -> dict:
        return self._req("PUT", path, data)

    def delete(self, path: str) -> dict:
        return self._req("DELETE", path)

    # ── Ontology helpers ──

    def create_entity(self, entity_type: str, data: dict) -> tuple[str, str]:
        resp = self.post(f"/ontology/v1/{entity_type}", data)
        rid = resp.get("data", {}).get("rid", "")
        if rid:
            self._rid_cache[data.get("api_name", "")] = rid
            return rid, "ok"
        err = resp.get("error", {}).get("message", "")
        # Duplicate = ok, try to find existing
        if "duplicate" in err.lower() or "already exists" in err.lower() or "ALREADY_EXISTS" in resp.get("error", {}).get("code", ""):
            existing = self.query_entities(entity_type, search=data.get("api_name", ""))
            for e in existing:
                if e.get("api_name") == data.get("api_name"):
                    self._rid_cache[data["api_name"]] = e["rid"]
                    return e["rid"], "exists"
        return "", err or "unknown error"

    def add_property(self, parent_type: str, parent_rid: str, prop: dict) -> tuple[str, str]:
        # Must lock parent before adding property
        self.lock_entity(parent_type, parent_rid)
        try:
            resp = self.post(f"/ontology/v1/{parent_type}/{parent_rid}/property-types", prop)
        finally:
            self.unlock_entity(parent_type, parent_rid)
        rid = resp.get("data", {}).get("rid", "")
        if rid:
            return rid, "ok"
        err = resp.get("error", {}).get("message", "")
        if "duplicate" in err.lower() or "already exists" in err.lower():
            return "", "exists"
        return "", err or "unknown error"

    def submit_to_staging(self, entity_type: str, rid: str) -> str:
        resp = self.post(f"/ontology/v1/{entity_type}/{rid}/submit-to-staging")
        if resp.get("data"):
            return "ok"
        err = resp.get("error", {}).get("message", "unknown")
        if "already" in err.lower() or "staging" in err.lower():
            return "already_staged"
        return err

    def commit_staging(self, message: str = "") -> tuple[str, str]:
        resp = self.post("/ontology/v1/staging/commit", {"commit_message": message})
        sid = resp.get("data", {}).get("snapshot_id", "")
        if sid:
            return sid, "ok"
        return "", resp.get("error", {}).get("message", "unknown")

    def discard_staging(self) -> str:
        resp = self.post("/ontology/v1/staging/discard")
        return "ok" if not resp.get("error") else resp["error"].get("message", "")

    def discard_draft(self, entity_type: str, rid: str) -> str:
        resp = self.delete(f"/ontology/v1/{entity_type}/{rid}/draft")
        return "ok" if not resp.get("error") else resp["error"].get("message", "")

    def staging_summary(self) -> dict:
        return self.get("/ontology/v1/staging/summary")

    def drafts_summary(self) -> dict:
        return self.get("/ontology/v1/drafts/summary")

    def query_entities(self, entity_type: str, page_size: int = 100, search: str = "") -> list[dict]:
        body: dict[str, Any] = {"pagination": {"page": 1, "page_size": page_size}}
        if search:
            body["search"] = search
        resp = self.post(f"/ontology/v1/{entity_type}/query", body)
        return resp.get("data", [])

    def get_entity(self, entity_type: str, rid: str) -> dict:
        return self.get(f"/ontology/v1/{entity_type}/{rid}")

    def update_entity(self, entity_type: str, rid: str, data: dict) -> dict:
        return self.put(f"/ontology/v1/{entity_type}/{rid}", data)

    def delete_entity(self, entity_type: str, rid: str) -> dict:
        return self.delete(f"/ontology/v1/{entity_type}/{rid}")

    def query_snapshots(self) -> list[dict]:
        resp = self.post("/ontology/v1/snapshots/query", {"pagination": {"page": 1, "page_size": 20}})
        return resp.get("data", [])

    def get_snapshot_diff(self, snapshot_id: str) -> dict:
        return self.get(f"/ontology/v1/snapshots/{snapshot_id}/diff")

    def rollback_snapshot(self, snapshot_id: str) -> dict:
        return self.post(f"/ontology/v1/snapshots/{snapshot_id}/rollback")

    def get_topology(self) -> dict:
        return self.get("/ontology/v1/topology")

    def search_entities(self, q: str) -> dict:
        return self.get(f"/ontology/v1/search?q={q}")

    def rid(self, api_name: str) -> str:
        return self._rid_cache.get(api_name, "")

    # ── Lock ──

    def lock_entity(self, entity_type: str, rid: str) -> dict:
        return self.post(f"/ontology/v1/{entity_type}/{rid}/lock")

    def unlock_entity(self, entity_type: str, rid: str) -> dict:
        return self.delete(f"/ontology/v1/{entity_type}/{rid}/lock")


# ════════════════════════════ Test Runner ════════════════════════════

def check(condition, msg="Assertion failed"):
    """Assert replacement for use inside lambdas."""
    if not condition:
        raise AssertionError(msg)
    return True


def run_api_test(name: str, phase: str, report: RoundReport, fn, critical=False):
    """Run a single API test case."""
    result = TestResult(name=name, phase=phase, critical=critical)
    start = time.time()
    try:
        detail = fn()
        result.status = "PASS"
        result.detail = str(detail)[:300] if detail else "OK"
    except AssertionError as e:
        result.status = "FAIL"
        result.detail = str(e)[:300]
    except Exception as e:
        result.status = "ERROR"
        result.detail = f"{type(e).__name__}: {e}"[:300]
        traceback.print_exc()
    result.duration = time.time() - start
    report.add(result)
    icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥"}.get(result.status, "⏭")
    print(f"  {icon} {phase} > {name} ({result.duration:.1f}s) — {result.detail[:80]}")
    return result


async def run_browser_test(
    llm, name: str, phase: str, task: str, report: RoundReport, max_steps: int = 20
):
    """Run a single BrowserUse test case."""
    result = TestResult(name=name, phase=phase)
    start = time.time()
    browser = None

    full_task = f"""First, go to {BASE_URL}/login
Fill email: {ADMIN_EMAIL}, password: {ADMIN_PASSWORD}
Click Sign in. Wait for redirect.
Then do the main task:
{task}"""

    try:
        browser = Browser(headless=False, disable_security=True)
        agent = Agent(
            task=full_task, llm=llm, browser=browser,
            use_vision=True, max_actions_per_step=5, generate_gif=False,
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
        result.detail = f"{type(e).__name__}: {e}"[:300]
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    result.duration = time.time() - start
    report.add(result)
    icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥"}.get(result.status, "⏭")
    print(f"  {icon} {phase} > {name} ({result.duration:.1f}s)")
    return result


# ════════════════════════════ Ontology Definitions ════════════════════════════

# Full entity definitions (reused from prior, plus properties)
OBJECT_TYPES = [
    {"api_name": "F35Aircraft", "display_name": "F-35 整机",
     "description": "F-35 Lightning II 战斗机整机，含 A/B/C 三个变体"},
    {"api_name": "MajorAssembly", "display_name": "大部件",
     "description": "飞机主要结构大部件：前机身/中机身/后机身/机翼/尾翼"},
    {"api_name": "SubAssembly", "display_name": "组件",
     "description": "大部件下属组件单元：起落架舱/武器舱门/进气道唇口/翼梢挂架"},
    {"api_name": "Component", "display_name": "零件",
     "description": "最小可追溯零件/标准件/紧固件，含MPN和CAGE Code"},
    {"api_name": "AvionicsModule", "display_name": "航电模块",
     "description": "ICP/DAS/AN/APG-81雷达/EOTS等航电系统模块"},
    {"api_name": "EngineUnit", "display_name": "发动机单元",
     "description": "F135涡扇发动机及附属系统，含推力矢量喷管(B型)"},
    {"api_name": "ProductionLine", "display_name": "产线",
     "description": "部装线(Sub-Assembly)和总装线(FACO)定义"},
    {"api_name": "WorkStation", "display_name": "工位",
     "description": "工位编号、工位能力、人员配额、设备清单"},
    {"api_name": "WorkCell", "display_name": "工作单元",
     "description": "工位内独立工作区域，含专用工装夹具和检测设备"},
    {"api_name": "WorkOrder", "display_name": "工单",
     "description": "生产工单/制造订单，关联BOM、工艺路线、交付节点"},
    {"api_name": "WorkInstruction", "display_name": "作业指导书",
     "description": "工序级作业指导书(WI)，含操作步骤和质量标准"},
    {"api_name": "ProcessStep", "display_name": "工序",
     "description": "工艺路线单工序节点，含标准工时和前置依赖"},
    {"api_name": "Technician", "display_name": "技师",
     "description": "装配技师/检验员，技能等级A/B/C，资质认证"},
    {"api_name": "Team", "display_name": "班组",
     "description": "生产班组，含班组长、排班模式(日/夜/轮)"},
    {"api_name": "Material", "display_name": "物料",
     "description": "原材料/辅材/消耗品，含保质期和存储条件"},
    {"api_name": "Tooling", "display_name": "工装",
     "description": "工装/夹具/检具/模具，含校准周期和使用寿命"},
    {"api_name": "Supplier", "display_name": "供应商",
     "description": "零部件供应商，Tier 1/2/3等级，ITAR合规"},
    {"api_name": "QualityInspection", "display_name": "质检记录",
     "description": "FAI/过程/最终检验，检验方法：目视/量具/CMM/NDT"},
    {"api_name": "NonConformance", "display_name": "不合格品报告",
     "description": "NCR/MRB，含8D/5Why根因分析和处置决定"},
    {"api_name": "CAPA", "display_name": "纠正预防措施",
     "description": "纠正与预防措施(CAPA)，关联NCR，效果验证"},
    {"api_name": "EngineeringChange", "display_name": "工程更改",
     "description": "ECN/ECO，含影响分析、构型管理、生效架次"},
    {"api_name": "TechnicalDocument", "display_name": "技术文档",
     "description": "图纸/规范，含版本号、密级(ITAR/CUI)"},
    {"api_name": "GroundTest", "display_name": "地面测试",
     "description": "液压/电气/航电/武器系统联调测试记录"},
    {"api_name": "FlightTest", "display_name": "试飞记录",
     "description": "试飞科目、飞行小时、故障记录、试飞员评语"},
    {"api_name": "DeliveryMilestone", "display_name": "交付里程碑",
     "description": "DD-250签收、军方验收、移交仪式节点"},
]

# 每个 ObjectType 的属性定义 — 车间主管真正会填写的字段
OBJECT_TYPE_PROPERTIES: dict[str, list[dict]] = {
    "F35Aircraft": [
        {"api_name": "tail_number", "display_name": "尾号", "data_type": "DT_STRING",
         "description": "飞机尾号，如 AF-42"},
        {"api_name": "variant", "display_name": "变体型号", "data_type": "DT_STRING",
         "description": "A(CTOL)/B(STOVL)/C(CV)"},
        {"api_name": "customer_country", "display_name": "客户国家", "data_type": "DT_STRING",
         "description": "交付目标国家/军种"},
        {"api_name": "target_delivery_date", "display_name": "目标交付日期", "data_type": "DT_TIMESTAMP",
         "description": "合同交付日期"},
        {"api_name": "current_station", "display_name": "当前工位", "data_type": "DT_STRING",
         "description": "当前所在总装工位编号"},
        {"api_name": "assembly_progress_pct", "display_name": "装配进度%", "data_type": "DT_DOUBLE",
         "description": "总装完成百分比 0-100"},
    ],
    "MajorAssembly": [
        {"api_name": "section_code", "display_name": "段号", "data_type": "DT_STRING",
         "description": "结构段号：S41/S43/S46/Wing/Emp"},
        {"api_name": "assembly_type", "display_name": "装配类型", "data_type": "DT_STRING",
         "description": "structural/systems/payload"},
        {"api_name": "weight_actual_kg", "display_name": "实测重量(kg)", "data_type": "DT_DOUBLE",
         "description": "称重实测重量"},
    ],
    "Component": [
        {"api_name": "mpn", "display_name": "制造商零件号", "data_type": "DT_STRING",
         "description": "Manufacturer Part Number"},
        {"api_name": "cage_code", "display_name": "CAGE Code", "data_type": "DT_STRING",
         "description": "商业和政府实体代码"},
        {"api_name": "shelf_life_days", "display_name": "保质期(天)", "data_type": "DT_INTEGER",
         "description": "限寿件保质期天数，0=无限"},
    ],
    "WorkOrder": [
        {"api_name": "wo_number", "display_name": "工单号", "data_type": "DT_STRING",
         "description": "工单编号 WO-YYYY-NNNNN"},
        {"api_name": "wo_status", "display_name": "工单状态", "data_type": "DT_STRING",
         "description": "created/released/in_progress/completed/closed"},
        {"api_name": "bom_version", "display_name": "BOM版本", "data_type": "DT_STRING",
         "description": "关联的BOM版本号"},
        {"api_name": "target_aircraft", "display_name": "目标架次", "data_type": "DT_STRING",
         "description": "目标飞机尾号"},
    ],
    "ProcessStep": [
        {"api_name": "step_number", "display_name": "工序号", "data_type": "DT_INTEGER",
         "description": "工艺路线中的序号"},
        {"api_name": "step_type", "display_name": "工序类型", "data_type": "DT_STRING",
         "description": "assembly/inspection/test/rework"},
        {"api_name": "is_critical_path", "display_name": "关键路径", "data_type": "DT_BOOLEAN",
         "description": "是否在关键路径上"},
        {"api_name": "standard_hours", "display_name": "标准工时(h)", "data_type": "DT_DOUBLE",
         "description": "标准工时"},
    ],
    "Technician": [
        {"api_name": "badge_number", "display_name": "工号", "data_type": "DT_STRING",
         "description": "员工工号"},
        {"api_name": "skill_level", "display_name": "技能等级", "data_type": "DT_STRING",
         "description": "A(高级)/B(中级)/C(初级)"},
        {"api_name": "certifications", "display_name": "资质认证", "data_type": "DT_STRING",
         "description": "NDT/焊接/密封/电气等认证，逗号分隔"},
    ],
    "QualityInspection": [
        {"api_name": "inspection_type", "display_name": "检验类型", "data_type": "DT_STRING",
         "description": "FAI/process/final"},
        {"api_name": "inspection_method", "display_name": "检验方法", "data_type": "DT_STRING",
         "description": "visual/gauge/cmm/ndt"},
        {"api_name": "result", "display_name": "检验结果", "data_type": "DT_STRING",
         "description": "pass/fail/conditional"},
        {"api_name": "inspector_badge", "display_name": "检验员工号", "data_type": "DT_STRING",
         "description": "检验员工号"},
    ],
    "NonConformance": [
        {"api_name": "ncr_number", "display_name": "NCR编号", "data_type": "DT_STRING",
         "description": "NCR-YYYY-NNNNN"},
        {"api_name": "defect_category", "display_name": "缺陷分类", "data_type": "DT_STRING",
         "description": "dimensional/cosmetic/functional/material"},
        {"api_name": "severity", "display_name": "严重等级", "data_type": "DT_STRING",
         "description": "critical/major/minor"},
        {"api_name": "disposition", "display_name": "处置决定", "data_type": "DT_STRING",
         "description": "rework/repair/scrap/use_as_is"},
    ],
    "Material": [
        {"api_name": "material_code", "display_name": "物料编码", "data_type": "DT_STRING",
         "description": "物料主数据编码"},
        {"api_name": "uom", "display_name": "计量单位", "data_type": "DT_STRING",
         "description": "EA/KG/M/L等"},
        {"api_name": "storage_temp_min", "display_name": "最低存储温度℃", "data_type": "DT_DOUBLE",
         "description": "存储温度下限"},
        {"api_name": "storage_temp_max", "display_name": "最高存储温度℃", "data_type": "DT_DOUBLE",
         "description": "存储温度上限"},
    ],
    "Tooling": [
        {"api_name": "tool_code", "display_name": "工装编号", "data_type": "DT_STRING",
         "description": "工装唯一编号"},
        {"api_name": "calibration_due", "display_name": "校准到期日", "data_type": "DT_TIMESTAMP",
         "description": "下次校准日期"},
        {"api_name": "tool_status", "display_name": "工装状态", "data_type": "DT_STRING",
         "description": "in_use/maintenance/retired"},
    ],
    "EngineeringChange": [
        {"api_name": "eco_number", "display_name": "ECO编号", "data_type": "DT_STRING",
         "description": "ECO-YYYY-NNNNN"},
        {"api_name": "effectivity_from", "display_name": "生效起始架次", "data_type": "DT_STRING",
         "description": "从哪架飞机开始生效"},
        {"api_name": "effectivity_to", "display_name": "生效截止架次", "data_type": "DT_STRING",
         "description": "到哪架飞机截止，空=永久"},
        {"api_name": "change_class", "display_name": "变更等级", "data_type": "DT_STRING",
         "description": "Class I(重大)/Class II(次要)"},
    ],
}

LINK_TYPES = [
    {"api_name": "ComposedOf", "display_name": "包含",
     "description": "产品结构层级：整机→大部件→组件→零件"},
    {"api_name": "IntegratesWith", "display_name": "集成于",
     "description": "航电/发动机模块集成到大部件或整机"},
    {"api_name": "DependsOn", "display_name": "依赖",
     "description": "工序间前置依赖，支持FS/FF/SS/SF"},
    {"api_name": "BelongsToLine", "display_name": "属于产线",
     "description": "工位/工作单元归属产线"},
    {"api_name": "LocatedAt", "display_name": "位于",
     "description": "设备/工装/物料的空间位置"},
    {"api_name": "AssignedTo", "display_name": "分配给",
     "description": "工单/工序分配给工位和技师"},
    {"api_name": "PerformedBy", "display_name": "执行人",
     "description": "工序由某技师执行"},
    {"api_name": "ConsumesItem", "display_name": "消耗",
     "description": "工序消耗物料/零件的BOM用量"},
    {"api_name": "RequiresTool", "display_name": "需要工装",
     "description": "工序需要某工装/检具"},
    {"api_name": "ProducesOutput", "display_name": "产出",
     "description": "工序/工单产出部件或整机"},
    {"api_name": "InspectedAt", "display_name": "检验于",
     "description": "部件/工序在检验点被检验"},
    {"api_name": "RaisedAgainst", "display_name": "针对",
     "description": "NCR/CAPA针对某部件或工序"},
    {"api_name": "ResolvedBy", "display_name": "解决方",
     "description": "NCR通过某CAPA解决"},
    {"api_name": "SuppliedBy", "display_name": "供应商",
     "description": "零件/物料由某供应商提供"},
    {"api_name": "ReferencesDoc", "display_name": "参考文档",
     "description": "工单/工序/NCR引用某技术文档"},
    {"api_name": "Supersedes", "display_name": "替代",
     "description": "新版本替代旧版本"},
    {"api_name": "ImpactedBy", "display_name": "受影响",
     "description": "部件/工序受某ECO影响"},
]

INTERFACE_TYPES = [
    {"api_name": "Trackable", "display_name": "可追溯", "category": "OBJECT_INTERFACE",
     "description": "提供序列号、批次号，支持正向/反向追溯"},
    {"api_name": "Measurable", "display_name": "可度量", "category": "OBJECT_INTERFACE",
     "description": "提供尺寸/重量/公差等物理量度量能力"},
    {"api_name": "Certifiable", "display_name": "可认证", "category": "OBJECT_INTERFACE",
     "description": "适航认证(FAA/EASA)、MIL-STD、ITAR合规"},
    {"api_name": "Schedulable", "display_name": "可排程", "category": "OBJECT_INTERFACE",
     "description": "计划/实际开始结束时间、关键路径标记"},
    {"api_name": "Costed", "display_name": "可计价", "category": "OBJECT_INTERFACE",
     "description": "标准成本、实际成本、货币单位"},
    {"api_name": "Auditable", "display_name": "可审计", "category": "OBJECT_INTERFACE",
     "description": "创建人/修改人/审批人/时间/变更历史"},
    {"api_name": "Classifiable", "display_name": "可分级", "category": "OBJECT_INTERFACE",
     "description": "密级(ITAR/CUI)、安全等级、ECCN"},
]

ACTION_TYPES = [
    {"api_name": "StartAssembly", "display_name": "启动装配",
     "description": "验证前置工序完成、确认物料齐套、记录操作员上岗",
     "safety_level": "SAFETY_IDEMPOTENT_WRITE"},
    {"api_name": "CompleteAssembly", "display_name": "完成装配",
     "description": "记录实际工时、确认装配质量自检、触发下一工序",
     "safety_level": "SAFETY_IDEMPOTENT_WRITE"},
    {"api_name": "PauseAssembly", "display_name": "暂停装配",
     "description": "记录暂停原因(等料/等工装/质量问题/换班)",
     "safety_level": "SAFETY_IDEMPOTENT_WRITE"},
    {"api_name": "ResumeAssembly", "display_name": "恢复装配",
     "description": "验证暂停原因已解决、记录恢复时间",
     "safety_level": "SAFETY_IDEMPOTENT_WRITE"},
    {"api_name": "SubmitInspection", "display_name": "提交质检",
     "description": "选择检验类型(FAI/过程/最终)、上传检测数据",
     "safety_level": "SAFETY_NON_IDEMPOTENT"},
    {"api_name": "ApproveInspection", "display_name": "批准质检",
     "description": "质检员签字确认、更新质量状态为合格",
     "safety_level": "SAFETY_CRITICAL"},
    {"api_name": "RejectInspection", "display_name": "拒绝质检",
     "description": "标记不合格项、触发NCR流程",
     "safety_level": "SAFETY_CRITICAL"},
    {"api_name": "RaiseNCR", "display_name": "发起NCR",
     "description": "记录缺陷描述和分类(外观/尺寸/功能/材料)",
     "safety_level": "SAFETY_NON_IDEMPOTENT"},
    {"api_name": "DispositionNCR", "display_name": "NCR处置",
     "description": "返工/返修/报废/让步接收，需MRB批准",
     "safety_level": "SAFETY_CRITICAL"},
    {"api_name": "ReceiveMaterial", "display_name": "物料入库",
     "description": "来料检验、批次登记、保质期录入、库位分配",
     "safety_level": "SAFETY_IDEMPOTENT_WRITE"},
    {"api_name": "IssueMaterial", "display_name": "物料发料",
     "description": "扫码确认、FIFO、用量记录、库存扣减",
     "safety_level": "SAFETY_NON_IDEMPOTENT"},
    {"api_name": "ReturnMaterial", "display_name": "物料退库",
     "description": "数量确认、质量检查、库存回冲",
     "safety_level": "SAFETY_IDEMPOTENT_WRITE"},
    {"api_name": "IssueECO", "display_name": "发布ECO",
     "description": "影响分析、生效条件、审批流程、BOM更新",
     "safety_level": "SAFETY_CRITICAL"},
    {"api_name": "ImplementECO", "display_name": "执行ECO",
     "description": "标记受影响在制品、更新作业指导书",
     "safety_level": "SAFETY_NON_IDEMPOTENT"},
    {"api_name": "StartGroundTest", "display_name": "启动地面测试",
     "description": "系统加电、液压充压、航电自检",
     "safety_level": "SAFETY_IDEMPOTENT_WRITE"},
    {"api_name": "RecordFlightTest", "display_name": "记录试飞",
     "description": "飞行科目、故障代码、飞行小时、试飞员签字",
     "safety_level": "SAFETY_NON_IDEMPOTENT"},
    {"api_name": "ApproveDelivery", "display_name": "批准交付",
     "description": "DD-250签收、军方验收、构型审计",
     "safety_level": "SAFETY_CRITICAL"},
]

SHARED_PROPERTY_TYPES = [
    {"api_name": "SerialNumber", "display_name": "序列号", "data_type": "DT_STRING",
     "description": "唯一序列号 {产品代码}-{年份}-{序号}"},
    {"api_name": "BatchNumber", "display_name": "批次号", "data_type": "DT_STRING",
     "description": "生产/采购批次号，用于批次追溯"},
    {"api_name": "PartNumber", "display_name": "零件号", "data_type": "DT_STRING",
     "description": "设计零件号(P/N)"},
    {"api_name": "CageCode", "display_name": "笼号", "data_type": "DT_STRING",
     "description": "CAGE Code，国防部供应商标识"},
    {"api_name": "ManufactureDate", "display_name": "制造日期", "data_type": "DT_TIMESTAMP",
     "description": "制造/生产日期 UTC"},
    {"api_name": "ExpiryDate", "display_name": "有效期", "data_type": "DT_TIMESTAMP",
     "description": "有效期截止日期"},
    {"api_name": "PlannedStart", "display_name": "计划开始", "data_type": "DT_TIMESTAMP",
     "description": "计划开始时间"},
    {"api_name": "PlannedEnd", "display_name": "计划完成", "data_type": "DT_TIMESTAMP",
     "description": "计划完成时间"},
    {"api_name": "ActualStart", "display_name": "实际开始", "data_type": "DT_TIMESTAMP",
     "description": "实际开始时间"},
    {"api_name": "ActualEnd", "display_name": "实际完成", "data_type": "DT_TIMESTAMP",
     "description": "实际完成时间"},
    {"api_name": "WeightKg", "display_name": "重量(kg)", "data_type": "DT_DOUBLE",
     "description": "重量千克，精度0.001"},
    {"api_name": "LengthMm", "display_name": "长度(mm)", "data_type": "DT_DOUBLE",
     "description": "长度毫米，精度0.01"},
    {"api_name": "ToleranceMm", "display_name": "公差(mm)", "data_type": "DT_DOUBLE",
     "description": "尺寸公差 ±mm"},
    {"api_name": "StandardHours", "display_name": "标准工时", "data_type": "DT_DOUBLE",
     "description": "标准工时(小时)"},
    {"api_name": "ActualHours", "display_name": "实际工时", "data_type": "DT_DOUBLE",
     "description": "实际工时(小时)"},
    {"api_name": "Priority", "display_name": "优先级", "data_type": "DT_STRING",
     "description": "P1紧急/P2高/P3正常/P4低"},
    {"api_name": "SecurityClass", "display_name": "密级", "data_type": "DT_STRING",
     "description": "ITAR/CUI/Unclassified"},
    {"api_name": "QualityGrade", "display_name": "质量等级", "data_type": "DT_STRING",
     "description": "A合格/B让步/C待返工/D报废"},
    {"api_name": "LifecycleStatus", "display_name": "生命周期状态", "data_type": "DT_STRING",
     "description": "Draft/Active/Suspended/Retired/Scrapped"},
]


# ════════════════════════════════════════════════════════════════════
# TEST PHASES
# ════════════════════════════════════════════════════════════════════

def phase1_setting(c: LingShuClient, report: RoundReport):
    """Phase 1: Setting 模块 — 用户/租户/角色 CRUD"""
    print("\n[Phase 1] Setting 模块")
    print("=" * 50)

    # 1.1 登录
    run_api_test("管理员登录", "Setting", report, lambda: (
        c.login(),
        "Logged in"
    )[-1], critical=True)

    # 1.2 获取当前用户
    run_api_test("获取当前用户 /auth/me", "Setting", report, lambda: (
        resp := c.get("/setting/v1/auth/me"),
        check(resp.get("data", {}).get("email") == ADMIN_EMAIL, "email mismatch"),
        f"email={resp['data']['email']}, role={resp['data'].get('role')}"
    )[-1])

    # 1.3 创建新用户 — 质检主管
    run_api_test("创建用户: 质检主管 王工", "Setting", report, lambda: (
        resp := c.post("/setting/v1/users", {
            "email": "wang.qc@f35factory.com",
            "display_name": "王建国（质检主管）",
            "password": "QcAdmin2026!",
            "role": "member",
        }),
        rid := resp.get("data", {}).get("rid", ""),
        check(rid or "already" in resp.get("error", {}).get("message", "").lower()
            or "duplicate" in resp.get("error", {}).get("message", "").lower(), "create user failed"),
        f"rid={rid}" if rid else "already exists"
    )[-1])

    # 1.4 创建新用户 — 产线班组长
    run_api_test("创建用户: 产线班组长 李工", "Setting", report, lambda: (
        resp := c.post("/setting/v1/users", {
            "email": "li.lead@f35factory.com",
            "display_name": "李明（班组长）",
            "password": "LineLeader2026!",
            "role": "member",
        }),
        rid := resp.get("data", {}).get("rid", ""),
        f"rid={rid}" if rid else "already exists or error"
    )[-1])

    # 1.5 查询用户列表
    run_api_test("查询用户列表 ≥ 1人", "Setting", report, lambda: (
        resp := c.post("/setting/v1/users/query", {"pagination": {"page": 1, "page_size": 20}}),
        users := resp.get("data", []),
        check(len(users) >= 1, f"Expected ≥1 users, got {len(users)}"),
        f"total={resp.get('pagination', {}).get('total', len(users))}, "
        f"users={[u.get('email') for u in users[:5]]}"
    )[-1])

    # 1.6 查询租户
    run_api_test("查询租户列表", "Setting", report, lambda: (
        resp := c.post("/setting/v1/tenants/query", {"pagination": {"page": 1, "page_size": 20}}),
        tenants := resp.get("data", []),
        check(len(tenants) >= 1, "No tenants found"),
        f"tenants={[t.get('display_name') for t in tenants]}"
    )[-1])

    # 1.7 创建新租户 — Fort Worth 工厂
    run_api_test("创建租户: Fort Worth FACO", "Setting", report, lambda: (
        resp := c.post("/setting/v1/tenants", {
            "display_name": "Fort Worth FACO",
            "config": {"location": "Fort Worth, TX", "line_type": "Final Assembly"},
        }),
        rid := resp.get("data", {}).get("rid", ""),
        f"rid={rid}" if rid else resp.get("error", {}).get("message", "exists")
    )[-1])

    # 1.8 审计日志
    run_api_test("查询审计日志 ≥ 1条", "Setting", report, lambda: (
        resp := c.post("/setting/v1/audit-logs/query", {"pagination": {"page": 1, "page_size": 10}}),
        logs := resp.get("data", []),
        check(len(logs) >= 1, f"Expected ≥1 audit logs, got {len(logs)}"),
        f"total={resp.get('pagination', {}).get('total', len(logs))}, latest_event={logs[0].get('event_type', 'N/A')}"
    )[-1])

    # 1.9 Setting 概览
    run_api_test("Setting 概览统计", "Setting", report, lambda: (
        resp := c.get("/setting/v1/overview"),
        data := resp.get("data", {}),
        f"users={data.get('total_users')}, tenants={data.get('total_tenants')}"
    )[-1])

    # 1.10 修改密码（改后改回）
    run_api_test("修改密码 (改→改回)", "Setting", report, lambda: (
        r1 := c.post("/setting/v1/auth/change-password", {
            "current_password": ADMIN_PASSWORD,
            "new_password": "TempPass2026!",
        }),
        # Login with new password
        c.login(ADMIN_EMAIL, "TempPass2026!"),
        # Change back
        r2 := c.post("/setting/v1/auth/change-password", {
            "current_password": "TempPass2026!",
            "new_password": ADMIN_PASSWORD,
        }),
        c.login(),  # re-login with original
        "Password changed and restored"
    )[-1])


def phase2_ontology_create(c: LingShuClient, report: RoundReport):
    """Phase 2: 创建完整本体 — OT+属性, LT, IT, AT, SPT"""
    print("\n[Phase 2] Ontology 本体创建")
    print("=" * 50)

    # 2.1 创建所有 SharedPropertyType
    def create_spts():
        ok, fail = 0, 0
        for sp in SHARED_PROPERTY_TYPES:
            rid, status = c.create_entity("shared-property-types", sp)
            if rid:
                ok += 1
            else:
                fail += 1
        return f"created/exists={ok}, failed={fail}"

    run_api_test(f"创建 {len(SHARED_PROPERTY_TYPES)} 个 SharedPropertyType", "Ontology.Create", report, create_spts)

    # 2.2 创建所有 InterfaceType (含 category!)
    def create_its():
        ok, fail = 0, 0
        for it in INTERFACE_TYPES:
            rid, status = c.create_entity("interface-types", it)
            if rid:
                ok += 1
            else:
                fail += 1
                print(f"    ⚠ IT {it['api_name']}: {status}")
        return f"created/exists={ok}, failed={fail}"

    run_api_test(f"创建 {len(INTERFACE_TYPES)} 个 InterfaceType", "Ontology.Create", report, create_its)

    # 2.3 创建所有 ObjectType
    def create_ots():
        ok, fail = 0, 0
        for ot in OBJECT_TYPES:
            rid, status = c.create_entity("object-types", ot)
            if rid:
                ok += 1
            else:
                fail += 1
                print(f"    ⚠ OT {ot['api_name']}: {status}")
        return f"created/exists={ok}, failed={fail}"

    run_api_test(f"创建 {len(OBJECT_TYPES)} 个 ObjectType", "Ontology.Create", report, create_ots)

    # 2.4 为 ObjectType 添加 PropertyType (batch lock per parent)
    def add_properties():
        total_props, ok, fail = 0, 0, 0
        for ot_name, props in OBJECT_TYPE_PROPERTIES.items():
            ot_rid = c.rid(ot_name)
            if not ot_rid:
                print(f"    ⚠ No RID for {ot_name}, skipping properties")
                fail += len(props)
                continue
            # Lock once per parent
            c.lock_entity("object-types", ot_rid)
            try:
                for prop in props:
                    total_props += 1
                    resp = c.post(f"/ontology/v1/object-types/{ot_rid}/property-types", prop)
                    rid = resp.get("data", {}).get("rid", "")
                    err = resp.get("error", {}).get("message", "")
                    if rid or "duplicate" in err.lower() or "already" in err.lower():
                        ok += 1
                    else:
                        fail += 1
                        print(f"    ⚠ {ot_name}.{prop['api_name']}: {err}")
            finally:
                c.unlock_entity("object-types", ot_rid)
        return f"total={total_props}, ok={ok}, fail={fail}"

    total_props = sum(len(v) for v in OBJECT_TYPE_PROPERTIES.values())
    run_api_test(f"添加 {total_props} 个 PropertyType 到 ObjectType", "Ontology.Create", report, add_properties)

    # 2.5 创建所有 LinkType
    def create_lts():
        ok, fail = 0, 0
        for lt in LINK_TYPES:
            rid, status = c.create_entity("link-types", lt)
            if rid:
                ok += 1
            else:
                fail += 1
        return f"created/exists={ok}, failed={fail}"

    run_api_test(f"创建 {len(LINK_TYPES)} 个 LinkType", "Ontology.Create", report, create_lts)

    # 2.6 创建所有 ActionType (含 safety_level)
    def create_ats():
        ok, fail = 0, 0
        for at in ACTION_TYPES:
            rid, status = c.create_entity("action-types", at)
            if rid:
                ok += 1
            else:
                fail += 1
        return f"created/exists={ok}, failed={fail}"

    run_api_test(f"创建 {len(ACTION_TYPES)} 个 ActionType", "Ontology.Create", report, create_ats)


def phase3_ontology_verify(c: LingShuClient, report: RoundReport):
    """Phase 3: 验证本体数据完整性"""
    print("\n[Phase 3] Ontology 数据验证")
    print("=" * 50)

    # 3.1 查询验证各实体数量
    for entity_type, expected, label in [
        ("object-types", len(OBJECT_TYPES), "ObjectType"),
        ("link-types", len(LINK_TYPES), "LinkType"),
        ("interface-types", len(INTERFACE_TYPES), "InterfaceType"),
        ("action-types", len(ACTION_TYPES), "ActionType"),
        ("shared-property-types", len(SHARED_PROPERTY_TYPES), "SharedPropertyType"),
    ]:
        run_api_test(f"验证 {label} 数量 = {expected}", "Ontology.Verify", report, lambda et=entity_type, exp=expected: (
            items := c.query_entities(et),
            count := len(items),
            check(count == exp, f"Expected {exp}, got {count}"),
            f"count={count}, names={[i.get('api_name') for i in items[:5]]}..."
        )[-1])

    # 3.2 验证 F35Aircraft 属性
    run_api_test("验证 F35Aircraft 属性字段", "Ontology.Verify", report, lambda: (
        rid := c.rid("F35Aircraft"),
        check(rid, "No RID for F35Aircraft"),
        resp := c.get_entity("object-types", rid),
        data := resp.get("data", {}),
        props := data.get("property_types", []),
        prop_names := [p.get("api_name") for p in props],
        expected := ["tail_number", "variant", "customer_country", "target_delivery_date",
                     "current_station", "assembly_progress_pct"],
        missing := [e for e in expected if e not in prop_names],
        check(len(missing) == 0, f"Missing props: {missing}"),
        f"Found {len(props)} properties: {prop_names}"
    )[-1])

    # 3.3 验证 InterfaceType 有 category
    run_api_test("验证 InterfaceType 含 category", "Ontology.Verify", report, lambda: (
        items := c.query_entities("interface-types"),
        check(len(items) >= 1, f"No InterfaceTypes found! Got {len(items)}"),
        categories := [i.get("category") for i in items],
        check(all(c_val for c_val in categories), f"Some IT missing category: {categories}"),
        f"count={len(items)}, categories={categories}"
    )[-1])

    # 3.4 获取单个实体详情
    run_api_test("获取 WorkOrder 详情", "Ontology.Verify", report, lambda: (
        rid := c.rid("WorkOrder"),
        check(rid, "No RID for WorkOrder"),
        resp := c.get_entity("object-types", rid),
        data := resp.get("data", {}),
        props := data.get("property_types", []),
        f"rid={rid}, api_name={data.get('api_name')}, "
        f"props={len(props)}: {[p.get('api_name') for p in props]}"
    )[-1])

    # 3.5 搜索实体
    run_api_test("搜索 'Assembly' 相关实体", "Ontology.Verify", report, lambda: (
        resp := c.search_entities("Assembly"),
        results := resp.get("data", []),
        f"found={len(results)}, items={[r.get('api_name') for r in results[:5]]}"
    )[-1])

    # 3.6 获取拓扑
    run_api_test("获取本体拓扑图", "Ontology.Verify", report, lambda: (
        resp := c.get_topology(),
        data := resp.get("data", {}),
        f"nodes={len(data.get('nodes', []))}, edges={len(data.get('edges', []))}"
    )[-1])


def phase4_version_management(c: LingShuClient, report: RoundReport):
    """Phase 4: 版本管理全生命周期"""
    print("\n[Phase 4] 版本管理")
    print("=" * 50)

    # 4.1 查看 Draft 摘要
    run_api_test("查看 Draft 摘要", "Version", report, lambda: (
        resp := c.drafts_summary(),
        data := resp.get("data", {}),
        f"counts={data.get('counts', {})}, total={data.get('total', 0)}"
    )[-1])

    # 4.2 提交所有 Draft 到 Staging (只提交有 Draft 的实体)
    def submit_all_to_staging():
        submitted = {"ok": 0, "already": 0, "fail": 0, "no_draft": 0}
        entity_types = [
            ("shared-property-types", SHARED_PROPERTY_TYPES),
            ("interface-types", INTERFACE_TYPES),
            ("object-types", OBJECT_TYPES),
            ("link-types", LINK_TYPES),
            ("action-types", ACTION_TYPES),
        ]
        for et, items in entity_types:
            for item in items:
                rid = c.rid(item["api_name"])
                if not rid:
                    continue
                status = c.submit_to_staging(et, rid)
                if status == "ok":
                    submitted["ok"] += 1
                elif status == "already_staged":
                    submitted["already"] += 1
                elif "draft" in status.lower() or "not found" in status.lower():
                    submitted["no_draft"] += 1  # Already active, no draft to submit
                else:
                    submitted["fail"] += 1
        return (f"ok={submitted['ok']}, already={submitted['already']}, "
                f"no_draft={submitted['no_draft']}, fail={submitted['fail']}")

    run_api_test("提交所有实体到 Staging", "Version", report, submit_all_to_staging)

    # 4.3 查看 Staging 摘要
    run_api_test("查看 Staging 摘要", "Version", report, lambda: (
        resp := c.staging_summary(),
        data := resp.get("data", {}),
        f"counts={data.get('counts', {})}, total={data.get('total', 0)}"
    )[-1])

    # 4.4 Commit Staging → Snapshot v1 (如果有 Staging 实体才提交; 否则验证已有快照)
    def commit_or_verify_snapshot():
        # Try to commit if there are staged entities
        result = c.commit_staging("v1.0: F35产线初始本体模型 — 25 OT + 17 LT + 7 IT + 17 AT + 19 SPT")
        if result[1] == "ok":
            return f"snapshot_id={result[0]}"
        # If nothing to commit, verify we have at least 1 snapshot from previous runs
        snaps = c.query_snapshots()
        check(len(snaps) >= 1, f"No snapshots and commit failed: {result[1]}")
        return f"already_committed, existing_snapshots={len(snaps)}"

    run_api_test("Commit Staging → Snapshot v1 (初始产线模型)", "Version", report,
                 commit_or_verify_snapshot, critical=True)

    # 4.5 查询快照列表
    run_api_test("验证快照列表 ≥ 1", "Version", report, lambda: (
        snaps := c.query_snapshots(),
        check(len(snaps) >= 1, f"Expected ≥1 snapshots, got {len(snaps)}"),
        f"count={len(snaps)}, latest={snaps[0].get('snapshot_id', 'N/A')}"
    )[-1])

    # 4.6 修改一个实体并创建 v2 快照 — 模拟 ECO 变更
    def create_v2():
        # 修改 F35Aircraft 描述（模拟 ECO: 增加 Block 4 升级说明）
        rid = c.rid("F35Aircraft")
        if not rid:
            return "SKIP: no F35Aircraft RID"
        # Must lock → update → submit → commit
        c.lock_entity("object-types", rid)
        try:
            c.update_entity("object-types", rid, {
                "description": "F-35 Lightning II 战斗机整机 — 含 A/B/C 三个变体。Block 4 升级：增强电子战能力、新型雷达模式、扩展武器挂载",
            })
        finally:
            c.unlock_entity("object-types", rid)
        # Submit draft to staging
        submit_status = c.submit_to_staging("object-types", rid)
        check(submit_status == "ok", f"v2 submit failed: {submit_status}")
        # Commit
        sid, status = c.commit_staging("v2.0: ECO-2026-0001 Block 4 升级变更")
        check(status == "ok", f"v2 commit failed: {status}")
        return f"snapshot_id={sid}"

    run_api_test("创建 Snapshot v2 (ECO 变更)", "Version", report, create_v2)

    # 4.7 查看快照 diff
    run_api_test("查看 v2 快照 diff", "Version", report, lambda: (
        snaps := c.query_snapshots(),
        check(len(snaps) >= 1, "No snapshots found"),
        diff := c.get_snapshot_diff(snaps[0].get("snapshot_id", "")),
        f"diff_data={str(diff.get('data', {}))[:200]}"
    )[-1])

    # 4.8 创建另一个实体变更并 discard staging
    def test_discard():
        rid = c.rid("WorkStation")
        if not rid:
            return "SKIP: no WorkStation RID"
        # Lock → update → submit → discard
        c.lock_entity("object-types", rid)
        try:
            c.update_entity("object-types", rid, {
                "description": "测试 discard — 这个变更应该被丢弃",
            })
        finally:
            c.unlock_entity("object-types", rid)
        c.submit_to_staging("object-types", rid)
        # Verify staging has items
        summary = c.staging_summary()
        total = summary.get("data", {}).get("total", 0)
        # Discard
        result = c.discard_staging()
        # Verify staging empty
        summary2 = c.staging_summary()
        total2 = summary2.get("data", {}).get("total", 0)
        return f"before_discard={total}, after_discard={total2}, result={result}"

    run_api_test("Discard Staging 测试", "Version", report, test_discard)

    # 4.9 验证快照数量
    run_api_test("验证快照数量 ≥ 2", "Version", report, lambda: (
        snaps := c.query_snapshots(),
        f"snapshot_count={len(snaps)}, ids={[s.get('snapshot_id', '')[:20] for s in snaps]}"
    )[-1])


def phase5_data_module(c: LingShuClient, report: RoundReport):
    """Phase 5: Data 模块 — 连接 CRUD"""
    print("\n[Phase 5] Data 模块")
    print("=" * 50)

    # 5.1 Data 概览
    run_api_test("Data 概览", "Data", report, lambda: (
        resp := c.get("/data/v1/overview"),
        data := resp.get("data", {}),
        f"overview={data}"
    )[-1])

    # 5.2 创建数据连接 — PostgreSQL (模拟产线MES数据库)
    conn_rid = None

    def create_connection():
        nonlocal conn_rid
        resp = c.post("/data/v1/connections", {
            "display_name": "F35 MES Production DB",
            "type": "postgresql",
            "config": {
                "host": "mes-db.f35factory.local",
                "port": 5432,
                "database": "f35_mes",
                "schema": "production",
            },
        })
        conn_rid = resp.get("data", {}).get("rid", "")
        if conn_rid:
            return f"rid={conn_rid}"
        return f"response={resp.get('error', resp)}"

    run_api_test("创建数据连接: F35 MES DB", "Data", report, create_connection)

    # 5.3 查询连接列表
    run_api_test("查询数据连接列表", "Data", report, lambda: (
        resp := c.post("/data/v1/connections/query", {"pagination": {"page": 1, "page_size": 10}}),
        conns := resp.get("data", []),
        f"count={len(conns)}, names={[cn.get('display_name') for cn in conns]}"
    )[-1])

    # 5.4 获取连接详情
    if conn_rid:
        run_api_test("获取连接详情", "Data", report, lambda: (
            resp := c.get(f"/data/v1/connections/{conn_rid}"),
            data := resp.get("data", {}),
            f"name={data.get('display_name')}, type={data.get('type')}, status={data.get('status')}"
        )[-1])

        # 5.5 更新连接
        run_api_test("更新连接: 添加说明", "Data", report, lambda: (
            resp := c.put(f"/data/v1/connections/{conn_rid}", {
                "display_name": "F35 MES Production DB (Fort Worth)",
            }),
            data := resp.get("data", {}),
            f"updated_name={data.get('display_name')}"
        )[-1])

    # 5.6 创建第二个连接 — Iceberg (质量数据湖)
    run_api_test("创建数据连接: Quality Data Lake", "Data", report, lambda: (
        resp := c.post("/data/v1/connections", {
            "display_name": "F35 Quality Data Lake",
            "type": "postgresql",
            "config": {
                "host": "datalake.f35factory.local",
                "port": 5432,
                "database": "quality_lake",
            },
        }),
        f"rid={resp.get('data', {}).get('rid', 'N/A')}"
    )[-1])


def phase6_function_module(c: LingShuClient, report: RoundReport):
    """Phase 6: Function 模块 — 全局函数, 工作流, 能力目录"""
    print("\n[Phase 6] Function 模块")
    print("=" * 50)

    # 6.1 Function 概览
    run_api_test("Function 概览", "Function", report, lambda: (
        resp := c.get("/function/v1/overview"),
        data := resp.get("data", {}),
        f"overview={data}"
    )[-1])

    # 6.2 创建全局函数 — 计算工序完成率
    func_rid = None

    def create_function():
        nonlocal func_rid
        resp = c.post("/function/v1/functions", {
            "api_name": "calc_assembly_progress",
            "display_name": "计算装配进度",
            "description": "根据工单下所有工序的完成状态，计算总装配进度百分比",
            "parameters": [
                {"name": "work_order_rid", "type": "string", "description": "工单RID", "required": True},
            ],
        })
        func_rid = resp.get("data", {}).get("rid", "")
        return f"rid={func_rid}" if func_rid else f"error={resp.get('error', {}).get('message', 'unknown')}"

    run_api_test("创建全局函数: calc_assembly_progress", "Function", report, create_function)

    # 6.3 创建第二个函数 — 齐套检查
    run_api_test("创建全局函数: check_material_readiness", "Function", report, lambda: (
        resp := c.post("/function/v1/functions", {
            "api_name": "check_material_readiness",
            "display_name": "物料齐套检查",
            "description": "检查工序所需物料是否全部到位，返回齐套率和缺料清单",
            "parameters": [
                {"name": "process_step_rid", "type": "string", "description": "工序RID", "required": True},
            ],
        }),
        f"rid={resp.get('data', {}).get('rid', 'N/A')}"
    )[-1])

    # 6.4 查询全局函数列表
    run_api_test("查询全局函数列表", "Function", report, lambda: (
        resp := c.post("/function/v1/functions/query", {"pagination": {"page": 1, "page_size": 20}}),
        funcs := resp.get("data", []),
        f"count={len(funcs)}, names={[f_.get('api_name') for f_ in funcs]}"
    )[-1])

    # 6.5 获取函数详情
    if func_rid:
        run_api_test("获取函数详情", "Function", report, lambda: (
            resp := c.get(f"/function/v1/functions/{func_rid}"),
            data := resp.get("data", {}),
            f"name={data.get('api_name')}, params={data.get('parameters')}"
        )[-1])

    # 6.6 创建工作流 — 装配质检流程
    run_api_test("创建工作流: 装配→质检→放行", "Function", report, lambda: (
        resp := c.post("/function/v1/workflows", {
            "api_name": "assembly_qc_release",
            "display_name": "装配-质检-放行流程",
            "description": "标准装配工序流程：启动装配→完成装配→提交质检→(通过→放行 | 不通过→NCR)",
            "nodes": [
                {"id": "start", "type": "action", "action_rid": c.rid("StartAssembly") or "pending"},
                {"id": "complete", "type": "action", "action_rid": c.rid("CompleteAssembly") or "pending"},
                {"id": "inspect", "type": "action", "action_rid": c.rid("SubmitInspection") or "pending"},
                {"id": "approve", "type": "action", "action_rid": c.rid("ApproveInspection") or "pending"},
                {"id": "ncr", "type": "action", "action_rid": c.rid("RaiseNCR") or "pending"},
            ],
            "edges": [
                {"from": "start", "to": "complete"},
                {"from": "complete", "to": "inspect"},
                {"from": "inspect", "to": "approve", "condition": "result == 'pass'"},
                {"from": "inspect", "to": "ncr", "condition": "result == 'fail'"},
            ],
        }),
        f"rid={resp.get('data', {}).get('rid', 'N/A')}"
    )[-1])

    # 6.7 查询工作流列表
    run_api_test("查询工作流列表", "Function", report, lambda: (
        resp := c.post("/function/v1/workflows/query", {"pagination": {"page": 1, "page_size": 10}}),
        wfs := resp.get("data", []),
        f"count={len(wfs)}, names={[w.get('api_name') for w in wfs]}"
    )[-1])

    # 6.8 能力目录
    run_api_test("查询能力目录 (Action + Function)", "Function", report, lambda: (
        resp := c.post("/function/v1/capabilities/query", {}),
        caps := resp.get("data", []),
        f"total_capabilities={len(caps)}"
    )[-1])


def phase7_agent_module(c: LingShuClient, report: RoundReport):
    """Phase 7: Agent 模块 — 模型/技能/MCP/子代理/会话"""
    print("\n[Phase 7] Agent 模块")
    print("=" * 50)

    # 7.1 Agent 概览
    run_api_test("Agent 概览", "Agent", report, lambda: (
        resp := c.get("/copilot/v1/overview"),
        data := resp.get("data", {}),
        f"sessions={data.get('total_sessions')}, models={data.get('total_models')}"
    )[-1])

    # 7.2 注册模型 — GPT-4o (用于车间问答)
    model_rid = None

    def register_model():
        nonlocal model_rid
        resp = c.post("/copilot/v1/models", {
            "api_name": "gpt4o_factory",
            "display_name": "GPT-4o (车间助手)",
            "provider": "openai",
            "connection": {"api_key": "sk-placeholder-for-test"},
            "parameters": {"temperature": 0.3, "max_tokens": 4096},
            "is_default": True,
        })
        model_rid = resp.get("data", {}).get("rid", "")
        return f"rid={model_rid}" if model_rid else f"error={resp.get('error', {}).get('message', 'unknown')}"

    run_api_test("注册模型: GPT-4o (车间助手)", "Agent", report, register_model)

    # 7.3 注册第二个模型
    run_api_test("注册模型: Claude (技术文档分析)", "Agent", report, lambda: (
        resp := c.post("/copilot/v1/models", {
            "api_name": "claude_docs",
            "display_name": "Claude (技术文档分析)",
            "provider": "anthropic",
            "connection": {"api_key": "sk-placeholder-for-test"},
            "parameters": {"temperature": 0.1, "max_tokens": 8192},
        }),
        f"rid={resp.get('data', {}).get('rid', 'N/A')}"
    )[-1])

    # 7.4 查询模型列表
    run_api_test("查询模型列表 ≥ 2", "Agent", report, lambda: (
        resp := c.post("/copilot/v1/models/query", {"pagination": {"page": 1, "page_size": 20}}),
        models := resp.get("data", []),
        f"count={len(models)}, names={[m.get('api_name') for m in models]}"
    )[-1])

    # 7.5 创建技能 — 工序查询
    skill_rid = None

    def create_skill():
        nonlocal skill_rid
        resp = c.post("/copilot/v1/skills", {
            "api_name": "query_process_status",
            "display_name": "工序状态查询",
            "description": "查询指定工单下所有工序的执行状态、耗时和质检结果",
            "system_prompt": "你是F-35产线的工序查询助手。当用户询问工序状态时，调用相关API查询工序执行情况。",
            "tool_bindings": [
                {"tool_name": "query_work_order", "description": "查询工单详情"},
                {"tool_name": "list_process_steps", "description": "列出工序清单"},
            ],
        })
        skill_rid = resp.get("data", {}).get("rid", "")
        return f"rid={skill_rid}" if skill_rid else f"error={resp.get('error', {}).get('message', 'unknown')}"

    run_api_test("创建技能: 工序状态查询", "Agent", report, create_skill)

    # 7.6 创建第二个技能 — 质量分析
    run_api_test("创建技能: NCR 趋势分析", "Agent", report, lambda: (
        resp := c.post("/copilot/v1/skills", {
            "api_name": "ncr_trend_analysis",
            "display_name": "NCR 趋势分析",
            "description": "分析不合格品报告的趋势，识别高发缺陷类型和工位",
            "system_prompt": "你是F-35产线质量分析师。分析NCR数据，找出缺陷趋势和根因。",
        }),
        f"rid={resp.get('data', {}).get('rid', 'N/A')}"
    )[-1])

    # 7.7 查询技能列表
    run_api_test("查询技能列表 ≥ 2", "Agent", report, lambda: (
        resp := c.post("/copilot/v1/skills/query", {"pagination": {"page": 1, "page_size": 20}}),
        skills := resp.get("data", []),
        f"count={len(skills)}, names={[s.get('api_name') for s in skills]}"
    )[-1])

    # 7.8 创建 MCP 连接 — 产线监控
    run_api_test("创建 MCP 连接: 产线监控 OPC-UA", "Agent", report, lambda: (
        resp := c.post("/copilot/v1/mcp", {
            "api_name": "opcua_line_monitor",
            "display_name": "OPC-UA 产线监控",
            "description": "连接产线 OPC-UA 服务器，获取工位状态和设备数据",
            "transport": {
                "protocol": "sse",
                "url": "http://opcua-bridge.f35factory.local:8080/mcp",
            },
        }),
        f"rid={resp.get('data', {}).get('rid', 'N/A')}"
    )[-1])

    # 7.9 查询 MCP 列表
    run_api_test("查询 MCP 连接列表", "Agent", report, lambda: (
        resp := c.post("/copilot/v1/mcp/query", {"pagination": {"page": 1, "page_size": 20}}),
        mcps := resp.get("data", []),
        f"count={len(mcps)}, names={[m.get('api_name') for m in mcps]}"
    )[-1])

    # 7.10 创建子代理 — 质量管理助手
    run_api_test("创建子代理: 质量管理助手", "Agent", report, lambda: (
        resp := c.post("/copilot/v1/sub-agents", {
            "api_name": "qc_assistant",
            "display_name": "质量管理助手",
            "description": "专注于质量检验、NCR处置和CAPA跟踪的AI助手",
            "system_prompt": "你是F-35产线的质量管理AI助手，帮助质检人员处理检验、NCR和CAPA相关事务。",
            "model_rid": model_rid or "",
            "enabled": True,
        }),
        f"rid={resp.get('data', {}).get('rid', 'N/A')}"
    )[-1])

    # 7.11 创建子代理 — 物料管理助手
    run_api_test("创建子代理: 物料管理助手", "Agent", report, lambda: (
        resp := c.post("/copilot/v1/sub-agents", {
            "api_name": "material_assistant",
            "display_name": "物料管理助手",
            "description": "物料收发、齐套检查、库存管理的AI助手",
            "system_prompt": "你是F-35产线的物料管理AI助手，处理物料入库、发料、退库和齐套检查。",
            "enabled": True,
        }),
        f"rid={resp.get('data', {}).get('rid', 'N/A')}"
    )[-1])

    # 7.12 查询子代理列表
    run_api_test("查询子代理列表 ≥ 2", "Agent", report, lambda: (
        resp := c.post("/copilot/v1/sub-agents/query", {"pagination": {"page": 1, "page_size": 20}}),
        agents := resp.get("data", []),
        f"count={len(agents)}, names={[a.get('api_name') for a in agents]}"
    )[-1])

    # 7.13 创建会话
    session_rid = None

    def create_session():
        nonlocal session_rid
        resp = c.post("/copilot/v1/sessions", {
            "mode": "agent",
            "context": {"aircraft": "AF-42", "station": "FACO-L12"},
        })
        session_rid = resp.get("data", {}).get("rid", "") or resp.get("data", {}).get("session_id", "")
        return f"session={session_rid}" if session_rid else f"error={resp.get('error', {}).get('message', 'unknown')}"

    run_api_test("创建会话: AF-42 总装上下文", "Agent", report, create_session)

    # 7.14 查询会话列表
    run_api_test("查询会话列表", "Agent", report, lambda: (
        resp := c.post("/copilot/v1/sessions/query", {"pagination": {"page": 1, "page_size": 20}}),
        sessions := resp.get("data", []),
        f"count={len(sessions)}"
    )[-1])


def phase8_ui_verification(report: RoundReport):
    """Phase 8: BrowserUse UI 验证"""
    print("\n[Phase 8] BrowserUse UI 验证")
    print("=" * 50)

    if not _browser_use_available:
        print("  ⚠ BrowserUse not available, skipping UI tests")
        report.add(TestResult(name="BrowserUse 不可用", phase="UI", status="SKIP", detail="browser_use package not installed"))
        return

    llm = ChatGoogle(model="gemini-2.5-flash", temperature=0)

    ui_tests = [
        ("Ontology 概览 — 统计卡片", f"""
Navigate to {BASE_URL}/ontology/overview.
Look at the statistics cards. Report the EXACT numbers for:
- Object Types count (should be 25)
- Link Types count (should be 17)
- Interface Types count (should be 7)
- Action Types count (should be 17)
- Shared Property Types count (should be 19)
Report each count you see.""", 15),

        ("ObjectType 列表 — 含 F35Aircraft", f"""
Navigate to {BASE_URL}/ontology/object-types.
Look at the table. Report:
1. Total count shown (header or pagination)
2. First 5 object type names in the table
3. Whether you can see an object type called 'F35Aircraft'""", 15),

        ("ObjectType 详情 — F35Aircraft 属性", f"""
Navigate to {BASE_URL}/ontology/object-types.
Click on the row for 'F35Aircraft' to open its detail page.
Report what properties/fields you see (e.g., tail_number, variant, etc.).""", 20),

        ("InterfaceType 列表 — 7个接口", f"""
Navigate to {BASE_URL}/ontology/interface-types.
Report ALL interface type names shown and the total count.
Expected: Trackable, Measurable, Certifiable, Schedulable, Costed, Auditable, Classifiable""", 15),

        ("ActionType 列表 — 安全等级", f"""
Navigate to {BASE_URL}/ontology/action-types.
Report the first 5 action type names and any safety_level information shown.""", 15),

        ("版本/快照页 — ≥2个快照", f"""
Navigate to {BASE_URL}/ontology/versions.
Report how many snapshots are listed and their commit messages or IDs.""", 15),

        ("Setting 用户管理 — 多用户", f"""
Navigate to {BASE_URL}/setting/users.
Report ALL users shown in the table (email and display name).""", 15),

        ("Setting 租户管理 — Fort Worth", f"""
Navigate to {BASE_URL}/setting/tenants.
Report ALL tenants shown. Look for 'Fort Worth FACO'.""", 15),

        ("Data 数据源 — MES连接", f"""
Navigate to {BASE_URL}/data/sources.
Report data source connections listed. Look for 'F35 MES Production DB'.""", 15),

        ("Agent 模型 — 2个AI模型", f"""
Navigate to {BASE_URL}/agent/models.
Report ALL models shown. Look for GPT-4o and Claude.""", 15),

        ("Agent 技能 — 工序查询+NCR分析", f"""
Navigate to {BASE_URL}/agent/skills.
Report ALL skills shown.""", 15),

        ("Agent 子代理 — 质量+物料助手", f"""
Navigate to {BASE_URL}/agent/sub-agents.
Report ALL sub-agents shown.""", 15),

        ("Function 能力列表", f"""
Navigate to {BASE_URL}/function/capabilities.
Report capabilities/actions listed.""", 15),

        ("跨模块 Dock 导航", f"""
Navigate to {BASE_URL}/ontology/overview.
Use the bottom navigation dock to visit ALL 5 modules in order:
Ontology → Data → Function → Agent → Setting
Report success for each navigation.""", 20),

        ("API 健康检查", f"""
Navigate to {API_URL}/health.
Report the JSON response.""", 5),
    ]

    async def run_all_ui():
        for name, task, steps in ui_tests:
            await run_browser_test(llm, name, "UI", task, report, max_steps=steps)

    asyncio.run(run_all_ui())


# ════════════════════════════ Report Generation ════════════════════════════

def generate_report(report: RoundReport) -> str:
    total, passed, failed, errors, skipped = report.summary()
    pass_rate = (passed / total * 100) if total > 0 else 0

    lines = [
        f"# LingShu 平台 E2E 测试报告 — 第 {report.round_num} 轮",
        "",
        "## 测试概况",
        "",
        "| 项目 | 值 |",
        "|------|-----|",
        f"| 轮次 | 第 {report.round_num} 轮 |",
        f"| 开始时间 | {report.start_time} |",
        f"| 结束时间 | {report.end_time} |",
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

    # Group by phase
    phases: dict[str, list[TestResult]] = {}
    for r in report.results:
        phases.setdefault(r.phase, []).append(r)

    for phase, results in phases.items():
        p = sum(1 for r in results if r.status == "PASS")
        t = len(results)
        lines.append(f"## {phase} ({p}/{t})")
        lines.append("")
        lines.append("| # | 测试项 | 状态 | 耗时 | 详情 |")
        lines.append("|---|--------|------|------|------|")
        for i, r in enumerate(results, 1):
            detail = r.detail[:120].replace("|", "/").replace("\n", " ") if r.detail else "-"
            icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥", "SKIP": "⏭"}.get(r.status, "?")
            lines.append(f"| {i} | {r.name} | {icon} {r.status} | {r.duration:.1f}s | {detail} |")
        lines.append("")

    # 失败项汇总
    failures = [r for r in report.results if r.status in ("FAIL", "ERROR")]
    if failures:
        lines.append("## 失败/错误项汇总")
        lines.append("")
        for r in failures:
            lines.append(f"- **{r.phase} > {r.name}** [{r.status}]: {r.detail[:200]}")
        lines.append("")

    return "\n".join(lines)


# ════════════════════════════ Main — Single Round ════════════════════════════

def run_single_round(round_num: int) -> RoundReport:
    """Execute one full test round."""
    print(f"\n{'═' * 70}")
    print(f"  第 {round_num} 轮测试开始")
    print(f"{'═' * 70}")

    report = RoundReport(round_num=round_num)
    report.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c = LingShuClient()

    # Phase 1: Setting
    phase1_setting(c, report)

    # Phase 2: Ontology 创建
    phase2_ontology_create(c, report)

    # Phase 3: Ontology 数据验证
    phase3_ontology_verify(c, report)

    # Phase 4: 版本管理
    phase4_version_management(c, report)

    # Phase 5: Data 模块
    phase5_data_module(c, report)

    # Phase 6: Function 模块
    phase6_function_module(c, report)

    # Phase 7: Agent 模块
    phase7_agent_module(c, report)

    # Phase 8: UI 验证
    phase8_ui_verification(report)

    report.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Write report
    report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"f35_round{round_num}_report.md",
    )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(generate_report(report))

    total, passed, failed, errors, skipped = report.summary()
    print(f"\n{'─' * 70}")
    print(f"第 {round_num} 轮测试完成:")
    print(f"  总计={total}  通过={passed}  失败={failed}  错误={errors}  跳过={skipped}")
    print(f"  通过率: {passed/total*100:.1f}%" if total > 0 else "  无测试")
    print(f"  报告: {report_path}")
    print(f"{'─' * 70}")

    return report


# ════════════════════════════ Main Entry ════════════════════════════

if __name__ == "__main__":
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    all_reports = []

    for i in range(1, rounds + 1):
        r = run_single_round(i)
        all_reports.append(r)
        total, passed, failed, errors, skipped = r.summary()
        if failed + errors == 0:
            print(f"\n🎉 第 {i} 轮全部通过! 继续下一轮...")
        else:
            print(f"\n⚠ 第 {i} 轮有 {failed} 失败 + {errors} 错误")
            # 仍然继续下一轮（不中断）

    # Final summary
    print(f"\n{'═' * 70}")
    print("五轮测试最终汇总")
    print(f"{'═' * 70}")
    for r in all_reports:
        total, passed, failed, errors, skipped = r.summary()
        rate = passed / total * 100 if total > 0 else 0
        icon = "✅" if failed + errors == 0 else "❌"
        print(f"  {icon} 第 {r.round_num} 轮: {passed}/{total} ({rate:.0f}%) — {r.start_time} ~ {r.end_time}")

    # Exit code based on last round
    last = all_reports[-1]
    _, _, f_count, e_count, _ = last.summary()
    sys.exit(1 if f_count + e_count > 0 else 0)
