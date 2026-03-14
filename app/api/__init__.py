from fastapi import APIRouter
from app.api import health
from app.api import cobros
from app.api import config_api
from app.api import plantillas_api
from app.api import contifico_api
from app.api import pdfs_api

router = APIRouter()
router.include_router(health.router,         tags=["sistema"])
router.include_router(cobros.router,         tags=["cartera"])
router.include_router(config_api.router,     tags=["config"])
router.include_router(plantillas_api.router, tags=["plantillas"])
router.include_router(contifico_api.router,  tags=["contifico"])
router.include_router(pdfs_api.router,       tags=["pdfs"])
