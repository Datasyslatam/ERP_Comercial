# Manual de usuario

## Ingreso y empresa activa
1. Ingrese con su correo y contraseña. Tras 5 intentos fallidos el usuario se bloquea 15 minutos.
2. En la barra superior seleccione la **empresa** (Colombia o Venezuela). Todo lo que vea y registre
   pertenece a esa empresa; el menú muestra solo lo que su rol permite.
3. La sesión se renueva sola mientras la pestaña esté abierta; al cerrarla debe ingresar de nuevo.

## Dashboard ejecutivo
- Elija la **vista** (general o por módulo), el **periodo** y, si aplica, **sede** y **centro de costo**.
- Cada tarjeta muestra el valor, el estado frente a la meta (En meta / Alerta / Crítico / Sin meta) y
  avisa "Pocos datos" cuando hay menos de 5 observaciones.
- **"Pendiente de datos"** significa que aún no existen transacciones para calcularlo: el sistema nunca
  rellena cifras.
- Al hacer clic se ve la fórmula exacta, la fuente, la unidad, la frecuencia, la meta, el responsable,
  la tendencia de 6 meses y el botón **Ver transacciones de origen**.
- **Exportar** descarga el tablero en CSV (queda registrado en auditoría).

## Compras
1. **Solicitud**: Compras → Solicitudes → *Nueva*. Agregue artículos y cantidades → *Enviar*.
2. **Aprobación**: un usuario distinto al solicitante la aprueba o rechaza (con motivo). Si la empresa
   configuró límites de aprobación, el monto debe estar dentro de su atribución.
3. **Cotizaciones**: *Cotizar* → registre las ofertas de cada proveedor → el comparativo recomienda la
   mejor (precio, cobertura y plazo) → *Adjudicar* crea la orden de compra.
4. **Orden de compra**: *Enviar a aprobación* → otro usuario *Aprueba*. Se valida el presupuesto del
   periodo (advertencia o bloqueo según política).
5. **Recepción**: en la orden → *Registrar recepción* (parcial o total, lote y vencimiento si el artículo
   lo exige). No se puede recibir más de lo pendiente. Los artículos con inspección quedan en cuarentena.
6. **Factura del proveedor**: Compras → Facturas → *Registrar factura*: seleccione las recepciones
   aceptadas, digite el precio facturado (se valida contra la OC con tolerancia) → *Contabilizar*.
   El sistema calcula IVA y retenciones y crea la cuenta por pagar. Un mismo número de factura del
   proveedor no puede registrarse dos veces.

## Calidad
- **Inspecciones pendientes**: registre los resultados de cada característica, la cantidad aceptada y la
  rechazada. Lo aceptado se libera a bodega; lo rechazado se devuelve al proveedor y se crea una **no
  conformidad**. Una característica crítica fuera de tolerancia impide aceptar sin concesión.
- **No conformidades**: Abierta → Análisis (causa raíz obligatoria) → Acción (acciones correctivas,
  preventivas o de contención) → Verificación → Cerrada. No se cierra con acciones abiertas.

## Almacén
- **Existencias y kardex**: saldos por ubicación y lote, reservado y disponible, valor; seleccione un
  artículo para ver su kardex con saldo acumulado. El indicador verde confirma que los saldos coinciden
  con el historial de movimientos.
- **Movimientos**: transferencias, consumos internos (con centro de costo), ajustes y bajas. Ajustes y
  bajas requieren **aprobación** por un usuario distinto a quien los crea.
- **Conteos físicos**: *Abrir conteo* por bodega → digite cantidades (conteo ciego) → un aprobador
  *Aprueba y ajusta*; las diferencias se contabilizan.

## Ventas, logística y facturación
1. **Pedido**: Ventas → Pedidos → *Nuevo*. *Confirmar y reservar* valida el cupo de crédito y reserva
   inventario (primero lo que vence primero; nunca lotes vencidos, bloqueados o en cuarentena).
2. **Despacho**: *Generar despacho* → *Planificar* (ruta, transportista, fecha de envío y dirección) →
   *Iniciar picking* → *Confirmar picking* (no puede superar lo solicitado/reservado) → *Empacar* →
   *Enviar* (placa, guía y flete) → *Registrar entrega* (quién recibe; entregas parciales generan
   incidencia). Durante el tránsito puede agregar eventos de seguimiento. Adjunte el soporte firmado como adjunto.
   - **Incidencias**: *Reportar incidencia* en el despacho (avería, faltante, retraso, rechazo, dirección);
     se resuelven desde el despacho o desde Logística → Incidencias de entrega.
   - **Devoluciones**: *Registrar devolución* en un despacho enviado: cantidad por artículo, estado
     (revendible o dañado) y ubicación de reingreso. Lo dañado genera una no conformidad. El valor se
     reconoce al cliente emitiendo una nota crédito.
   - **Rutas y plan de entregas**: Logística → Rutas y plan de entregas muestra, para una fecha, los
     despachos planificados agrupados por ruta, y permite crear las rutas.
3. **Factura**: desde el despacho → *Facturar* → en Facturación *Emitir*: asigna el número autorizado,
   contabiliza y crea la cuenta por cobrar. El envío al proveedor tecnológico es automático.
4. **Estados del documento electrónico**: Pendiente → Enviada → Aceptada / Rechazada / Error. Si fue
   rechazado por datos del cliente, corrija el tercero y use *Reenviar* (se conserva el número).
5. **Notas crédito/débito**: abra la factura emitida → *Nota crédito / débito* → elija el tipo, el
   concepto de corrección, el motivo y la cantidad/precio por línea. La nota queda en borrador y se emite
   desde el listado (requiere numeración autorizada para su tipo). Una factura emitida nunca se anula:
   se corrige con nota crédito.

> **Importante**: mientras no se contrate el proveedor tecnológico, los documentos se validan con el
> adaptador **SANDBOX** y muestran "Documento de PRUEBAS: sin validez fiscal".

## Contabilidad
- **Comprobantes**: los documentos comerciales se contabilizan solos. Los comprobantes manuales se crean
  en borrador (deben cuadrar) y los contabiliza otro usuario. Los contabilizados no se editan: se reversan.
- **Cartera y pagos**: antigüedad de saldos por cobrar y pagar; *Recaudar/Pagar* aplica el pago a la
  partida. En recaudos puede agregar las **retenciones que practica el cliente** (*+ Retención*, elegir la
  retención, digitar la base y *Calcular*): a la partida se aplica el valor recibido en banco más lo
  retenido. En Venezuela, cobros en divisas de contribuyentes especiales calculan el IGTF.
- **Estados financieros**: balance de prueba (con exportación), estado de resultados, balance general y
  flujo de efectivo, con trazabilidad al documento origen en el libro mayor.
- **Periodos**: cerrar bloquea contabilizaciones en el mes; reabrir exige justificación y un usuario
  distinto a quien cerró.

## Operaciones (si está activo para su empresa)
**Listas de materiales**: Operaciones → Listas de materiales → producto, cantidad base y componentes con
su % de desperdicio. Al crear una orden de producción con lista, los materiales se calculan solos.
Órdenes de producción, de servicio o mantenimiento: liberar → entregar
materiales → registrar horas → reportar unidades buenas, desperdicio y reproceso → terminar → cerrar
(la diferencia de costo va a variación).

## Importación de datos
Importar datos → elija la entidad → *Descargar plantilla* → cargue CSV/XLSX (puede mapear columnas con
JSON, p. ej. `{"NIT":"tax_id"}`) → revise las filas con error, corríjalas y guarde → *Importar filas
válidas*. Para **saldos iniciales** cree primero un lote con fecha de corte y origen documentado; otro
usuario lo aprueba y luego se contabiliza contra la cuenta puente de saldos iniciales.
