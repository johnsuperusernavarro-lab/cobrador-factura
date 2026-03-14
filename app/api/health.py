from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok", "app": "Cobrador de Facturas", "version": "2.0"}
