# Manual de usuario

## Ingreso y empresa activa
1. Ingrese con su correo y contraseña. Tras 5 intentos fallidos el usuario se bloquea 15 minutos.
   Bajo el formulario se indica si el servidor está **en línea** (y en qué entorno) o **sin conexión**;
   si aparece sin conexión, el problema es la API y no sus credenciales: avise a soporte.
2. En la barra superior seleccione la **empresa** (Colombia o Venezuela). Todo lo que vea y registre
   pertenece a esa empresa; el menú muestra solo lo que su rol permite.
   Las secciones del menú lateral (Gerencia, Compras, Almacén…) se despliegan con un clic y se pliegan
   con otro; la sección de la pantalla abierta se despliega sola y la opción actual queda resaltada.
   La barra superior muestra dónde está (sección › pantalla), la empresa activa con su país, su usuario y
   el botón **Salir**.
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

## Trazabilidad de documentos
- *Gerencia → Trazabilidad de documentos*: busque cualquier documento por su número (OC, recepción, factura de
  proveedor, cotización, pedido, despacho, factura electrónica, pago o comprobante) y vea su **cadena
  completa**: de dónde viene, qué generó, cómo se pagó y qué comprobantes contables produjo.
- La misma cadena aparece al final de las órdenes de compra, recepciones, cotizaciones, pedidos, despachos,
  facturas, pagos y comprobantes. Cada tarjeta lleva al documento; las de módulos que su rol no puede consultar
  aparecen como *Sin acceso*.
- En el **kardex**, un clic en un movimiento de recepción, despacho, devolución o inspección abre su cadena.

## Documentos en PDF y envío por correo
- En la **cotización**, el **pedido**, la **orden de compra**, la **factura o nota** y el **pago** (recibo de caja
  o comprobante de egreso) hay dos acciones: *Descargar PDF* y *Enviar por correo*.
- El PDF lleva los datos de la empresa y del tercero, las líneas con descuentos e impuestos, los totales y, en
  facturas, el CUFE / número de control y la autorización de numeración. Mientras se opere con el adaptador
  SANDBOX, la factura indica "Documento de PRUEBAS: sin validez fiscal".
- El **recibo de caja** (recaudo de cliente) y el **comprobante de egreso** (pago a proveedor) detallan los
  documentos pagados, las retenciones con su número de comprobante de retención, el IGTF si aplica, el valor en
  letras y, en egresos, la línea de firma de quien recibe. Un pago anulado se imprime con la marca "ANULADO".
- *Enviar por correo* propone el correo del cliente o proveedor, el asunto y un mensaje que puede editar; admite
  varios destinatarios y copia. El envío queda en cola y el historial muestra si fue entregado o el error.
- Solo se envía lo que tiene sentido para el negocio: cotizaciones vigentes (al enviarla pasa a *Enviada*), pedidos
  confirmados, órdenes de compra aprobadas, facturas emitidas y pagos contabilizados (no anulados).

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
   proveedor no puede registrarse dos veces. Si la empresa practica las retenciones **al pagar** (ver
   Contabilidad → Pagos y recaudos), la factura se causa sin retenciones y estas se liquidan en el pago.
   En **Venezuela** el **número de control** de la factura del proveedor es obligatorio (sin él no se
   contabiliza): va al libro de compras y al TXT de retenciones. La retención de IVA practicada al
   contabilizar recibe su comprobante (`AAAAMM` + 8 dígitos, consecutivo propio).
7. **Rechazo o anulación de la OC**: el aprobador puede *Rechazar* con motivo; una orden sin recepciones se
   *Anula* con motivo. Mientras está en borrador, *Editar* permite cambiar proveedor, bodega, fechas y líneas.
- **Recepciones**: listado por periodo y proveedor con lote, vencimiento, cantidades aceptadas, rechazadas y
  facturadas y estado de inspección.
- **Historial de precios**: por artículo, precios pactados por proveedor con mínimo, máximo y variación frente
  a la compra anterior.
- **Evaluación de proveedores**: ranking del periodo por entrega a tiempo y aceptación de calidad (≥ 90
  confiable, 75–89 seguimiento, < 75 plan de mejora).
- **Presupuesto de compras**: comprometido en órdenes aprobadas frente al presupuesto del mes y centro de costo.

## Calidad
- **Planes de inspección**: por artículo o categoría y etapa (recepción, proceso, final, despacho), con
  características numéricas (mínimo, objetivo, máximo, unidad), de cumple/no cumple u observación, y marca de
  característica crítica.
- **Lotes e historial**: estado de cada lote (liberado, cuarentena, bloqueado) y su cambio con motivo; el
  historial de inspecciones y no conformidades por lote, artículo o proveedor.
- **Inspecciones pendientes**: registre los resultados de cada característica, la cantidad aceptada y la
  rechazada. Lo aceptado se libera a bodega; lo rechazado se devuelve al proveedor y se crea una **no
  conformidad**. Una característica crítica fuera de tolerancia impide aceptar sin concesión.
- **No conformidades**: Abierta → Análisis (causa raíz obligatoria) → Acción (acciones correctivas,
  preventivas o de contención) → Verificación → Cerrada. No se cierra con acciones abiertas.

## Almacén
- **Existencias**: saldos por ubicación y lote, reservado y disponible, valor. El indicador verde confirma
  que los saldos coinciden con el historial de movimientos.
- **Kardex**: por artículo y rango de fechas, con saldo inicial, entradas, salidas, costo y saldo valorizado.
- **Reabastecimiento**: artículos con disponible bajo el mínimo y cantidad sugerida hasta el máximo. Ajuste
  las cantidades, elija la sede y *Generar solicitud de compra*: se crea en borrador con el último precio de
  compra como estimado y sigue el flujo normal de aprobación.
- **Vencimientos**: lotes con existencia que vencen dentro del horizonte elegido (despache primero lo que
  vence antes).
- **Movimientos**: transferencias, consumos internos (con centro de costo), ajustes y bajas. Ajustes y
  bajas requieren **aprobación** por un usuario distinto a quien los crea.
- **Conteos físicos**: *Abrir conteo* por bodega → digite cantidades (conteo ciego) → un aprobador
  *Aprueba y ajusta*; las diferencias se contabilizan.

## Precios y promociones
- **Listas de precios** (*Ventas y logística → Listas de precios*): por moneda y vigencia, con uno o varios tramos
  por artículo (*Desde cantidad*). Repetir un artículo con una cantidad mínima mayor y un precio menor es un descuento
  por volumen. Cada cliente puede tener su lista (*Asignar clientes*); una lista por moneda es la *predeterminada*.
- **Cómo se fija el precio** de una línea de cotización o pedido sin precio digitado: lista del cliente → lista
  predeterminada → precio base del artículo. Lo digitado a mano siempre se respeta.
- **Promociones** (*Ventas y logística → Promociones*): descuento porcentual con vigencia para un artículo, una
  categoría o todo el catálogo, con cantidad mínima y cliente opcionales. Se aplica sola cuando la línea no trae
  descuento digitado (dejar *Desc. %* vacío); si varias aplican, gana la mayor. Escribir 0 desactiva la promoción en esa
  línea.
- Las líneas muestran el **origen del precio** (manual, lista de precios, precio base o cotización) y si tienen
  promoción. *Consultar precio* muestra lo que obtendría un cliente por un artículo y cantidad antes de cotizar.

## Ventas, logística y facturación
0. **Cotización**: Ventas → Cotizaciones → *Nueva* (cliente, vigencia, precios y descuentos). *Marcar como
   enviada* cuando la reciba el cliente. *Convertir en pedido* crea el pedido con las mismas condiciones;
   *Registrar como perdida* exige el motivo (precio, plazo, competencia). Vencida la vigencia no se convierte:
   emita una nueva con precios actualizados. *Editar* solo está disponible en borrador (una enviada ya la tiene el
   cliente); *Anular* (con motivo) es para errores, duplicados o cuando se reemplaza por una nueva.
1. **Pedido**: Ventas → Pedidos → *Nuevo* (o desde la cotización). *Confirmar y reservar* valida el cupo de
   crédito y reserva inventario (primero lo que vence primero; nunca lotes vencidos, bloqueados o en
   cuarentena). La ficha del pedido muestra por línea lo pedido, la reserva vigente, lo despachado, facturado,
   devuelto y pendiente, y el cupo de crédito disponible del cliente mientras está en borrador.
   - **Editar**: un pedido en borrador se puede modificar (cliente, bodega, fechas, dirección y líneas); al guardar
     se recalculan precios, promociones e impuestos. Confirmado ya no se edita.
   - **Cerrar saldo**: si el cliente ya no requiere lo pendiente, el pedido se cierra con motivo y se liberan
     sus reservas (no debe haber despachos en preparación). **Anular** solo aplica a pedidos sin despachos.
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
   se corrige con nota crédito. Un borrador sí puede *Anularse* con motivo.
6. **Conciliación fiscal**: en Facturación → *Conciliación fiscal* verifica, para el periodo, que cada
   documento emitido tenga asiento contable vigente, partida en cartera por el mismo valor y aceptación
   electrónica.

> **Importante**: mientras no se contrate el proveedor tecnológico, los documentos se validan con el
> adaptador **SANDBOX** y muestran "Documento de PRUEBAS: sin validez fiscal".

## Contabilidad
- **Comprobantes**: los documentos comerciales se contabilizan solos. Los comprobantes manuales se crean
  en borrador (deben cuadrar) y los contabiliza otro usuario. Los contabilizados no se editan: se reversan.
- **Cartera por edades**: antigüedad de saldos por cobrar y pagar; *Recaudar/Pagar* aplica el pago a la
  partida. En recaudos puede agregar las **retenciones que practica el cliente** (*+ Retención*, elegir la
  retención, digitar la base y *Calcular*): a la partida se aplica el valor recibido en banco más lo
  retenido. En Venezuela, cobros en divisas de contribuyentes especiales calculan el IGTF.
- **Retenciones al pagar a proveedores**: en *Pagar*, *Sugerir según el proveedor* propone las retenciones
  configuradas para el proveedor sobre la parte que se paga (base proporcional, bases mínimas) y omite las
  que la factura ya liquidó; el valor pagado se propone neto de retenciones. Cada retención recibe su número
  de **comprobante de retención** (Colombia `CR-000001`; Venezuela `AAAAMM` + secuencia de 8 dígitos) y se
  contabiliza en la cuenta de retenciones por pagar. Una misma retención no se practica dos veces sobre la
  misma factura. Solo aplica si la empresa es agente de retención.
- **Pagos y recaudos**: historial con tercero, medio, retenciones y valor; abra uno para ver su trazabilidad,
  descargar o enviar el recibo / comprobante de egreso, o *Anularlo* con motivo (reabre las partidas
  aplicadas y reversa el comprobante). Quien administra la empresa elige ahí el momento de las
  **retenciones a proveedores**: *al causar la factura* (por defecto) o *al pagar*; el cambio rige para las
  facturas que se registren desde entonces.
- **Conciliación bancaria**: *Cargar extracto* → *Archivo del banco* lee el extracto en **CSV**, **Excel
  (.xlsx)** u **OFX** (fecha, descripción, referencia y valor, o columnas separadas de débito y crédito; montos
  en formato local `1.234,56` o internacional) y prellena los movimientos, los saldos inicial y final y la fecha
  de corte; revise los avisos de filas no reconocidas antes de cargar. También puede pegar los movimientos
  (`AAAA-MM-DD;descripción;referencia;valor`, débitos en negativo). El saldo inicial más los movimientos debe
  dar el saldo final. Luego *Conciliar automáticamente* empareja por valor
  y fecha; lo restante se concilia a mano con la partida en libros del mismo valor o se marca *Ignorar*. La
  diferencia la explican las partidas en libros aún no reflejadas por el banco.
- **Estados financieros**: balance de prueba (con exportación), estado de resultados, balance general, flujo
  de efectivo, **libro mayor** por cuenta y **libro diario**.
- **Libros y reportes fiscales** (Contabilidad → Libros y reportes fiscales; elija el periodo arriba). Todo
  en la moneda funcional, convertido con la tasa de cada documento. Valídelos con el contador antes de
  presentarlos: el ERP los genera, no los declara.
  - **Venezuela**
    - *Libro de ventas*: facturas, notas de débito y crédito (con la factura afectada), anuladas como
      `03-ANU`, ventas exentas y bases e IVA por alícuota (general 16 %, reducida 8 %, general + adicional),
      tipo de cliente (contribuyente o no) y las **retenciones de IVA que nos practicaron** con el número de
      comprobante del cliente. Ese número se registra al *Recaudar*, en la columna *Comprobante del cliente*
      de cada retención.
    - *Libro de compras*: facturas de proveedor con número de control, compras exentas, bases e IVA por
      alícuota y el IVA retenido con su comprobante. Las retenciones de facturas de periodos anteriores
      aparecen como línea propia.
    - *Retenciones de IVA*: comprobantes emitidos en el periodo, su **PDF** (formato de la Providencia
      SNAT/2015/0049, una línea por alícuota) y el **TXT para el portal del SENIAT** por quincena o mes
      completo (16 campos separados por tabulador: RIF del agente, periodo, fecha, tipo de operación `C`,
      tipo de documento `01`, RIF del proveedor, factura, control, total, base, IVA retenido, documento
      afectado, comprobante, exento, alícuota y expediente).
    - Los avisos señalan lo que falta antes de presentar (facturas sin número de control, retenciones sin
      comprobante). Los libros se exportan a Excel.
  - **Colombia**
    - *Auxiliar de IVA*: IVA generado (ventas y notas) y descontable (facturas de proveedor) por documento y
      tarifa, retenciones de IVA que nos practicaron y el saldo estimado del periodo; exportable a Excel.
    - *Certificados de retención*: elija **fuente, IVA o ICA**; aparece un certificado por tercero con sus
      conceptos, bases y valores retenidos (practicados al causar o al pagar) y el PDF listo para entregar
      (artículo 381 del Estatuto Tributario, valor en letras, ciudad de práctica y consignación tomada de la
      ciudad de la empresa).
- **Comprobantes**: un clic abre sus líneas (cuenta, tercero, débito, crédito) y la cadena del documento que
  lo originó.
- **Periodos**: cerrar bloquea contabilizaciones en el mes; reabrir exige justificación y un usuario
  distinto a quien cerró. *Cierre del ejercicio* genera el asiento que traslada ingresos, costos y gastos del
  año anterior a resultados acumulados.

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
