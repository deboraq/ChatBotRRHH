# Subir foto o archivo desde el panel de atención

Los agentes pueden **subir una foto o archivo** desde la PC (escritorio) o desde el celular (galería/archivos) para enviarlo al colaborador por WhatsApp o verlo en el chat.

---

## Cómo se usa

1. En el **Panel de atención**, abrí una conversación.
2. Debajo del cuadro de texto vas a ver **"📎 Subir foto o archivo"**.
3. Clic ahí y elegí un archivo desde tu PC o desde el teléfono (galería, archivos).
4. Opcional: escribí un mensaje de texto.
5. Clic en **Enviar**. El archivo se sube a Firebase Storage, se obtiene una URL y se envía como adjunto en el mensaje (y por WhatsApp si la conversación es por ese canal).

---

## Requisitos en Firebase

Para que la subida funcione, en tu proyecto de Firebase tenés que tener **Storage** activo:

1. Entrá a [Firebase Console](https://console.firebase.google.com) → tu proyecto (ej. it-analyzer).
2. En el menú izquierdo: **Storage** (Build → Storage).
3. Si no está activado, **"Get started"** y aceptá las reglas por defecto (o las que quieras para producción).
4. El bucket por defecto (`tu-proyecto.appspot.com`) se usa automáticamente; no hace falta configurar nada más en la app.

**Variable de entorno (importante):** La app tiene que saber qué bucket usar. En tu `.env` (local) y en **Cloud Run** (variables del servicio) agregá:

```bash
FIREBASE_STORAGE_BUCKET=it-analyzer.firebasestorage.app
```

El nombre del bucket lo ves en la consola de Firebase → Storage → arriba donde dice el bucket (en tu caso `it-analyzer.firebasestorage.app`). Sin esta variable suele aparecer "Storage no configurado".

En **Cloud Run** las credenciales por defecto (ADC) ya tienen acceso a ese bucket si el servicio usa la misma cuenta de servicio del proyecto.

---

## Límites

- **Tamaño máximo:** 10 MB por archivo.
- **Tipos permitidos:** imágenes (jpg, jpeg, png, gif, webp) y PDF.

Si necesitás otros formatos (por ejemplo .doc), se pueden agregar en el backend (`UPLOAD_ALLOWED_EXTENSIONS` en `web_chat.py`).
