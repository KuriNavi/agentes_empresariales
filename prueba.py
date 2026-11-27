import pandas as pd
from crewai import Agent, Task, Crew, Process, LLM
from datetime import date
#defs

def sin_contradicciones(resultado):
    texto = resultado.raw.lower()  
    if metricas["margen_q3"] > 0 and ("márgenes negativos" in texto or "pérdidas unitarias" in texto):
        return (False, "El margen bruto Q3 es +34,9%. No puedes afirmar pérdidas ni márgenes negativos. Reescribe.")
    return (True, resultado)

def cargar_datos(ruta):
    df = pd.read_excel(ruta)
    df.columns = [
        str(columna).strip().lower()
        for columna in df.columns
    ]

    if df.columns.duplicated().any():
        raise ValueError(
            "Hay columnas duplicadas después de normalizar sus nombres."
        )

    return validar_datos(df)

def validar_datos(df):
    df = df.copy()

    necesarias = {
        "mes", "ventas", "coste_ventas",
        "gasto_marketing", "clientes_nuevos",
        "pedidos", "pedidos_retrasados", "renuncias"
    }

    faltan = necesarias - set(df.columns)

    if faltan:
        raise ValueError(
            f"Faltan columnas en el Excel: {sorted(faltan)}"
        )

    # Normalizar los nombres de los meses.
    df["mes"] = (
        df["mes"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    if df["mes"].isna().any() or df["mes"].eq("").any():
        raise ValueError(
            "Hay meses vacíos o sin identificar."
        )

    meses_validos = {
        "ene", "feb", "mar", "abr", "may", "jun",
        "jul", "ago", "sep", "oct", "nov", "dic"
    }

    meses_desconocidos = set(df["mes"]) - meses_validos

    if meses_desconocidos:
        raise ValueError(
            f"Meses desconocidos: {sorted(meses_desconocidos)}"
        )

    if df["mes"].duplicated().any():
        duplicados = df.loc[
            df["mes"].duplicated(keep=False), "mes"
        ].unique()

        raise ValueError(
            f"Hay meses duplicados: {sorted(duplicados)}"
        )

    numericas = [
        "ventas", "coste_ventas", "gasto_marketing",
        "clientes_nuevos", "pedidos",
        "pedidos_retrasados", "renuncias"
    ]

    for columna in numericas:
        try:
            df[columna] = pd.to_numeric(
                df[columna], errors="raise"
            )
        except (ValueError, TypeError):
            raise ValueError(
                f"La columna '{columna}' contiene "
                "valores que no son numéricos."
            )

        if df[columna].isna().any():
            raise ValueError(
                f"La columna '{columna}' contiene valores vacíos."
            )

        if not df[columna].map(
            lambda valor: pd.notna(valor)
            and abs(valor) != float("inf")
        ).all():
            raise ValueError(
                f"La columna '{columna}' contiene "
                "valores infinitos o inválidos."
            )

    no_negativas = [
        "ventas", "coste_ventas", "gasto_marketing",
        "clientes_nuevos", "pedidos",
        "pedidos_retrasados", "renuncias"
    ]

    for columna in no_negativas:
        if (df[columna] < 0).any():
            raise ValueError(
                f"La columna '{columna}' contiene "
                "valores negativos."
            )
    cantidades = [
        "clientes_nuevos", "pedidos",
        "pedidos_retrasados", "renuncias"
    ]

    for columna in cantidades:
        if (df[columna] % 1 != 0).any():
            raise ValueError(
                f"La columna '{columna}' contiene "
                "cantidades no enteras."
            )
    if (df["pedidos_retrasados"] > df["pedidos"]).any():
        raise ValueError(
            "Hay meses donde los pedidos retrasados "
            "superan el total de pedidos."
        )

    meses_requeridos = {
        "abr", "may", "jun",
        "jul", "ago", "sep"
    }

    faltan_meses = meses_requeridos - set(df["mes"])

    if faltan_meses:
        raise ValueError(
            f"Faltan meses necesarios para el análisis: "
            f"{sorted(faltan_meses)}"
        )

    for trimestre in [
        ["abr", "may", "jun"],
        ["jul", "ago", "sep"]
    ]:
        periodo = df[df["mes"].isin(trimestre)]

        if periodo["clientes_nuevos"].sum() == 0:
            raise ValueError(
                "No se puede calcular el CAC: "
                "hay un trimestre sin clientes nuevos."
            )

        if periodo["ventas"].sum() == 0:
            raise ValueError(
                "No se puede calcular el margen bruto: "
                "hay un trimestre sin ventas."
            )

    return df




def calcular_metricas(df):
    # Separar los datos por trimestre.
    q2 = df[df["mes"].isin(["abr", "may", "jun"])]
    q3 = df[df["mes"].isin(["jul", "ago", "sep"])]

    if len(q2) != 3 or len(q3) != 3:
        raise ValueError(
            "Se necesitan los tres meses completos de Q2 y Q3."
        )


    datos_q2 = q2.sum(numeric_only=True)
    datos_q3 = q3.sum(numeric_only=True)
    if datos_q2["pedidos"] == 0 or datos_q3["pedidos"] == 0:
        raise ValueError(
        "No se puede calcular la tasa de retrasos "
        "si un trimestre no tiene pedidos."
        ) 
    
    
    ventas_q2 = datos_q2["ventas"]
    ventas_q3 = datos_q3["ventas"]

    costes_q2 = datos_q2["coste_ventas"]
    costes_q3 = datos_q3["coste_ventas"]

    marketing_q2 = datos_q2["gasto_marketing"]
    marketing_q3 = datos_q3["gasto_marketing"]

    clientes_q2 = datos_q2["clientes_nuevos"]
    clientes_q3 = datos_q3["clientes_nuevos"]

    pedidos_q2 = datos_q2["pedidos"]
    pedidos_q3 = datos_q3["pedidos"]

    retrasos_q2 = datos_q2["pedidos_retrasados"]
    retrasos_q3 = datos_q3["pedidos_retrasados"]

 
    beneficio_bruto_q2 = ventas_q2 - costes_q2
    beneficio_bruto_q3 = ventas_q3 - costes_q3


    margen_q2 = beneficio_bruto_q2 / ventas_q2 * 100
    margen_q3 = beneficio_bruto_q3 / ventas_q3 * 100

 
    cac_q2 = marketing_q2 / clientes_q2
    cac_q3 = marketing_q3 / clientes_q3


    tasa_retrasos_q2 = retrasos_q2 / pedidos_q2 * 100
    tasa_retrasos_q3 = retrasos_q3 / pedidos_q3 * 100
    if not (0 <= tasa_retrasos_q3 <= 100):
            raise ValueError(f"Tasa de retrasos imposible: {tasa_retrasos_q3}")
    return {
   
        "ventas_q2": ventas_q2,
        "ventas_q3": ventas_q3,
        "var_ventas": calcular_variacion_porcentual(
            ventas_q2, ventas_q3
        ),

  
        "coste_ventas_q2": costes_q2,
        "coste_ventas_q3": costes_q3,
        "beneficio_bruto_q2": beneficio_bruto_q2,
        "beneficio_bruto_q3": beneficio_bruto_q3,
        "margen_q2": margen_q2,
        "margen_q3": margen_q3,


        "var_margen_pp": margen_q3 - margen_q2,


        "marketing_q2": marketing_q2,
        "marketing_q3": marketing_q3,
        "cac_q2": cac_q2,
        "cac_q3": cac_q3,
        "var_cac": calcular_variacion_porcentual(
            cac_q2, cac_q3
        ),

        # Clientes y pedidos
        "clientes_q2": clientes_q2,
        "clientes_q3": clientes_q3,
        "var_clientes": calcular_variacion_porcentual(
            clientes_q2, clientes_q3
        ),
        "pedidos_q2": pedidos_q2,
        "pedidos_q3": pedidos_q3,
        "var_pedidos": calcular_variacion_porcentual(
            pedidos_q2, pedidos_q3
        ),

        # Logística
        "retrasos_q2": retrasos_q2,
        "retrasos_q3": retrasos_q3,
        "tasa_retrasos_q2": tasa_retrasos_q2,
        "tasa_retrasos_q3": tasa_retrasos_q3,
        "var_retrasos_pp": tasa_retrasos_q3 - tasa_retrasos_q2,

        # Equipo
        "renuncias_q2": int(datos_q2["renuncias"]),
        "renuncias_q3": int(datos_q3["renuncias"]),
    }

def calcular_variacion_porcentual(valor_inicial, valor_final):
    if valor_inicial == 0:
        raise ValueError(
            "No se puede calcular una variación porcentual "
            "con un valor inicial igual a cero."
        )

    return (valor_final / valor_inicial - 1) * 100


def formatear_para_agente(m):

    return (
     
        f"Ventas Q3 vs Q2: {m['var_ventas']:+.1f}%\n"
        f"Clientes nuevos: {m['clientes_q2']} en Q2, "
        f"{m['clientes_q3']} en Q3 "
        f"({m['var_clientes']:+.1f}%)\n"
        f"Pedidos: {int(m['pedidos_q2'])} en Q2, {int(m['pedidos_q3'])} en Q3 "
        f"({m['var_pedidos']:+.1f}%)\n"

       
        f"Margen bruto: {m['margen_q2']:.1f}% en Q2, "
        f"{m['margen_q3']:.1f}% en Q3 "
        f"({m['var_margen_pp']:+.1f} puntos porcentuales)\n"

       
        f"CAC: {m['cac_q2']:.2f} en Q2, "
        f"{m['cac_q3']:.2f} en Q3 "
        f"({m['var_cac']:+.1f}%)\n"

        
        f"Logística: {m['tasa_retrasos_q2']:.1f}% "
        f"de pedidos con retraso en Q2, "
        f"{m['tasa_retrasos_q3']:.1f}% en Q3\n"
        f"Pedidos retrasados: {m['retrasos_q2']} en Q2, "
        f"{m['retrasos_q3']} en Q3\n"

      
        f"Renuncias: {m['renuncias_q2']} en Q2, "
        f"{m['renuncias_q3']} en Q3\n"
    )



#reglas de interpretación de datos para los agentes
reglas_cifras = (
    "\n\nREGLAS: "
    "1) Los datos entregados son la única fuente de hechos; no inventes datos, "
    "entidades ni metas numéricas que no estén en ellos. "
    "2) Distingue cantidades absolutas de porcentajes; nunca interpretes un conteo "
    "como un porcentaje. "
    "3) Indica si un cambio es en puntos porcentuales (pp) o variación relativa (%). "
    "4) No afirmes pérdidas ni márgenes negativos si los datos no los muestran. "
    "5) Toda causa que no esté en los datos debe empezar con 'Hipótesis:'."
)
#datos cargados en el excel
RUTA_EXCEL = "datos_empresa.xlsx"
df = cargar_datos(RUTA_EXCEL)
metricas = calcular_metricas(df)
datos = formatear_para_agente(metricas)


#llm (IA local que se usa mas parametros limitantes y el url base)
llm = LLM(
    model="ollama/qwen3.5:9b",      
    base_url="http://localhost:11434",
    temperature=0.3,
    max_tokens=2048,       
    reasoning_effort="none",                         
)

#agentes
analista = Agent(
    role="Analista de datos",
    goal="Extraer tendencias y anomalías",
    backstory="Analista experto en datos empresariales. ",
    llm=llm,
    verbose=True
)

evaluador = Agent(
    role="Evaluador de riesgos",
    goal="Identificar vulnerabilidades y riesgos operativos",
    backstory="Consultor pragmático de riesgos. ",
    llm=llm,
    verbose=True
)

estratega = Agent(
    role="Estratega de negocios",
    goal="Diseñar planes de acción viables",
    backstory="Director de operaciones con enfoque en eficiencia. ",
    llm=llm,
    verbose=True
)

coordinador = Agent(
    role="Director Ejecutivo",
    goal="Sintetizar todo en un informe claro",
    backstory="Líder que valora la claridad y la acción. ",
    llm=llm,
    verbose=True
)

#tareas
tarea_analisis = Task(
    description=(
        "Analiza estos datos:\n{datos_empresa}\n\n"
        "Identifica: 3 tendencias, 2 anomalías y 1 oportunidad. " + reglas_cifras
    ),
    expected_output="Lista estructurada con TENDENCIAS, ANOMALÍAS, OPORTUNIDAD.",
    agent=analista
)

tarea_riesgos = Task(
    description=(
        "Evalúa riesgos de dos escenarios: 1) Status quo, 2) Cambios agresivos. "
        "Da EXACTAMENTE 3 riesgos por escenario (6 en total). "
        "Para cada uno escribe una sola línea: riesgo | probabilidad (alta/media/baja) | "
        "impacto (alto/medio/bajo) | mitigación en 10 palabras. "
        "No agregues introducción ni conclusión. "
    ),
    expected_output="6 líneas, una por riesgo, en el formato indicado. Máximo 150 palabras.",
    agent=evaluador,
    context=[tarea_analisis],
)

tarea_estrategia = Task(
    description=(
        "Propón 2 estrategias con: objetivo, pasos, recursos y métrica a 90 días. "
    ),
    expected_output="ESTRATEGIA A y ESTRATEGIA B con pros y contras.",
    agent=estratega,
    context=[tarea_analisis, tarea_riesgos]
)

tarea_final = Task(
    description=(
        "Redacta informe ejecutivo fechado el {fecha} de 1 página con: diagnóstico, riesgo principal, "
        "estrategia recomendada (A o B) y 3 próximos pasos. " + reglas_cifras
        
    ),
    expected_output="Informe ejecutivo en Markdown.",
    agent=coordinador,
    context=[tarea_analisis, tarea_riesgos, tarea_estrategia],
    guardrail=sin_contradicciones
)

#la crew
crew = Crew(
    agents=[analista, evaluador, estratega, coordinador],
    tasks=[tarea_analisis, tarea_riesgos, tarea_estrategia, tarea_final],
    process=Process.sequential,
    verbose=True
)



#el final, no se para que puse estos comentarios si igual me pierdo xd
resultados = crew.kickoff(inputs={"datos_empresa": datos, "fecha": date.today().strftime("%d/%m/%Y")})
with open("informe_ejecutivo.md", "w", encoding="utf-8") as f:
    f.write(str(resultados))

print("\n" + "="*60)
print("INFORME GUARDADO EN: informe_ejecutivo.md")
print("="*60)
print(resultados)