# Miribilla × Ecotisa · Portal privado 2027

Aplicación Flask con PostgreSQL Supabase, desplegada en Vercel. Los datos se conservan cifrados en el esquema `mbb_private`, fuera de los esquemas públicos de la API de Supabase. No se importan expedientes ficticios de la demo.

## Módulos

- Inicio de Dirección con resumen y accesos directos.
- Calendario, disponibilidad, convocatorias publicadas y paquete Excel para licencias y alojamiento.
- Planning: inscripciones, responsables, hoteles, habitaciones, salidas Bilbao/Zaragoza, recursos y enlaces de horarios/recorridos.
- Personal técnico, vehículos, material y dos medidas de ajuste.
- Fichas de corredores, tallas y pedidos de ropa, con dos hojas Excel.
- Licencias con estado y filtros; resultados y días de actividad.
- CONTA: ingresos/gastos, partidas de presupuesto, movimientos de banco CSV con revisión/confirmación y deduplicación, conciliación manual, liquidaciones individuales de hotel y manutención.
- Multas: motivos acordados e historial con estados.
- Comunicación: biblioteca de fotos autorizadas, cinco plantillas, formatos cuadrado/vertical/Story, diseños colectivos e individuales, borrador/aprobación, publicación disponible en el área del corredor, exportación PNG y menú de compartir del dispositivo.
- Alta individual o masiva por CSV, invitaciones de un solo uso, recuperación, desactivación/restauración, archivo reversible y auditoría.

El calendario previsto aportado por Dirección se recupera una sola vez: doce carreras con fechas y participación pendientes. No sobrescribe carreras existentes ni inventa fechas, DNI, contactos o cuentas de corredores.

## Acceso

Contraseña mínima de seis caracteres, sin TOTP, según petición expresa del titular. Scrypt, limitación de intentos, cookies HttpOnly/Secure/SameSite y CSRF. El navegador puede guardar la contraseña con permiso del usuario; no se guarda en localStorage. «Recordarme» conserva sesión 30 días; sin marcarlo, sesión de navegador de máximo ocho horas y 30 minutos de inactividad. Desactivar el usuario revoca todas sus sesiones.

La protección de acceso de Vercel se mantiene. El acceso al despliegue puede requerir una cuenta Vercel autorizada; debe resolverse el acceso de visitantes antes del despliegue general al equipo. No desactivar esa capa automáticamente.

## Documentos y límites

`DOCUMENT_UPLOADS_ENABLED=false`: SEPA y autorizaciones no admiten nuevas cargas en producción. El DNI, la licencia federativa y las fotos deportivas admiten JPG/PNG, con decodificación y reescritura a JPEG, máximo 3 MB. Comunicación solo puede cargar/descargar fotos de corredores con permiso de imagen, nunca documentos privados. Los archivos usan cifrado y controles por objeto. Límite agregado de archivos: 400 MB en la base.

No se afirma que exista auditoría externa ni cumplimiento legal certificado. Con contraseña corta y sin segundo factor, no habilitar documentación sensible sin revisar de nuevo el modelo de protección. Supabase Free no ofrece las mismas copias automáticas y recuperación que el plan de pago de Render previsto inicialmente. No se ha contratado ningún servicio de pago.

CONTA incorpora lectura OCR local de fotos y PDF (digitales o escaneados), revisión obligatoria, base, IVA, NIF y asignación propuesta por fecha. Los originales de factura se guardan cifrados, sin compresión ni modificación, vinculados a un apunte y con descarga solo para Dirección. Máximo 4 MB por original y 8 páginas leídas. Las cargas de PDF están habilitadas únicamente como justificantes de CONTA; no para DNI, SEPA ni otros expedientes personales. La lectura descarga dependencias fijadas de Tesseract.js 7.0.0 y PDF.js 6.5.438 desde jsDelivr; los documentos se procesan localmente y solo se envían a la aplicación al confirmar Guardar. La sesión y el CSRF protegen carga y descarga. No hay cargos SEPA ni envío de correos automáticos ni publicación directa a Instagram. La importación bancaria admite CSV; no XLSX/PDF bancario en esta versión. El usuario descarga o comparte las imágenes por su propia acción.

## Configuración

`POSTGRES_URL` o `DATABASE_URL`, `ENCRYPTION_KEY`, `PUBLIC_ORIGIN`, `ADMIN_EMAIL`, `BOOTSTRAP_TOKEN_HASH`, `BOOTSTRAP_EXPIRES`, `DOCUMENT_UPLOADS_ENABLED`. Secretos solo en Vercel; nunca Git. Conservar la clave de cifrado en el gestor de secretos con copia controlada por el titular. Rotarla sin migrar los datos impide recuperar el contenido cifrado.

Vercel: framework Flask, raíz `private_portal`, entrada `app.py`, activos `public/static`. La creación de tablas es aditiva; la única migración de columna añade `sessions.remember` sin cambiar usuarios, contraseñas, sesiones ni registros existentes.

## Validación

`python -m pytest private_portal/test_security.py -q`
`npm --prefix qa ci && node qa/check-ui.cjs` (entorno local con jsdom)

Las pruebas cubren el aislamiento por rol y corredor, los flujos de archivo/restauración, protección documental por objeto, cookies, formularios, importaciones atómicas, consentimiento de fotos, convocatorias y exportación de listados sin DNI ni IBAN. Las comprobaciones DOM cubren navegación y guardado representativo; no sustituyen pruebas en móviles reales ni revisión de seguridad externa.

Prueba del parser OCR: `node qa/check-ocr.cjs` tras instalar las dependencias de QA.

### Laboral Kutxa y tesorería

Dirección puede usar la previsión a 13 semanas con un saldo inicial introducido manualmente y los vencimientos de Ingresos y gastos. El saldo contable sincronizado en el día se propone como saldo inicial.

Para activar la conexión de consulta, registra una aplicación en el panel de Enable Banking y registra la URL de retorno `PUBLIC_ORIGIN + /banco/laboral-kutxa/retorno`. Guarda `ENABLE_BANKING_APP_ID` y `ENABLE_BANKING_PRIVATE_KEY` como variables sensibles del servidor de producción y vuelve a desplegar. El equipo de importación es Netkom por defecto y puede elegirse con `LABORAL_KUTXA_TEAM` antes de vincular la cuenta. Vincula y sincroniza desde una cuenta propietaria de Dirección. Los movimientos ya importados se conservan al revocar el consentimiento.
