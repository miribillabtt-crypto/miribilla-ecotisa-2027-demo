# Miribilla × Ecotisa: portal privado inicial

Primera versión separada de la demo pública. No importa automáticamente datos de localStorage ni datos ficticios.

## Inicio

- Instalar `pip install -r private_portal/requirements.txt`.
- Arrancar con `python -m gunicorn --chdir private_portal 'server:create_app()' --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60`.
- Configurar `DATABASE_URL` con PostgreSQL; SQLite se usa únicamente en pruebas.
- Configurar `ENCRYPTION_KEY` con una clave Fernet generada aleatoriamente; conservarla fuera del repositorio, en el gestor de secretos de Render, con copia de recuperación controlada por el titular.
- `PUBLIC_ORIGIN`: origen HTTPS exacto, sin barra final.
- Alta inicial mediante `BOOTSTRAP_TOKEN_HASH`, SHA256 de un token aleatorio de 40 bytes o más; `BOOTSTRAP_EXPIRES`, Unix timestamp de caducidad; `ADMIN_EMAIL`, correo del responsable. Nunca guardar el token ni el cifrado en Git.
- El responsable recibe `https://ORIGEN/#activar=TOKEN` por un canal privado. La primera activación crea la dirección responsable. Enlaces posteriores se generan en Usuarios y no se envían automáticamente.
- `DOCUMENT_UPLOADS_ENABLED` no permite cargas salvo que tenga el valor `true`. Activar solo tras comprobar permisos en el despliegue real y las copias de recuperación.

## Funciones incluidas

Usuarios individuales, contraseña scrypt, TOTP obligatorio, invitaciones con vencimiento y de un solo uso, revocación de sesiones, recuperación mediante Dirección responsable; perfiles con permisos del lado del servidor; calendario compartido, disponibilidad y convocatoria; tallas, cantidades y exportación XLSX con dos hojas; registro de multas; expedientes y fotos cifrados con Fernet; acceso a fotos para Comunicación sujeto a consentimiento; registro de cambios y descargas.

Los documentos iniciales se limitan a JPG/PNG, decodificados y convertidos a JPEG. No se admite PDF en esta versión. Límite de carga 8 MB por archivo y 400 MB para todos los archivos: revisar almacenamiento antes de ampliar. No se publican rutas de disco ni enlaces de archivo sin autenticación.

## Límites del primer lanzamiento

- El generador de publicaciones y los módulos de contabilidad/logística de la demo no están migrados. Permanecen en la demo; no presentarlos como integrados.
- No hay envío de correo configurado: Dirección entrega las invitaciones a cada persona.
- No hay recuperación de segundo factor por correo. La dirección responsable debe conservar su clave de autenticación; la recuperación excepcional del propietario requiere intervención sobre la infraestructura.
- No hay todavía programación automática de retención documental ni pantalla de solicitud de derechos. El borrado disponible es manual y deja trazabilidad; las copias mantienen la ventana de recuperación del proveedor.
- El acceso a DNI/SEPA se concede aparte del rol Dirección. Técnicos y Comunicación nunca reciben datos personales o bancarios.
- La autorización de imágenes de menores debe registrarse por sus representantes antes de activar el consentimiento.
- No afirmar certificación legal ni auditoría externa. Las pruebas automatizadas cubren permisos y flujos conocidos; no sustituyen una revisión completa de seguridad ni las obligaciones del responsable del tratamiento.

## Despliegue previsto

Render, región Frankfurt; servidor mínimo 0.5c-512mb y Postgres 0.1c-256mb con 1 GB. Una base de pago conserva datos y ofrece recuperación del proveedor. Inspeccionar política de acceso a la base, cifrado, origen, secretos y copias antes de autorizar documentos reales.

**Estado al preparar esta versión:** Render rechaza crear Postgres con HTTP 402 porque falta método de pago. No se ha creado la base ni el servidor privado, no hay usuarios reales activos y la carga documental queda deshabilitada. No usar la demo pública para DNI, SEPA o datos bancarios.

## Validación

`python -m pytest private_portal/test_security.py -q`

Comprueba falta de autenticación, separación de corredores, exclusión de técnicos/Comunicación, documentos por objeto, Dirección limitada, cifrado de archivos, CSRF, revocación de sesiones, repetición TOTP, invitaciones de un solo uso, enlace vencido, invalidación de recuperaciones anteriores, exportación de cantidades, disponibilidad previa a convocatoria, consentimiento de imágenes y limitación de intentos.
