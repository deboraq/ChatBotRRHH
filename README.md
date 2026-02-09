## 📊 Business Intelligence & Monitoreo

Solución integral de automatización para el departamento de Recursos Humanos de Bacar SA. El proyecto integra un Chatbot interactivo con un ecosistema de Business Intelligence para la toma de decisiones basada en datos.

🚀 Tecnologías Utilizadas
Backend: Python con integración de Firebase Admin SDK.

Base de Datos: Google Firebase Cloud Firestore (NoSQL).

Visualización: Google Looker Studio para monitoreo de KPIs.

📊 Dashboard de Monitoreo e Inteligencia
El sistema no solo resuelve dudas, sino que captura métricas estratégicas en tiempo real:

Tasa de Satisfacción: Seguimiento de respuestas útiles mediante feedback directo.

Hot Topics: Análisis de los temas más consultados (Vacaciones, ART, Sueldo).

Mejora Continua: Registro automático de consultas no entendidas para alimentar la base de conocimientos.

🛠️ Estructura del Repositorio
app.py: Lógica principal del chatbot interactivo.

generar_reporte.py: Script para exportar datos de feedback a Google Sheets.

extraer_pendientes.py: Extractor de dudas no resueltas para auditoría de RRHH.

cargar_faqs.py: Administrador de carga masiva de la base de conocimientos.
