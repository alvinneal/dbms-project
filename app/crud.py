import inspect
from typing import Annotated, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import create_model
from sqlalchemy import String, func, or_, select
from sqlalchemy.orm import Session

from .auth import require_admin
from .deps import DB, Page, get_or_404
from .schemas import Strict

# hook(db, obj, changes) runs before an update/delete is applied; raise HTTPException to refuse
Hook = Callable[[Session, object, dict], None]


def crud(path: str, model, schema_in, schema_out, *,
         read: Callable | None = require_admin,
         filters: dict[str, type] | None = None,
         before_update: Hook | None = None,
         before_delete: Hook | None = None) -> APIRouter:
    """List / get / create / patch / delete for a master table.

    Who may call: reading needs the `read` dependency (None = anyone, even logged out;
    current_user = any logged-in user; require_admin = staff); writing is always staff only.
    List: ?limit=&offset=&q=<text search> plus an equality filter per entry of `filters`;
    the number of matching rows (ignoring limit/offset) is in the X-Total-Count header.
    """
    reading = [Depends(read)] if read else []
    writing = [Depends(require_admin)]
    pk = model.__mapper__.primary_key[0]
    filters = filters or {}
    text_cols = [c for c in model.__table__.columns if isinstance(c.type, String)]
    # same fields as schema_in, all optional, for PATCH
    schema_patch = create_model(
        f"{schema_in.__name__}Patch", __base__=Strict,
        **{n: (Annotated[(f.annotation | None, *f.metadata)] if f.metadata else f.annotation | None, None)
           for n, f in schema_in.model_fields.items()},
    )
    router = APIRouter(prefix=f"/{path}", tags=[path])

    def list_all(response: Response, db: DB, page: Annotated[Page, Depends()],
                 q: str | None = Query(None, max_length=100, description="search text columns"), **eq):
        stmt = select(model)
        for name, value in eq.items():
            if value is not None:
                stmt = stmt.where(getattr(model, name) == value)
        if q and q.strip():
            # % and _ typed by the user are plain characters, not wildcards
            term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(or_(*(c.ilike(f"%{term}%", escape="\\") for c in text_cols)))
        response.headers["X-Total-Count"] = str(db.scalar(select(func.count()).select_from(stmt.subquery())))
        return db.scalars(stmt.order_by(pk).limit(page.limit).offset(page.offset)).unique().all()

    # expose the filters as real query parameters so they show up in /docs
    sig = inspect.signature(list_all)
    params = [p for p in sig.parameters.values() if p.kind is not p.VAR_KEYWORD]
    params += [inspect.Parameter(n, inspect.Parameter.KEYWORD_ONLY, default=Query(None), annotation=t | None)
               for n, t in filters.items()]
    list_all.__signature__ = sig.replace(parameters=params)
    router.add_api_route("", list_all, methods=["GET"], response_model=list[schema_out],
                         summary=f"List {path}", dependencies=reading)

    @router.get("/{item_id}", response_model=schema_out, dependencies=reading)
    def get_one(item_id: int, db: DB):
        return get_or_404(db, model, item_id)

    @router.post("", response_model=schema_out, status_code=201, dependencies=writing)
    def create(body: schema_in, db: DB):
        obj = model(**body.model_dump(exclude_none=True))
        db.add(obj)
        db.commit()
        return obj

    @router.patch("/{item_id}", response_model=schema_out, dependencies=writing)
    def patch(item_id: int, body: schema_patch, db: DB):
        obj = get_or_404(db, model, item_id, lock=True)
        # only what actually changes
        changes = {k: v for k, v in body.model_dump(exclude_none=True).items() if getattr(obj, k) != v}
        if changes and before_update:
            before_update(db, obj, changes)
        for k, v in changes.items():
            setattr(obj, k, v)
        db.commit()
        return obj

    @router.delete("/{item_id}", status_code=204, dependencies=writing)
    def delete(item_id: int, db: DB):
        obj = get_or_404(db, model, item_id, lock=True)
        if before_delete:
            before_delete(db, obj, {})
        db.delete(obj)
        db.commit()

    return router


def refuse(message: str):
    raise HTTPException(409, message)
