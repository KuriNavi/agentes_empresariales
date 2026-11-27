import pandas as pd
import re
from crewai import Agent, Task, Crew, Process, LLM
from datetime import date
#defs

PORCENTAJE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def extraer_porcentajes(texto):
    return [float(p.replace(",", ".")) for p in PORCENTAJE.findall(texto)]

# guardrail que valida el informe final contra las métricas reales
def crear_guardrail(m):
    """Devuelve un guardrail que valida el informe contra las métricas reales."""

    def guardrail(resultado):
        texto = resultado.raw
        bajo = texto.lower()
        porcentajes = extraer_porcentajes(texto)
        errores = []

        # 1) Porcentajes imposibles (suele ser un conteo usado como porcentaje)
        if any(p > 100 for p in porcentajes):
            errores.append(
                "Hay un porcentaje mayor a 100%. No uses un conteo como porcentaje."
            )

        # 2) Afirmaciones que los datos no sostienen
        prohibidas = [
            "márgenes negativos", "pérdidas unitarias",
            "operar a pérdida", "quiebra", "bancarrota",
        ]
        halladas = [f for f in prohibidas if f in bajo]
        if halladas:
            errores.append(
                f"Elimina estas afirmaciones que los datos no respaldan: {halladas}. "
                f"El margen bruto fue {m['margen_q2']:.1f}% en Q2 y "
                f"{m['margen_q3']:.1f}% en Q3 (positivo en ambos)."
            )

        # 3) Debe citar las cifras clave correctas
        if not any(abs(p - m["tasa_retrasos_q3"]) < 0.5 for p in porcentajes):
            errores.append(
                f"Incluye la tasa de retrasos real de Q3: {m['tasa_retrasos_q3']:.1f}%."
            )
        if not any(abs(p - m["margen_q3"]) < 0.5 for p in porcentajes):
            errores.append(
                f"Incluye el margen bruto real de Q3: {m['margen_q3']:.1f}%."
            )

        # 4) No puede ignorar las renuncias
        if m["renuncias_q3"] > 0 and "renuncia" not in bajo:
            errores.append(
                f"Menciona las {m['renuncias_q3']} renuncias del equipo comercial en Q3."
            )

        # 5) Una sola estrategia, no combinadas
        if re.search(r"\ba\s*\+\s*b\b|híbrid|conjunt|ambas estrategias", bajo):
            errores.append(
                "Recomienda UNA sola estrategia (A o B), no una combinación."
            )
        
        # 6) Moneda y presupuestos inventados
        if re.search(r"\$|usd|€|\beur\b|dólar", bajo):
            errores.append(
                "No uses símbolos ni nombres de moneda ni inventes presupuestos: "
                "los datos no indican la unidad."
            )

        # 7) Recomendar la otra estrategia "en paralelo"
        if "en paralelo" in bajo:
            errores.append(
                "No propongas ejecutar la otra estrategia en paralelo. Elige solo una."
            )    

        if errores:
            return (False, "Corrige lo siguiente y reescribe el informe: "
                           + " ".join(errores))
        return (True, resultado)

    return guardrail

#auditorias de porcentajes y causalidad, para avisar de posibles errores en el informe
def auditar_porcentajes(texto, m):

    """Aviso (no bloquea): porcentajes del informe que no están en las métricas."""
    claves = [
        "margen_q2", "margen_q3", "var_margen_pp", "var_ventas",
        "var_coste_ventas", "var_marketing", "var_clientes", "var_cac",
        "var_pedidos", "tasa_retrasos_q2", "tasa_retrasos_q3", "var_retrasos_pp",
    ]
    conocidos = [abs(m[k]) for k in claves]
    return sorted({
        p for p in extraer_porcentajes(texto)
        if not any(abs(p - c) < 0.5 for c in conocidos)
    })

def auditar_causalidad(texto):
    """Aviso (no bloquea): causas afirmadas sin marcar como hipótesis."""
    marcadores = ["causa raíz", "debido a", "se debe a", "provoca", "provocado"]
    bajo = texto.lower()
    hallados = [x for x in marcadores if x in bajo]
    return hallados if hallados and "hipótesis" not in bajo else []

#carga y validación de datos
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



#calcular métricas de Q2 y Q3, con validaciones de consistencia
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
    clientes_q2 = int(datos_q2["clientes_nuevos"])
    clientes_q3 = int(datos_q3["clientes_nuevos"])

    pedidos_q2 = int(datos_q2["pedidos"])
    pedidos_q3 = int(datos_q3["pedidos"])

    retrasos_q2 = int(datos_q2["pedidos_retrasados"])
    retrasos_q3 = int(datos_q3["pedidos_retrasados"])

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
        "var_coste_ventas": calcular_variacion_porcentual(
            costes_q2, costes_q3
        ),
        "beneficio_bruto_q2": beneficio_bruto_q2,
        "beneficio_bruto_q3": beneficio_bruto_q3,
        "margen_q2": margen_q2,
        "margen_q3": margen_q3,


        "var_margen_pp": margen_q3 - margen_q2,


        "marketing_q2": marketing_q2,
        "marketing_q3": marketing_q3,
        "var_marketing": calcular_variacion_porcentual(
            marketing_q2, marketing_q3
        ),
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

#formatear los datos para el agente, con las métricas calculadas
def formatear_para_agente(m):
    return (
        "VENTAS Y COSTES (importes)\n"
        f"- Ventas: {m['ventas_q2']:,.0f} en Q2, {m['ventas_q3']:,.0f} en Q3 "
        f"({m['var_ventas']:+.1f}%)\n"
        f"- Coste de ventas: {m['coste_ventas_q2']:,.0f} en Q2, "
        f"{m['coste_ventas_q3']:,.0f} en Q3 ({m['var_coste_ventas']:+.1f}%)\n"
        f"- Margen bruto: {m['margen_q2']:.1f}% en Q2, {m['margen_q3']:.1f}% en Q3 "
        f"({m['var_margen_pp']:+.1f} pp)\n\n"

        "MARKETING Y CLIENTES\n"
        f"- Gasto de marketing: {m['marketing_q2']:,.0f} en Q2, "
        f"{m['marketing_q3']:,.0f} en Q3 ({m['var_marketing']:+.1f}%)\n"
        f"- Clientes nuevos (cantidad): {m['clientes_q2']} en Q2, "
        f"{m['clientes_q3']} en Q3 ({m['var_clientes']:+.1f}%)\n"
        f"- CAC (gasto de marketing / clientes nuevos): {m['cac_q2']:.2f} en Q2, "
        f"{m['cac_q3']:.2f} en Q3 ({m['var_cac']:+.1f}%)\n\n"

        "LOGÍSTICA\n"
        f"- Pedidos (cantidad): {m['pedidos_q2']} en Q2, {m['pedidos_q3']} en Q3 "
        f"({m['var_pedidos']:+.1f}%)\n"
        f"- Pedidos retrasados (cantidad): {m['retrasos_q2']} en Q2, "
        f"{m['retrasos_q3']} en Q3\n"
        f"- Tasa de retrasos (porcentaje de pedidos): {m['tasa_retrasos_q2']:.1f}% en Q2, "
        f"{m['tasa_retrasos_q3']:.1f}% en Q3 ({m['var_retrasos_pp']:+.1f} pp)\n\n"

        "EQUIPO\n"
        f"- Renuncias (cantidad): {m['renuncias_q2']} en Q2, {m['renuncias_q3']} en Q3\n"
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
    "6) No uses símbolos ni nombres de moneda (los datos no indican la unidad) "
    "ni inventes presupuestos, plazos legales o metas numéricas."
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
    max_tokens=1024,       
    reasoning_effort="none",                         
)

print(datos)
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
        "Identifica: 3 tendencias, 2 anomalías y 1 oportunidad. "
        "Cada punto cita al menos una cifra de los datos."
        + reglas_cifras
    ),
    expected_output=(
        "Lista con TENDENCIAS, ANOMALÍAS, OPORTUNIDAD. Máximo 200 palabras."
    ),
    agent=analista,
)

tarea_riesgos = Task(
    description=(
        "Evalúa riesgos de dos escenarios: 1) Status quo, 2) Cambios agresivos. "
        "Da EXACTAMENTE 3 riesgos por escenario (6 en total). "
        "Para cada uno escribe una sola línea: riesgo | probabilidad (alta/media/baja) | "
        "impacto (alto/medio/bajo) | mitigación en 10 palabras. "
        "Basa cada riesgo en una cifra de los datos. "
        "No agregues introducción ni conclusión."
        + reglas_cifras
    ),
    expected_output="6 líneas, una por riesgo, en el formato indicado. Máximo 150 palabras.",
    agent=evaluador,
    context=[tarea_analisis],
)

tarea_estrategia = Task(
    description=(
        "Propón 2 estrategias (A y B). Para cada una: objetivo, 3 pasos, "
        "tipo de recursos (sin cifras de dinero), indicador a seguir a 90 días "
        "(nómbralo junto con su valor actual, sin fijar metas numéricas), "
        "un pro y un contra de una línea cada uno."
        + reglas_cifras
    ),
    expected_output="ESTRATEGIA A y ESTRATEGIA B con pros y contras. Máximo 250 palabras.",
    agent=estratega,
    context=[tarea_analisis, tarea_riesgos],
)

tarea_final = Task(
    description=(
        "Redacta un informe ejecutivo fechado el {fecha}, de 1 página, con estas "
        "secciones: diagnóstico, riesgo principal, UNA estrategia recomendada "
        "(A o B) y 3 próximos pasos. Menciona las renuncias del equipo. "
        "No añadas notas finales ni propongas ejecutar la otra estrategia."
        + reglas_cifras
    ),
    expected_output="Informe ejecutivo en Markdown. Máximo 350 palabras.",
    agent=coordinador,
    context=[tarea_analisis, tarea_riesgos, tarea_estrategia],
    guardrail=crear_guardrail(metricas),
    guardrail_max_retries=3,
)
#la crew
crew = Crew(
    agents=[analista, evaluador, estratega, coordinador],
    tasks=[tarea_analisis, tarea_riesgos, tarea_estrategia, tarea_final],
    process=Process.sequential,
    verbose=True
)



#el final, no se para que puse estos comentarios si igual me pierdo xd
try:
    resultados = crew.kickoff(inputs={
        "datos_empresa": datos,
        "fecha": date.today().strftime("%d/%m/%Y"),
    })
except Exception as e:
    print(f"\nEl informe no pasó la validación o hubo un error: {e}")
    raise SystemExit(1)

texto_final = str(resultados)

with open("informe_ejecutivo.md", "w", encoding="utf-8") as f:
    f.write(texto_final)

print("\n" + "=" * 60)
print("INFORME GUARDADO EN: informe_ejecutivo.md")
print("=" * 60)
print(texto_final)

dudosos = auditar_porcentajes(texto_final, metricas)
if dudosos:
    print(f"\nAVISO: el informe cita porcentajes que no están en los datos: {dudosos}")
    print("Revísalos: pueden ser metas propuestas o cifras inventadas.")
causas = auditar_causalidad(texto_final)
if causas:
    print(f"\nAVISO: el informe afirma causas sin marcarlas como hipótesis: {causas}")