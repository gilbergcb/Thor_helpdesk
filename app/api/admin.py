import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_admin, require_supervisor_or_admin
from app.core.audit import record_admin_action
from app.core.database import get_db
from app.core.security import (
    decrypt_secret,
    encrypt_secret,
    generate_reveal_token,
    get_password_hash,
    verify_totp_code,
)
from app.models.client import Client, ClientAccessCredential, ClientEmployee, EmployeeRole
from app.models.security import AdminAuditLog
from app.models.support import Agent
from app.models.whatsapp import WhatsAppGroup
from app.schemas.admin import (
    AdminAuditLogRead,
    AgentCreate,
    AgentRead,
    AgentUpdate,
    ClientAccessCredentialCreate,
    ClientAccessCredentialCreated,
    ClientAccessCredentialRead,
    ClientAccessCredentialReveal,
    ClientAccessCredentialRevealRequest,
    ClientCreate,
    ClientEmployeeCreate,
    ClientEmployeeRead,
    ClientEmployeeUpdate,
    ClientRead,
    ClientUpdate,
    EmployeeRoleCreate,
    EmployeeRoleRead,
    EmployeeRoleUpdate,
    WhatsAppGroupCreate,
    WhatsAppGroupRead,
    WhatsAppGroupUpdate,
)

# F-10: audit log dedicado para acessos ao vault de credenciais de cliente.
_vault_audit = logging.getLogger("security.vault")

router = APIRouter(prefix="/admin", tags=["admin"])


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message = str(exc.orig) if exc.orig else "Registro duplicado ou referência inválida"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=message[:240],
        ) from exc


@router.get("/clients", response_model=list[ClientRead])
def list_clients(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> list[Client]:
    return list(db.scalars(select(Client).order_by(Client.name)))


@router.post("/clients", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> Client:
    client = Client(**payload.model_dump())
    db.add(client)
    _commit_or_conflict(db)
    db.refresh(client)
    return client


@router.get("/whatsapp-groups", response_model=list[WhatsAppGroupRead])
def list_whatsapp_groups(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> list[WhatsAppGroup]:
    return list(
        db.scalars(
            select(WhatsAppGroup)
            .options(joinedload(WhatsAppGroup.client))
            .order_by(WhatsAppGroup.name)
        )
    )


@router.post(
    "/whatsapp-groups",
    response_model=WhatsAppGroupRead,
    status_code=status.HTTP_201_CREATED,
)
def create_whatsapp_group(
    payload: WhatsAppGroupCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> WhatsAppGroup:
    group = WhatsAppGroup(**payload.model_dump())
    db.add(group)
    _commit_or_conflict(db)
    return db.scalar(
        select(WhatsAppGroup)
        .where(WhatsAppGroup.id == group.id)
        .options(joinedload(WhatsAppGroup.client))
    )


@router.get("/agents", response_model=list[AgentRead])
def list_agents(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> list[Agent]:
    return list(db.scalars(select(Agent).order_by(Agent.name)))


@router.post("/agents", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> Agent:
    data = payload.model_dump()
    password = data.pop("password")
    agent = Agent(
        **data,
        password_hash=get_password_hash(password),
        must_change_password=True,
    )
    db.add(agent)
    _commit_or_conflict(db)
    db.refresh(agent)
    return agent


@router.get("/employee-roles", response_model=list[EmployeeRoleRead])
def list_employee_roles(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> list[EmployeeRole]:
    return list(db.scalars(select(EmployeeRole).order_by(EmployeeRole.name)))


@router.post(
    "/employee-roles",
    response_model=EmployeeRoleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_employee_role(
    payload: EmployeeRoleCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> EmployeeRole:
    role = EmployeeRole(**payload.model_dump())
    db.add(role)
    _commit_or_conflict(db)
    db.refresh(role)
    return role


@router.get("/client-employees", response_model=list[ClientEmployeeRead])
def list_client_employees(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> list[ClientEmployee]:
    return list(
        db.scalars(
            select(ClientEmployee)
            .options(
                joinedload(ClientEmployee.whatsapp_group).joinedload(WhatsAppGroup.client),
                joinedload(ClientEmployee.role),
            )
            .order_by(ClientEmployee.name)
        )
    )


@router.post(
    "/client-employees",
    response_model=ClientEmployeeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_client_employee(
    payload: ClientEmployeeCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> ClientEmployee:
    employee = ClientEmployee(**payload.model_dump())
    db.add(employee)
    _commit_or_conflict(db)
    return db.scalar(
        select(ClientEmployee)
        .where(ClientEmployee.id == employee.id)
        .options(
            joinedload(ClientEmployee.whatsapp_group).joinedload(WhatsAppGroup.client),
            joinedload(ClientEmployee.role),
        )
    )


def _get_or_404(db: Session, model, pk: int):
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não encontrado")
    return obj


@router.patch("/clients/{client_id}", response_model=ClientRead)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> Client:
    client = _get_or_404(db, Client, client_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, key, value)
    _commit_or_conflict(db)
    db.refresh(client)
    return client


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    request: Request,
    client_id: int,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[Agent, Depends(require_admin)],
) -> None:
    client = _get_or_404(db, Client, client_id)
    active_groups = db.scalar(
        select(func.count())
        .select_from(WhatsAppGroup)
        .where(WhatsAppGroup.client_id == client.id, WhatsAppGroup.is_active.is_(True))
    )
    if active_groups:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cliente possui grupos ativos. Desative ou exclua os grupos antes.",
        )
    db.delete(client)
    _commit_or_conflict(db)
    record_admin_action(
        db, actor=current, action="client.delete", target_type="client",
        target_id=client_id, request=request,
    )


@router.patch("/whatsapp-groups/{group_id}", response_model=WhatsAppGroupRead)
def update_whatsapp_group(
    group_id: int,
    payload: WhatsAppGroupUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> WhatsAppGroup:
    group = _get_or_404(db, WhatsAppGroup, group_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(group, key, value)
    _commit_or_conflict(db)
    return db.scalar(
        select(WhatsAppGroup)
        .where(WhatsAppGroup.id == group.id)
        .options(joinedload(WhatsAppGroup.client))
    )


@router.delete("/whatsapp-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_whatsapp_group(
    group_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> None:
    db.delete(_get_or_404(db, WhatsAppGroup, group_id))
    _commit_or_conflict(db)


@router.patch("/agents/{agent_id}", response_model=AgentRead)
def update_agent(
    request: Request,
    agent_id: int,
    payload: AgentUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[Agent, Depends(require_admin)],
) -> Agent:
    agent = _get_or_404(db, Agent, agent_id)
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    role_changed = "role" in data and data.get("role") != agent.role
    for key, value in data.items():
        setattr(agent, key, value)
    if password:
        agent.password_hash = get_password_hash(password)
        agent.must_change_password = True
    _commit_or_conflict(db)
    db.refresh(agent)
    # F-18: audit log com hash do payload (sem persistir a senha em claro).
    audit_payload = {k: v for k, v in data.items() if k != "password"}
    audit_payload["password_changed"] = bool(password)
    record_admin_action(
        db, actor=current,
        action="agent.update.role" if role_changed else "agent.update",
        target_type="agent", target_id=agent_id, request=request,
        payload=audit_payload,
    )
    return agent


@router.patch("/employee-roles/{role_id}", response_model=EmployeeRoleRead)
def update_employee_role(
    role_id: int,
    payload: EmployeeRoleUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> EmployeeRole:
    role = _get_or_404(db, EmployeeRole, role_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, key, value)
    _commit_or_conflict(db)
    db.refresh(role)
    return role


@router.patch("/client-employees/{employee_id}", response_model=ClientEmployeeRead)
def update_client_employee(
    employee_id: int,
    payload: ClientEmployeeUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> ClientEmployee:
    employee = _get_or_404(db, ClientEmployee, employee_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(employee, key, value)
    _commit_or_conflict(db)
    return db.scalar(
        select(ClientEmployee)
        .where(ClientEmployee.id == employee.id)
        .options(
            joinedload(ClientEmployee.whatsapp_group).joinedload(WhatsAppGroup.client),
            joinedload(ClientEmployee.role),
        )
    )


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    request: Request,
    agent_id: int,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[Agent, Depends(require_admin)],
) -> None:
    if agent_id == current.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível excluir o próprio usuário",
        )
    db.delete(_get_or_404(db, Agent, agent_id))
    _commit_or_conflict(db)
    record_admin_action(
        db, actor=current, action="agent.delete", target_type="agent",
        target_id=agent_id, request=request,
    )


@router.delete("/employee-roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee_role(
    role_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> None:
    db.delete(_get_or_404(db, EmployeeRole, role_id))
    _commit_or_conflict(db)


@router.delete("/client-employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_employee(
    employee_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
) -> None:
    db.delete(_get_or_404(db, ClientEmployee, employee_id))
    _commit_or_conflict(db)


@router.get("/client-access-credentials", response_model=list[ClientAccessCredentialRead])
def list_client_access_credentials(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_supervisor_or_admin)],
) -> list[ClientAccessCredential]:
    return list(
        db.scalars(
            select(ClientAccessCredential)
            .options(joinedload(ClientAccessCredential.client))
            .order_by(ClientAccessCredential.title)
        )
    )


@router.post(
    "/client-access-credentials",
    response_model=ClientAccessCredentialCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_client_access_credential(
    request: Request,
    payload: ClientAccessCredentialCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[Agent, Depends(require_admin)],
) -> ClientAccessCredentialCreated:
    credential = ClientAccessCredential(
        client_id=payload.client_id,
        title=payload.title,
        access_url=payload.access_url,
        username=payload.username,
        secret_encrypted=encrypt_secret(payload.secret),
        notes_encrypted=encrypt_secret(payload.notes),
        reveal_token_hash=get_password_hash(generate_reveal_token()),
        created_by_agent_id=current.id,
        is_active=payload.is_active,
    )
    db.add(credential)
    _commit_or_conflict(db)
    saved = db.scalar(
        select(ClientAccessCredential)
        .where(ClientAccessCredential.id == credential.id)
        .options(joinedload(ClientAccessCredential.client))
    )
    data = ClientAccessCredentialRead.model_validate(saved).model_dump()
    record_admin_action(
        db, actor=current, action="vault.credential.create",
        target_type="client_access_credential", target_id=credential.id,
        request=request,
        payload={"client_id": payload.client_id, "title": payload.title},
    )
    return ClientAccessCredentialCreated(**data, reveal_token=None)


@router.post(
    "/client-access-credentials/{credential_id}/reveal",
    response_model=ClientAccessCredentialReveal,
)
def reveal_client_access_credential(
    request: Request,
    credential_id: int,
    payload: ClientAccessCredentialRevealRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Agent, Depends(require_supervisor_or_admin)],
) -> ClientAccessCredentialReveal:
    credential = _get_or_404(db, ClientAccessCredential, credential_id)
    if not credential.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acesso inativo")
    totp_secret = decrypt_secret(actor.totp_secret_encrypted)
    if not actor.totp_enabled or not totp_secret:
        _vault_audit.warning(
            "vault.reveal.denied actor_id=%s actor_email=%s credential_id=%s "
            "client_id=%s ip=%s reason=totp_not_configured",
            actor.id, actor.email, credential.id, credential.client_id,
            request.client.host if request.client else None,
        )
        record_admin_action(
            db, actor=actor, action="vault.credential.reveal.denied",
            target_type="client_access_credential", target_id=credential.id,
            request=request, payload={"reason": "totp_not_configured"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Configure o 2FA no G.Autenticador antes de visualizar acessos",
        )
    if not verify_totp_code(totp_secret, payload.totp_code):
        _vault_audit.warning(
            "vault.reveal.denied actor_id=%s actor_email=%s credential_id=%s "
            "client_id=%s ip=%s reason=bad_totp_code",
            actor.id, actor.email, credential.id, credential.client_id,
            request.client.host if request.client else None,
        )
        record_admin_action(
            db, actor=actor, action="vault.credential.reveal.denied",
            target_type="client_access_credential", target_id=credential.id,
            request=request, payload={"reason": "bad_totp_code"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Codigo G.Autenticador invalido",
        )
    _vault_audit.info(
        "vault.reveal.ok actor_id=%s actor_email=%s actor_role=%s "
        "credential_id=%s client_id=%s ip=%s",
        actor.id, actor.email, actor.role.value,
        credential.id, credential.client_id,
        request.client.host if request.client else None,
    )
    record_admin_action(
        db, actor=actor, action="vault.credential.reveal",
        target_type="client_access_credential", target_id=credential.id,
        request=request,
    )
    return ClientAccessCredentialReveal(
        id=credential.id,
        title=credential.title,
        access_url=credential.access_url,
        username=credential.username,
        secret=decrypt_secret(credential.secret_encrypted) or "",
        notes=decrypt_secret(credential.notes_encrypted),
    )


@router.delete("/client-access-credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_access_credential(
    request: Request,
    credential_id: int,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[Agent, Depends(require_admin)],
) -> None:
    db.delete(_get_or_404(db, ClientAccessCredential, credential_id))
    _commit_or_conflict(db)
    record_admin_action(
        db, actor=current, action="vault.credential.delete",
        target_type="client_access_credential", target_id=credential_id,
        request=request,
    )


# ============================================================================
# F-18 — leitura paginada do admin_audit_log
# ============================================================================
@router.get("/audit-log", response_model=list[AdminAuditLogRead])
def list_admin_audit_log(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Agent, Depends(require_admin)],
    limit: int = 100,
    offset: int = 0,
    action: str | None = None,
    target_type: str | None = None,
) -> list[AdminAuditLog]:
    """Lista entradas do audit log mais recentes primeiro.
    Filtros opcionais por action e target_type.
    Limit hard-cap em 500 para evitar dump completo."""
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    stmt = select(AdminAuditLog).order_by(AdminAuditLog.id.desc())
    if action:
        stmt = stmt.where(AdminAuditLog.action == action)
    if target_type:
        stmt = stmt.where(AdminAuditLog.target_type == target_type)
    stmt = stmt.limit(safe_limit).offset(safe_offset)
    return list(db.scalars(stmt))
