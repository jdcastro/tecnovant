# Python standard library imports
from functools import wraps
import json
from decimal import Decimal
from datetime import datetime

# Third party imports
from werkzeug.exceptions import InternalServerError, BadRequest, NotFound, Forbidden
from flask.views import MethodView
from flask_jwt_extended import get_jwt, jwt_required
from flask import request, jsonify, Response, current_app


# Local application imports
from app.extensions import db
from app.core.controller import check_permission, check_resource_access
from app.core.models import ResellerPackage, RoleEnum
from app.modules.foliage.models import CommonAnalysis, LeafAnalysis, SoilAnalysis, Farm, Lot, Crop, LotCrop, Recommendation, Nutrient, Objective, objective_nutrients
from .helpers import NutrientOptimizer, determinar_coeficientes_variacion, contribuciones_de_producto, ObjectiveResource, LeafAnalysisResource, ReportView


class RecommendationView(MethodView):
    """Class to manage CRUD operations for recommendations"""

    decorators = [jwt_required()]

    @check_permission(required_roles=["administrator", "reseller"])
    def get(self, recommendation_id=None):
        """
        Retrieve a list of recommendations or a specific recommendation
        Args:
            recommendation_id (int, optional): ID of the recommendation to retrieve
        Returns:
            JSON: List of recommendations or details of a specific recommendation
        """
        if recommendation_id:
            return self._get_recommendation(recommendation_id)
        return self._get_recommendation_list()

    @check_permission(required_roles=["administrator", "reseller"])
    def post(self):
        """
        Create a new recommendation
        Returns:
            JSON: Details of the created recommendation
        """
        data = request.get_json()
        required_fields = ["lot_id", "date", "recommendation"]
        if not data or not all(k in data for k in required_fields):
            raise BadRequest("Missing required fields")
        return self._create_recommendation(data)

    @check_permission(resource_owner_check=True)
    def put(self, id: int):
        """
        Update an existing recommendation
        Args:
            recommendation_id (int): ID of the recommendation to update
        Returns:
            JSON: Details of the updated recommendation
        """
        data = request.get_json()
        recommendation_id = id
        if not data or not recommendation_id:
            raise BadRequest("Missing recommendation_id or data")
        return self._update_recommendation(recommendation_id, data)

    @check_permission(resource_owner_check=True)
    def delete(self, id=None):
        """
        Delete an existing recommendation
        Args:
            recommendation_id (int): ID of the recommendation to delete
        Returns:
            JSON: Confirmation message
        """
        recommendation_id = id
        if not recommendation_id:
            raise BadRequest("Missing recommendation_id")
        return self._delete_recommendation(recommendation_id)

    # Helper Methods
    def _get_recommendation_list(self):
        """Retrieve a list of all recommendations"""
        claims = get_jwt()
        user_role = claims.get("rol")
        if user_role == RoleEnum.ADMINISTRATOR.value:
            recommendations = Recommendation.query.all()
        elif user_role == RoleEnum.RESELLER.value:
            reseller_package = ResellerPackage.query.filter_by(
                reseller_id=claims.get("org_id")
            ).first()
            if not reseller_package:
                raise NotFound("Reseller package not found.")
            recommendations = []
            for organization in reseller_package.organizations:
                for lot in organization.lots:
                    recommendations.extend(lot.recommendations)
        else:
            raise Forbidden(
                "Only administrators and resellers can list recommendations"
            )
        response_data = [self._serialize_recommendation(r) for r in recommendations]
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _get_recommendation(self, recommendation_id):
        """Retrieve details of a specific recommendation"""
        recommendation = Recommendation.query.get_or_404(recommendation_id)
        claims = get_jwt()
        if not self._has_access(recommendation, claims):
            raise Forbidden("You do not have access to this recommendation")
        response_data = self._serialize_recommendation(recommendation)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _create_recommendation(self, data):
        """Create a new recommendation"""
        lot_id = data["lot_id"]
        date = data["date"]
        recommendation = data["recommendation"]
        rec = Recommendation(lot_id=lot_id, date=date, recommendation=recommendation)
        db.session.add(rec)
        db.session.commit()
        response_data = self._serialize_recommendation(rec)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=201, mimetype="application/json")

    def _update_recommendation(self, recommendation_id, data):
        """Update an existing recommendation"""
        recommendation = Recommendation.query.get_or_404(recommendation_id)
        if "date" in data:
            recommendation.date = data["date"]
        if "recommendation" in data:
            recommendation.recommendation = data["recommendation"]
        db.session.commit()
        response_data = self._serialize_recommendation(recommendation)
        json_data = json.dumps(response_data, ensure_ascii=False, indent=4)
        return Response(json_data, status=200, mimetype="application/json")

    def _delete_recommendation(self, recommendation_id):
        """Delete an existing recommendation"""
        recommendation = Recommendation.query.get_or_404(recommendation_id)
        db.session.delete(recommendation)
        db.session.commit()
        return jsonify({"message": "Recommendation deleted successfully"}), 200

    def _has_access(self, recommendation, claims):
        """Check if the current user has access to the recommendation"""
        return check_resource_access(recommendation, claims)

    def _serialize_recommendation(self, recommendation):
        """Serialize a Recommendation object to a dictionary"""
        return {
            "id": recommendation.id,
            "lot_id": recommendation.lot_id,
            "date": recommendation.date,
            "recommendation": recommendation.recommendation,
            "created_at": recommendation.created_at.isoformat(),
            "updated_at": recommendation.updated_at.isoformat(),
        }

class RecommendationGenerator(MethodView):
    """Genera y guarda un nuevo reporte de recomendación."""
    decorators = [jwt_required()]

    @check_permission(required_roles=["administrator", "reseller", "org_admin", "org_editor"])
    def post(self):
        """
        Genera un reporte basado en los parámetros recibidos.
        Expected JSON: {"farm_id": int, "lot_id": int, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
        """
        claims = get_jwt()
        user_id = claims.get("id") # O el identificador relevante del usuario
        author_name = claims.get("username", "Sistema") # Nombre del autor

        data = request.get_json()
        if not data or not all(k in data for k in ["farm_id", "lot_id", "start_date", "end_date"]):
            raise BadRequest("Faltan parámetros: farm_id, lot_id, start_date, end_date")

        farm_id = data.get("farm_id")
        lot_id = data.get("lot_id")
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            raise BadRequest("Formato de fecha inválido. Usar YYYY-MM-DD.")

        # --- Lógica para obtener datos de análisis ---
        # (Similar a la de /api/foliage/report/analyses, pero quizás solo el más reciente)
        common_analysis = CommonAnalysis.query.options(
                db.joinedload(CommonAnalysis.soil_analysis),
                db.joinedload(CommonAnalysis.leaf_analysis),
                db.joinedload(CommonAnalysis.lot).joinedload(Lot.farm)
            ).filter(
                CommonAnalysis.lot_id == lot_id,
                CommonAnalysis.date >= start_date,
                CommonAnalysis.date <= end_date
            ).order_by(CommonAnalysis.date.desc()).first()

        if not common_analysis:
            raise NotFound("No se encontraron análisis para los parámetros dados.")

        # Verificar acceso al lote/finca
        lot = Lot.query.get(lot_id)
        if not lot or not check_resource_access(lot.farm, claims):
             raise Forbidden("No tienes acceso a este lote/finca.")

        # --- Obtener datos necesarios para el optimizador ---
        # 1. Niveles actuales (del LeafAnalysis más reciente)
        leaf_analysis_resource = LeafAnalysisResource()
        current_levels_response = leaf_analysis_resource._get_leaf_analysis_list(lot_id=lot_id, latest=True) # Necesitaría adaptar esta función
        # Procesar current_levels_response para obtener el diccionario {Nutriente: Valor}
        # Asegurarse de convertir a Decimal
        # Ejemplo simplificado:
        leaf_data_json = json.loads(current_levels_response.get_data(as_text=True))
        # Asumiendo que leaf_data_json es una lista y tomamos el primero si existe
        nutrientes_actuales_raw = {}
        if leaf_data_json:
            # Buscar análisis específico o el más reciente
            analysis_to_use = next((a for a in leaf_data_json if a['common_analysis_id'] == common_analysis.id), leaf_data_json[0]) # O buscar el más reciente
            for nv in analysis_to_use.get('nutrient_values', []):
                 nutrientes_actuales_raw[nv['nutrient_name']] = nv['value']

        nutrientes_actuales = {k: Decimal(str(v)) for k, v in nutrientes_actuales_raw.items()}


        # 2. Demandas ideales (del Objective asociado al cultivo actual del lote)
        # Encontrar el cultivo actual del lote en la fecha del análisis
        lot_crop = LotCrop.query.filter(
            LotCrop.lot_id == lot_id,
            LotCrop.start_date <= common_analysis.date,
            db.or_(LotCrop.end_date >= common_analysis.date, LotCrop.end_date.is_(None))
        ).first()

        if not lot_crop:
             raise NotFound(f"No se encontró un cultivo activo para el lote {lot_id} en la fecha {common_analysis.date}.")

        crop_id = lot_crop.crop_id

        objective_resource = ObjectiveResource()
        # Obtener objetivos para el cultivo específico
        objectives = Objective.query.filter_by(crop_id=crop_id).order_by(Objective.updated_at.desc()).first()
        if not objectives:
            raise NotFound(f"No se encontraron objetivos para el cultivo ID {crop_id}.")

        # Asumiendo que usamos el objetivo más reciente
        serialized_objective = objective_resource._serialize_objective(objectives)
        demandas_ideales = {item['nutrient_name']: Decimal(str(item['target_value'])) for item in serialized_objective['nutrient_targets']}


        # 3. Contribuciones de producto
        productos_contribuciones_data = contribuciones_de_producto()

        # 4. Coeficientes de variación
        coeficientes_variacion = determinar_coeficientes_variacion(lot_id)

        # --- Instanciar y usar NutrientOptimizer ---
        try:
            optimizer = NutrientOptimizer(
                nutrientes_actuales,
                demandas_ideales,
                productos_contribuciones_data,
                coeficientes_variacion
            )
            recomendacion_texto = optimizer.generar_recomendacion(lot_id=lot_id)
            limitante_nombre = optimizer.identificar_limitante() # Nombre del nutriente limitante
        except Exception as e:
            # Loggear el error detallado
            current_app.logger.error(f"Error en optimización para lote {lot_id}: {str(e)}", exc_info=True)
            raise BadRequest(f"Error al generar recomendación: {str(e)}")


        # --- Preparar datos para guardar en Recommendation ---
        # Serializar datos de análisis, niveles óptimos, etc.
        report_creator = ReportView() # Reutilizar la lógica de ReportView si es posible
        analysis_data_for_report = report_creator._build_analysis_data(common_analysis)
        optimal_levels_for_report = report_creator._get_optimal_levels(common_analysis)


        # --- Crear y guardar la Recommendation ---
        try:
            new_recommendation = Recommendation(
                lot_id=lot_id,
                crop_id=crop_id,
                date=datetime.now().date(), # O la fecha del análisis
                author=author_name,
                title=f"Reporte Lote {lot.name} ({common_analysis.date.strftime('%Y-%m-%d')})",
                limiting_nutrient_id = limitante_nombre, # Guardar el nombre del limitante
                automatic_recommendations=recomendacion_texto,
                text_recommendations="", # Dejar vacío para edición manual
                # Serializar datos complejos a JSON
                optimal_comparison=json.dumps(optimal_levels_for_report, default=str),
                soil_analysis_details=json.dumps(analysis_data_for_report.get("soil"), default=str),
                foliar_analysis_details=json.dumps(analysis_data_for_report.get("foliar"), default=str),
                # Podrías añadir más campos si es necesario
                applied=False,
                active=True
            )
            db.session.add(new_recommendation)
            db.session.commit()

            return jsonify({"message": "Reporte generado con éxito", "report_id": new_recommendation.id}), 201

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error guardando recomendación: {str(e)}", exc_info=True)
            raise InternalServerError("No se pudo guardar el reporte.")