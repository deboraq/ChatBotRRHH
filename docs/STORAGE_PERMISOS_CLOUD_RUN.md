# 403 al subir archivos: dar permiso de Storage a la cuenta de Cloud Run

Si al enviar una foto o archivo desde el Panel de atención ves un error **403** tipo:

> chatbot-rrhh-run@it-analyzer.iam.gserviceaccount.com does not have **storage.objects.create** access

es porque la cuenta de servicio de Cloud Run no tiene permiso para escribir en el bucket de Firebase Storage. Hay que darle ese permiso.

---

## Opción 1 – Desde la consola (Google Cloud)

1. Entrá a **[Google Cloud Console](https://console.cloud.google.com)** con el proyecto **it-analyzer**.
2. Menú **☰** → **Cloud Storage** → **Buckets** (o buscá “Storage”).
3. En la lista, abrí el bucket **`it-analyzer.firebasestorage.app`** (o el que uses en `FIREBASE_STORAGE_BUCKET`).
4. Arriba, pestaña **PERMISSIONS** (Permisos).
5. Clic en **+ GRANT ACCESS** (Conceder acceso).
6. En **New principals** (Nuevos principales) poné:  
   `chatbot-rrhh-run@it-analyzer.iam.gserviceaccount.com`
7. En **Role** elegí **Cloud Storage** → **Storage Object Admin** (o al menos **Storage Object Creator**).
8. Guardá con **Save** (Guardar).

Después de unos segundos, probá de nuevo subir un archivo desde el panel.

---

## Opción 2 – Desde la terminal (gcloud)

Con el proyecto **it-analyzer** y la cuenta de servicio **chatbot-rrhh-run**:

```powershell
gcloud storage buckets add-iam-policy-binding gs://it-analyzer.firebasestorage.app `
  --member="serviceAccount:chatbot-rrhh-run@it-analyzer.iam.gserviceaccount.com" `
  --role="roles/storage.objectAdmin" `
  --project=it-analyzer
```

Si tu bucket tiene otro nombre (el que está en la variable `FIREBASE_STORAGE_BUCKET`), reemplazá `it-analyzer.firebasestorage.app` por ese nombre.

---

## Resumen

| Qué                      | Dónde / valor                                                |
|--------------------------|--------------------------------------------------------------|
| Cuenta de Cloud Run      | `chatbot-rrhh-run@it-analyzer.iam.gserviceaccount.com`     |
| Bucket (ejemplo)         | `it-analyzer.firebasestorage.app`                            |
| Rol necesario            | **Storage Object Admin** (o **Storage Object Creator**)       |

Con eso el 403 al subir archivos debería desaparecer.
