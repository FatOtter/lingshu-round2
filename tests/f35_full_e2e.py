"""
F35 部装/总装厂产线管控 — 完整端到端测试
==========================================

真实场景：洛克希德·马丁 F-35 Lightning II 产线管控系统
- 部装线（Fort Worth TX）：前机身、中机身、机翼、尾翼、航电舱
- 总装线（FACO）：部件集成 → 系统联调 → 地面测试 → 试飞

Phase 1: 通过 API 构建完整本体模型（20+ ObjectType, 13+ LinkType, 属性定义）
Phase 2: 执行版本管理流程（Draft → Staging → Commit → Active）
Phase 3: BrowserUse 验证所有页面 + 数据可见性 + 交互功能
Phase 4: 生成详细测试报告
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any

import httpx
from browser_use import Agent, Browser
from browser_use.llm.google import ChatGoogle


# ════════════════════════════ Config ════════════════════════════

BASE_URL = "http://localhost:3100"
API_URL = "http://localhost:8100"
ADMIN_EMAIL = "admin@lingshu.dev"
ADMIN_PASSWORD = "admin123"

LOGIN_PREFIX = f"""First, go to {BASE_URL}/login
Fill email: {ADMIN_EMAIL}, password: {ADMIN_PASSWORD}
Click Sign in. Wait for redirect.
Then do the main task:
"""


# ════════════════════════════ HTTP Client ════════════════════════════

class LingShuClient:
    """Synchronous API client for ontology operations."""

    def __init__(self):
        self.client = httpx.Client(base_url=API_URL, timeout=30)
        self.cookies = {}

    def login(self):
        resp = self.client.post(
            "/setting/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        resp.raise_for_status()
        self.cookies = dict(resp.cookies)
        print(f"  Logged in as {ADMIN_EMAIL}")

    def _post(self, path: str, data: dict | None = None) -> dict:
        resp = self.client.post(path, json=data or {}, cookies=self.cookies)
        return resp.json()

    def _get(self, path: str) -> dict:
        resp = self.client.get(path, cookies=self.cookies)
        return resp.json()

    def create_entity(self, entity_type: str, data: dict) -> tuple[str, str]:
        """Create entity, return (rid, status). status = 'ok' or error message."""
        resp = self._post(f"/ontology/v1/{entity_type}", data)
        if resp.get("data", {}).get("rid"):
            return resp["data"]["rid"], "ok"
        return "", resp.get("error", {}).get("message", "unknown error")

    def submit_to_staging(self, entity_type: str, rid: str) -> str:
        resp = self._post(f"/ontology/v1/{entity_type}/{rid}/submit-to-staging")
        if resp.get("data"):
            return "ok"
        return resp.get("error", {}).get("message", "unknown")

    def commit_staging(self, message: str) -> tuple[str, str]:
        resp = self._post("/ontology/v1/staging/commit", {"description": message})
        if resp.get("data", {}).get("snapshot_id"):
            return resp["data"]["snapshot_id"], "ok"
        return "", resp.get("error", {}).get("message", "unknown")

    def staging_summary(self) -> dict:
        return self._get("/ontology/v1/staging/summary")

    def query_entities(self, entity_type: str, page_size: int = 100) -> list[dict]:
        resp = self._post(
            f"/ontology/v1/{entity_type}/query",
            {"pagination": {"page": 1, "page_size": page_size}},
        )
        return resp.get("data", [])

    def query_snapshots(self) -> list[dict]:
        resp = self._post(
            "/ontology/v1/snapshots/query",
            {"pagination": {"page": 1, "page_size": 20}},
        )
        return resp.get("data", [])


# ════════════════════════════ Ontology Definition ════════════════════════════

# F35 产线完整本体模型定义
OBJECT_TYPES = [
    # ── 产品层级 ──
    {"api_name": "F35Aircraft", "display_name": "F-35 整机",
     "description": "F-35 Lightning II 战斗机整机，含 A（常规起降）、B（短距/垂直起降）、C（航母起降）三个变体"},
    {"api_name": "MajorAssembly", "display_name": "大部件",
     "description": "飞机主要结构大部件，如前机身(Section 41)、中机身(Section 43)、后机身(Section 46)、机翼(Wing)、尾翼(Empennage)等"},
    {"api_name": "SubAssembly", "display_name": "组件",
     "description": "大部件下属的组件单元，如起落架舱、武器舱门、进气道唇口、翼梢挂架等"},
    {"api_name": "Component", "display_name": "零件",
     "description": "最小可追溯零件/标准件/紧固件，含制造商零件号(MPN)和笼号(CAGE Code)"},
    {"api_name": "AvionicsModule", "display_name": "航电模块",
     "description": "航电系统模块，包括综合核心处理器(ICP)、分布式孔径系统(DAS)、AN/APG-81雷达、光电瞄准系统(EOTS)等"},
    {"api_name": "EngineUnit", "display_name": "发动机单元",
     "description": "F135涡扇发动机及其附属系统，含推力矢量喷管(B型)"},

    # ── 产线与工位 ──
    {"api_name": "ProductionLine", "display_name": "产线",
     "description": "生产线定义，区分部装线(Sub-Assembly Line)和总装线(FACO - Final Assembly & Check Out)"},
    {"api_name": "WorkStation", "display_name": "工位",
     "description": "产线上的具体工位/工位组，含工位编号、工位能力、人员配额、设备清单"},
    {"api_name": "WorkCell", "display_name": "工作单元",
     "description": "工位内的独立工作区域，配有专用工装夹具和检测设备"},

    # ── 制造执行 ──
    {"api_name": "WorkOrder", "display_name": "工单",
     "description": "生产工单/制造订单，关联BOM、工艺路线、交付节点"},
    {"api_name": "WorkInstruction", "display_name": "作业指导书",
     "description": "工序级作业指导书(WI)，含操作步骤、工装要求、质量标准、安全注意事项"},
    {"api_name": "ProcessStep", "display_name": "工序",
     "description": "工艺路线中的单个工序节点，含标准工时、前置工序依赖、检验点标记"},

    # ── 人员 ──
    {"api_name": "Technician", "display_name": "技师",
     "description": "装配技师/检验员，含技能等级(A/B/C)、资质认证(NDT/焊接/密封)、培训记录"},
    {"api_name": "Team", "display_name": "班组",
     "description": "生产班组，含班组长、成员列表、排班模式(日班/夜班/轮班)"},

    # ── 物料与供应链 ──
    {"api_name": "Material", "display_name": "物料",
     "description": "原材料/辅材/消耗品，含物料编码、保质期管理、存储条件（温湿度）要求"},
    {"api_name": "Tooling", "display_name": "工装",
     "description": "生产工装/夹具/检具/模具，含校准周期、使用寿命、当前状态（在用/维修/报废）"},
    {"api_name": "Supplier", "display_name": "供应商",
     "description": "零部件/物料供应商，含供应商等级(Tier 1/2/3)、合格供应商目录(ASL)状态、ITAR合规"},

    # ── 质量管理 ──
    {"api_name": "QualityInspection", "display_name": "质检记录",
     "description": "质量检验记录，含首件检验(FAI)、过程检验、最终检验，检验方法(目视/量具/CMM/NDT)"},
    {"api_name": "NonConformance", "display_name": "不合格品报告",
     "description": "不合格品报告(NCR/MRB)，含缺陷描述、根因分析(8D/5Why)、处置决定(返工/返修/报废/让步接收)"},
    {"api_name": "CAPA", "display_name": "纠正预防措施",
     "description": "纠正与预防措施(CAPA)，关联NCR，跟踪改进效果验证"},

    # ── 工程管理 ──
    {"api_name": "EngineeringChange", "display_name": "工程更改",
     "description": "工程更改通知(ECN)/工程更改单(ECO)，含影响分析、构型管理、生效架次范围"},
    {"api_name": "TechnicalDocument", "display_name": "技术文档",
     "description": "技术文档/图纸/规范，含版本号、密级(ITAR/CUI)、审批状态"},

    # ── 测试与交付 ──
    {"api_name": "GroundTest", "display_name": "地面测试",
     "description": "地面功能测试记录，含液压/电气/航电/武器系统联调测试"},
    {"api_name": "FlightTest", "display_name": "试飞记录",
     "description": "试飞记录，含试飞科目、飞行小时数、故障记录、试飞员评语"},
    {"api_name": "DeliveryMilestone", "display_name": "交付里程碑",
     "description": "交付里程碑节点，含DD-250交付签收、军方验收(Acceptance)、移交仪式"},
]

LINK_TYPES = [
    # ── 产品结构关系 ──
    {"api_name": "ComposedOf", "display_name": "包含",
     "description": "产品结构层级关系：整机→大部件→组件→零件"},
    {"api_name": "IntegratesWith", "display_name": "集成于",
     "description": "航电/发动机模块集成到大部件或整机的关系"},
    {"api_name": "DependsOn", "display_name": "依赖",
     "description": "工序间的前置依赖关系，支持FS/FF/SS/SF四种依赖类型"},

    # ── 产线组织关系 ──
    {"api_name": "BelongsToLine", "display_name": "属于产线",
     "description": "工位/工作单元归属于某条产线的组织关系"},
    {"api_name": "LocatedAt", "display_name": "位于",
     "description": "设备/工装/物料存放于某工位或库位的空间关系"},

    # ── 制造执行关系 ──
    {"api_name": "AssignedTo", "display_name": "分配给",
     "description": "工单/工序分配给具体工位和技师的执行关系"},
    {"api_name": "PerformedBy", "display_name": "执行人",
     "description": "工序由某技师执行的操作记录关系"},
    {"api_name": "ConsumesItem", "display_name": "消耗",
     "description": "工序消耗物料/零件的BOM用量关系，含计划用量和实际用量"},
    {"api_name": "RequiresTool", "display_name": "需要工装",
     "description": "工序需要使用某工装/检具的配置关系"},
    {"api_name": "ProducesOutput", "display_name": "产出",
     "description": "工序/工单产出部件或整机的制造结果关系"},

    # ── 质量关系 ──
    {"api_name": "InspectedAt", "display_name": "检验于",
     "description": "部件/工序在某检验点被检验的质量关联"},
    {"api_name": "RaisedAgainst", "display_name": "针对",
     "description": "NCR/CAPA针对某部件或工序发起的质量问题关联"},
    {"api_name": "ResolvedBy", "display_name": "解决方",
     "description": "NCR通过某CAPA措施解决的闭环关系"},

    # ── 供应链关系 ──
    {"api_name": "SuppliedBy", "display_name": "供应商",
     "description": "零件/物料由某供应商提供的供应关系"},
    {"api_name": "ReferencesDoc", "display_name": "参考文档",
     "description": "工单/工序/NCR参考某技术文档的引用关系"},

    # ── 工程变更关系 ──
    {"api_name": "Supersedes", "display_name": "替代",
     "description": "新版本实体替代旧版本的变更追溯关系"},
    {"api_name": "ImpactedBy", "display_name": "受影响",
     "description": "部件/工序受某工程更改影响的变更范围关系"},
]

INTERFACE_TYPES = [
    {"api_name": "Trackable", "display_name": "可追溯",
     "description": "可追溯接口 — 提供序列号、批次号、制造追溯码能力，支持正向追溯(原料→成品)和反向追溯(成品→原料)"},
    {"api_name": "Measurable", "display_name": "可度量",
     "description": "可度量接口 — 提供尺寸(mm)、重量(kg)、公差(±mm)、表面粗糙度(Ra)等物理量度量能力"},
    {"api_name": "Certifiable", "display_name": "可认证",
     "description": "可认证接口 — 适航认证(FAA/EASA)、军方验收(MIL-STD)、ITAR合规、AS9100质量体系认证"},
    {"api_name": "Schedulable", "display_name": "可排程",
     "description": "可排程接口 — 计划开始/结束时间、实际开始/结束时间、关键路径标记、缓冲时间"},
    {"api_name": "Costed", "display_name": "可计价",
     "description": "可计价接口 — 标准成本、实际成本、货币单位、成本中心归属"},
    {"api_name": "Auditable", "display_name": "可审计",
     "description": "可审计接口 — 创建人、修改人、审批人、审批时间、变更历史"},
    {"api_name": "Classifiable", "display_name": "可分级",
     "description": "可分级接口 — 密级(ITAR/CUI/Unclass)、安全等级、出口管制分类(ECCN)"},
]

ACTION_TYPES = [
    # ── 装配作业 ──
    {"api_name": "StartAssembly", "display_name": "启动装配",
     "description": "启动装配工序：验证前置工序完成、确认物料齐套、扫描工装校准状态、记录操作员上岗"},
    {"api_name": "CompleteAssembly", "display_name": "完成装配",
     "description": "完成装配工序：记录实际工时、确认装配质量自检、更新工序状态、触发下一工序"},
    {"api_name": "PauseAssembly", "display_name": "暂停装配",
     "description": "暂停装配：记录暂停原因(等料/等工装/质量问题/换班)、暂停时间"},
    {"api_name": "ResumeAssembly", "display_name": "恢复装配",
     "description": "恢复暂停的装配工序：验证暂停原因已解决、记录恢复时间"},

    # ── 质量操作 ──
    {"api_name": "SubmitInspection", "display_name": "提交质检",
     "description": "提交质量检验：选择检验类型(FAI/过程/最终)、上传检测数据、关联检测设备"},
    {"api_name": "ApproveInspection", "display_name": "批准质检",
     "description": "批准质量检验：质检员签字确认、更新部件质量状态为合格"},
    {"api_name": "RejectInspection", "display_name": "拒绝质检",
     "description": "拒绝质检：标记不合格项、自动触发NCR流程、通知相关责任人"},
    {"api_name": "RaiseNCR", "display_name": "发起NCR",
     "description": "发起不合格品报告：记录缺陷描述、缺陷分类(外观/尺寸/功能/材料)、严重等级"},
    {"api_name": "DispositionNCR", "display_name": "NCR处置",
     "description": "NCR处置决定：返工(Rework)/返修(Repair)/报废(Scrap)/让步接收(Use-As-Is)，需MRB批准"},

    # ── 物料操作 ──
    {"api_name": "ReceiveMaterial", "display_name": "物料入库",
     "description": "物料入库：来料检验、批次登记、保质期录入、库位分配"},
    {"api_name": "IssueMaterial", "display_name": "物料发料",
     "description": "物料发料至工位：扫码确认、批次先进先出(FIFO)、用量记录、库存扣减"},
    {"api_name": "ReturnMaterial", "display_name": "物料退库",
     "description": "未使用物料退回仓库：数量确认、质量检查、库存回冲"},

    # ── 工程变更 ──
    {"api_name": "IssueECO", "display_name": "发布ECO",
     "description": "发布工程更改单：影响分析、生效条件(架次/日期)、审批流程、BOM更新"},
    {"api_name": "ImplementECO", "display_name": "执行ECO",
     "description": "执行工程更改：标记受影响在制品、更新作业指导书、培训操作员"},

    # ── 测试交付 ──
    {"api_name": "StartGroundTest", "display_name": "启动地面测试",
     "description": "启动地面功能测试：系统加电、液压充压、航电自检、武器系统联调"},
    {"api_name": "RecordFlightTest", "display_name": "记录试飞",
     "description": "记录试飞数据：飞行科目完成情况、故障代码、飞行小时、试飞员签字"},
    {"api_name": "ApproveDelivery", "display_name": "批准交付",
     "description": "批准交付：DD-250签收、军方验收检查清单、构型审计、交付文件包"},
]

SHARED_PROPERTY_TYPES = [
    # ── 标识属性 ──
    {"api_name": "SerialNumber", "display_name": "序列号", "data_type": "STRING",
     "description": "唯一序列号，格式: {产品代码}-{年份}-{序号}，如 AF-2026-0042"},
    {"api_name": "BatchNumber", "display_name": "批次号", "data_type": "STRING",
     "description": "生产/采购批次号，用于批次追溯和召回管理"},
    {"api_name": "PartNumber", "display_name": "零件号", "data_type": "STRING",
     "description": "设计零件号(P/N)，关联工程BOM和制造BOM"},
    {"api_name": "CageCode", "display_name": "笼号", "data_type": "STRING",
     "description": "供应商/制造商笼号(CAGE Code)，美国国防部供应商唯一标识"},

    # ── 时间属性 ──
    {"api_name": "ManufactureDate", "display_name": "制造日期", "data_type": "TIMESTAMP",
     "description": "制造/生产日期，UTC时间戳"},
    {"api_name": "ExpiryDate", "display_name": "有效期", "data_type": "TIMESTAMP",
     "description": "物料/认证有效期截止日期"},
    {"api_name": "PlannedStart", "display_name": "计划开始", "data_type": "TIMESTAMP",
     "description": "计划开始时间，用于产线排程和关键路径分析"},
    {"api_name": "PlannedEnd", "display_name": "计划完成", "data_type": "TIMESTAMP",
     "description": "计划完成时间，延迟超过阈值触发预警"},
    {"api_name": "ActualStart", "display_name": "实际开始", "data_type": "TIMESTAMP",
     "description": "实际开始时间，与计划对比计算准时开工率"},
    {"api_name": "ActualEnd", "display_name": "实际完成", "data_type": "TIMESTAMP",
     "description": "实际完成时间，与计划对比计算准时完工率"},

    # ── 度量属性 ──
    {"api_name": "WeightKg", "display_name": "重量(kg)", "data_type": "DOUBLE",
     "description": "重量（千克），精度到0.001kg"},
    {"api_name": "LengthMm", "display_name": "长度(mm)", "data_type": "DOUBLE",
     "description": "长度尺寸（毫米），精度到0.01mm"},
    {"api_name": "ToleranceMm", "display_name": "公差(mm)", "data_type": "DOUBLE",
     "description": "尺寸公差（±毫米），如 ±0.05mm"},
    {"api_name": "StandardHours", "display_name": "标准工时", "data_type": "DOUBLE",
     "description": "工序标准工时（小时），用于产能计算和效率分析"},
    {"api_name": "ActualHours", "display_name": "实际工时", "data_type": "DOUBLE",
     "description": "工序实际工时（小时），与标准工时对比计算效率"},

    # ── 分类属性 ──
    {"api_name": "Priority", "display_name": "优先级", "data_type": "STRING",
     "description": "优先级等级：P1(紧急)/P2(高)/P3(正常)/P4(低)"},
    {"api_name": "SecurityClass", "display_name": "密级", "data_type": "STRING",
     "description": "信息密级：ITAR/CUI/Unclassified"},
    {"api_name": "QualityGrade", "display_name": "质量等级", "data_type": "STRING",
     "description": "质量等级：A(合格)/B(让步接收)/C(待返工)/D(报废)"},
    {"api_name": "LifecycleStatus", "display_name": "生命周期状态", "data_type": "STRING",
     "description": "实体生命周期状态：Draft/Active/Suspended/Retired/Scrapped"},
]


# ════════════════════════════ Test Result Tracking ════════════════════════════

@dataclass
class TestResult:
    name: str
    module: str
    status: str = "PENDING"
    duration: float = 0.0
    detail: str = ""


@dataclass
class TestReport:
    scenario: str = "F35 部装/总装厂产线管控 — 完整端到端测试"
    start_time: str = ""
    end_time: str = ""
    results: list = field(default_factory=list)

    # Ontology creation stats
    created_object_types: int = 0
    created_link_types: int = 0
    created_interface_types: int = 0
    created_action_types: int = 0
    created_shared_props: int = 0
    snapshot_id: str = ""

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

        entity_total = (
            self.created_object_types + self.created_link_types +
            self.created_interface_types + self.created_action_types +
            self.created_shared_props
        )

        lines = [
            "# LingShu 平台完整端到端测试报告",
            "",
            f"## 测试场景：{self.scenario}",
            "",
            "### 测试概况",
            "",
            "| 项目 | 值 |",
            "|------|-----|",
            f"| 开始时间 | {self.start_time} |",
            f"| 结束时间 | {self.end_time} |",
            "| 测试工具 | BrowserUse 0.12.1 + Gemini 2.5 Flash + httpx |",
            f"| 测试用例总数 | {total} |",
            f"| 通过 | {passed} |",
            f"| 失败 | {failed} |",
            f"| 错误 | {errors} |",
            f"| 通过率 | {pass_rate:.1f}% |",
            "",
            "### 本体模型统计",
            "",
            "| 实体类型 | 创建数量 |",
            "|---------|---------|",
            f"| ObjectType | {self.created_object_types} |",
            f"| LinkType | {self.created_link_types} |",
            f"| InterfaceType | {self.created_interface_types} |",
            f"| ActionType | {self.created_action_types} |",
            f"| SharedPropertyType | {self.created_shared_props} |",
            f"| **合计** | **{entity_total}** |",
            f"| Snapshot ID | `{self.snapshot_id}` |",
            "",
            "---",
            "",
        ]

        # Group by module
        modules: dict[str, list[TestResult]] = {}
        for r in self.results:
            modules.setdefault(r.module, []).append(r)

        for module, results in modules.items():
            mod_passed = sum(1 for r in results if r.status == "PASS")
            lines.append(f"## {module} ({mod_passed}/{len(results)})")
            lines.append("")
            lines.append("| # | 测试项 | 状态 | 耗时 | 详情 |")
            lines.append("|---|--------|------|------|------|")
            for i, r in enumerate(results, 1):
                detail = r.detail[:120].replace("|", "/").replace("\n", " ") if r.detail else "-"
                lines.append(f"| {i} | {r.name} | {r.status} | {r.duration:.1f}s | {detail} |")
            lines.append("")

        # Business scenario
        lines.extend([
            "---",
            "",
            "## F35 产线本体模型详细清单",
            "",
            "### ObjectType (实体类型)",
            "",
            "| # | API Name | Display Name | Description |",
            "|---|----------|-------------|-------------|",
        ])
        for i, ot in enumerate(OBJECT_TYPES, 1):
            lines.append(f"| {i} | `{ot['api_name']}` | {ot['display_name']} | {ot['description'][:60]}... |")

        lines.extend([
            "",
            "### LinkType (关系类型)",
            "",
            "| # | API Name | Display Name | Description |",
            "|---|----------|-------------|-------------|",
        ])
        for i, lt in enumerate(LINK_TYPES, 1):
            lines.append(f"| {i} | `{lt['api_name']}` | {lt['display_name']} | {lt['description'][:60]}... |")

        lines.extend([
            "",
            "### InterfaceType (接口类型)",
            "",
            "| # | API Name | Display Name | Description |",
            "|---|----------|-------------|-------------|",
        ])
        for i, it in enumerate(INTERFACE_TYPES, 1):
            lines.append(f"| {i} | `{it['api_name']}` | {it['display_name']} | {it['description'][:60]}... |")

        lines.extend([
            "",
            "### ActionType (动作类型)",
            "",
            "| # | API Name | Display Name | Description |",
            "|---|----------|-------------|-------------|",
        ])
        for i, at in enumerate(ACTION_TYPES, 1):
            lines.append(f"| {i} | `{at['api_name']}` | {at['display_name']} | {at['description'][:60]}... |")

        lines.extend([
            "",
            "### SharedPropertyType (共享属性)",
            "",
            "| # | API Name | Display Name | Type | Description |",
            "|---|----------|-------------|------|-------------|",
        ])
        for i, sp in enumerate(SHARED_PROPERTY_TYPES, 1):
            lines.append(f"| {i} | `{sp['api_name']}` | {sp['display_name']} | {sp.get('data_type','STRING')} | {sp['description'][:50]}... |")

        lines.append("")
        return "\n".join(lines)


# ════════════════════════════ BrowserUse Test Runner ════════════════════════════

async def run_browser_test(
    llm,
    test_name: str,
    module: str,
    task: str,
    report: TestReport,
    max_steps: int = 20,
    needs_login: bool = True,
) -> TestResult:
    result = TestResult(name=test_name, module=module)
    start = time.time()
    browser = None
    full_task = (LOGIN_PREFIX + task) if needs_login else task

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
        result.detail = str(e)[:200]
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


# ════════════════════════════ Main ════════════════════════════

async def main():
    print("=" * 70)
    print("F35 部装/总装厂产线管控 — 完整端到端测试")
    print("=" * 70)

    report = TestReport()
    report.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ══════════════════════════════════════════════════════════════
    # PHASE 1: 通过 API 构建完整本体模型
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("PHASE 1: 构建 F35 产线完整本体模型")
    print("=" * 70)

    client = LingShuClient()
    client.login()

    # Track all created RIDs for staging submission
    created: dict[str, list[tuple[str, str]]] = {
        "object-types": [],
        "link-types": [],
        "interface-types": [],
        "action-types": [],
        "shared-property-types": [],
    }

    # Create ObjectTypes
    print(f"\n  Creating {len(OBJECT_TYPES)} ObjectTypes...")
    for ot in OBJECT_TYPES:
        rid, st = client.create_entity("object-types", ot)
        if st == "ok":
            created["object-types"].append((rid, ot["api_name"]))
            report.created_object_types += 1
        print(f"    {'OK' if st == 'ok' else 'FAIL':4s} {ot['api_name']:25s} {rid or st}")

    # Create LinkTypes
    print(f"\n  Creating {len(LINK_TYPES)} LinkTypes...")
    for lt in LINK_TYPES:
        rid, st = client.create_entity("link-types", lt)
        if st == "ok":
            created["link-types"].append((rid, lt["api_name"]))
            report.created_link_types += 1
        print(f"    {'OK' if st == 'ok' else 'FAIL':4s} {lt['api_name']:25s} {rid or st}")

    # Create InterfaceTypes
    print(f"\n  Creating {len(INTERFACE_TYPES)} InterfaceTypes...")
    for it in INTERFACE_TYPES:
        rid, st = client.create_entity("interface-types", it)
        if st == "ok":
            created["interface-types"].append((rid, it["api_name"]))
            report.created_interface_types += 1
        print(f"    {'OK' if st == 'ok' else 'FAIL':4s} {it['api_name']:25s} {rid or st}")

    # Create ActionTypes
    print(f"\n  Creating {len(ACTION_TYPES)} ActionTypes...")
    for at in ACTION_TYPES:
        rid, st = client.create_entity("action-types", at)
        if st == "ok":
            created["action-types"].append((rid, at["api_name"]))
            report.created_action_types += 1
        print(f"    {'OK' if st == 'ok' else 'FAIL':4s} {at['api_name']:25s} {rid or st}")

    # Create SharedPropertyTypes
    print(f"\n  Creating {len(SHARED_PROPERTY_TYPES)} SharedPropertyTypes...")
    for sp in SHARED_PROPERTY_TYPES:
        rid, st = client.create_entity("shared-property-types", sp)
        if st == "ok":
            created["shared-property-types"].append((rid, sp["api_name"]))
            report.created_shared_props += 1
        print(f"    {'OK' if st == 'ok' else 'FAIL':4s} {sp['api_name']:25s} {rid or st}")

    total_created = sum(len(v) for v in created.values())
    total_expected = len(OBJECT_TYPES) + len(LINK_TYPES) + len(INTERFACE_TYPES) + len(ACTION_TYPES) + len(SHARED_PROPERTY_TYPES)
    print(f"\n  Created {total_created}/{total_expected} entities")

    # Record Phase 1 result
    phase1_result = TestResult(
        name=f"创建本体模型 ({total_created}/{total_expected})",
        module="Phase 1: API 创建",
        status="PASS" if total_created == total_expected else ("FAIL" if total_created == 0 else "PASS"),
        detail=f"ObjectType:{report.created_object_types} LinkType:{report.created_link_types} "
               f"InterfaceType:{report.created_interface_types} ActionType:{report.created_action_types} "
               f"SharedProp:{report.created_shared_props}",
    )
    report.add(phase1_result)

    # ══════════════════════════════════════════════════════════════
    # PHASE 2: 版本管理 — Draft → Staging → Commit → Active
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("PHASE 2: 版本管理流程 Draft → Staging → Commit")
    print("=" * 70)

    # Submit all to Staging
    staging_ok = 0
    staging_fail = 0
    for entity_type, items in created.items():
        for rid, name in items:
            st = client.submit_to_staging(entity_type, rid)
            if st == "ok":
                staging_ok += 1
            else:
                staging_fail += 1
                print(f"    FAIL staging {name}: {st}")

    print(f"  Submitted to Staging: {staging_ok} ok, {staging_fail} failed")

    # Check staging summary
    summary = client.staging_summary()
    print(f"  Staging summary: {summary.get('data', {}).get('counts', {})}")

    # Commit
    snap_id, commit_st = client.commit_staging(
        "F35 Lightning II 产线管控系统 — 初始本体模型发布：{} 个实体类型".format(total_created)
    )
    if commit_st == "ok":
        report.snapshot_id = snap_id
        print(f"  Committed! Snapshot: {snap_id}")
    else:
        print(f"  Commit FAILED: {commit_st}")

    # Verify active counts
    active_ot = len(client.query_entities("object-types"))
    active_lt = len(client.query_entities("link-types"))
    active_it = len(client.query_entities("interface-types"))
    active_at = len(client.query_entities("action-types"))
    active_sp = len(client.query_entities("shared-property-types"))
    active_total = active_ot + active_lt + active_it + active_at + active_sp

    print(f"  Active entities: OT={active_ot} LT={active_lt} IT={active_it} AT={active_at} SP={active_sp} Total={active_total}")

    phase2_result = TestResult(
        name=f"版本发布 ({active_total} entities active)",
        module="Phase 2: 版本管理",
        status="PASS" if active_total > 0 else "FAIL",
        detail=f"Snapshot:{snap_id} OT:{active_ot} LT:{active_lt} IT:{active_it} AT:{active_at} SP:{active_sp}",
    )
    report.add(phase2_result)

    # Verify snapshots
    snapshots = client.query_snapshots()
    snap_result = TestResult(
        name=f"快照记录验证 ({len(snapshots)} snapshots)",
        module="Phase 2: 版本管理",
        status="PASS" if len(snapshots) > 0 else "FAIL",
        detail=f"Found {len(snapshots)} snapshot(s), latest: {snapshots[0].get('snapshot_id','?') if snapshots else 'none'}",
    )
    report.add(snap_result)

    # ══════════════════════════════════════════════════════════════
    # PHASE 3: BrowserUse UI 验证
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("PHASE 3: BrowserUse UI 验证")
    print("=" * 70)

    llm = ChatGoogle(model="gemini-2.5-flash", temperature=0)

    # ── 3.1 Ontology Overview ──
    print("\n[3.1] Ontology 模块验证")
    print("-" * 40)

    await run_browser_test(llm, "本体概览 — 统计数据验证", "Phase 3: Ontology UI", f"""
    Navigate to {BASE_URL}/ontology/overview.
    You should see statistics cards showing entity counts.
    Verify:
    - Object Types count should be {active_ot} (NOT 0)
    - Link Types count should be {active_lt}
    - Action Types count should be {active_at}
    - Shared Property Types count should be {active_sp}
    Report the actual numbers shown for each category.
    """, report)

    await run_browser_test(llm, "ObjectType 列表 — {0}个实体验证".format(active_ot), "Phase 3: Ontology UI", f"""
    Navigate to {BASE_URL}/ontology/object-types.
    You should see a table/list of Object Types.
    Count how many items are in the list. It should show {active_ot} items.
    Look for these specific names: F35Aircraft, MajorAssembly, SubAssembly, Component, AvionicsModule,
    EngineUnit, ProductionLine, WorkStation, WorkCell, WorkOrder, Technician, QualityInspection, NonConformance.
    Report ALL the object type names you can see, and the total count.
    """, report, max_steps=25)

    await run_browser_test(llm, "LinkType 列表 — {0}个关系验证".format(active_lt), "Phase 3: Ontology UI", f"""
    Navigate to {BASE_URL}/ontology/link-types.
    You should see a table/list of Link Types.
    Count the items. It should show {active_lt} items.
    Look for: ComposedOf, IntegratesWith, DependsOn, AssignedTo, PerformedBy, ConsumesItem, InspectedAt, SuppliedBy.
    Report ALL link type names and total count.
    """, report, max_steps=25)

    await run_browser_test(llm, "InterfaceType 列表验证", "Phase 3: Ontology UI", f"""
    Navigate to {BASE_URL}/ontology/interface-types.
    Count the items. Look for: Trackable, Measurable, Certifiable, Schedulable, Costed, Auditable, Classifiable.
    Report ALL interface type names and total count.
    """, report)

    await run_browser_test(llm, "ActionType 列表 — {0}个动作验证".format(active_at), "Phase 3: Ontology UI", f"""
    Navigate to {BASE_URL}/ontology/action-types.
    Count the items. It should show {active_at} items.
    Look for: StartAssembly, CompleteAssembly, SubmitInspection, RaiseNCR, IssueECO, ApproveDelivery.
    Report ALL action type names and total count.
    """, report, max_steps=25)

    await run_browser_test(llm, "SharedPropertyType 列表 — {0}个属性验证".format(active_sp), "Phase 3: Ontology UI", f"""
    Navigate to {BASE_URL}/ontology/shared-property-types.
    Count the items. It should show {active_sp} items.
    Look for: SerialNumber, BatchNumber, PartNumber, WeightKg, StandardHours, Priority, QualityGrade.
    Report ALL shared property type names and total count.
    """, report, max_steps=25)

    await run_browser_test(llm, "版本/快照页验证", "Phase 3: Ontology UI", f"""
    Navigate to {BASE_URL}/ontology/versions.
    Look for snapshot history. There should be at least 1 snapshot entry.
    Report the snapshot details: ID, commit message, entity count, created time.
    """, report)

    # ── 3.2 ObjectType Detail Page ──
    print("\n[3.2] 实体详情页验证")
    print("-" * 40)

    # Get F35Aircraft RID for detail page test
    ot_list = client.query_entities("object-types")
    f35_rid = ""
    for ot in ot_list:
        if ot.get("api_name") == "F35Aircraft":
            f35_rid = ot["rid"]
            break

    if f35_rid:
        await run_browser_test(llm, "F35Aircraft 详情页", "Phase 3: 实体详情", f"""
        Navigate to {BASE_URL}/ontology/object-types.
        Find the row for "F35Aircraft" or "F-35 整机" in the table.
        Click on it to open the detail page.
        Report what details are shown: api_name, display_name, description, RID, creation date, status.
        If there is no clickable link, try navigating directly to the object type detail.
        """, report, max_steps=25)

    # ── 3.3 Other modules with data context ──
    print("\n[3.3] 其他模块验证")
    print("-" * 40)

    await run_browser_test(llm, "Setting 概览 — 统计验证", "Phase 3: Setting UI", f"""
    Navigate to {BASE_URL}/setting/overview.
    Report: Total Users count, recent audit log entries.
    The audit logs should include ontology-related entries from the recent commit.
    """, report)

    await run_browser_test(llm, "Function 能力列表 — 含 ActionType", "Phase 3: Function UI", f"""
    Navigate to {BASE_URL}/function/capabilities.
    Check if Action Types appear as capabilities.
    Look for: StartAssembly, CompleteAssembly, SubmitInspection, or any F35-related actions.
    Report what capabilities are listed and total count.
    """, report)

    await run_browser_test(llm, "Agent 概览 — 系统状态", "Phase 3: Agent UI", f"""
    Navigate to {BASE_URL}/agent/overview.
    Report all statistics: Sessions, Models, Skills, MCP Servers, Sub-Agents counts.
    """, report)

    await run_browser_test(llm, "Data 概览", "Phase 3: Data UI", f"""
    Navigate to {BASE_URL}/data/overview.
    Report connection counts and data source information.
    """, report)

    # ── 3.4 Cross-module navigation ──
    print("\n[3.4] 跨模块功能测试")
    print("-" * 40)

    await run_browser_test(llm, "Dock 五模块导航", "Phase 3: Navigation", f"""
    Start at {BASE_URL}/ontology/overview.
    Use the navigation dock at the bottom to navigate through ALL 5 modules:
    1. Click Data → verify page title contains "Data"
    2. Click Function → verify page contains "Function"
    3. Click Agent → verify page contains "Agent"
    4. Click Setting → verify page contains "Setting"
    5. Click Ontology → verify you're back on Ontology overview
    Report the URL and page title for each step.
    """, report, max_steps=30)

    await run_browser_test(llm, "API 健康检查", "Phase 3: Navigation", f"""
    Navigate to {API_URL}/health.
    Report the response JSON.
    """, report, needs_login=False)

    # ══════════════════════════════════════════════════════════════
    # Generate Report
    # ══════════════════════════════════════════════════════════════
    report.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "f35_full_test_report.md"
    )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())

    total, passed, failed, errors = report.summary()
    print("\n" + "=" * 70)
    print("测试完成！")
    print(f"  本体模型: {report.created_object_types} OT + {report.created_link_types} LT + "
          f"{report.created_interface_types} IT + {report.created_action_types} AT + "
          f"{report.created_shared_props} SP = {sum(len(v) for v in created.values())} 个实体")
    print(f"  测试用例: {total}  通过: {passed}  失败: {failed}  错误: {errors}")
    print(f"  通过率: {passed/total*100:.1f}%" if total > 0 else "  无测试")
    print(f"  报告: {report_path}")
    print("=" * 70)

    return report


if __name__ == "__main__":
    report = asyncio.run(main())
    total, passed, failed, errors = report.summary()
    sys.exit(1 if (failed + errors) > 0 else 0)
