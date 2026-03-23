"""
FastAPI dependency providers for VM services.

Each function in this module is a FastAPI dependency that constructs and
returns a fully configured service or repository instance, resolving its
own sub-dependencies automatically via :func:`fastapi.Depends`.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.core import get_db
from app.db.repositories.vm import VmAccessRepo, VmCmdRepo, VmQueryRepo
from app.services.proxmox.gateway import get_proxmox_gateway
from app.services.vm.access import VmAccessService
from app.services.vm.command import VmCommandService
from app.services.vm.query import VmQueryService
from app.services.vm.share import VmShareService


def get_vm_query_repo(db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)) -> VmQueryRepo:
    """
    FastAPI dependency that provides a :class:`~app.db.repositories.vm.VmQueryRepo`.

    :param db: Injected async database session.
    :param settings: Injected application settings.
    :returns: A new :class:`~app.db.repositories.vm.VmQueryRepo` bound to ``db``.
    :rtype: VmQueryRepo
    """
    return VmQueryRepo(db, dns_zone=settings.dns_zone.rstrip("."))


def get_vm_cmd_repo(db: AsyncSession = Depends(get_db)) -> VmCmdRepo:
    """
    FastAPI dependency that provides a :class:`~app.db.repositories.vm.VmCmdRepo`.

    :param db: Injected async database session.
    :returns: A new :class:`~app.db.repositories.vm.VmCmdRepo` bound to ``db``.
    :rtype: VmCmdRepo
    """
    return VmCmdRepo(db)


def get_vm_access_repo(db: AsyncSession = Depends(get_db)) -> VmAccessRepo:
    """
    FastAPI dependency that provides a :class:`~app.db.repositories.vm.VmAccessRepo`.

    :param db: Injected async database session.
    :returns: A new :class:`~app.db.repositories.vm.VmAccessRepo` bound to ``db``.
    :rtype: VmAccessRepo
    """
    return VmAccessRepo(db)


def get_vm_query_service(
    repo: VmQueryRepo = Depends(get_vm_query_repo),
    settings: Settings = Depends(get_settings),
) -> VmQueryService:
    """
    FastAPI dependency that provides a :class:`~app.services.vm.query.VmQueryService`.

    :param repo: Injected VM query repository.
    :param settings: Injected application settings.
    :returns: A configured :class:`~app.services.vm.query.VmQueryService`.
    :rtype: VmQueryService
    """
    return VmQueryService(repo=repo, settings=settings)


def get_vm_access_service(repo: VmAccessRepo = Depends(get_vm_access_repo)) -> VmAccessService:
    """
    FastAPI dependency that provides a :class:`~app.services.vm.access.VmAccessService`.

    :param repo: Injected VM access repository.
    :returns: A configured :class:`~app.services.vm.access.VmAccessService`.
    :rtype: VmAccessService
    """
    return VmAccessService(repo)


def get_vm_share_service(
    db: AsyncSession = Depends(get_db),
    repo: VmAccessRepo = Depends(get_vm_access_repo),
) -> VmShareService:
    """
    FastAPI dependency that provides a :class:`~app.services.vm.share.VmShareService`.

    :param db: Injected async database session.
    :param repo: Injected VM access repository.
    :returns: A configured :class:`~app.services.vm.share.VmShareService`.
    :rtype: VmShareService
    """
    return VmShareService(db=db, repo=repo)


def get_vm_command_service(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> VmCommandService:
    """
    FastAPI dependency that provides a :class:`~app.services.vm.command.VmCommandService`.

    :param db: Injected request-scoped async database session.
    :param settings: Injected application settings.
    :returns: A configured :class:`~app.services.vm.command.VmCommandService`.
    :rtype: VmCommandService
    """
    return VmCommandService(
        db=db,
        gateway=get_proxmox_gateway(),
        settings=settings,
    )
