# Python standard library imports
from decimal import Decimal, ROUND_HALF_UP

class LeyLiebig:
    """
    Clase que implementa la Ley del Mínimo de Liebig para el cálculo de nutrientes en un cultivo.
    
    La Ley del Mínimo establece que el crecimiento de una planta está limitado por el nutriente más escaso en relación
    con sus necesidades, en lugar de depender de la cantidad total de nutrientes disponibles.
    
    Esta clase permite evaluar el estado nutricional de un cultivo comparando los niveles actuales con la demanda ideal,
    identificando el nutriente más limitante y proponiendo ajustes para optimizar su disponibilidad.
    """

    def __init__(self, nutrientes: dict, demanda_planta: Decimal):
        """
        Inicializa la clase con los nutrientes disponibles y la demanda ideal de la planta.
        
        :param nutrientes: Diccionario con los nutrientes y sus valores actuales en el suelo.
        :param demanda_planta: Valor total de la demanda nutricional ideal de la planta.
        """
        self.nutrientes = nutrientes
        self.demanda_planta = Decimal(demanda_planta)

    def calcular_p(self, valor_registro: Decimal) -> Decimal:
        """
        Calcula el porcentaje de suficiencia de un nutriente con respecto a la demanda de la planta.
        
        :param valor_registro: Valor actual del nutriente en el suelo.
        :return: Porcentaje de suficiencia del nutriente con respecto a la demanda ideal.
        """
        if self.demanda_planta == 0:
            return Decimal('0.00')
        return (Decimal(valor_registro) / self.demanda_planta) * Decimal('100.00')

    def calcular_i(self, mineral_p: Decimal, mineral_cv: Decimal) -> Decimal:
        """
        Calcula la cantidad de ajuste necesario para un nutriente limitante en función de su coeficiente de variación.
        
        :param mineral_p: Porcentaje de suficiencia del nutriente.
        :param mineral_cv: Coeficiente de variación del nutriente.
        :return: Cantidad de ajuste necesaria para alcanzar el nivel óptimo.
        """
        if mineral_p > Decimal('100.00'):
            result = ((mineral_p - Decimal('100.00')) * mineral_cv / Decimal('100.00'))
        else:
            result = ((Decimal('100.00') - mineral_p) * mineral_cv / Decimal('100.00'))
        return result.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)

    def calcular_r(self, mineral_p: Decimal, mineral_i: Decimal) -> Decimal:
        """
        Determina el nivel corregido del nutriente después del ajuste.
        
        :param mineral_p: Porcentaje de suficiencia del nutriente.
        :param mineral_i: Cantidad de ajuste aplicada al nutriente.
        :return: Nivel corregido del nutriente en el suelo.
        """
        if mineral_p > Decimal('100.00'):
            return (mineral_p - mineral_i).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
        return (mineral_p + mineral_i).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)

    def calcular_nutriente_limite(self, valores_registro: dict) -> str:
        """
        Identifica el nutriente más limitante según la Ley del Mínimo de Liebig.
        
        El nutriente limitante es aquel que tiene el menor porcentaje de suficiencia.
        
        :param valores_registro: Diccionario con los valores actuales de los nutrientes en el suelo.
        :return: Nombre del nutriente más limitante.
        """
        valores_p = {mineral: self.calcular_p(valor) for mineral, valor in valores_registro.items()}
        return min(valores_p, key=valores_p.get)  # Devuelve el nutriente con el menor porcentaje de suficiencia

    def calcular_nutrientes(self, valores_registro: dict, valores_cv: dict) -> dict:
        """
        Calcula los ajustes necesarios para los nutrientes del cultivo.
        
        La corrección se aplica únicamente al nutriente más limitante para respetar la Ley del Mínimo de Liebig.
        
        :param valores_registro: Diccionario con los valores actuales de los nutrientes en el suelo.
        :param valores_cv: Diccionario con los coeficientes de variación de cada nutriente.
        :return: Diccionario con los valores de suficiencia (p), ajuste necesario (i) y nivel corregido (r) de cada nutriente.
        """
        nutriente_limitante = self.calcular_nutriente_limite(valores_registro)
        nutrientes = {}
        for mineral, valor_registro in valores_registro.items():
            p = self.calcular_p(valor_registro)
            i = self.calcular_i(p, valores_cv[mineral]) if mineral == nutriente_limitante else Decimal('0.00')
            r = self.calcular_r(p, i)
            nutrientes[mineral] = {'p': p, 'i': i, 'r': r}
        return nutrientes
