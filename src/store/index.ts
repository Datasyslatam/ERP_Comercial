// ============================================================
// DATASYS LATAM GROUP - ERP Enterprise System
// Data Store - Synthetic Data (Development Environment)
// ============================================================
import { v4 as uuidv4 } from 'uuid';
import type {
  Company, Branch, User, Supplier, Article, Warehouse,
  PurchaseOrder, PurchaseRequest, GoodsReceipt, WorkOrder,
  QualityInspection, NonConformance, ShipmentOrder, Customer,
  Invoice, ChartOfAccount, JournalEntry, AccountingPeriod,
  CostCenter, KPI, AuditLog, Carrier, InventoryMovement,
  AccountsReceivable, AccountsPayable, Budget
} from '../types';

const STORAGE_KEY = 'datasys_erp_data';

// --- SYNTHETIC DATA GENERATOR ---
function generateSyntheticData() {
  const now = new Date().toISOString();
  const company: Company = {
    id: 'comp-001', name: 'DATASYS LATAM GROUP', taxId: 'DLG-2024-001',
    country: 'EC', currency: 'USD', fiscalRegime: 'General',
    address: 'Av. Principal 123, Quito', phone: '+593-2-1234567',
    email: 'info@datasyslatam.com', active: true
  };

  const branches: Branch[] = [
    { id: 'br-001', companyId: 'comp-001', name: 'Casa Matriz Quito', code: 'UIO', address: 'Av. Principal 123', active: true },
    { id: 'br-002', companyId: 'comp-001', name: 'Sucursal Guayaquil', code: 'GYE', address: 'Av. del Río 456', active: true },
    { id: 'br-003', companyId: 'comp-001', name: 'Sucursal Cuenca', code: 'CUE', address: 'Calle Larga 789', active: true },
  ];

  const users: User[] = [
    { id: 'usr-001', username: 'admin', fullName: 'Carlos Administrador', email: 'admin@datasyslatam.com', role: 'admin', branchId: 'br-001', active: true, createdAt: now },
    { id: 'usr-002', username: 'mgarcia', fullName: 'María García', email: 'mgarcia@datasyslatam.com', role: 'manager', branchId: 'br-001', active: true, createdAt: now },
    { id: 'usr-003', username: 'llopez', fullName: 'Luis López', email: 'llopez@datasyslatam.com', role: 'accountant', branchId: 'br-001', active: true, createdAt: now },
    { id: 'usr-004', username: 'amartinez', fullName: 'Ana Martínez', email: 'amartinez@datasyslatam.com', role: 'warehouse', branchId: 'br-001', active: true, createdAt: now },
    { id: 'usr-005', username: 'jramirez', fullName: 'Jorge Ramírez', email: 'jramirez@datasyslatam.com', role: 'purchasing', branchId: 'br-002', active: true, createdAt: now },
    { id: 'usr-006', username: 'psalazar', fullName: 'Patricia Salazar', email: 'psalazar@datasyslatam.com', role: 'quality', branchId: 'br-001', active: true, createdAt: now },
  ];

  const suppliers: Supplier[] = [
    { id: 'sup-001', name: 'Distribuidora Industrial SA', taxId: '1234567890001', contactName: 'Roberto Sánchez', email: 'rsanchez@distind.com', phone: '+593-2-9876543', address: 'Zona Industrial Norte', category: 'Materias Primas', rating: 4.5, paymentTerms: 30, active: true, createdAt: now },
    { id: 'sup-002', name: 'Tecnología y Suministros EC', taxId: '9876543210001', contactName: 'Elena Torres', email: 'etorres@tecsumec.com', phone: '+593-4-5551234', address: 'Parque Industrial GYE', category: 'Equipos', rating: 4.2, paymentTerms: 15, active: true, createdAt: now },
    { id: 'sup-003', name: 'Químicos del Pacífico', taxId: '5556667770001', contactName: 'Fernando Vega', email: 'fvega@quimicospac.com', phone: '+593-2-4445678', address: 'Vía a la Costa Km 12', category: 'Insumos Químicos', rating: 3.8, paymentTerms: 45, active: true, createdAt: now },
    { id: 'sup-004', name: 'Embalajes Modernos', taxId: '1112223330001', contactName: 'Sandra Mora', email: 'smora@embmod.com', phone: '+593-2-3334567', address: 'Industrial Sur', category: 'Embalajes', rating: 4.0, paymentTerms: 20, active: true, createdAt: now },
    { id: 'sup-005', name: 'Servicios Logísticos Express', taxId: '9998887770001', contactName: 'Diego Herrera', email: 'dherrera@slexpress.com', phone: '+593-2-2223456', address: 'Centro Empresarial', category: 'Logística', rating: 4.7, paymentTerms: 30, active: true, createdAt: now },
  ];

  const articles: Article[] = [
    { id: 'art-001', code: 'MP-001', name: 'Resina Polimérica Tipo A', description: 'Materia prima principal', category: 'Materias Primas', type: 'raw_material', unit: 'kg', minStock: 100, maxStock: 5000, reorderPoint: 200, cost: 12.50, costMethod: 'weighted_avg', active: true, createdAt: now },
    { id: 'art-002', code: 'MP-002', name: 'Aditivo Catalizador X', description: 'Catalizador para proceso', category: 'Insumos', type: 'raw_material', unit: 'lt', minStock: 50, maxStock: 1000, reorderPoint: 100, cost: 45.00, costMethod: 'weighted_avg', active: true, createdAt: now },
    { id: 'art-003', code: 'MP-003', name: 'Pigmento Azul Industrial', description: 'Colorante para producción', category: 'Insumos', type: 'raw_material', unit: 'kg', minStock: 20, maxStock: 500, reorderPoint: 50, cost: 85.00, costMethod: 'fifo', active: true, createdAt: now },
    { id: 'art-004', code: 'PT-001', name: 'Producto Terminado Alfa', description: 'Producto principal línea 1', category: 'Productos', type: 'finished', unit: 'un', minStock: 50, maxStock: 2000, reorderPoint: 100, cost: 125.00, costMethod: 'standard', active: true, createdAt: now },
    { id: 'art-005', code: 'PT-002', name: 'Producto Terminado Beta', description: 'Producto línea 2', category: 'Productos', type: 'finished', unit: 'un', minStock: 30, maxStock: 1500, reorderPoint: 75, cost: 250.00, costMethod: 'standard', active: true, createdAt: now },
    { id: 'art-006', code: 'SU-001', name: 'Caja Cartón 40x30x20', description: 'Embalaje estándar', category: 'Embalajes', type: 'supply', unit: 'un', minStock: 200, maxStock: 5000, reorderPoint: 500, cost: 1.50, costMethod: 'weighted_avg', active: true, createdAt: now },
    { id: 'art-007', code: 'SU-002', name: 'Etiqueta Código Barras', description: 'Etiqueta de identificación', category: 'Embalajes', type: 'supply', unit: 'un', minStock: 1000, maxStock: 20000, reorderPoint: 2000, cost: 0.05, costMethod: 'weighted_avg', active: true, createdAt: now },
    { id: 'art-008', code: 'PP-001', name: 'Semielaborado Base', description: 'Producto en proceso', category: 'Semielaborados', type: 'wip', unit: 'kg', minStock: 10, maxStock: 500, reorderPoint: 50, cost: 65.00, costMethod: 'weighted_avg', active: true, createdAt: now },
  ];

  const warehouses: Warehouse[] = [
    { id: 'wh-001', code: 'BOD-MP', name: 'Bodega Materias Primas', branchId: 'br-001', type: 'raw_materials', zones: [{ id: 'z-001', code: 'Z1', name: 'Zona A', warehouseId: 'wh-001' }, { id: 'z-002', code: 'Z2', name: 'Zona B', warehouseId: 'wh-001' }], active: true },
    { id: 'wh-002', code: 'BOD-PT', name: 'Bodega Productos Terminados', branchId: 'br-001', type: 'finished', zones: [{ id: 'z-003', code: 'Z1', name: 'Zona Despacho', warehouseId: 'wh-002' }, { id: 'z-004', code: 'Z2', name: 'Zona Reserva', warehouseId: 'wh-002' }], active: true },
    { id: 'wh-003', code: 'BOD-PP', name: 'Bodega Productos en Proceso', branchId: 'br-001', type: 'wip', zones: [{ id: 'z-005', code: 'Z1', name: 'Zona Principal', warehouseId: 'wh-003' }], active: true },
    { id: 'wh-004', code: 'BOD-GYE', name: 'Bodega Guayaquil', branchId: 'br-002', type: 'general', zones: [{ id: 'z-006', code: 'Z1', name: 'Zona General', warehouseId: 'wh-004' }], active: true },
  ];

  const customers: Customer[] = [
    { id: 'cus-001', name: 'Constructora Andina SA', taxId: '1789012345001', email: 'compras@conandina.com', phone: '+593-2-5550001', address: 'Av. Naciones Unidas 567', customerType: 'business', taxRegime: 'General', paymentTerms: 30, creditLimit: 50000, active: true, createdAt: now },
    { id: 'cus-002', name: 'Industrias del Valle', taxId: '1767890123001', email: 'admin@indvalle.com', phone: '+593-4-5550002', address: 'Zona Industrial Sur', customerType: 'business', taxRegime: 'General', paymentTerms: 15, creditLimit: 30000, active: true, createdAt: now },
    { id: 'cus-003', name: 'Gobierno Municipal Norte', taxId: '1700001000001', email: 'adquisiciones@municipionorte.gov', phone: '+593-2-5550003', address: 'Plaza Central', customerType: 'government', taxRegime: 'Public', paymentTerms: 45, creditLimit: 100000, active: true, createdAt: now },
    { id: 'cus-004', name: 'María Fernanda Ruiz', taxId: '1712345678', email: 'mfruiz@email.com', phone: '+593-9-5550004', address: 'Quito Norte', customerType: 'individual', taxRegime: 'RIMPE', paymentTerms: 0, creditLimit: 5000, active: true, createdAt: now },
  ];

  const carriers: Carrier[] = [
    { id: 'car-001', name: 'Transportes Rápidos SA', contactName: 'Miguel Ángel', phone: '+593-2-7770001', email: 'operaciones@transrap.com', coverageZones: ['Nacional'], active: true },
    { id: 'car-002', name: 'Logística Express EC', contactName: 'Carolina Paz', phone: '+593-4-7770002', email: 'info@logexpress.com', coverageZones: ['Costa', 'Sierra'], active: true },
  ];

  const purchaseOrders: PurchaseOrder[] = [
    { id: 'po-001', number: 'OC-2024-001', supplierId: 'sup-001', branchId: 'br-001', status: 'received', items: [{ id: 'poi-001', articleId: 'art-001', quantity: 500, receivedQuantity: 500, unitPrice: 12.00, taxRate: 12, total: 6000 }], subtotal: 6000, tax: 720, total: 6720, currency: 'USD', paymentTerms: 30, deliveryDate: '2024-11-15', createdAt: '2024-11-01T10:00:00Z', createdBy: 'usr-005' },
    { id: 'po-002', number: 'OC-2024-002', supplierId: 'sup-002', branchId: 'br-001', status: 'sent', items: [{ id: 'poi-002', articleId: 'art-002', quantity: 200, receivedQuantity: 0, unitPrice: 44.50, taxRate: 12, total: 8900 }], subtotal: 8900, tax: 1068, total: 9968, currency: 'USD', paymentTerms: 15, deliveryDate: '2024-12-01', createdAt: '2024-11-20T14:00:00Z', createdBy: 'usr-005' },
    { id: 'po-003', number: 'OC-2024-003', supplierId: 'sup-003', branchId: 'br-002', status: 'partial', items: [{ id: 'poi-003', articleId: 'art-003', quantity: 100, receivedQuantity: 60, unitPrice: 83.00, taxRate: 12, total: 4980 }], subtotal: 4980, tax: 597.60, total: 5577.60, currency: 'USD', paymentTerms: 45, deliveryDate: '2024-11-25', createdAt: '2024-11-10T09:00:00Z', createdBy: 'usr-005' },
  ];

  const purchaseRequests: PurchaseRequest[] = [
    { id: 'pr-001', number: 'SC-2024-001', branchId: 'br-001', requestedBy: 'usr-004', status: 'approved', items: [{ id: 'pri-001', articleId: 'art-001', quantity: 500, estimatedPrice: 12.50, notes: 'Reposición mensual' }], priority: 'high', justification: 'Stock bajo, necesario para producción', createdAt: '2024-10-28T08:00:00Z', approvedAt: '2024-10-29T10:00:00Z', approvedBy: 'usr-002' },
    { id: 'pr-002', number: 'SC-2024-002', branchId: 'br-001', requestedBy: 'usr-004', status: 'pending_approval', items: [{ id: 'pri-002', articleId: 'art-006', quantity: 2000, estimatedPrice: 1.50, notes: 'Embalajes para despachos diciembre' }], priority: 'medium', justification: 'Preparación temporada alta', createdAt: '2024-11-22T11:00:00Z' },
  ];

  const workOrders: WorkOrder[] = [
    { id: 'wo-001', number: 'OT-2024-001', productArticleId: 'art-004', plannedQuantity: 200, completedQuantity: 180, status: 'completed', priority: 'high', startDate: '2024-11-01', endDate: '2024-11-15', bomItems: [{ id: 'bom-001', articleId: 'art-001', quantityRequired: 2.5, unit: 'kg' }, { id: 'bom-002', articleId: 'art-002', quantityRequired: 0.1, unit: 'lt' }], actualConsumptions: [], branchId: 'br-001', createdBy: 'usr-002', createdAt: '2024-10-30T08:00:00Z' },
    { id: 'wo-002', number: 'OT-2024-002', productArticleId: 'art-005', plannedQuantity: 100, completedQuantity: 45, status: 'in_progress', priority: 'medium', startDate: '2024-11-20', bomItems: [{ id: 'bom-003', articleId: 'art-001', quantityRequired: 3.0, unit: 'kg' }, { id: 'bom-004', articleId: 'art-003', quantityRequired: 0.5, unit: 'kg' }], actualConsumptions: [], branchId: 'br-001', createdBy: 'usr-002', createdAt: '2024-11-18T08:00:00Z' },
  ];

  const qualityInspections: QualityInspection[] = [
    { id: 'qi-001', number: 'INS-2024-001', inspectionPlanId: 'ip-001', type: 'reception', referenceType: 'goods_receipt', referenceId: 'gr-001', articleId: 'art-001', lotNumber: 'LOT-2024-1101', sampleSize: 25, inspectedQuantity: 500, conformingQuantity: 495, nonConformingQuantity: 5, results: [{ criteriaId: 'cr-001', measuredValue: 99.2, specification: '>=98%', conforming: true }, { criteriaId: 'cr-002', measuredValue: 0.3, specification: '<=0.5%', conforming: true }], status: 'conditional', inspectorId: 'usr-006', inspectionDate: '2024-11-16T10:00:00Z', notes: '5 kg con humedad ligeramente elevada' },
    { id: 'qi-002', number: 'INS-2024-002', inspectionPlanId: 'ip-002', type: 'final', referenceType: 'work_order', referenceId: 'wo-001', articleId: 'art-004', lotNumber: 'LOT-PT-2024-001', sampleSize: 20, inspectedQuantity: 180, conformingQuantity: 180, nonConformingQuantity: 0, results: [{ criteriaId: 'cr-003', measuredValue: 100, specification: 'Peso 500g ±2g', conforming: true }], status: 'conforming', inspectorId: 'usr-006', inspectionDate: '2024-11-16T14:00:00Z', notes: 'Lote conforme en todos los parámetros' },
  ];

  const nonConformances: NonConformance[] = [
    { id: 'nc-001', number: 'NC-2024-001', inspectionId: 'qi-001', articleId: 'art-001', description: 'Humedad superior al límite en 5 kg del lote', severity: 'minor', rootCause: 'Almacenamiento inadecuado durante transporte', correctiveAction: 'Revisar condiciones de transporte con proveedor', status: 'in_progress', openedBy: 'usr-006', openedDate: '2024-11-16T11:00:00Z', cost: 62.50 },
    { id: 'nc-002', number: 'NC-2024-002', articleId: 'art-003', description: 'Variación de tono en pigmento recibido', severity: 'major', rootCause: 'Cambio de formulación no comunicada', correctiveAction: 'Solicitar certificado de análisis actualizado', preventiveAction: 'Incluir verificación de color en plan de inspección', status: 'closed', openedBy: 'usr-006', openedDate: '2024-10-15T09:00:00Z', closedDate: '2024-11-01T16:00:00Z', cost: 425.00 },
  ];

  const shipmentOrders: ShipmentOrder[] = [
    { id: 'so-001', number: 'DE-2024-001', customerId: 'cus-001', invoiceId: 'inv-001', status: 'delivered', items: [{ id: 'si-001', articleId: 'art-004', requestedQuantity: 50, pickedQuantity: 50, deliveredQuantity: 50 }], carrierId: 'car-001', trackingNumber: 'TRK-001-2024', plannedDate: '2024-11-18', actualDeliveryDate: '2024-11-18', branchId: 'br-001', createdBy: 'usr-004', createdAt: '2024-11-17T08:00:00Z' },
    { id: 'so-002', number: 'DE-2024-002', customerId: 'cus-002', invoiceId: 'inv-002', status: 'in_transit', items: [{ id: 'si-002', articleId: 'art-005', requestedQuantity: 30, pickedQuantity: 30, deliveredQuantity: 0 }], carrierId: 'car-002', trackingNumber: 'TRK-002-2024', plannedDate: '2024-11-25', branchId: 'br-001', createdBy: 'usr-004', createdAt: '2024-11-24T10:00:00Z' },
    { id: 'so-003', number: 'DE-2024-003', customerId: 'cus-003', status: 'pending', items: [{ id: 'si-003', articleId: 'art-004', requestedQuantity: 100, pickedQuantity: 0, deliveredQuantity: 0 }, { id: 'si-004', articleId: 'art-005', requestedQuantity: 50, pickedQuantity: 0, deliveredQuantity: 0 }], plannedDate: '2024-12-01', branchId: 'br-001', createdBy: 'usr-004', createdAt: '2024-11-25T09:00:00Z' },
  ];

  const invoices: Invoice[] = [
    { id: 'inv-001', number: '001-001-000012345', series: '001-001', customerId: 'cus-001', branchId: 'br-001', status: 'accepted', items: [{ id: 'ii-001', articleId: 'art-004', description: 'Producto Terminado Alfa', quantity: 50, unitPrice: 180, discount: 0, taxRate: 12, taxAmount: 1080, total: 10080 }], subtotal: 9000, taxAmount: 1080, total: 10080, currency: 'USD', paymentMethod: 'transfer', dueDate: '2024-12-17', issueDate: '2024-11-17', electronicId: 'SRI-2024-0012345', electronicStatus: 'AUTORIZADO', notes: '', createdBy: 'usr-003', createdAt: '2024-11-17T07:00:00Z' },
    { id: 'inv-002', number: '001-001-000012346', series: '001-001', customerId: 'cus-002', branchId: 'br-001', status: 'accepted', items: [{ id: 'ii-002', articleId: 'art-005', description: 'Producto Terminado Beta', quantity: 30, unitPrice: 350, discount: 0, taxRate: 12, taxAmount: 1260, total: 11760 }], subtotal: 10500, taxAmount: 1260, total: 11760, currency: 'USD', paymentMethod: 'credit', dueDate: '2024-12-02', issueDate: '2024-11-24', electronicId: 'SRI-2024-0012346', electronicStatus: 'AUTORIZADO', notes: '', createdBy: 'usr-003', createdAt: '2024-11-24T09:00:00Z' },
    { id: 'inv-003', number: '001-001-000012347', series: '001-001', customerId: 'cus-004', branchId: 'br-001', status: 'draft', items: [{ id: 'ii-003', articleId: 'art-004', description: 'Producto Terminado Alfa', quantity: 5, unitPrice: 195, discount: 0, taxRate: 12, taxAmount: 117, total: 1092 }], subtotal: 975, taxAmount: 117, total: 1092, currency: 'USD', paymentMethod: 'cash', dueDate: '2024-11-26', issueDate: '2024-11-26', notes: 'Venta mostrador', createdBy: 'usr-003', createdAt: '2024-11-26T10:00:00Z' },
  ];

  const chartOfAccounts: ChartOfAccount[] = [
    { id: 'coa-001', code: '1', name: 'ACTIVO', type: 'asset', level: 1, active: true, allowsMovement: false },
    { id: 'coa-002', code: '1.1', name: 'Activo Corriente', type: 'asset', parentId: 'coa-001', level: 2, active: true, allowsMovement: false },
    { id: 'coa-003', code: '1.1.01', name: 'Caja y Bancos', type: 'asset', parentId: 'coa-002', level: 3, active: true, allowsMovement: true },
    { id: 'coa-004', code: '1.1.02', name: 'Cuentas por Cobrar', type: 'asset', parentId: 'coa-002', level: 3, active: true, allowsMovement: true },
    { id: 'coa-005', code: '1.1.03', name: 'Inventarios', type: 'asset', parentId: 'coa-002', level: 3, active: true, allowsMovement: true },
    { id: 'coa-006', code: '1.2', name: 'Activo No Corriente', type: 'asset', parentId: 'coa-001', level: 2, active: true, allowsMovement: false },
    { id: 'coa-007', code: '1.2.01', name: 'Propiedad Planta y Equipo', type: 'asset', parentId: 'coa-006', level: 3, active: true, allowsMovement: true },
    { id: 'coa-008', code: '2', name: 'PASIVO', type: 'liability', level: 1, active: true, allowsMovement: false },
    { id: 'coa-009', code: '2.1', name: 'Pasivo Corriente', type: 'liability', parentId: 'coa-008', level: 2, active: true, allowsMovement: false },
    { id: 'coa-010', code: '2.1.01', name: 'Cuentas por Pagar', type: 'liability', parentId: 'coa-009', level: 3, active: true, allowsMovement: true },
    { id: 'coa-011', code: '2.1.02', name: 'Impuestos por Pagar', type: 'liability', parentId: 'coa-009', level: 3, active: true, allowsMovement: true },
    { id: 'coa-012', code: '3', name: 'PATRIMONIO', type: 'equity', level: 1, active: true, allowsMovement: false },
    { id: 'coa-013', code: '3.1', name: 'Capital Social', type: 'equity', parentId: 'coa-012', level: 2, active: true, allowsMovement: true },
    { id: 'coa-014', code: '4', name: 'INGRESOS', type: 'income', level: 1, active: true, allowsMovement: false },
    { id: 'coa-015', code: '4.1', name: 'Ingresos por Ventas', type: 'income', parentId: 'coa-014', level: 2, active: true, allowsMovement: true },
    { id: 'coa-016', code: '5', name: 'GASTOS', type: 'expense', level: 1, active: true, allowsMovement: false },
    { id: 'coa-017', code: '5.1', name: 'Costo de Ventas', type: 'expense', parentId: 'coa-016', level: 2, active: true, allowsMovement: true },
    { id: 'coa-018', code: '5.2', name: 'Gastos Operativos', type: 'expense', parentId: 'coa-016', level: 2, active: true, allowsMovement: true },
  ];

  const journalEntries: JournalEntry[] = [
    { id: 'je-001', number: 'AS-2024-001', date: '2024-11-17', reference: 'FV-001-001-000012345', referenceType: 'invoice', referenceId: 'inv-001', description: 'Venta de mercadería - Factura 001-001-000012345', lines: [{ id: 'jel-001', accountId: 'coa-004', debit: 10080, credit: 0, description: 'CxC Cliente Constructora Andina' }, { id: 'jel-002', accountId: 'coa-015', debit: 0, credit: 9000, description: 'Ingreso por venta' }, { id: 'jel-003', accountId: 'coa-011', debit: 0, credit: 1080, description: 'IVA generado' }], status: 'posted', periodId: 'per-2024-11', createdBy: 'usr-003', postedBy: 'usr-003', postedAt: '2024-11-17T08:00:00Z', createdAt: '2024-11-17T07:30:00Z' },
    { id: 'je-002', number: 'AS-2024-002', date: '2024-11-24', reference: 'FV-001-001-000012346', referenceType: 'invoice', referenceId: 'inv-002', description: 'Venta de mercadería - Factura 001-001-000012346', lines: [{ id: 'jel-004', accountId: 'coa-004', debit: 11760, credit: 0, description: 'CxC Cliente Industrias del Valle' }, { id: 'jel-005', accountId: 'coa-015', debit: 0, credit: 10500, description: 'Ingreso por venta' }, { id: 'jel-006', accountId: 'coa-011', debit: 0, credit: 1260, description: 'IVA generado' }], status: 'posted', periodId: 'per-2024-11', createdBy: 'usr-003', postedBy: 'usr-003', postedAt: '2024-11-24T10:00:00Z', createdAt: '2024-11-24T09:30:00Z' },
  ];

  const accountingPeriods: AccountingPeriod[] = [
    { id: 'per-2024-10', year: 2024, month: 10, status: 'closed', closedBy: 'usr-003', closedAt: '2024-11-05T08:00:00Z' },
    { id: 'per-2024-11', year: 2024, month: 11, status: 'open' },
    { id: 'per-2024-12', year: 2024, month: 12, status: 'open' },
  ];

  const costCenters: CostCenter[] = [
    { id: 'cc-001', code: 'CC-01', name: 'Administración General', active: true },
    { id: 'cc-002', code: 'CC-02', name: 'Producción', active: true },
    { id: 'cc-003', code: 'CC-03', name: 'Ventas', active: true },
    { id: 'cc-004', code: 'CC-04', name: 'Logística', active: true },
    { id: 'cc-005', code: 'CC-05', name: 'Investigación y Desarrollo', active: true },
  ];

  const inventoryMovements: InventoryMovement[] = [
    { id: 'im-001', type: 'in', articleId: 'art-001', warehouseId: 'wh-001', zoneId: 'z-001', quantity: 500, cost: 6000, reference: 'OC-2024-001', referenceType: 'purchase_order', referenceId: 'po-001', lotNumber: 'LOT-2024-1101', reason: 'Recepción de compra', userId: 'usr-004', timestamp: '2024-11-15T14:00:00Z' },
    { id: 'im-002', type: 'out', articleId: 'art-001', warehouseId: 'wh-001', zoneId: 'z-001', quantity: 500, cost: 6250, reference: 'OT-2024-001', referenceType: 'work_order', referenceId: 'wo-001', reason: 'Consumo en orden de trabajo', userId: 'usr-004', timestamp: '2024-11-02T08:00:00Z' },
    { id: 'im-003', type: 'in', articleId: 'art-004', warehouseId: 'wh-002', zoneId: 'z-003', quantity: 180, cost: 22500, reference: 'OT-2024-001', referenceType: 'work_order', referenceId: 'wo-001', lotNumber: 'LOT-PT-2024-001', reason: 'Producto terminado de OT', userId: 'usr-004', timestamp: '2024-11-15T16:00:00Z' },
    { id: 'im-004', type: 'out', articleId: 'art-004', warehouseId: 'wh-002', zoneId: 'z-003', quantity: 50, cost: 6250, reference: 'DE-2024-001', referenceType: 'shipment', referenceId: 'so-001', reason: 'Despacho a cliente', userId: 'usr-004', timestamp: '2024-11-17T07:00:00Z' },
  ];

  const accountsReceivable: AccountsReceivable[] = [
    { id: 'ar-001', customerId: 'cus-001', invoiceId: 'inv-001', amount: 10080, paidAmount: 0, dueDate: '2024-12-17', status: 'open', currency: 'USD' },
    { id: 'ar-002', customerId: 'cus-002', invoiceId: 'inv-002', amount: 11760, paidAmount: 0, dueDate: '2024-12-02', status: 'open', currency: 'USD' },
  ];

  const accountsPayable: AccountsPayable[] = [
    { id: 'ap-001', supplierId: 'sup-001', invoiceId: 'po-001', amount: 6720, paidAmount: 6720, dueDate: '2024-12-01', status: 'paid', currency: 'USD' },
    { id: 'ap-002', supplierId: 'sup-002', invoiceId: 'po-002', amount: 9968, paidAmount: 0, dueDate: '2024-12-05', status: 'open', currency: 'USD' },
  ];

  const budgets: Budget[] = [
    { id: 'bud-001', name: 'Presupuesto Ventas Q4 2024', year: 2024, period: 'Q4', accountId: 'coa-015', amount: 250000, currency: 'USD', status: 'approved' },
    { id: 'bud-002', name: 'Presupuesto Compras Q4 2024', year: 2024, period: 'Q4', accountId: 'coa-017', amount: 120000, currency: 'USD', status: 'approved' },
    { id: 'bud-003', name: 'Presupuesto Gastos Operativos Q4 2024', year: 2024, period: 'Q4', accountId: 'coa-018', amount: 80000, currency: 'USD', status: 'approved' },
  ];

  const auditLogs: AuditLog[] = [
    { id: 'al-001', userId: 'usr-001', action: 'LOGIN', module: 'auth', entityId: 'usr-001', entityType: 'user', details: 'Inicio de sesión exitoso', timestamp: now, ipAddress: '192.168.1.100' },
    { id: 'al-002', userId: 'usr-005', action: 'CREATE', module: 'purchasing', entityId: 'po-001', entityType: 'purchase_order', details: 'Creó orden de compra OC-2024-001', timestamp: '2024-11-01T10:00:00Z', ipAddress: '192.168.1.105' },
    { id: 'al-003', userId: 'usr-003', action: 'POST', module: 'accounting', entityId: 'je-001', entityType: 'journal_entry', details: 'Contabilizó asiento AS-2024-001', timestamp: '2024-11-17T08:00:00Z', ipAddress: '192.168.1.103' },
  ];

  const kpis: KPI[] = [
    { id: 'kpi-001', name: 'Ingresos del Período', description: 'Total de ingresos facturados', formula: 'SUM(invoice.total) WHERE status=accepted', module: 'finance', value: 21840, target: 62500, unit: 'USD', frequency: 'monthly', alertThreshold: 50, warningThreshold: 75, status: 'warning', lastUpdated: now, responsible: 'Gerencia' },
    { id: 'kpi-002', name: 'Margen Bruto', description: 'Porcentaje de margen sobre ingresos', formula: '(Ingresos - Costo Ventas) / Ingresos * 100', module: 'finance', value: 42.5, target: 45, unit: '%', frequency: 'monthly', alertThreshold: 30, warningThreshold: 38, status: 'warning', lastUpdated: now, responsible: 'Gerencia' },
    { id: 'kpi-003', name: 'Cuentas por Cobrar', description: 'Total pendiente de cobro', formula: 'SUM(ar.amount - ar.paidAmount) WHERE status != paid', module: 'finance', value: 21840, target: 15000, unit: 'USD', frequency: 'daily', alertThreshold: 30000, warningThreshold: 20000, status: 'warning', lastUpdated: now, responsible: 'Contabilidad' },
    { id: 'kpi-004', name: 'Rotación de Inventarios', description: 'Veces que rota el inventario en el período', formula: 'Costo Ventas / Inventario Promedio', module: 'inventory', value: 4.2, target: 6, unit: 'veces', frequency: 'monthly', alertThreshold: 2, warningThreshold: 3, status: 'warning', lastUpdated: now, responsible: 'Almacén' },
    { id: 'kpi-005', name: 'Entregas a Tiempo', description: 'Porcentaje de despachos entregados en fecha', formula: 'Despachos a tiempo / Total despachos * 100', module: 'logistics', value: 92, target: 95, unit: '%', frequency: 'monthly', alertThreshold: 80, warningThreshold: 88, status: 'good', lastUpdated: now, responsible: 'Logística' },
    { id: 'kpi-006', name: 'Tasa de No Conformidad', description: 'Porcentaje de inspecciones con NC', formula: 'NC abiertas / Total inspecciones * 100', module: 'quality', value: 3.2, target: 2, unit: '%', frequency: 'monthly', alertThreshold: 8, warningThreshold: 5, status: 'good', lastUpdated: now, responsible: 'Calidad' },
    { id: 'kpi-007', name: 'Cumplimiento Plan Producción', description: 'Porcentaje de OTs completadas a tiempo', formula: 'OTs completadas / OTs planificadas * 100', module: 'production', value: 85, target: 90, unit: '%', frequency: 'monthly', alertThreshold: 70, warningThreshold: 80, status: 'warning', lastUpdated: now, responsible: 'Producción' },
    { id: 'kpi-008', name: 'Ciclo de Compra', description: 'Días promedio desde solicitud hasta recepción', formula: 'AVG(días entre solicitud y recepción)', module: 'purchasing', value: 14, target: 10, unit: 'días', frequency: 'monthly', alertThreshold: 25, warningThreshold: 18, status: 'warning', lastUpdated: now, responsible: 'Compras' },
    { id: 'kpi-009', name: 'Exactitud de Inventario', description: 'Coincidencia entre sistema y conteo físico', formula: 'Líneas exactas / Total líneas * 100', module: 'inventory', value: 96.5, target: 98, unit: '%', frequency: 'monthly', alertThreshold: 90, warningThreshold: 95, status: 'good', lastUpdated: now, responsible: 'Almacén' },
    { id: 'kpi-010', name: 'Presupuesto vs Real', description: 'Ejecución presupuestaria del período', formula: 'Gasto real / Presupuesto * 100', module: 'finance', value: 78, target: 100, unit: '%', frequency: 'monthly', alertThreshold: 110, warningThreshold: 95, status: 'good', lastUpdated: now, responsible: 'Gerencia' },
  ];

  return {
    company, branches, users, suppliers, articles, warehouses, customers, carriers,
    purchaseOrders, purchaseRequests, workOrders, qualityInspections, nonConformances,
    shipmentOrders, invoices, chartOfAccounts, journalEntries, accountingPeriods,
    costCenters, inventoryMovements, accountsReceivable, accountsPayable, budgets,
    auditLogs, kpis
  };
}

// --- DATA ACCESS LAYER ---
class DataStore {
  private data: ReturnType<typeof generateSyntheticData>;

  constructor() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        this.data = JSON.parse(stored);
      } catch {
        this.data = generateSyntheticData();
        this.save();
      }
    } else {
      this.data = generateSyntheticData();
      this.save();
    }
  }

  private save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(this.data));
  }

  resetData() {
    this.data = generateSyntheticData();
    this.save();
  }

  // Company
  getCompany() { return this.data.company; }

  // Branches
  getBranches() { return this.data.branches; }
  getBranch(id: string) { return this.data.branches.find(b => b.id === id); }

  // Users
  getUsers() { return this.data.users; }
  getUser(id: string) { return this.data.users.find(u => u.id === id); }
  authenticate(username: string, _password: string): User | null {
    const user = this.data.users.find(u => u.username === username && u.active);
    if (user) {
      user.lastLogin = new Date().toISOString();
      this.save();
    }
    return user || null;
  }

  // Suppliers
  getSuppliers() { return this.data.suppliers; }
  getSupplier(id: string) { return this.data.suppliers.find(s => s.id === id); }
  addSupplier(s: Omit<Supplier, 'id' | 'createdAt'>) {
    const supplier = { ...s, id: `sup-${uuidv4().slice(0, 8)}`, createdAt: new Date().toISOString() } as Supplier;
    this.data.suppliers.push(supplier);
    this.save();
    return supplier;
  }

  // Articles
  getArticles() { return this.data.articles; }
  getArticle(id: string) { return this.data.articles.find(a => a.id === id); }
  addArticle(a: Omit<Article, 'id' | 'createdAt'>) {
    const article = { ...a, id: `art-${uuidv4().slice(0, 8)}`, createdAt: new Date().toISOString() } as Article;
    this.data.articles.push(article);
    this.save();
    return article;
  }

  // Warehouses
  getWarehouses() { return this.data.warehouses; }
  getWarehouse(id: string) { return this.data.warehouses.find(w => w.id === id); }

  // Customers
  getCustomers() { return this.data.customers; }
  getCustomer(id: string) { return this.data.customers.find(c => c.id === id); }
  addCustomer(c: Omit<Customer, 'id' | 'createdAt'>) {
    const customer = { ...c, id: `cus-${uuidv4().slice(0, 8)}`, createdAt: new Date().toISOString() } as Customer;
    this.data.customers.push(customer);
    this.save();
    return customer;
  }

  // Carriers
  getCarriers() { return this.data.carriers; }

  // Purchase Orders
  getPurchaseOrders() { return this.data.purchaseOrders; }
  getPurchaseOrder(id: string) { return this.data.purchaseOrders.find(po => po.id === id); }

  // Purchase Requests
  getPurchaseRequests() { return this.data.purchaseRequests; }

  // Work Orders
  getWorkOrders() { return this.data.workOrders; }
  getWorkOrder(id: string) { return this.data.workOrders.find(wo => wo.id === id); }

  // Quality
  getQualityInspections() { return this.data.qualityInspections; }
  getNonConformances() { return this.data.nonConformances; }

  // Shipments
  getShipmentOrders() { return this.data.shipmentOrders; }

  // Invoices
  getInvoices() { return this.data.invoices; }
  getInvoice(id: string) { return this.data.invoices.find(i => i.id === id); }

  // Accounting
  getChartOfAccounts() { return this.data.chartOfAccounts; }
  getJournalEntries() { return this.data.journalEntries; }
  getAccountingPeriods() { return this.data.accountingPeriods; }
  getCostCenters() { return this.data.costCenters; }
  getAccountsReceivable() { return this.data.accountsReceivable; }
  getAccountsPayable() { return this.data.accountsPayable; }

  // Inventory
  getInventoryMovements() { return this.data.inventoryMovements; }
  getStockBalances(): { articleId: string; warehouseId: string; quantity: number; available: number }[] {
    const balances: Record<string, { articleId: string; warehouseId: string; quantity: number; available: number }> = {};
    this.data.inventoryMovements.forEach(m => {
      const key = `${m.articleId}-${m.warehouseId}`;
      if (!balances[key]) balances[key] = { articleId: m.articleId, warehouseId: m.warehouseId, quantity: 0, available: 0 };
      if (m.type === 'in') { balances[key].quantity += m.quantity; balances[key].available += m.quantity; }
      else if (m.type === 'out') { balances[key].quantity -= m.quantity; balances[key].available -= m.quantity; }
    });
    return Object.values(balances);
  }

  // Budgets
  getBudgets() { return this.data.budgets; }

  // KPIs
  getKPIs() { return this.data.kpis; }
  getKPIsByModule(module: string) { return this.data.kpis.filter(k => k.module === module); }

  // Audit
  getAuditLogs() { return this.data.auditLogs; }
  addAuditLog(log: Omit<AuditLog, 'id'>) {
    const entry = { ...log, id: `al-${uuidv4().slice(0, 8)}` } as AuditLog;
    this.data.auditLogs.unshift(entry);
    if (this.data.auditLogs.length > 500) this.data.auditLogs = this.data.auditLogs.slice(0, 500);
    this.save();
  }

  // Generic update
  updateEntity(collection: keyof ReturnType<typeof generateSyntheticData>, id: string, updates: Partial<any>) {
    const arr = this.data[collection] as any[];
    const idx = arr.findIndex((item: any) => item.id === id);
    if (idx >= 0) {
      arr[idx] = { ...arr[idx], ...updates };
      this.save();
      return arr[idx];
    }
    return null;
  }
}

export const store = new DataStore();
export { generateSyntheticData };
