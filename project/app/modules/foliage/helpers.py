from .models import (
    Nutrient,
    NutrientCategory,
    leaf_analysis_nutrients,
    objective_nutrients,
)
from app.extensions import db
from decimal import Decimal
from typing import Dict
from app.modules.foliage_report.helpers import NutrientOptimizer

# Macronutrientes
macronutrients = [
    {
        "name": "Nitrógeno",
        "symbol": "N",
        "unit": "kg/ha",
        "description": "Esencial para el crecimiento vegetativo y el desarrollo de hojas",
        "category": NutrientCategory.MACRONUTRIENT,
    },
    {
        "name": "Fósforo",
        "symbol": "P",
        "unit": "kg/ha",
        "description": "Importante para el desarrollo de raíces y flores",
        "category": NutrientCategory.MACRONUTRIENT,
    },
    {
        "name": "Potasio",
        "symbol": "K",
        "unit": "kg/ha",
        "description": "Mejora la resistencia a enfermedades y el rendimiento",
        "category": NutrientCategory.MACRONUTRIENT,
    },
    {
        "name": "Calcio",
        "symbol": "Ca",
        "unit": "kg/ha",
        "description": "Fundamental para el desarrollo de células y paredes celulares",
        "category": NutrientCategory.MACRONUTRIENT,
    },
    {
        "name": "Magnesio",
        "symbol": "Mg",
        "unit": "kg/ha",
        "description": "Esencial para la fotosíntesis y el metabolismo energético",
        "category": NutrientCategory.MACRONUTRIENT,
    },
    {
        "name": "Azufre",
        "symbol": "S",
        "unit": "kg/ha",
        "description": "Importante para la formación de aminoácidos y enzimas",
        "category": NutrientCategory.MACRONUTRIENT,
    },
]

# Micronutrientes
micronutrients = [
    {
        "name": "Cobre",
        "symbol": "Cu",
        "unit": "g/ha",
        "description": "Actúa como cofactor en varias enzimas",
        "category": NutrientCategory.MICRONUTRIENT,
    },
    {
        "name": "Zinc",
        "symbol": "Zn",
        "unit": "g/ha",
        "description": "Importante para la regulación génica y el crecimiento",
        "category": NutrientCategory.MICRONUTRIENT,
    },
    {
        "name": "Manganeso",
        "symbol": "Mn",
        "unit": "g/ha",
        "description": "Participa en la fotosíntesis y el metabolismo de carbohidratos",
        "category": NutrientCategory.MICRONUTRIENT,
    },
    {
        "name": "Boro",
        "symbol": "B",
        "unit": "g/ha",
        "description": "Importante para la pared celular y el transporte de azúcares",
        "category": NutrientCategory.MICRONUTRIENT,
    },
    {
        "name": "Molibdeno",
        "symbol": "Mo",
        "unit": "g/ha",
        "description": "Esfuerzo en la fijación de nitrógeno y metabolismo del azufre",
        "category": NutrientCategory.MICRONUTRIENT,
    },
    {
        "name": "Cloro",
        "symbol": "Cl",
        "unit": "g/ha",
        "description": "Importante para la osmoregulación y el rendimiento",
        "category": NutrientCategory.MICRONUTRIENT,
    },
    {
        "name": "Hierro",
        "symbol": "Fe",
        "unit": "g/ha",
        "description": "Componente clave de las enzimas respiratorias",
        "category": NutrientCategory.MICRONUTRIENT,
    },
    {
        "name": "Silicio",
        "symbol": "Si",
        "unit": "kg/ha",
        "description": "Mejora la estructura de las plantas y su resistencia",
        "category": NutrientCategory.MICRONUTRIENT,
    },
]


def initialize_nutrients():
    """Initialize the nutrients table with default values"""
    # Verificar si ya existen nutrientes
    if Nutrient.query.count() == 0:

        try:
            # Add macronutrients
            for nutrient_data in macronutrients:
                nutrient = Nutrient(
                    name=nutrient_data["name"],
                    symbol=nutrient_data["symbol"],
                    unit=nutrient_data["unit"],
                    description=nutrient_data["description"],
                    category=nutrient_data["category"],
                )
                db.session.add(nutrient)

            # Add micronutrients
            for nutrient_data in micronutrients:
                nutrient = Nutrient(
                    name=nutrient_data["name"],
                    symbol=nutrient_data["symbol"],
                    unit=nutrient_data["unit"],
                    description=nutrient_data["description"],
                    category=nutrient_data["category"],
                )
                db.session.add(nutrient)

            db.session.commit()
            print("Nutrients initialized successfully")

        except Exception as e:
            db.session.rollback()
            print(f"Error initializing nutrients: {str(e)}")
    else:
        print("Nutrients already initialized")


def calculate_liebig_balance(
    objective_id: int, analysis_id: int
) -> Dict[str, Dict[str, Decimal]]:
    """Calculate nutrient balance and limiting nutrient using Liebig's law.

    Args:
        objective_id (int): Objective identifier.
        analysis_id (int): Leaf analysis identifier.

    Returns:
        dict: Dictionary containing standard values, foliar values, balance and
        limiting nutrient information.
    """
    # Retrieve target nutrient values for the objective
    standard: Dict[str, Decimal] = {}
    objective_rows = (
        db.session.query(
            objective_nutrients.c.nutrient_id,
            objective_nutrients.c.target_value,
        )
        .filter(objective_nutrients.c.objective_id == objective_id)
        .all()
    )
    for nutrient_id, target_value in objective_rows:
        nutrient = Nutrient.query.get(nutrient_id)
        if nutrient:
            standard[nutrient.name] = Decimal(str(target_value))

    # Retrieve foliar nutrient values for the analysis
    foliar: Dict[str, Decimal] = {}
    analysis_rows = (
        db.session.query(
            leaf_analysis_nutrients.c.nutrient_id,
            leaf_analysis_nutrients.c.value,
        )
        .filter(leaf_analysis_nutrients.c.leaf_analysis_id == analysis_id)
        .all()
    )
    for nutrient_id, value in analysis_rows:
        nutrient = Nutrient.query.get(nutrient_id)
        if nutrient:
            foliar[nutrient.name] = Decimal(str(value))

    # Calculate balance values (foliar - standard)
    balance: Dict[str, Decimal] = {}
    all_nutrients = set(standard.keys()) | set(foliar.keys())
    for name in all_nutrients:
        foliar_val = foliar.get(name, Decimal("0"))
        target_val = standard.get(name, Decimal("0"))
        balance[name] = foliar_val - target_val

    # Determine limiting nutrient using NutrientOptimizer
    limiting_info = {}
    if standard:
        optimizer = NutrientOptimizer(
            foliar,
            standard,
            {},
            {n: Decimal("0") for n in standard.keys()},
        )
        limit_name = optimizer.identificar_limitante()
        nutrient_obj = Nutrient.query.filter_by(name=limit_name).first()
        if nutrient_obj:
            limiting_info = {
                "id": nutrient_obj.id,
                "name": nutrient_obj.name,
                "symbol": nutrient_obj.symbol,
            }
        else:
            limiting_info = {"name": limit_name}

    return {
        "standard": {k: float(v) for k, v in standard.items()},
        "foliar": {k: float(v) for k, v in foliar.items()},
        "balance": {k: float(v) for k, v in balance.items()},
        "limiting_nutrient_info": limiting_info,
    }
