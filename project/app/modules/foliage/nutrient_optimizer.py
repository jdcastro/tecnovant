# Python standard library imports
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple
from datetime import datetime
from statistics import mean, stdev
import json

# Third party imports
from scipy.optimize import linprog

# Local application imports
from .models import LeafAnalysis, leaf_analysis_nutrients, CommonAnalysis, Nutrient, ProductContribution, product_contribution_nutrients, Objective, objective_nutrients
from .controller import ProductContributionView
from .helpers import macronutrients, micronutrients
from app.extensions import db



class NutrientOptimizer:
    """
    Clase que optimiza la aplicación de productos para satisfacer los requerimientos de nutrientes de un cultivo,
    basada en la Ley del Mínimo de Liebig y programación lineal.
    """

    def __init__(self, nutrientes_actuales: Dict[str, Decimal], demandas_ideales: Dict[str, Decimal], 
                 productos_contribuciones: Dict[str, Dict[str, Decimal]], coeficientes_variacion: Dict[str, Decimal]):
        """
        Inicializa el optimizador de nutrientes.

        :param nutrientes_actuales: Diccionario con los niveles actuales de nutrientes (kg/ha o g/ha).
        :param demandas_ideales: Diccionario con los niveles ideales de nutrientes (kg/ha o g/ha).
        :param productos_contribuciones: Diccionario con los productos y sus contribuciones por nutriente.
        :param coeficientes_variacion: Diccionario con los coeficientes de variación por nutriente.
        """
        self.nutrientes_actuales = nutrientes_actuales
        self.demandas_ideales = demandas_ideales
        self.productos_contribuciones = productos_contribuciones
        self.coeficientes_variacion = coeficientes_variacion
        self.nutrientes = list(demandas_ideales.keys())
        self.productos = list(productos_contribuciones.keys())

    def calcular_ajustes(self) -> Dict[str, Decimal]:
        """
        Calcula los ajustes necesarios para cada nutriente usando la Ley de Liebig adaptada.
        """
        ajustes = {}
        for nutriente in self.nutrientes:
            actual = self.nutrientes_actuales.get(nutriente, Decimal('0.0'))
            ideal = self.demandas_ideales[nutriente]
            if actual < ideal:
                p = (actual / ideal) * Decimal('100.0') if ideal > 0 else Decimal('0.0')
                i = ((Decimal('100.0') - p) * self.coeficientes_variacion[nutriente] / Decimal('100.0')).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
                ajustes[nutriente] = (ideal - actual) * i  # Cantidad absoluta a ajustar
            else:
                ajustes[nutriente] = Decimal('0.0')
        return ajustes

    def identificar_limitante(self) -> str:
        """
        Identifica el nutriente más limitante según la Ley de Liebig.
        """
        porcentajes = {
            nutriente: (self.nutrientes_actuales.get(nutriente, Decimal('0.0')) / self.demandas_ideales[nutriente]) * Decimal('100.0')
            if self.demandas_ideales[nutriente] > 0 else Decimal('0.0')
            for nutriente in self.nutrientes
        }
        return min(porcentajes, key=porcentajes.get)

    def optimizar_productos(self) -> Tuple[Dict[str, Decimal], Dict[str, Decimal]]:
        """
        Optimiza las cantidades de productos a aplicar usando programación lineal.
        
        :return: Diccionario con las cantidades de productos y los nutrientes aportados.
        """
        ajustes = self.calcular_ajustes()
        
        # Coeficientes de la función objetivo (minimizar la suma de productos)
        c = [1] * len(self.productos)

        # Matriz de restricciones (negativa para linprog)
        A_eq = []
        b_eq = []
        for nutriente in self.nutrientes:
            if ajustes[nutriente] > 0:
                fila = []
                for prod in self.productos:
                    contrib = self.productos_contribuciones[prod].get(nutriente, Decimal('0.0'))
                    fila.append(-float(contrib))  # Negativo para linprog
                A_eq.append(fila)
                b_eq.append(-float(ajustes[nutriente]))  # Negativo para linprog

        # Límites (cantidades >= 0)
        bounds = [(0, None)] * len(self.productos)

        # Resolver optimización
        res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
        if not res.success:
            raise ValueError("No se pudo optimizar la aplicación de productos.")

        # Resultados: cantidades de productos
        cantidades = {self.productos[i]: Decimal(str(round(x, 2))) for i, x in enumerate(res.x)}

        # Calcular nutrientes aportados
        nutrientes_aportados = {nutriente: Decimal('0.0') for nutriente in self.nutrientes}
        for prod, cantidad in cantidades.items():
            for nutriente, contrib in self.productos_contribuciones[prod].items():
                nutrientes_aportados[nutriente] += contrib * cantidad

        return cantidades, nutrientes_aportados

    def generar_recomendacion(self, lot_id: int) -> str:
        """
        Genera una recomendación para aplicar en el lote.
        
        :param lot_id: ID del lote donde se aplicará la recomendación.
        :return: Texto de la recomendación.
        """
        cantidades, nutrientes_aportados = self.optimizar_productos()
        lineas = [f"Aplicar en el lote {lot_id}:"]
        for prod, cantidad in cantidades.items():
            if cantidad > 0:
                lineas.append(f"- {cantidad} unidades de {prod}")
        lineas.append("Nutrientes aportados:")
        for nutriente, cantidad in nutrientes_aportados.items():
            unidad = "kg/ha" if nutriente in [n["name"] for n in macronutrients] else "g/ha"
            lineas.append(f"- {nutriente}: {cantidad} {unidad}")
        return "\n".join(lineas)


# # # Datos de ejemplo basados en los nutrientes proporcionados
# macronutrients = [
#     {"name": "Nitrógeno", "symbol": "N", "unit": "kg/ha", "category": "MACRONUTRIENT"},
#     {"name": "Fósforo", "symbol": "P", "unit": "kg/ha", "category": "MACRONUTRIENT"},
#     {"name": "Potasio", "symbol": "K", "unit": "kg/ha", "category": "MACRONUTRIENT"},
#     {"name": "Calcio", "symbol": "Ca", "unit": "kg/ha", "category": "MACRONUTRIENT"},
#     {"name": "Magnesio", "symbol": "Mg", "unit": "kg/ha", "category": "MACRONUTRIENT"},
#     {"name": "Azufre", "symbol": "S", "unit": "kg/ha", "category": "MACRONUTRIENT"},
# ]

# micronutrients = [
#     {"name": "Cobre", "symbol": "Cu", "unit": "g/ha", "category": "MICRONUTRIENT"},
#     {"name": "Zinc", "symbol": "Zn", "unit": "g/ha", "category": "MICRONUTRIENT"},
#     {"name": "Manganeso", "symbol": "Mn", "unit": "g/ha", "category": "MICRONUTRIENT"},
#     {"name": "Boro", "symbol": "B", "unit": "g/ha", "category": "MICRONUTRIENT"},
#     {"name": "Molibdeno", "symbol": "Mo", "unit": "g/ha", "category": "MICRONUTRIENT"},
#     {"name": "Cloro", "symbol": "Cl", "unit": "g/ha", "category": "MICRONUTRIENT"},
#     {"name": "Hierro", "symbol": "Fe", "unit": "g/ha", "category": "MICRONUTRIENT"},
#     {"name": "Silicio", "symbol": "Si", "unit": "kg/ha", "category": "MICRONUTRIENT"},
# ]

# # Ejemplo de uso
# nutrientes_actuales = {
#     "Nitrógeno": Decimal("50.0"),  # kg/ha
#     "Fósforo": Decimal("20.0"),    # kg/ha
#     "Potasio": Decimal("80.0"),    # kg/ha
#     "Cobre": Decimal("100.0"),     # g/ha
#     "Zinc": Decimal("50.0")        # g/ha
# }

# demandas_ideales = {
#     "Nitrógeno": Decimal("100.0"),  # kg/ha
#     "Fósforo": Decimal("50.0"),     # kg/ha
#     "Potasio": Decimal("90.0"),     # kg/ha
#     "Cobre": Decimal("150.0"),      # g/ha
#     "Zinc": Decimal("80.0")         # g/ha
# }

# productos_contribuciones = {
#     "Fertilizante A": {"Nitrógeno": Decimal("10.0"), "Fósforo": Decimal("5.0"), "Potasio": Decimal("2.0")},
#     "Fertilizante B": {"Nitrógeno": Decimal("5.0"), "Fósforo": Decimal("15.0"), "Cobre": Decimal("20.0")},
#     "Fertilizante C": {"Zinc": Decimal("30.0"), "Cobre": Decimal("10.0")}
# }

# coeficientes_variacion = {
#     "Nitrógeno": Decimal("0.5"),
#     "Fósforo": Decimal("0.3"),
#     "Potasio": Decimal("0.4"),
#     "Cobre": Decimal("0.2"),
#     "Zinc": Decimal("0.25")
# }

# # Instanciar y usar la clase
# optimizador = NutrientOptimizer(nutrientes_actuales, demandas_ideales, productos_contribuciones, coeficientes_variacion)
# limitante = optimizador.identificar_limitante()
# print(f"Nutriente limitante: {limitante}")

# recomendacion = optimizador.generar_recomendacion(lot_id=1)
# print(recomendacion)


def calcular_cv_nutriente(lot_id, nutriente_name):
    """Determinar los Coeficientes de Variación """
    # Obtener valores históricos de LeafAnalysis para el lote
    valores = db.session.query(leaf_analysis_nutrients.c.value).join(LeafAnalysis).join(CommonAnalysis).filter(
        CommonAnalysis.lot_id == lot_id,
        leaf_analysis_nutrients.c.nutrient_id == Nutrient.query.filter_by(name=nutriente_name).first().id
    ).all()
    valores = [v[0] for v in valores]
    if len(valores) < 2:
        return Decimal('0.5')  # Valor por defecto si no hay suficientes datos
    mu = mean(valores)
    sigma = stdev(valores)
    return Decimal(str(sigma / mu)).quantize(Decimal('0.01'))

# ejemplo. 
# cv_nitrogeno = calcular_cv_nutriente(lot_id=1, nutriente_name="Nitrógeno")
# print(f"CV Nitrógeno: {cv_nitrogeno}")

# Calculo por ajuste dinámico. 
# Datos históricos: Calcula el CV estadístico si hay suficientes análisis previos.
# Valores por defecto: Usa estándares agrícolas si no hay datos.
# Ajuste dinámico: Permite que un usuario (ej., agrónomo) modifique los CV según observaciones locales.

def determinar_coeficientes_variacion(lot_id: int) -> Dict[str, Decimal]:
    coeficientes = {}
    nutrientes = [n["name"] for n in macronutrients + micronutrients]
    for nutriente in nutrientes:
        cv = calcular_cv_nutriente(lot_id, nutriente)
        if cv == Decimal('0.5'):  # Valor por defecto si no hay datos
            # Asignar valores basados en literatura
            if nutriente in ["Nitrógeno"]:
                cv = Decimal("0.5")
            elif nutriente in ["Fósforo"]:
                cv = Decimal("0.3")
            elif nutriente in ["Potasio"]:
                cv = Decimal("0.4")
            elif nutriente in ["Cobre", "Zinc"]:
                cv = Decimal("0.25")
            else:
                cv = Decimal("0.3")  # Default genérico
        coeficientes[nutriente] = cv
    return coeficientes


def contribuciones_de_producto():
    """Contribuciones de producto """
    product_contributions = ProductContribution.query.all()
    
    result = {}
    
    for pc in product_contributions:
        product_name = pc.product.name
        
        if product_name not in result:
            result[product_name] = {}
        
        nutrient_contributions = (
            db.session.query(product_contribution_nutrients)
            .filter_by(product_contribution_id=pc.id)
            .all()
        )
        
        for contribution in nutrient_contributions:
            nutrient = Nutrient.query.get(contribution.nutrient_id)
            result[product_name][nutrient.name] = Decimal(str(contribution.contribution))
    
    return result




##################################################################
class ObjectiveResource:
    def get_objective_list(self):
        objectives = Objective.query.all()
        crop_data = self._process_objectives_by_crop(objectives)
        return CropResponse(crop_data)

    def _serialize_objective(self, objective):
        """Serialize an Objective object to a dictionary (unchanged from your code)"""
        nutrient_targets = (
            db.session.query(objective_nutrients)
            .filter_by(objective_id=objective.id)
            .all()
        )
        nutrient_targets_dict = [
            {
                "nutrient_id": target.nutrient_id,
                "target_value": Decimal(str(target.target_value)),  # Convert to Decimal
                "nutrient_name": Nutrient.query.get(target.nutrient_id).name,
                "nutrient_symbol": Nutrient.query.get(target.nutrient_id).symbol,
                "nutrient_unit": Nutrient.query.get(target.nutrient_id).unit,
            }
            for target in nutrient_targets
        ]
        return {
            "id": objective.id,
            "crop_id": objective.crop_id,
            "crop_name": objective.crop.name,
            "target_value": Decimal(str(objective.target_value)),
            "protein": Decimal(str(objective.protein)),
            "rest": Decimal(str(objective.rest)),
            "created_at": objective.created_at.isoformat(),
            "updated_at": objective.updated_at.isoformat(),
            "nutrient_targets": nutrient_targets_dict,
        }

    def _process_objectives_by_crop(self, objectives):
        """Process objectives into a dictionary grouped by crop name with multiple objectives"""
        crop_dict = {}
        for obj in objectives:
            serialized = self._serialize_objective(obj)
            crop_name = serialized["crop_name"].lower()  # e.g., 'arroz', 'papa'
            
            # Initialize crop entry as a list if not present
            if crop_name not in crop_dict:
                crop_dict[crop_name] = []
            
            # Simplify nutrient targets into a dict for easier access
            nutrient_dict = {
                target["nutrient_name"]: target["target_value"]
                for target in serialized["nutrient_targets"]
            }
            # Add objective data to the crop's list
            crop_dict[crop_name].append({
                "id": serialized["id"],
                "created_at": serialized["created_at"],
                "updated_at": serialized["updated_at"],
                "nutrients": nutrient_dict
            })
        
        return crop_dict

class CropResponse:
    """Custom response class to allow accessing crop data like response.arroz"""
    def __init__(self, crop_data):
        self.crop_data = crop_data
        # Dynamically set attributes for each crop
        for crop_name in crop_data:
            setattr(self, crop_name, CropObjectives(crop_data[crop_name]))

    def get_json(self):
        """Return the full crop data as JSON"""
        return json.dumps(self.crop_data, ensure_ascii=False, indent=4, default=str)

class CropObjectives:
    """Class to handle multiple objectives for a single crop"""
    def __init__(self, objectives):
        self.objectives = objectives  # List of objectives for this crop

    def get(self, index=None, id=None):
        """Access a specific objective by index or id"""
        if id is not None:
            for obj in self.objectives:
                if obj["id"] == id:
                    return CropData(obj["nutrients"])
            raise ValueError(f"No objective found with id {id}")
        if index is not None:
            if 0 <= index < len(self.objectives):
                return CropData(self.objectives[index]["nutrients"])
            raise IndexError(f"Index {index} out of range for {len(self.objectives)} objectives")
        # Default: return the most recent objective (based on updated_at)
        sorted_objectives = sorted(self.objectives, key=lambda x: x["updated_at"], reverse=True)
        return CropData(sorted_objectives[0]["nutrients"])

    def all(self):
        """Return all objectives as a list of CropData objects"""
        return [CropData(obj["nutrients"]) for obj in self.objectives]

    def get_json(self):
        """Return all objectives as JSON"""
        return json.dumps(self.objectives, ensure_ascii=False, indent=4, default=str)

class CropData:
    """Helper class to represent nutrient data for a single objective"""
    def __init__(self, nutrient_data):
        self.nutrient_data = nutrient_data

    def get_json(self):
        """Return nutrient data as JSON"""
        return json.dumps(self.nutrient_data, ensure_ascii=False, indent=4, default=str)

    def __str__(self):
        """String representation for printing"""
        return str({k: str(v) for k, v in self.nutrient_data.items()})

########################################################

# leaf_analyses

class LeafAnalysisResource:
    def get_leaf_analysis_list(self):
        leaf_analyses = LeafAnalysis.query.all()
        
        # Process leaf analyses into a structure grouped by common_analysis_id
        analysis_data = self._process_leaf_analyses_by_common_id(leaf_analyses)
        return LeafAnalysisResponse(analysis_data)

    def _serialize_leaf_analysis(self, leaf_analysis):
        """Serializa un objeto LeafAnalysis a un diccionario."""
        nutrient_values = (
            db.session.query(leaf_analysis_nutrients)
            .filter_by(leaf_analysis_id=leaf_analysis.id)
            .all()
        )
        nutrient_values_dict = [
            {
                "nutrient_id": nv.nutrient_id,
                "value": Decimal(str(nv.value)),  # Convert to Decimal
                "nutrient_name": Nutrient.query.get(nv.nutrient_id).name,
                "nutrient_symbol": Nutrient.query.get(nv.nutrient_id).symbol,
                "nutrient_unit": Nutrient.query.get(nv.nutrient_id).unit,
            }
            for nv in nutrient_values
        ]
        return {
            "id": leaf_analysis.id,
            "common_analysis_id": leaf_analysis.common_analysis_id,
            "created_at": leaf_analysis.created_at.isoformat(),
            "updated_at": leaf_analysis.updated_at.isoformat(),
            "nutrient_values": nutrient_values_dict,
        }

    def _process_leaf_analyses_by_common_id(self, leaf_analyses):
        """Process leaf analyses into a dictionary grouped by common_analysis_id."""
        analysis_dict = {}
        for leaf_analysis in leaf_analyses:
            serialized = self._serialize_leaf_analysis(leaf_analysis)
            common_id = str(serialized["common_analysis_id"])  # Convert to string for attribute access
            
            # Initialize entry as a list if not present
            if common_id not in analysis_dict:
                analysis_dict[common_id] = []
            
            # Simplify nutrient values into a dict
            nutrient_dict = {
                nutrient["nutrient_name"]: nutrient["value"]
                for nutrient in serialized["nutrient_values"]
            }
            # Add analysis data to the common_analysis_id's list
            analysis_dict[common_id].append({
                "id": serialized["id"],
                "created_at": serialized["created_at"],
                "updated_at": serialized["updated_at"],
                "nutrients": nutrient_dict
            })
        
        return analysis_dict

class LeafAnalysisResponse:
    """Custom response class to allow accessing leaf analyses like response.common_analysis_id.<id>"""
    def __init__(self, analysis_data):
        self.analysis_data = analysis_data
        # Dynamically create a nested object for common_analysis_id
        self.common_analysis_id = CommonAnalysisContainer(analysis_data)

    def get_json(self):
        """Return the full analysis data as JSON"""
        return json.dumps(self.analysis_data, ensure_ascii=False, indent=4, default=str)

class CommonAnalysisContainer:
    """Container for accessing leaf analyses by common_analysis_id"""
    def __init__(self, analysis_data):
        self.analysis_data = analysis_data
        # Dynamically set attributes for each common_analysis_id
        for common_id in analysis_data:
            setattr(self, common_id, LeafAnalyses(self.analysis_data[common_id]))

class LeafAnalyses:
    """Class to handle multiple leaf analyses for a single common_analysis_id"""
    def __init__(self, analyses):
        self.analyses = analyses  # List of leaf analyses for this common_analysis_id

    def get(self, index=None, id=None):
        """Access a specific leaf analysis by index or id"""
        if id is not None:
            for analysis in self.analyses:
                if analysis["id"] == id:
                    return LeafAnalysisData(analysis["nutrients"])
            raise ValueError(f"No leaf analysis found with id {id}")
        if index is not None:
            if 0 <= index < len(self.analyses):
                return LeafAnalysisData(self.analyses[index]["nutrients"])
            raise IndexError(f"Index {index} out of range for {len(self.analyses)} analyses")
        # Default: return the most recent analysis (based on updated_at)
        sorted_analyses = sorted(self.analyses, key=lambda x: x["updated_at"], reverse=True)
        return LeafAnalysisData(sorted_analyses[0]["nutrients"])

    def all(self):
        """Return all analyses as a list of LeafAnalysisData objects"""
        return [LeafAnalysisData(analysis["nutrients"]) for analysis in self.analyses]

    def get_json(self):
        """Return all analyses as JSON"""
        return json.dumps(self.analyses, ensure_ascii=False, indent=4, default=str)

class LeafAnalysisData:
    """Helper class to represent nutrient data for a single leaf analysis"""
    def __init__(self, nutrient_data):
        self.nutrient_data = nutrient_data

    def get_json(self):
        """Return nutrient data as JSON"""
        return json.dumps(self.nutrient_data, ensure_ascii=False, indent=4, default=str)

    def __str__(self):
        """String representation for printing"""
        return str({k: str(v) for k, v in self.nutrient_data.items()})
    

