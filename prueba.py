from crewai import Agent, Task, Crew, Process, LLM

llm = LLM(
    model="ollama/qwen3.5:4b",      
    base_url="http://localhost:11434",
    temperature=0.3,
    max_tokens=1024,       
    reasoning_effort="none",                         
)
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
    backstory="Consultor pragmático de riesgos. k",
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

tarea_analisis = Task(
    description=(
        "Analiza estos datos:\n{datos_empresa}\n\n"
        "Identifica: 3 tendencias, 2 anomalías y 1 oportunidad. "
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
        "Redacta informe ejecutivo de 1 página con: diagnóstico, riesgo principal, "
        "estrategia recomendada (A o B) y 3 próximos pasos. "
    ),
    expected_output="Informe ejecutivo en Markdown.",
    agent=coordinador,
    context=[tarea_analisis, tarea_riesgos, tarea_estrategia]
)

crew = Crew(
    agents=[analista, evaluador, estratega, coordinador],
    tasks=[tarea_analisis, tarea_riesgos, tarea_estrategia, tarea_final],
    process=Process.sequential,
    verbose=True
)

datos = """
- Ventas Q3: bajaron 15% vs Q2
- CAC: subió 20%
- Logística: 30% de retrasos
- Equipo comercial: 2 renuncias en el último mes
- Margen bruto: pasó del 42% al 35%
"""

resultados = crew.kickoff(inputs={"datos_empresa": datos})

with open("informe_ejecutivo.md", "w", encoding="utf-8") as f:
    f.write(str(resultados))

print("\n" + "="*60)
print("INFORME GUARDADO EN: informe_ejecutivo.md")
print("="*60)
print(resultados)