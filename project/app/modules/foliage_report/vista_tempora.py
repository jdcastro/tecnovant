
@web.route("/vista_reporte/<int:report_id>")
@jwt_required()
def vista_reporte(report_id):
    claims = get_jwt()
    context = {
        "dashboard": True,
        "title": "Ver Informe de Análisis",
        "description": "Detalles del informe.",
        "author": "Johnny De Castro",
        "site_title": "Ver Informe",
        "data_menu": get_dashboard_menu(),
    }

    view = ReportView()
    response = view.get(report_id)
    data_response = response.get_json()

    analysis_data = data_response.get("analysisData", {})
    foliar_data = analysis_data.get("foliar", {})
    soil_data = analysis_data.get("soil") or {}

    optimal_levels = data_response.get("optimalLevels", {})
    soil_optimal = optimal_levels.get("soil") or {}

    foliar_chart_data = data_response.get("foliarChartData", [])
    soil_chart_data = data_response.get("soilChartData", [])
    historical_data = data_response.get("historicalData", [])

    nutrient_names = {
        "nitrógeno": "N",
        "fósforo": "P",
        "potasio": "K",
        "calcio": "Ca",
        "magnesio": "Mg",
        "azufre": "S",
        "hierro": "Fe",
        "manganeso": "Mn",
        "zinc": "Zn",
        "cobre": "Cu",
        "boro": "B",
        "molibdeno": "Mo",
        "silicio": "Si",
        "ph": "pH",
        "materiaOrganica": "MO",
        "cic": "CIC"
    }


    def get_nutrient_status(actual, min_val, max_val):
        if actual < min_val:
            return "deficiente"
        if actual > max_val:
            return "excesivo"
        return "óptimo"

    def get_status_color(status):
        match status:
            case "deficiente":
                return "text-red-500"
            case "excesivo":
                return "text-yellow-500"
            case "óptimo":
                return "text-green-500"
            case _:
                return ""

    def get_status_icon(status):
        icons = {
            "deficiente": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                          'fill="none" stroke="currentColor" stroke-width="2" '
                          'stroke-linecap="round" stroke-linejoin="round" '
                          'class="h-4 w-4 text-red-500">'
                          '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 '
                          '16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"></polygon>'
                          '<line x1="12" y1="8" x2="12" y2="12"></line>'
                          '<line x1="12" y1="16" x2="12.01" y2="16"></line>'
                          '</svg>',
            "excesivo": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                        'fill="none" stroke="currentColor" stroke-width="2" '
                        'stroke-linecap="round" stroke-linejoin="round" '
                        'class="h-4 w-4 text-yellow-500">'
                        '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 '
                        '16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"></polygon>'
                        '<line x1="12" y1="8" x2="12" y2="12"></line>'
                        '<line x1="12" y1="16" x2="12.01" y2="16"></line>'
                        '</svg>',
            "óptimo": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                      'fill="none" stroke="currentColor" stroke-width="2" '
                      'stroke-linecap="round" stroke-linejoin="round" '
                      'class="h-4 w-4 text-green-500">'
                      '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>'
                      '<polyline points="12 2 2 7.86 12 12"></polyline>'
                      '<line x1="12" y1="16" x2="12.01" y2="16"></line>'
                      '</svg>',
        }
        return icons.get(status, "")

    def find_limiting_nutrient():
        limiting_nutrient = None
        lowest_percentage = 100

        for nutrient, value in foliar_data.items():
            if nutrient in optimal_levels:
                min_val = optimal_levels[nutrient].get("min")
                max_val = optimal_levels[nutrient].get("max")
                if min_val is not None and max_val is not None:
                    optimal_mid = (min_val + max_val) / 2
                    percentage = (value / optimal_mid) * 100
                    if percentage < lowest_percentage and percentage < 90:
                        lowest_percentage = percentage
                        limiting_nutrient = {
                            "name": nutrient,
                            "value": value,
                            "optimal": optimal_mid,
                            "percentage": percentage,
                            "type": "foliar",
                        }

        for nutrient, value in soil_data.items():
            if nutrient in soil_optimal and nutrient != "ph":
                min_val = soil_optimal[nutrient].get("min")
                max_val = soil_optimal[nutrient].get("max")
                if min_val is not None and max_val is not None:
                    optimal_mid = (min_val + max_val) / 2
                    percentage = (value / optimal_mid) * 100
                    if percentage < lowest_percentage and percentage < 90:
                        lowest_percentage = percentage
                        limiting_nutrient = {
                            "name": nutrient,
                            "value": value,
                            "optimal": optimal_mid,
                            "percentage": percentage,
                            "type": "soil",
                        }

        return limiting_nutrient

    def generate_recommendations():
        recommendations = []
        limiting = find_limiting_nutrient()

        if limiting:
            nutrient_label = nutrient_names.get(limiting["name"], limiting["name"])
            recommendations.append({
                "title": f"Corregir deficiencia de {nutrient_label}",
                "description": (
                    f"{nutrient_label} es el nutriente limitante según la Ley de Liebig. "
                    f"Está al {round(limiting['percentage'], 1)}% del nivel óptimo."
                ),
                "priority": "alta",
                "action": (
                    f"Aplicar fertilizante foliar rico en {nutrient_label}"
                    if limiting["type"] == "foliar"
                    else f"Incorporar {nutrient_label} al suelo mediante fertilización"
                ),
            })

        # Revisión pH
        ph_val = soil_data.get("ph")
        ph_opt = soil_optimal.get("ph")
        if ph_val is not None and ph_opt:
            ph_status = get_nutrient_status(ph_val, ph_opt["min"], ph_opt["max"])
            if ph_status != "óptimo":
                recommendations.append({
                    "title": (
                        "Corregir acidez del suelo"
                        if ph_status == "deficiente"
                        else "Reducir alcalinidad del suelo"
                    ),
                    "description": (
                        f"El pH actual ({ph_val}) está "
                        f"{'por debajo' if ph_status == 'deficiente' else 'por encima'} "
                        f"del rango óptimo."
                    ),
                    "priority": "media",
                    "action": (
                        "Aplicar cal agrícola para elevar el pH"
                        if ph_status == "deficiente"
                        else "Aplicar azufre elemental o materia orgánica para reducir el pH"
                    ),
                })

        # Revisión materia orgánica
        mo_val = soil_data.get("materiaOrganica")
        mo_opt = soil_optimal.get("materiaOrganica")
        if mo_val is not None and mo_opt:
            mo_status = get_nutrient_status(mo_val, mo_opt["min"], mo_opt["max"])
            if mo_status == "deficiente":
                recommendations.append({
                    "title": "Aumentar materia orgánica",
                    "description": (
                        f"El nivel de materia orgánica ({mo_val}%) está por debajo del óptimo."
                    ),
                    "priority": "media",
                    "action": "Incorporar compost, estiércol bien descompuesto o abonos verdes",
                })

        return recommendations

    limiting_nutrient = find_limiting_nutrient()
    recommendations = generate_recommendations()

    return render_template(
        "ver_reporte2.j2",
        **context,
        request=request,
        analysisData=analysis_data,
        optimalLevels=optimal_levels,
        foliarChartData=foliar_chart_data,
        soilChartData=soil_chart_data,
        historicalData=historical_data,
        nutrientNames=nutrient_names,
        limitingNutrient=limiting_nutrient,
        recommendations=recommendations,
        getNutrientStatus=get_nutrient_status,
        getStatusColor=get_status_color,
        getStatusIcon=get_status_icon
    )
