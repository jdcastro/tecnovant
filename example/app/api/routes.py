from flask import Blueprint, jsonify, request

api_bp = Blueprint('api', __name__)

FARMS = [{"id": 1, "name": "Finca El Paraíso"}, {"id": 2, "name": "Finca Las Nubes"}]

LOTS = {
    1: [
        {"id": 101, "name": "Lote Norte", "crop_id": 1},
        {"id": 102, "name": "Lote Sur", "crop_id": 2}
    ],
    2: [
        {"id": 201, "name": "Lote Alto", "crop_id": 3}
    ]
}

CROPS = {
    1: {"name": "Maíz"},
    2: {"name": "Soya"},
    3: {"name": "Caña"}
}

OBJECTIVES = {
    1: {"N": 3.0, "P": 0.4, "K": 2.5},
    2: {"N": 3.5, "P": 0.5, "K": 2.8},
    3: {"N": 4.0, "P": 0.6, "K": 3.0}
}

ANALYSIS = {
    101: [
        {"id": 1001, "date": "2024-06-01", "N": 2.1, "P": 0.35, "K": 2.0},
        {"id": 1002, "date": "2024-06-10", "N": 2.8, "P": 0.38, "K": 2.2}
    ],
    102: [
        {"id": 1003, "date": "2024-06-05", "N": 3.2, "P": 0.45, "K": 2.6}
    ],
    201: [
        {"id": 1004, "date": "2024-06-08", "N": 3.9, "P": 0.58, "K": 2.9}
    ]
}

@api_bp.route("/farms")
def get_farms():
    return jsonify(FARMS)

@api_bp.route("/lots")
def get_lots():
    farm_id = int(request.args.get("farm_id"))
    return jsonify(LOTS.get(farm_id, []))

@api_bp.route("/analyses")
def get_analyses():
    lot_id = int(request.args.get("lot_id"))
    return jsonify(ANALYSIS.get(lot_id, []))

@api_bp.route("/objective")
def get_objective():
    crop_id = int(request.args.get("crop_id"))
    return jsonify(OBJECTIVES.get(crop_id, {}))

@api_bp.route("/calculate_balance", methods=["POST"])
def calculate_balance():
    data = request.get_json()
    mode = data.get("mode")
    result = {}

    if mode == "optimum":
        crop_id = int(data.get("crop_id"))
        analysis_id = int(data.get("analysis_id"))
        objective = OBJECTIVES.get(crop_id)
        analysis = next((a for lst in ANALYSIS.values() for a in lst if a["id"] == analysis_id), None)

        if not analysis or not objective:
            return jsonify({"error": "Datos incompletos"}), 400

        result = {
            k: round(objective[k] - analysis.get(k, 0), 2) for k in objective
        }

    elif mode == "dual":
        primary_id = int(data.get("primary_id"))
        compare_id = int(data.get("compare_id"))
        a = next((a for lst in ANALYSIS.values() for a in lst if a["id"] == primary_id), None)
        b = next((a for lst in ANALYSIS.values() for a in lst if a["id"] == compare_id), None)

        if not a or not b:
            return jsonify({"error": "Análisis no encontrados"}), 400

        result = {
            k: round(a[k] - b[k], 2) for k in ['N', 'P', 'K']
        }

    return jsonify({"balance": result})