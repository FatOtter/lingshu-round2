"""First-run seed: create default tenant and admin user."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.config import Settings
from lingshu.infra.logging import get_logger
from lingshu.infra.rid import generate_rid
from lingshu.setting.auth.password import hash_password
from lingshu.setting.authz.enforcer import SYSTEM_ROLE_DEFINITIONS, PermissionEnforcer
from lingshu.setting.models import AuditLog, CustomRole, Tenant, User, UserTenantMembership

logger = get_logger("setting.seed")


async def run_seed(
    session: AsyncSession,
    settings: Settings,
    enforcer: PermissionEnforcer,
) -> None:
    """Create default tenant and admin user if database is empty.

    Also seeds RBAC policies and syncs the admin user role.
    """
    # Always seed policies on startup (idempotent)
    enforcer.seed_policies()

    result = await session.execute(select(User).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("seed_skip", reason="users table is not empty")

        # Even if data exists, sync existing admin roles to enforcer
        memberships_result = await session.execute(
            select(UserTenantMembership)
        )
        for membership in memberships_result.scalars().all():
            enforcer.sync_user_role(membership.user_rid, membership.role)

        # Seed system roles if they don't exist yet (upgrade path)
        await _seed_system_roles(session)

        # Sync custom role policies to Casbin
        custom_roles_result = await session.execute(select(CustomRole))
        for cr in custom_roles_result.scalars().all():
            if not cr.is_system:
                enforcer.add_custom_role_policies(cr.name, cr.permissions)

        return

    logger.info("seed_start", admin_email=settings.seed_admin_email)

    # Create default tenant
    tenant_rid = generate_rid("tenant")
    tenant = Tenant(
        rid=tenant_rid,
        display_name=settings.seed_tenant_name,
    )
    session.add(tenant)

    # Create admin user
    user_rid = generate_rid("user")
    user = User(
        rid=user_rid,
        email=settings.seed_admin_email,
        display_name="Admin",
        password_hash=hash_password(settings.seed_admin_password),
    )
    session.add(user)

    # Create membership
    membership = UserTenantMembership(
        user_rid=user_rid,
        tenant_rid=tenant_rid,
        role="admin",
        is_default=True,
    )
    session.add(membership)

    # Seed system roles
    await _seed_system_roles(session, tenant_rid)

    # Audit log
    audit = AuditLog(
        tenant_id=tenant_rid,
        module="setting",
        event_type="seed",
        user_id=user_rid,
        action=f"System initialized: admin={settings.seed_admin_email}, tenant={settings.seed_tenant_name}",
    )
    session.add(audit)

    await session.commit()

    # Sync admin user role to enforcer
    enforcer.sync_user_role(user_rid, "admin")

    logger.info(
        "seed_complete",
        admin_rid=user_rid,
        tenant_rid=tenant_rid,
    )


async def _seed_system_roles(
    session: AsyncSession,
    tenant_rid: str | None = None,
) -> None:
    """Create system CustomRole records (admin, member, viewer) if they don't exist.

    If tenant_rid is None, seeds for all existing tenants (upgrade path).
    """
    from lingshu.setting.models import Tenant

    if tenant_rid is not None:
        tenant_rids = [tenant_rid]
    else:
        result = await session.execute(select(Tenant.rid))
        tenant_rids = [row[0] for row in result.all()]

    for t_rid in tenant_rids:
        for role_name, role_def in SYSTEM_ROLE_DEFINITIONS.items():
            # Check if already exists
            existing = await session.execute(
                select(CustomRole).where(
                    CustomRole.tenant_id == t_rid,
                    CustomRole.name == role_name,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            role_rid = generate_rid("role")
            system_role = CustomRole(
                rid=role_rid,
                tenant_id=t_rid,
                name=role_def["name"],
                description=role_def["description"],
                permissions=role_def["permissions"],
                is_system=True,
            )
            session.add(system_role)

    await session.flush()
    logger.info("seed_system_roles_complete")
