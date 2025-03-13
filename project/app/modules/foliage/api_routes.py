from . import foliage_api as api
from .controller import (
    FarmView, 
    LotView,
    CropView,
    LotCropView,
    CommonAnalysisView,
    NutrientView,
    LeafAnalysisView,
    NutrientApplicationView,
)

farm_view = FarmView()
api.add_url_rule('/farms', view_func=farm_view.as_view('farms'), methods=['GET', 'POST', 'DELETE'])
api.add_url_rule('/farms/<int:id>', view_func=farm_view.as_view('farm'), methods=['GET', 'PUT', 'DELETE'])

lot_view = LotView()
api.add_url_rule('/lots', view_func=lot_view.as_view('lots'), methods=['GET', 'POST', 'DELETE'])
api.add_url_rule('/lots/<int:id>', view_func=lot_view.as_view('lot'), methods=['GET', 'PUT', 'DELETE'])

crop_view = CropView()
api.add_url_rule('/crops', view_func=crop_view.as_view('crops'), methods=['GET', 'POST', 'DELETE'])
api.add_url_rule('/crops/<int:id>', view_func=crop_view.as_view('crop'), methods=['GET', 'PUT', 'DELETE'])

lot_crop_view = LotCropView()
api.add_url_rule('/lots/<int:lot_id>/crops', view_func=lot_crop_view.as_view('lot_crops'), methods=['GET', 'POST', 'DELETE'])
api.add_url_rule('/lots/<int:lot_id>/crops/<int:crop_id>', view_func=lot_crop_view.as_view('lot_crop'), methods=['GET', 'PUT', 'DELETE'])

common_analysis_view = CommonAnalysisView()
api.add_url_rule('/common_analyses', view_func=common_analysis_view.as_view('common_analyses'), methods=['GET', 'POST', 'DELETE'])
api.add_url_rule('/common_analyses/<int:id>', view_func=common_analysis_view.as_view('common_analysis'), methods=['GET', 'PUT', 'DELETE'])

nutrient_view = NutrientView()
api.add_url_rule('/nutrients', view_func=nutrient_view.as_view('nutrients'), methods=['GET', 'POST', 'DELETE'])
api.add_url_rule('/nutrients/<int:id>', view_func=nutrient_view.as_view('nutrient'), methods=['GET', 'PUT', 'DELETE'])

leaf_analysis_view = LeafAnalysisView()
api.add_url_rule('/leaf_analyses', view_func=leaf_analysis_view.as_view('leaf_analyses'), methods=['GET', 'POST', 'DELETE'])
api.add_url_rule('/leaf_analyses/<int:id>', view_func=leaf_analysis_view.as_view('leaf_analysis'), methods=['GET', 'PUT', 'DELETE'])

nutrient_application_view = NutrientApplicationView()
api.add_url_rule('/nutrient_applications', view_func=nutrient_application_view.as_view('nutrient_applications'), methods=['GET', 'POST', 'DELETE'])
#api.add_url_rule('/nutrient_applications/<int:id>', view_func=nutrient_application_view.as_view('nutrient_applications'), methods=['GET', 'PUT', 'DELETE'])

