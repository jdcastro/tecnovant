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
    ObjectiveView,
    ProductView, 
    ProductContributionView
)


farm_view = FarmView.as_view("farms_view")
api.add_url_rule("/farms/", view_func=farm_view, methods=["GET", "POST", "DELETE"])
api.add_url_rule(
    "/farms/<int:id>", view_func=farm_view, methods=["GET", "PUT", "DELETE"]
)

lot_view = LotView.as_view("lots_view")
api.add_url_rule("/lots/", view_func=lot_view, methods=["GET", "POST", "DELETE"])
api.add_url_rule("/lots/<int:id>", view_func=lot_view, methods=["GET", "PUT", "DELETE"])

crop_view = CropView.as_view("crops_view")
api.add_url_rule("/crops/", view_func=crop_view, methods=["GET", "POST", "DELETE"])
api.add_url_rule(
    "/crops/<int:id>", view_func=crop_view, methods=["GET", "PUT", "DELETE"]
)

lot_crop_view = LotCropView.as_view("lot_crops")
api.add_url_rule(
    "/lots/<int:lot_id>/crops",
    view_func=lot_crop_view,
    methods=["GET", "POST", "DELETE"],
)
api.add_url_rule(
    "/lots/<int:lot_id>/crops/<int:crop_id>",
    view_func=lot_crop_view,
    methods=["GET", "PUT", "DELETE"],
)

common_analysis_view = CommonAnalysisView.as_view("common_analyses")
api.add_url_rule(
    "/common_analyses/",
    view_func=common_analysis_view,
    methods=["GET", "POST", "DELETE"],
)
api.add_url_rule(
    "/common_analyses/<int:id>",
    view_func=common_analysis_view,
    methods=["GET", "PUT", "DELETE"],
)

nutrient_view = NutrientView.as_view("nutrients")
api.add_url_rule(
    "/nutrients/", view_func=nutrient_view, methods=["GET", "POST", "DELETE"]
)
api.add_url_rule(
    "/nutrients/<int:id>", view_func=nutrient_view, methods=["GET", "PUT", "DELETE"]
)

leaf_analysis_view = LeafAnalysisView.as_view("leaf_analyses")
api.add_url_rule(
    "/leaf_analyses/", view_func=leaf_analysis_view, methods=["GET", "POST", "DELETE"]
)
api.add_url_rule(
    "/leaf_analyses/<int:id>",
    view_func=leaf_analysis_view,
    methods=["GET", "PUT", "DELETE"],
)

nutrient_application_view = NutrientApplicationView.as_view("nutrient_applications")
api.add_url_rule(
    "/nutrient_applications/",
    view_func=nutrient_application_view,
    methods=["GET", "POST", "DELETE"],
)
api.add_url_rule(
    "/nutrient_applications/<int:id>",
    view_func=nutrient_application_view,
    methods=["GET", "PUT", "DELETE"],
)

objective_view = ObjectiveView.as_view("objectives")
api.add_url_rule(
    "/objectives/", view_func=objective_view, methods=["GET", "POST", "DELETE"]
)
api.add_url_rule(
    "/objectives/<int:id>", view_func=objective_view, methods=["GET", "PUT", "DELETE"]
)

product_view = ProductView.as_view("products")
api.add_url_rule(
    "/products/", view_func=product_view, methods=["GET", "POST", "DELETE"]
)
api.add_url_rule(
    "/products/<int:id>", view_func=product_view, methods=["GET", "PUT", "DELETE"]
)
product_contribution_view = ProductContributionView.as_view("product_contributions")
api.add_url_rule(
    "/products_contributions/",
    view_func=product_contribution_view,
    methods=["GET", "POST", "DELETE"],
)
api.add_url_rule(
    "/products_contributions/<int:id>",
    view_func=product_contribution_view,
    methods=["GET", "PUT", "DELETE"],
)