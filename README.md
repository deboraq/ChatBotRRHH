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
- Historial completo de chats: `http://localhost:5000/historial`
- Panel RRHH con temas de color mejorados y switch claro/oscuro.

## 👩‍💼 Derivación y atención humana (RRHH)

Cuando un colaborador pide “hablar con RRHH”, la conversación se deriva a una bandeja de atención humana.

- Panel RRHH: `http://localhost:5000/rrhh`
- Bandeja de conversaciones pendientes/activas.
- Botón para tomar conversación por agente.
- Respuesta en vivo desde RRHH al colaborador en el mismo chat.
- Cierre de conversación por RRHH o colaborador.

### 🔐 Usuarios para panel RRHH e historial

Ahora podés proteger `GET /rrhh`, `GET /historial` y sus APIs (`/api/rrhh/*`, `/api/historial`) con login.

1) Activá autenticación:

```bash
export RRHH_AUTH_ENABLED=true
```

2) Elegí una de estas opciones de usuarios:

- **Usuario admin por variables de entorno**:

```bash
export RRHH_ADMIN_USER=rrhh
export RRHH_ADMIN_PASSWORD="cambiame-por-una-segura"
```

- **Archivo con múltiples usuarios** (`rrhh_users.json`):
  - Tomá como base `rrhh_users.example.json`.
  - Definí la ruta (opcional, por defecto busca `rrhh_users.json`):

```bash
export RRHH_USERS_FILE=rrhh_users.json
```

Para generar hash de contraseña (recomendado):

```bash
python auth_rrhh.py --hash "mi-clave-segura"
```

Luego pegá ese valor en `password_hash`.

### Crear usuarios desde la interfaz web (sin editar JSON)

Con autenticación activa:

1) Ingresá con un usuario **admin** en `http://localhost:5000/login`.  
   (si usás `RRHH_ADMIN_USER`, por defecto queda con rol `admin`)

2) Entrá al panel `http://localhost:5000/rrhh`.

3) En la sección **Usuarios RRHH**:
   - completá usuario, nombre visible, contraseña y rol
   - hacé click en **Crear usuario**
   - para modificar rol, elegí el nuevo valor en la tabla y hacé click en **Actualizar rol**
   - en la columna **Permisos** ves qué puede ver/hacer cada usuario según su rol

Eso guarda automáticamente en `RRHH_USERS_FILE` (por defecto `rrhh_users.json`).

### Roles personalizados y permisos

Además de `admin` y `rrhh`, podés crear roles propios desde el panel:

- Sección **Roles y permisos** en `http://localhost:5000/rrhh`
- Crear rol nuevo con permisos
- Editar permisos de roles existentes

Permisos disponibles:
- `conversaciones_ver`: ver panel/bandeja RRHH
- `conversaciones_gestionar`: tomar, responder y cerrar conversaciones
- `historial_ver`: acceder al historial completo
- `usuarios_gestionar`: crear/editar usuarios
- `roles_gestionar`: crear/editar roles y permisos

Roles por defecto:
- `admin`: todos los permisos
- `rrhh`: conversaciones + historial (sin gestión de usuarios/roles)

Archivo de roles (opcional):

```bash
export RRHH_ROLES_FILE=rrhh_roles.json
```

## 🧾 Historial completo de conversaciones

Se guarda cada mensaje en la colección `chat_historial`:
- colaborador
- bot
- rrhh
- sistema

Consultas disponibles:
- Página visual: `GET /historial`
- API: `GET /api/historial` (filtros por remitente/canal/conversación/texto)

## 📈 Dashboard Web (sin Google Sheets)

El proyecto incluye una página de métricas conectada directo a Firestore para no depender de exportaciones manuales:

- Endpoint JSON: `GET /api/stats`
- Página visual: `GET /estadisticas`

Métricas incluidas:
- Total de feedback y porcentaje de utilidad.
- Votos sí/no.
- Casos "No útil" con detalle clickeable.
- Pendientes por sentimiento.
- Evolución de feedback y pendientes (últimos 7 días).
- Top temas consultados.
- Estado de derivaciones RRHH (abiertas, en atención, cerradas).
- Drill-down interactivo: podés hacer click en KPIs, temas y gráficos para ver detalle.
- Auto-refresco cada 1 minuto (sin cache del navegador).

Tip de diagnóstico: en la parte superior del dashboard se muestra el `Proyecto` y `Server boot`.
Si no cambian, probablemente seguís con una instancia vieja de `web_chat.py`.

![Dashboard](dashboard.png)


