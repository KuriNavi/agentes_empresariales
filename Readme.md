# Sistema de Agentes IA para Análisis Empresarial

## Qué hace
Sistema multi-agente que analiza datos empresariales (Excel) y genera 
informes ejecutivos automatizados usando IA local (Ollama + Qwen).

## Arquitectura
- **Analista**: Extrae tendencias y anomalías
- **Evaluador**: Identifica riesgos operativos
- **Estratega**: Diseña planes de acción
- **Coordinador**: Sintetiza informe final

## Requisitos
- Python 3.12+
- Ollama instalado con modelo qwen3.5:9b (modelo modificable a conveniencia del usuario)
- Dependencias: pandas, crewai, openpyxl

## Instalación
1. Instalar Ollama: https://ollama.com
2. Descargar modelo: `ollama pull qwen3.5:9b`
3. Instalar dependencias: `pip install pandas crewai openpyxl`

## Uso
1. Coloca tu Excel en `datos_empresa.xlsx` con columnas: mes, ventas, coste_ventas, etc. (O usar el python que genera un excel con los datos de prueba que generar el informe)
2. Ejecuta: `python prueba.py`
3. Revisa el informe en `informe_ejecutivo.md`

## Decisiones técnicas
- **IA local**: Privacidad, sin costos de API, control total
- **Guardrails**: Validación contra datos reales para evitar alucinaciones
- **Multi-agente**: Separación de responsabilidades para mejor calidad
