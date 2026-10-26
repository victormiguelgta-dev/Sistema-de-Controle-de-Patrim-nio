from sqlalchemy.orm import Session

from ..models import Auditoria


def registrar(db: Session, entidade: str, entidade_id: int, acao: str,
              antes: dict | None = None, depois: dict | None = None) -> None:
    db.add(Auditoria(entidade=entidade, entidade_id=entidade_id, acao=acao,
                     antes=antes, depois=depois))
