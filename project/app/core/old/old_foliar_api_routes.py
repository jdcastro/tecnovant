from . import foliage_api as api
from flask import jsonify, request
from .models import (
    NutrientCategory,
    Farm,
    Lot,
    Crop,
    LotCrop,
    CommonAnalysis,
    SoilAnalysis,
    Nutrient,
    LeafAnalysis,
    NutrientApplication,
    Objective,
    Production,
    Product,
    ProductContribution,
    ProductPrice,
    Recommendation,
)
from .schemas import (
    FarmSchema,
    LotSchema,
    CropSchema,
    LotCropSchema,
    CommonAnalysisSchema,
    SoilAnalysisSchema,
    NutrientSchema,
    LeafAnalysisSchema,
    NutrientApplicationSchema,
    ObjectiveSchema,
    ProductionSchema,
    ProductSchema,
    ProductContributionSchema,
    ProductPriceSchema,
    RecommendationSchema,
)
from app.extensions import db

"""
Set up the API routes for the foliage module
"""

"""
Endpoints for the Farm model

"""


@api.route("/farms", methods=["GET"])
def get_farms():
    farms = Farm.query.all()
    return jsonify(FarmSchema().dump(farms, many=True))


@api.route("/farm/<int:farm_id>", methods=["GET"])
def get_farm(farm_id):
    farm = Farm.query.get_or_404(farm_id)
    return jsonify(FarmSchema().dump(farm))


@api.route("/add_farm", methods=["POST"])
def add_farm():
    data = request.get_json()
    farm = FarmSchema().load(data)
    db.session.add(farm)
    db.session.commit()
    return jsonify(FarmSchema().dump(farm)), 201


@api.route("/update_farm/<int:farm_id>", methods=["PUT"])
def update_farm(farm_id):
    farm = Farm.query.get_or_404(farm_id)
    data = request.get_json()
    farm = FarmSchema().load(data, instance=farm)
    db.session.commit()
    return jsonify(FarmSchema().dump(farm))


@api.route("/delete_farm/<int:farm_id>", methods=["DELETE"])
def delete_farm(farm_id):
    farm = Farm.query.get_or_404(farm_id)
    db.session.delete(farm)
    db.session.commit()
    return jsonify(FarmSchema().dump(farm))


"""
Endpoints for the Lot model

"""


@api.route("/lots", methods=["GET"])
def get_lots():
    lots = Lot.query.all()
    return jsonify(LotSchema().dump(lots, many=True))


@api.route("/lot/<int:lot_id>", methods=["GET"])
def get_lot(lot_id):
    lot = Lot.query.get_or_404(lot_id)
    return jsonify(LotSchema().dump(lot))


@api.route("/add_lot", methods=["POST"])
def add_lot():
    data = request.get_json()
    lot = LotSchema().load(data)
    db.session.add(lot)
    db.session.commit()
    return jsonify(LotSchema().dump(lot)), 201


@api.route("/update_lot/<int:lot_id>", methods=["PUT"])
def update_lot(lot_id):
    lot = Lot.query.get_or_404(lot_id)
    data = request.get_json()
    lot = LotSchema().load(data, instance=lot)
    db.session.commit()
    return jsonify(LotSchema().dump(lot))


@api.route("/delete_lot/<int:lot_id>", methods=["DELETE"])
def delete_lot(lot_id):
    lot = Lot.query.get_or_404(lot_id)
    db.session.delete(lot)
    db.session.commit()
    return jsonify(LotSchema().dump(lot))


"""
Endpoints for the Crop model

"""


@api.route("/crops", methods=["GET"])
def get_crops():
    crops = Crop.query.all()
    return jsonify(CropSchema().dump(crops, many=True))


@api.route("/crop/<int:crop_id>", methods=["GET"])
def get_crop(crop_id):
    crop = Crop.query.get_or_404(crop_id)
    return jsonify(CropSchema().dump(crop))


@api.route("/add_crop", methods=["POST"])
def add_crop():
    data = request.get_json()
    crop = CropSchema().load(data)
    db.session.add(crop)
    db.session.commit()
    return jsonify(CropSchema().dump(crop)), 201


@api.route("/update_crop/<int:crop_id>", methods=["PUT"])
def update_crop(crop_id):
    crop = Crop.query.get_or_404(crop_id)
    data = request.get_json()
    crop = CropSchema().load(data, instance=crop)
    db.session.commit()
    return jsonify(CropSchema().dump(crop))


@api.route("/delete_crop/<int:crop_id>", methods=["DELETE"])
def delete_crop(crop_id):
    crop = Crop.query.get_or_404(crop_id)
    db.session.delete(crop)
    db.session.commit()
    return jsonify(CropSchema().dump(crop))


"""
Endpoints for the LotCrop model

"""


@api.route("/lot_crops", methods=["GET"])
def get_lot_crops():
    lot_crops = LotCrop.query.all()
    return jsonify(LotCropSchema().dump(lot_crops, many=True))
