"""
core/database.py — Acceso a datos para el modo escritorio.
Re-exporta todo desde app/database sin cambios.
"""
from app.database import (           # noqa: F401
    init_db,
    get_connection,
    # contactos
    upsert_contacto,
    get_contacto,
    get_todos_contactos,
    # plantillas
    get_plantilla,
    get_todas_plantillas,
    save_plantilla,
    # historial de envíos
    registrar_envio,
    get_enviados_hoy,
    ya_fue_enviado_hoy,
    # cache de facturas
    guardar_facturas_cache,
    get_facturas_cache,
    # score
    upsert_score,
    get_score,
    get_todos_scores,
    # mensajes log
    registrar_mensaje_log,
    get_mensajes_log,
    get_actividad_reciente,
    # acciones sugeridas
    crear_accion,
    get_acciones_pendientes,
    completar_accion,
    posponer_accion,
    limpiar_acciones_antiguas,
    hay_accion_pendiente_hoy,
    # config sistema
    get_config_sistema,
    set_config_sistema,
    # historial de cargas
    registrar_carga_historial,
    get_historial_cargas,
    restaurar_desde_historial,
    eliminar_carga_historial,
    limpiar_historial_antiguo,
    # estadísticas
    get_estadisticas_por_mes,
    # cotizaciones
    crear_cotizacion,
    get_cotizacion,
    get_cotizaciones,
    get_items_cotizacion,
    actualizar_estado_cotizacion,
    actualizar_cotizacion,
    eliminar_cotizacion,
    buscar_contactos_para_cotizacion,
)
