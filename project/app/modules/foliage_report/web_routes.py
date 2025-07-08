import json
from decimal import Decimal

from flask import current_app, render_template, request, url_for
from flask_jwt_extended import get_jwt, jwt_required
from werkzeug.exceptions import Forbidden

from app.core.controller import check_resource_access, login_required
from app.extensions import db
from app.modules.foliage.models import CommonAnalysis, Crop, Farm, Lot, Recommendation

from . import foliage_report as web
from .controller import ReportView
from .helpers import (
    LeafAnalysisResource,
    NutrientOptimizer,
    ObjectiveResource,
    calcular_cv_nutriente,
    contribuciones_de_producto,
    determinar_coeficientes_variacion,
)


def get_dashboard_menu():
    """Define el menu superior en los templates"""
    return {
        "menu": [
            {"name": "Home", "url": url_for("core.index")},
            {"name": "Logout", "url": url_for("core.logout")},
            {"name": "Profile", "url": url_for("core.profile")},
        ]
    }


@web.route("/listar_reportes/")
@login_required
def listar_reportes():
    claims = get_jwt()
    user_role = claims.get("rol")

    # Obtener parámetros de filtro de la URL
    farm_id = request.args.get("farm_id", type=int)
    lot_id = request.args.get("lot_id", type=int)

    context = {
        "dashboard": True,
        "title": "Informes de Análisis",
        "description": "Listado de informes generados.",
        "author": "Johnny De Castro",
        "site_title": "Listado de Informes",
        "data_menu": get_dashboard_menu(),
        "entity_name": "Reportes",
        "entity_name_lower": "reporte",
        "selected_farm_id": farm_id,  # Para mantener la selección
        "selected_lot_id": lot_id,  # Para mantener la selección
    }

    # Query base
    query = Recommendation.query.options(
        db.joinedload(Recommendation.lot)
        .joinedload(Lot.farm)
        .joinedload(Farm.organization),
        db.joinedload(Recommendation.crop),
    ).filter(Recommendation.active == True)

    # APLICAR FILTROS AQUÍ
    if lot_id:
        # Si se especifica un lote, filtrar por ese lote específico
        query = query.filter(Recommendation.lot_id == lot_id)
    elif farm_id:
        # Si solo se especifica finca, filtrar por todos los lotes de esa finca
        query = query.join(Lot).filter(Lot.farm_id == farm_id)

    accessible_recommendations = []
    all_recommendations = query.all()

    for rec in all_recommendations:
        if check_resource_access(rec.lot.farm, claims):
            accessible_recommendations.append(rec)

    # Serializar solo los datos necesarios para la tabla
    items_list = []
    for rec in accessible_recommendations:
        items_list.append(
            {
                "id": rec.id,
                "title": rec.title,
                "finca_lote": (
                    f"{rec.lot.farm.name} / {rec.lot.name}"
                    if rec.lot and rec.lot.farm
                    else "N/A"
                ),
                "crop": rec.crop.name if rec.crop else "N/A",
                "date": rec.date.strftime("%Y-%m-%d") if rec.date else "N/A",
                "autor": rec.author or "Sistema",
            }
        )

    total_informes = len(items_list)

    return render_template(
        "listar_reportes.j2",
        **context,
        request=request,
        total_informes=total_informes,
        items=items_list,
    )


@web.route("/vista_reporte/<int:report_id>")
@jwt_required()
def vista_reporte(report_id):
    claims = get_jwt()

    # Instanciar ReportView para llamar a su método get
    # Esto simula una llamada interna al endpoint de la API.
    # Necesitamos pasar el token JWT de alguna manera si ReportView.get lo requiere
    # y no lo puede obtener directamente del contexto de la solicitud actual
    # de la misma forma que lo haría si fuera llamado externamente.
    # Sin embargo, como ReportView usa @jwt_required(), y esta ruta también lo usa,
    # el contexto de JWT debería estar disponible.

    report_view_instance = ReportView()

    try:
        # Llamar al método get de ReportView con el report_id
        # El método get de ReportView devuelve un objeto Flask Response.
        # Necesitamos obtener el JSON de ese objeto.
        response_obj = report_view_instance.get(id=report_id)

        if response_obj.status_code == 200:
            report_data = response_obj.get_json()
        elif response_obj.status_code == 404:
             current_app.logger.error(f"Reporte con ID {report_id} no encontrado.")
             # Renderizar una plantilla de error o redirigir
             return render_template("default/404.j2", error_message=f"Reporte con ID {report_id} no encontrado."), 404
        else:
            current_app.logger.error(f"Error obteniendo reporte {report_id}: {response_obj.status_code} - {response_obj.get_data(as_text=True)}")
            return render_template("default/500.j2", error_message="Error al cargar el reporte."), response_obj.status_code

    except Exception as e:
        current_app.logger.error(f"Excepción al obtener datos del reporte {report_id}: {e}", exc_info=True)
        return render_template("default/500.j2", error_message="Error interno al procesar la solicitud del reporte."), 500

    # Contexto base para el template
    context = {
        "dashboard": True,
        "title": f"Ver Informe: {report_data.get('title', 'Detalle')}",
        "description": "Detalles del informe de análisis.",
        "author": "Sistema TecnoAgro", # O tomar de report_data si está disponible
        "site_title": "Ver Informe",
        "data_menu": get_dashboard_menu(),
        "request": request, # Pasar el objeto request al template
    }
    
    # Combinar el contexto base con los datos del reporte.
    # Las claves en report_data (analysisData, optimalLevels, etc.) estarán disponibles directamente.
    context.update(report_data)

    return render_template(
        "ver_reporte2.j2",
        **context
    )

# Eliminamos la ruta /vista_report ya que /vista_reporte/<id> la reemplaza con datos reales
# @web.route("/vista_report")
# @login_required
# def vista_report():
#     ... (código eliminado) ...


@web.route("/solicitar_informe")
@login_required
def generar_informe():
    context = {
        "dashboard": True,
        "title": "Dashboard TecnoAgro",
        "description": "Panel de control.",
        "author": "Johnny De Castro",
        "site_title": "Panel de Control",
        "og_image": "/img/og-image.jpg",
        "twitter_image": "/img/twitter-image.jpg",
        "data_menu": get_dashboard_menu(),
    }
    return render_template("solicitar_informe2.j2", **context, request=request)


# return render_template("solicitar_informe.j2", **context, request=request)


@web.route("/cv_nutrientes")
@login_required
def cv_nutrientes():
    """
    Página: Renderiza la vista de CV de nutrientes
    """
    # Calcular el CV para cada nutriente en el lote con ID 1
    coeficientes_variacion = determinar_coeficientes_variacion(1)
    productos_contribuciones = contribuciones_de_producto()
    objective_resource = ObjectiveResource()
    response = objective_resource.get_objective_list()

    # Obtener demandas ideales para el cultivo de papa
    crop_objectives = response.papa
    demandas_ideales = crop_objectives.get(index=0)
    demandas_ideales_dict = demandas_ideales.nutrient_data  # Already Decimal

    # Obtener análisis de hojas para el lote con ID 1
    leaf_analysis_resource = LeafAnalysisResource()
    response = leaf_analysis_resource.get_leaf_analysis_list()
    data_string = response.get_json()
    data = json.loads(data_string)
    nutrientes_actuales_raw = data["4"][0]["nutrients"]

    # Convertir los valores de nutrientes_actuales a Decimal
    nutrientes_actuales = {
        nutriente: Decimal(str(valor))  # Convert string to Decimal
        for nutriente, valor in nutrientes_actuales_raw.items()
    }

    # Asegurar que demandas_ideales_dict es un diccionario
    if not isinstance(demandas_ideales_dict, dict):
        raise ValueError("demandas_ideales no es un diccionario")

    # Asegurar que nutrientes_actuales es un diccionario
    if not isinstance(nutrientes_actuales, dict):
        raise ValueError("nutrientes_actuales no es un diccionario")

    # Instanciar y usar la clase
    optimizador = NutrientOptimizer(
        nutrientes_actuales,
        demandas_ideales_dict,
        productos_contribuciones,
        coeficientes_variacion,
    )
    limitante = optimizador.identificar_limitante()
    recomendacion = optimizador.generar_recomendacion(lot_id=1)
    return f"Nutriente limitante: {limitante}\n{recomendacion}"

