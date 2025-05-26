from datetime import datetime

from flask import jsonify, request
from flask_jwt_extended import get_jwt

from . import foliage_report_api as api
from app.core.controller import login_required, check_resource_access
from app.core.models import Organization
from app.modules.foliage.models import Farm, Lot, CommonAnalysis, Nutrient
from app.extensions import db
from .controller import RecommendationGenerator, RecommendationView, RecommendationFilterView, DeleteRecommendationView
from .helpers import ReportView


report_view = ReportView.as_view("report_view")
api.add_url_rule("/report/<int:id>", view_func=report_view, methods=["GET"])

report_generator_view = RecommendationGenerator.as_view("generate_report")
api.add_url_rule("/generate", view_func=report_generator_view, methods=["POST"])

report_filter_view = RecommendationFilterView.as_view("get_filtered_reports")
api.add_url_rule("/get_filtered_reports", view_func=report_filter_view, methods=["GET"])

# Registrar la ruta en tu API
delete_report_view = DeleteRecommendationView.as_view("delete_report")
api.add_url_rule("/delete_report/<int:report_id>", view_func=delete_report_view, methods=["DELETE"])

@api.route('/get-farms')
@login_required
def get_farms():
    claims = get_jwt()
    
    # Obtener todas las fincas que el usuario puede visualizar
    farms = Farm.query.join(Organization).filter(
        check_resource_access(Farm, claims)
    ).all()
    
    return jsonify([
        {'id': farm.id, 'name': farm.name} 
        for farm in farms
    ])

@api.route('/get-lots/')
@login_required
def get_lots():
    claims = get_jwt()
    farm_id = request.args.get('farm_id')
    farm = Farm.query.get_or_404(farm_id)
    
    # Verificar si el usuario tiene acceso a esta finca
    if not check_resource_access(farm, claims):
        return jsonify({'error': 'No tienes acceso a esta finca'}), 403
        
    lots = Lot.query.filter_by(farm_id=farm_id).all()
    
    return jsonify([
        {'id': lot.id, 'name': lot.name} 
        for lot in lots
    ])

@api.route('/analyses')
@login_required
def get_analyses():
    claims = get_jwt()
    farm_id = request.args.get('farm_id')
    lot_id = request.args.get('lot_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Construir la query con relaciones eager loading
    query = CommonAnalysis.query.options(
        db.joinedload(CommonAnalysis.soil_analysis),
        db.joinedload(CommonAnalysis.leaf_analysis),
        db.joinedload(CommonAnalysis.lot).joinedload(Lot.farm)
    )
    
    # Aplicar filtros
    if farm_id:
        query = query.filter(CommonAnalysis.lot.has(Lot.farm_id == farm_id))
        
    if lot_id:
        query = query.filter(CommonAnalysis.lot_id == lot_id)
        
    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(CommonAnalysis.date.between(start_date, end_date))
        except ValueError:
            return jsonify({'error': 'Formato de fecha incorrecto'}), 400
    
    # Obtener resultados
    common_analyses = query.all()
    
    # Preparar la respuesta
    analyses = []
    for common_analysis in common_analyses:
        soil_analysis = common_analysis.soil_analysis
        leaf_analysis = common_analysis.leaf_analysis
        
        analysis_data = {
            'id': common_analysis.id,
            'date': common_analysis.date.strftime('%Y-%m-%d'),
            'lot': {
                'id': common_analysis.lot.id,
                'name': common_analysis.lot.name,
                'farm': {
                    'id': common_analysis.lot.farm.id,
                    'name': common_analysis.lot.farm.name
                }
            },
            'soil_analysis': {
                'energy': soil_analysis.energy if soil_analysis else None,
                'grazing': soil_analysis.grazing if soil_analysis else None
            },
            'leaf_analysis': {
                'nutrients': [
                    {
                        'nutrient_id': nutrient.id,
                        'value': nutrient.value,
                        'nutrient_name': nutrient.nutrient.name if nutrient.nutrient else None
                    } for nutrient in (leaf_analysis.nutrients if leaf_analysis else [])
                ]
            }
        }
        analyses.append(analysis_data)
    
    return jsonify(analyses)

