"""Just-In-Time (JIT) user provisioning from OIDC claims."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.infra.rid import generate_rid
from lingshu.setting.auth.oidc_provider import OidcUserInfo
from lingshu.setting.models import User, UserTenantMembership
from lingshu.setting.repository.membership_repo import MembershipRepository
from lingshu.setting.repository.user_repo import UserRepository


class JitProvisioner:
    """Creates or updates local User records from OIDC claims."""

    async def provision_user(
        self,
        userinfo: OidcUserInfo,
        tenant_rid: str,
        session: AsyncSession,
    ) -> User:
        """Create a local User if not exists, or update display_name if exists.

        New users get the 'member' role and a membership in the given tenant.
        SSO users have a placeholder password_hash since they authenticate externally.
        """
        user_repo = UserRepository(session)
        membership_repo = MembershipRepository(session)

        # Look up by email (OIDC email claim is the key identifier)
        user = await user_repo.get_by_email(userinfo.email)

        if user is not None:
            # Existing user — update display_name from OIDC claims
            if user.display_name != userinfo.name:
                user = await user_repo.update_fields(user.rid, display_name=userinfo.name)

            # Ensure membership exists for this tenant
            membership = await membership_repo.get(user.rid, tenant_rid)
            if membership is None:
                await membership_repo.create(
                    UserTenantMembership(
                        user_rid=user.rid,
                        tenant_rid=tenant_rid,
                        role="member",
                        is_default=False,
                    )
                )
            return user

        # New user — create with SSO placeholder password
        user_rid = generate_rid("user")
        user = await user_repo.create(
            User(
                rid=user_rid,
                email=userinfo.email,
                display_name=userinfo.name,
                password_hash="SSO_MANAGED",  # Not used for SSO auth
            )
        )

        await membership_repo.create(
            UserTenantMembership(
                user_rid=user_rid,
                tenant_rid=tenant_rid,
                role="member",
                is_default=True,
            )
        )

        return user
