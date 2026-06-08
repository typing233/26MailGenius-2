import contextvars
import uuid

_tenant_id_ctx: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar("tenant_id", default=None)


def get_current_tenant_id() -> uuid.UUID:
    tid = _tenant_id_ctx.get()
    if tid is None:
        raise RuntimeError("Tenant context not set")
    return tid


def set_current_tenant_id(tid: uuid.UUID) -> contextvars.Token:
    return _tenant_id_ctx.set(tid)
