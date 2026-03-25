# Digitalización de legajos – Bacar (guía técnica)

Guía para digitalizar los legajos de ~800 empleados de forma segura, integrable con el ecosistema actual (ChatBot RRHH, Firebase, panel con usuarios y roles).

## Estado en el código

- **Permisos:** `legajos_ver` y `legajos_gestionar` en `auth_rrhh.py` (catálogo de roles).
- **Ruta:** `GET /legajos` — UI con listado, alta de colaborador, documentos, subida y descarga (enlace firmado ~15 min).
- **Firestore:** colecciones `legajos_empleados` (incluye `dni`, `updated_at`, `updated_by`), `legajos_documentos` y `legajos_auditoria` (ver `legajos_service.py`).
- **Storage:** prefijo `legajos_uploads/{company_id}/{empleado_id}/…` en el mismo bucket que `FIREBASE_STORAGE_BUCKET`.
- **APIs:** `GET/POST /api/legajos/empleados`, `GET /api/legajos/empleados/<id>`, `PATCH /api/legajos/empleados/<id>`, `GET /api/legajos/empleados/export` (CSV UTF-8 con BOM), `POST …/import`, `GET/POST …/empleados/<id>/documentos`, `GET …/documentos/<id>/link`, `DELETE …/documentos/<id>`, `POST /api/legajos/empresa/seleccionar`.
- **Menú principal:** botón **Legajos** si el usuario tiene `legajos_ver`.
- **Rol por defecto `rrhh`:** sin legajos; **admin** tiene todo. Asignar permisos en **Configuración → Roles y permisos**.

### Reglas Firebase (cliente)

En el repo hay `firestore.rules` y `storage.rules` que **niegan** lectura/escritura desde el SDK web (toda la lógica va por el backend con Admin SDK / cuenta de servicio).

Desplegar (cuando corresponda):

```bash
firebase deploy --only firestore:rules,storage
```

**Antes de desplegar:** si ya tenés reglas distintas en el proyecto (por ejemplo acceso cliente a alguna colección), fusioná los cambios a mano; estas reglas **bloquean todo** el acceso cliente a Firestore y Storage.

Si en el futuro alguna pantalla usa Firestore **desde el navegador**, habrá que ajustar reglas por colección; hasta entonces este enfoque es el más seguro para legajos y datos sensibles.

---

## 1. Qué necesitás tener claro

| Aspecto | Detalle |
|--------|--------|
| **Volumen** | ~800 empleados × varios documentos por persona (DNI, contratos, certificados, evaluaciones, etc.). Pueden ser miles de archivos. |
| **Formatos** | PDF, imágenes (escaneos), Word. Conviene definir tipos estándar (ej. solo PDF para contratos). |
| **Quién sube** | RRHH o áreas autorizadas. Los empleados no deberían subir sus propios legajos (salvo que se defina un flujo específico). |
| **Quién ve** | Solo personal autorizado (RRHH, jefes por área si aplica), con trazabilidad de quién accedió a qué. |
| **Seguridad** | Login obligatorio, roles, permisos por recurso y auditoría de accesos. |

---

## 2. Qué necesitás a nivel técnico

### 2.1 Almacenamiento de archivos

- **Google Cloud Storage (GCS)** es la opción natural si ya usás Firebase/GCP:
  - Bucket privado (sin acceso público).
  - Archivos por empleado en rutas tipo: `legajos/{company_id}/{empleado_id}/{tipo_documento}/{nombre_archivo}`.
  - Encriptación en reposo (por defecto en GCP).
- **Alternativa:** Firebase Storage (usa GCS por detrás). Misma lógica de carpetas y reglas de seguridad.

### 2.2 Base de datos de índice (metadatos)

- **Firestore** (ya lo tenés):
  - Colección tipo `legajos` o `empleados`: documento por empleado con datos básicos (nombre, legajo, área, sucursal, company_id).
  - Colección tipo `legajos_documentos`: cada documento = un archivo subido (empleado_id, tipo, nombre_archivo, ruta en GCS, fecha, usuario que subió).
  - Así podés listar “todos los documentos del empleado X” sin tocar el Storage en cada búsqueda.

### 2.3 Aplicación y seguridad

- **Reutilizar** el mismo stack que el chatbot:
  - **Flask** (o el mismo `web_chat.py`) con rutas protegidas.
  - **Autenticación RRHH** que ya tenés (`RRHH_AUTH_ENABLED`, `auth_rrhh`, login, sesión).
  - **Nuevos permisos** en `auth_rrhh.py`: por ejemplo `legajos_ver` y `legajos_gestionar` (subir, reemplazar, eliminar).
- **Roles:** por ejemplo:
  - `admin`: sigue teniendo todo.
  - `rrhh`: conversaciones + historial + **legajos_ver** + **legajos_gestionar**.
  - Opcional: rol `legajos_solo_lectura` solo con `legajos_ver`.

### 2.4 Cómo se asegura que “no cualquiera pueda ingresar”

1. **Login obligatorio:** Todas las rutas de legajos exigen sesión RRHH (igual que `/rrhh`, `/historial`, `/estadisticas`).
2. **Permisos por rol:** Solo roles con `legajos_ver` pueden ver listado y descargar; solo con `legajos_gestionar` pueden subir/eliminar.
3. **Bucket privado:** Los archivos en GCS no tienen URL pública. La app genera **URLs firmadas** (temporales) solo para usuarios autenticados con permiso, al momento de descargar.
4. **Reglas por empresa/área (opcional):** Si en el futuro querés que un jefe solo vea legajos de su área, se filtra en la consulta por `company_id` / `area` / `sucursal` usando los datos que ya manejás en empresas y handoffs.
5. **Auditoría:** Guardar en Firestore (o en una colección `auditoria_legajos`) quién accedió a qué documento y cuándo (lectura/descarga y subida/eliminación).

---

## 3. Cómo hacerlo: dos caminos

### Opción A: Integrado al proyecto actual (recomendado)

- Agregar al mismo `web_chat.py` (o a un blueprint):
  - Rutas: por ejemplo `/legajos`, `/legajos/empleado/<id>`, `/legajos/empleado/<id>/subir`, `/legajos/empleado/<id>/documento/<doc_id>/descargar`.
- Nuevas pantallas:
  - Listado de empleados (con búsqueda/filtro por nombre, legajo, área).
  - Detalle por empleado: lista de documentos del legajo y botones “Subir”, “Descargar”, “Eliminar” (según permiso).
- Backend:
  - Subida: recibir archivo → validar tipo/tamaño → subir a GCS → crear documento en `legajos_documentos` (y opcionalmente en `empleados` si no existe).
  - Descarga: comprobar permiso → generar URL firmada de GCS → redirigir o devolver JSON con la URL.
- Firestore:
  - Colecciones `empleados` (o `legajos`) y `legajos_documentos` como en el punto 2.2.
- Permisos:
  - Agregar `legajos_ver` y `legajos_gestionar` al catálogo en `auth_rrhh.py` y asignarlos a los roles que corresponda.

**Ventaja:** Un solo login, un solo deploy (Cloud Run / Render), misma política de usuarios y roles.

### Opción B: Módulo separado (misma cuenta GCP)

- Otra app (Flask/FastAPI) que:
  - Use el mismo Firestore y el mismo bucket GCS.
  - Comparta la lógica de usuarios (por ejemplo leyendo `rrhh_users.json` y `rrhh_roles.json`, o migrando usuarios a Firestore y leyendo de ahí).
- Desplegás este módulo en otro servicio (otro Cloud Run o mismo con otro prefijo de ruta).

**Ventaja:** Separación total del código del chatbot. **Desventaja:** Duplicar autenticación/roles o mantener dos apps alineadas.

---

## 4. Pasos sugeridos (opción A integrada)

1. **Definir modelo de datos**
   - Estructura de `empleados` (id, nombre, legajo_numero, area, sucursal, company_id, fecha_alta, etc.).
   - Estructura de `legajos_documentos` (empleado_id, tipo_documento, nombre_archivo, storage_path, subido_por, fecha, tamaño, etc.).
   - Tipos de documento permitidos (ej. DNI, contrato, certificado_medico, evaluacion, otros).

2. **GCP**
   - Crear un bucket (ej. `bacar-legajos-prod`) en el mismo proyecto.
   - Sin acceso público. IAM: que la cuenta de servicio de Cloud Run (o la que use la app) tenga `roles/storage.objectAdmin` (o el mínimo necesario) sobre ese bucket.

3. **Código**
   - En `auth_rrhh.py`: agregar `legajos_ver` y `legajos_gestionar` a `PERMISSIONS_CATALOG` y a los roles por defecto que deban tener acceso.
   - En la app: rutas de legajos protegidas con `@require_rrhh_login` y comprobación de permiso (`legajos_ver` / `legajos_gestionar`).
   - Servicio de almacenamiento: función que suba a GCS y guarde metadatos en Firestore; función que genere URL firmada para descarga.
   - Pantallas: listado de empleados, detalle de legajo, formulario de subida, y opcionalmente registro de auditoría en cada descarga/subida.

4. **Carga inicial**
   - Opción 1: RRHH va subiendo por empleado desde la web (priorizando los más consultados).
   - Opción 2: Script batch que lea desde una carpeta o ZIP con estructura fija (ej. una carpeta por empleado) y suba a GCS + Firestore usando la misma lógica (con una cuenta de servicio con permisos).

5. **Auditoría**
   - En cada “descarga” o “visualización” de un archivo, escribir en `auditoria_legajos`: usuario, empleado_id, documento_id, acción (lectura/descarga), timestamp.

---

## 5. Resumen de seguridad

| Medida | Cómo se cumple |
|--------|-----------------|
| Que no cualquiera ingrese | Login RRHH obligatorio; sin cuenta no se ve nada. |
| Que solo algunos vean legajos | Roles con permiso `legajos_ver`. |
| Que solo algunos suban/eliminen | Roles con permiso `legajos_gestionar`. |
| Que los archivos no sean públicos | Bucket privado; acceso solo por URL firmada generada por la app. |
| Saber quién accedió | Colección de auditoría en cada descarga/subida/eliminación. |
| Datos en reposo | GCS y Firestore con encriptación por defecto en GCP. |

---

## 6. Checklist “qué necesito”

- [ ] Proyecto GCP/Firebase (ya lo tenés).
- [ ] Bucket GCS privado para legajos.
- [ ] Colecciones Firestore: índice de empleados y de documentos por legajo.
- [ ] Permisos nuevos en la app: `legajos_ver`, `legajos_gestionar`.
- [ ] Rutas y pantallas de legajos protegidas con login y permisos.
- [ ] Subida a GCS + registro en Firestore y descarga vía URL firmada.
- [ ] (Opcional) Auditoría de accesos.
- [ ] (Opcional) Script o proceso para carga masiva inicial.

Si querés, el siguiente paso puede ser bajar esto a nombres concretos de colecciones, rutas y un ejemplo de código para una ruta de subida y una de descarga dentro de tu `web_chat.py` y `auth_rrhh.py` actuales.
