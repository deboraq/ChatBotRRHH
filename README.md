## 🏢 Asistente Virtual de RRHH Inteligente - Bacar SA
Solución integral de vanguardia para la gestión de Recursos Humanos que integra un Chatbot con Inteligencia Artificial y un ecosistema de Business Intelligence para la toma de decisiones basada en datos.

## 🚀 Funcionalidades Principales
Entendimiento Inteligente (Fuzzy Matching): Gracias a la librería TheFuzz, el bot entiende errores de ortografía y variaciones gramaticales (ej: "vacaSiones", "reCibo").

Análisis de Sentimiento (NLP): Utiliza TextBlob para detectar el estado emocional del colaborador en las consultas no resueltas.

Omnicanalidad y Escalabilidad: Arquitectura preparada para integrarse con WhatsApp y otros canales.

Persistencia en Tiempo Real: Uso de Firebase Cloud Firestore para el almacenamiento de interacciones y feedback.

## 📊 Dashboard de Monitoreo (Looker Studio)

El sistema recolecta métricas estratégicas visualizadas en tiempo real:

Tasa de Satisfacción: Basada en el feedback directo de los empleados (si/no).

Hot Topics: Mapa de calor de los temas más consultados (Vacaciones, ART, Sueldo).

Auditoría de Pendientes: RRHH puede identificar consultas fallidas y priorizarlas según el tono detectado por el análisis de sentimiento.

## 🛠️ Tecnologías y Librerías
Lenguaje: Python 3.12

Base de Datos: Firebase Admin SDK (Firestore NoSQL)

IA y Procesamiento de Lenguaje: TheFuzz (Fuzzy Matching) y TextBlob (Sentimiento)

BI: Google Looker Studio y Google Sheets

## 📁 Estructura del Proyecto

app.py: El cerebro del bot con lógica de IA y respuesta interactiva.

web_chat.py: Interfaz web local para probar conversaciones en navegador.

generar_reporte.py: Script ETL para exportar métricas de satisfacción.

extraer_pendientes.py: Auditoría y análisis de dudas no resueltas.

cargar_faqs.py: Script para la gestión y carga de la base de conocimientos.

## 🔁 Cambio de proyecto Firebase (nuevo mail/cuenta)

Para mover el chatbot al proyecto Firebase de `implementaciones.it@bacarsa.com.ar`:

1) En la consola del nuevo proyecto, creá una **Service Account Key** (JSON) y guardala localmente.
   Ejemplo: `claves-bacar.json`

2) Configurá el proyecto para usar esa clave:

```bash
export FIREBASE_CREDENTIALS=claves-bacar.json
```

3) Corré normalmente los scripts (`app.py`, `web_chat.py`, `cargar_faqs.py`, etc.).  
   Ahora se conectarán al proyecto indicado por esa clave.

### Migrar datos Firestore entre proyectos

Si querés copiar los datos del Firebase viejo al nuevo, usá:

```bash
python migrar_firestore.py \
  --source-credentials claves-viejo.json \
  --target-credentials claves-bacar.json
```

Colecciones migradas por defecto:
- `faq_rrhh`
- `feedback_respuestas`
- `consultas_pendientes`

Modo simulación (sin escribir):

```bash
python migrar_firestore.py \
  --source-credentials claves-viejo.json \
  --target-credentials claves-bacar.json \
  --dry-run
```

## 💬 Interfaz Web de Pruebas

Si querés probar el chatbot con una experiencia similar a un canal real (antes de WhatsApp), podés usar la UI web local.

1) Instalá dependencias mínimas (UI web):

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Opcional (si querés todas las integraciones y reportes):

```bash
pip install -r requirements-full.txt
```

2) Ejecutá la interfaz:

```bash
python web_chat.py
```

3) Abrí en tu navegador:

```text
http://localhost:5000
```

Funciones disponibles en la UI:
- Chat en tiempo real con el motor del bot.
- Flujo de feedback (si/no) integrado.
- Botones rápidos: menú, hablar con RRHH y reiniciar sesión.
- Atajos clickeables por número/tema y sugerencias de preguntas.
- Vista de estadísticas en tiempo real: `http://localhost:5000/estadisticas`

## 📈 Dashboard Web (sin Google Sheets)

El proyecto incluye una página de métricas conectada directo a Firestore para no depender de exportaciones manuales:

- Endpoint JSON: `GET /api/stats`
- Página visual: `GET /estadisticas`

Métricas incluidas:
- Total de feedback y porcentaje de utilidad.
- Votos sí/no.
- Pendientes por sentimiento.
- Evolución de feedback y pendientes (últimos 7 días).
- Top temas consultados.

![Dashboard](dashboard.png)


