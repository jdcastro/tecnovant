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
from app.modules.foliage.models import CommonAnalysis, LeafAnalysis, SoilAnalysis, Farm, Lot, Crop, LotCrop, Recommendation, Nutrient, Objective, objective_nutrients, leaf_analysis_nutrients
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
        Expected JSON: {"lot_id": int, "common_analysis_ids": list[int], "objective_id": int, "title": str}
        """
        claims = get_jwt()
        author_name = claims.get("username", "Sistema")

        data = request.get_json()
        if not data or not all(k in data for k in ["lot_id", "common_analysis_ids", "objective_id", "title"]):
            raise BadRequest("Faltan parámetros: lot_id, common_analysis_ids, objective_id, title")

        lot_id = data.get("lot_id")
        common_analysis_ids = data.get("common_analysis_ids")
        objective_id = data.get("objective_id")
        report_title = data.get("title")

        if not isinstance(lot_id, int):
            raise BadRequest("lot_id debe ser un entero.")
        if not isinstance(common_analysis_ids, list) or not all(isinstance(id, int) for id in common_analysis_ids):
            raise BadRequest("common_analysis_ids debe ser una lista de enteros.")
        if not common_analysis_ids:
            raise BadRequest("common_analysis_ids no puede estar vacía.")
        if not isinstance(objective_id, int):
            raise BadRequest("objective_id debe ser un entero.")
        if not isinstance(report_title, str) or not report_title.strip():
            raise BadRequest("El título no puede estar vacío.")

        # --- Procesar CommonAnalysis ---
        # Estrategia: Procesar solo el primer common_analysis_id de la lista.
        if len(common_analysis_ids) > 1:
            current_app.logger.warning(
                f"Múltiples common_analysis_ids recibidos: {common_analysis_ids}. "
                f"Solo se procesará el primero: {common_analysis_ids[0]}."
            )
        selected_common_analysis_id = common_analysis_ids[0]

        common_analysis = CommonAnalysis.query.options(
            db.joinedload(CommonAnalysis.leaf_analysis).joinedload(LeafAnalysis.nutrients).joinedload(Nutrient.objectives), # Preload Nutrient for objectives
            db.joinedload(CommonAnalysis.soil_analysis),
            db.joinedload(CommonAnalysis.lot) # Para crop_id y farm access check
        ).get(selected_common_analysis_id)

        if not common_analysis:
            raise NotFound(f"No se encontró CommonAnalysis con ID {selected_common_analysis_id}.")
        
        if not common_analysis.leaf_analysis:
            raise NotFound(f"CommonAnalysis ID {selected_common_analysis_id} no tiene un LeafAnalysis asociado.")

        # Verificar acceso al lote/finca
        lot = common_analysis.lot
        if not lot or not check_resource_access(lot.farm, claims):
             raise Forbidden("No tienes acceso a este lote/finca.")

        # 1. Niveles actuales (del LeafAnalysis)
        nutrientes_actuales_raw = {}
        # Acceder a los nutrientes a través de la relación cargada en common_analysis.leaf_analysis
        for nutrient_assoc in common_analysis.leaf_analysis.nutrients:
            # nutrient_assoc es una instancia de Nutrient, el valor está en la tabla de asociación
            # Necesitamos una forma de obtener el 'value' de la tabla leaf_analysis_nutrients
            # Esto requiere que el modelo LeafAnalysis.nutrients devuelva objetos que contengan el valor.
            # Asumimos que la relación está configurada para esto o se hace una subconsulta.
            # Por ahora, vamos a buscarlo directamente si no está en el objeto `nutrient_assoc`.
            # Esto es ineficiente y debería mejorarse con una carga adecuada en el modelo.
            
            stmt = db.select(db.column("value")).where(
                db.and_(
                    leaf_analysis_nutrients.c.leaf_analysis_id == common_analysis.leaf_analysis.id,
                    leaf_analysis_nutrients.c.nutrient_id == nutrient_assoc.id
                )
            )
            result = db.session.execute(stmt).scalar_one_or_none()
            if result is not None:
                 nutrientes_actuales_raw[nutrient_assoc.name] = result
            else:
                current_app.logger.warning(f"No se encontró valor para el nutriente {nutrient_assoc.name} en LeafAnalysis {common_analysis.leaf_analysis.id}")


        if not nutrientes_actuales_raw:
            raise NotFound(f"LeafAnalysis ID {common_analysis.leaf_analysis.id} no tiene valores de nutrientes.")
        nutrientes_actuales = {k: Decimal(str(v)) for k, v in nutrientes_actuales_raw.items()}


        # --- Procesar Objective ---
        objective = Objective.query.options(
            db.joinedload(Objective.nutrients) # Asegura que los nutrientes del objetivo están cargados
        ).get(objective_id)
        if not objective:
            raise NotFound(f"No se encontró Objective con ID {objective_id}.")
        
        crop_id = objective.crop_id # Usar el crop_id del objetivo

        # 2. Demandas ideales (del Objective)
        demandas_ideales = {}
        # Los nutrientes y sus target_value están en la tabla de asociación objective_nutrients
        for nutrient_target in objective.nutrients:
            # Similar al caso anterior, necesitamos el target_value de la tabla de asociación
            stmt = db.select(db.column("target_value")).where(
                db.and_(
                    objective_nutrients.c.objective_id == objective.id,
                    objective_nutrients.c.nutrient_id == nutrient_target.id
                )
            )
            target_value = db.session.execute(stmt).scalar_one_or_none()
            if target_value is not None:
                demandas_ideales[nutrient_target.name] = Decimal(str(target_value))
            else:
                 current_app.logger.warning(f"No se encontró target_value para el nutriente {nutrient_target.name} en Objective {objective.id}")


        if not demandas_ideales:
             raise NotFound(f"El objetivo ID {objective_id} no tiene metas de nutrientes definidas.")

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
            limitante_nombre = optimizer.identificar_limitante()
        except ValueError as ve:
            if "No products available for optimization" in str(ve):
                current_app.logger.error(f"ValueError en optimización para lote {lot_id} con objetivo {objective_id}: {str(ve)}", exc_info=True)
                raise BadRequest("No hay productos de fertilización configurados o disponibles que coincidan con los nutrientes requeridos. No se puede generar una recomendación.")
            # Re-raise other ValueErrors to be caught by the generic Exception handler or handled differently if needed
            raise
        
        except Exception as e:
            current_app.logger.error(f"Error en optimización para lote {lot_id} con objetivo {objective_id}: {str(e)}", exc_info=True)
            raise BadRequest(f"Error al generar recomendación con optimizador: {str(e)}")

        # --- Preparar datos para guardar en Recommendation ---
        report_creator = ReportView() 
        
        # Foliar details from the chosen common_analysis
        # _build_analysis_data espera un common_analysis completo
        analysis_data_for_report = report_creator._build_analysis_data(common_analysis)
        foliar_details_json = json.dumps(analysis_data_for_report.get("foliar"), default=str)
        soil_details_json = json.dumps(analysis_data_for_report.get("soil"), default=str)

        # Optimal comparison from the objective
        # Necesitamos un método para formatear los datos del objetivo como optimal_levels
        # Formato esperado: {'Nutriente': {'min': X, 'max': Y, 'ideal': Z, 'unit': 'unidad'}}
        optimal_comparison_data = {}
        for nutrient_name, ideal_value in demandas_ideales.items():
            # Encontrar el objeto Nutrient para obtener la unidad
            nutrient_obj = next((n for n in objective.nutrients if n.name == nutrient_name), None)
            unit = nutrient_obj.unit if nutrient_obj else '%' # Default unit
            optimal_comparison_data[nutrient_name] = {
                "min": float(ideal_value), # O un rango si el objetivo lo define
                "max": float(ideal_value),
                "ideal": float(ideal_value),
                "unit": unit
            }
        optimal_comparison_json = json.dumps(optimal_comparison_data, default=str)
        
        # --- Crear y guardar la Recommendation ---
        try:
            new_recommendation = Recommendation(
                lot_id=lot_id,
                crop_id=crop_id, 
                date=datetime.now().date(),
                author=author_name,
                title=report_title,
                limiting_nutrient_id=limitante_nombre,
                automatic_recommendations=recomendacion_texto,
                text_recommendations="", 
                optimal_comparison=optimal_comparison_json,
                soil_analysis_details=soil_details_json,
                foliar_analysis_details=foliar_details_json,
                # Considerar añadir objective_id y common_analysis_ids_used si se modifica el modelo
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

        

class RecommendationFilterView(MethodView):
    def get(self):
        try:
            farm_id = int(request.args.get('farm_id', 0))
            lot_id = int(request.args.get('lot_id', 0))
            
            # Query para filtrar las recomendaciones
            query = Recommendation.query.options(
                db.joinedload(Recommendation.lot),
                db.joinedload(Recommendation.crop)
            ).filter(
                Recommendation.lot_id == lot_id if lot_id else Recommendation.lot.has(farm_id=farm_id)
            )
            
            recommendations = query.all()
            
            # Convertir a lista para serializar
            recommendations_list = list(recommendations)
            
            return jsonify([{
                'id': rec.id,
                'lot_id': rec.lot_id,
                'crop_id': rec.crop_id,
                'date': rec.date.isoformat(),
                'author': rec.author,
                'title': rec.title,
                'limiting_nutrient_id': rec.limiting_nutrient_id,
                'automatic_recommendations': rec.automatic_recommendations,
                'text_recommendations': rec.text_recommendations,
                'optimal_comparison': rec.optimal_comparison,
                'minimum_law_analyses': rec.minimum_law_analyses,
                'soil_analysis_details': rec.soil_analysis_details,
                'foliar_analysis_details': rec.foliar_analysis_details,
                'applied': rec.applied,
                'active': rec.active,
                'created_at': rec.created_at.isoformat(),
                'updated_at': rec.updated_at.isoformat(),
                'lot': {
                    'id': rec.lot.id,
                    'name': rec.lot.name,
                    'farm_id': rec.lot.farm_id
                },
                'crop': {
                    'id': rec.crop.id,
                    'name': rec.crop.name
                }
            } for rec in recommendations_list])
            
        except ValueError:
            return jsonify({'error': 'Invalid farm_id or lot_id'}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
class DeleteRecommendationView(MethodView):
    @jwt_required()
    def delete(self, report_id):
        # Verificar autenticación y permisos (ajusta según tu lógica)
        claims = get_jwt()  # Asume que tienes una función get_jwt() para obtener claims
        if not claims or not claims.get("rol") in ["administrator", "reseller", "org_admin", "org_editor"]:
            return jsonify({"error": "No autorizado"}), 403

        # Buscar el reporte
        report = Recommendation.query.get(report_id)
        if not report:
            return jsonify({"error": "Reporte no encontrado"}), 404

        # Verificar acceso al recurso
        if not check_resource_access(report.lot.farm, claims):
            return jsonify({"error": "No tienes acceso a este reporte"}), 403

        try:
            # Eliminación lógica (soft delete)
            report.active = False
            db.session.commit()
            return jsonify({"message": "Reporte eliminado exitosamente"}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

