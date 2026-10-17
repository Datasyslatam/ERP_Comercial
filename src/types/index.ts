// ============================================================
// DATASYS LATAM GROUP - ERP Enterprise System
// Type Definitions
// ============================================================

// --- CORE ENTITIES ---
export interface Company {
  id: string;
  name: string;
  taxId: string;
  country: string;
  currency: string;
  fiscalRegime: string;
  address: string;
  phone: string;
  email: string;
  active: boolean;
}

export interface Branch {
  id: string;
  companyId: string;
  name: string;
  code: string;
  address: string;
  active: boolean;
}

export interface User {
  id: string;
  username: string;
  fullName: string;
  email: string;
  role: UserRole;
  branchId: string;
  active: boolean;
  lastLogin?: string;
  createdAt: string;
}

export type UserRole = 'admin' | 'manager' | 'accountant' | 'warehouse' | 'purchasing' | 'quality' | 'logistics' | 'production' | 'viewer';

export interface AuditLog {
  id: string;
  userId: string;
  action: string;
  module: string;
  entityId: string;
  entityType: string;
  details: string;
  timestamp: string;
  ipAddress: string;
}

// --- SUPPLIERS & PURCHASING ---
export interface Supplier {
  id: string;
  name: string;
  taxId: string;
  contactName: string;
  email: string;
  phone: string;
  address: string;
  category: string;
  rating: number;
  paymentTerms: number;
  active: boolean;
  createdAt: string;
}

export interface PurchaseRequest {
  id: string;
  number: string;
  branchId: string;
  requestedBy: string;
  status: 'draft' | 'pending_approval' | 'approved' | 'rejected' | 'converted';
  items: PurchaseRequestItem[];
  priority: 'low' | 'medium' | 'high' | 'urgent';
  justification: string;
  createdAt: string;
  approvedAt?: string;
  approvedBy?: string;
}

export interface PurchaseRequestItem {
  id: string;
  articleId: string;
  quantity: number;
  estimatedPrice: number;
  notes: string;
}

export interface PurchaseOrder {
  id: string;
  number: string;
  supplierId: string;
  branchId: string;
  requestId?: string;
  status: 'draft' | 'sent' | 'partial' | 'received' | 'cancelled';
  items: PurchaseOrderItem[];
  subtotal: number;
  tax: number;
  total: number;
  currency: string;
  paymentTerms: number;
  deliveryDate: string;
  createdAt: string;
  createdBy: string;
}

export interface PurchaseOrderItem {
  id: string;
  articleId: string;
  quantity: number;
  receivedQuantity: number;
  unitPrice: number;
  taxRate: number;
  total: number;
}

export interface GoodsReceipt {
  id: string;
  number: string;
  purchaseOrderId: string;
  supplierId: string;
  warehouseId: string;
  status: 'pending' | 'inspected' | 'accepted' | 'rejected' | 'partial';
  receivedDate: string;
  items: GoodsReceiptItem[];
  receivedBy: string;
  notes: string;
}

export interface GoodsReceiptItem {
  id: string;
  articleId: string;
  expectedQuantity: number;
  receivedQuantity: number;
  acceptedQuantity: number;
  rejectedQuantity: number;
  lotNumber?: string;
  expiryDate?: string;
}

// --- INVENTORY ---
export interface Article {
  id: string;
  code: string;
  name: string;
  description: string;
  category: string;
  type: 'raw_material' | 'wip' | 'finished' | 'service' | 'supply';
  unit: string;
  unitConversion?: { toUnit: string; factor: number }[];
  minStock: number;
  maxStock: number;
  reorderPoint: number;
  cost: number;
  costMethod: 'fifo' | 'weighted_avg' | 'standard';
  active: boolean;
  createdAt: string;
}

export interface Warehouse {
  id: string;
  code: string;
  name: string;
  branchId: string;
  type: 'raw_materials' | 'wip' | 'finished' | 'general';
  zones: Zone[];
  active: boolean;
}

export interface Zone {
  id: string;
  code: string;
  name: string;
  warehouseId: string;
}

export interface InventoryMovement {
  id: string;
  type: 'in' | 'out' | 'transfer' | 'adjustment';
  articleId: string;
  warehouseId: string;
  zoneId?: string;
  quantity: number;
  cost: number;
  reference: string;
  referenceType: string;
  referenceId: string;
  lotNumber?: string;
  reason: string;
  userId: string;
  timestamp: string;
}

export interface StockBalance {
  articleId: string;
  warehouseId: string;
  quantity: number;
  reservedQuantity: number;
  availableQuantity: number;
  averageCost: number;
  lastMovement: string;
}

// --- PRODUCTION ---
export interface WorkOrder {
  id: string;
  number: string;
  productArticleId: string;
  plannedQuantity: number;
  completedQuantity: number;
  status: 'planned' | 'in_progress' | 'completed' | 'cancelled' | 'on_hold';
  priority: 'low' | 'medium' | 'high';
  startDate: string;
  endDate?: string;
  bomItems: BomItem[];
  actualConsumptions: Consumption[];
  branchId: string;
  createdBy: string;
  createdAt: string;
}

export interface BomItem {
  id: string;
  articleId: string;
  quantityRequired: number;
  unit: string;
}

export interface Consumption {
  id: string;
  workOrderId: string;
  articleId: string;
  quantity: number;
  lotNumber?: string;
  timestamp: string;
  userId: string;
}

// --- QUALITY ---
export interface InspectionPlan {
  id: string;
  name: string;
  articleId: string;
  type: 'reception' | 'process' | 'final';
  criteria: InspectionCriteria[];
  sampleSize: number;
  active: boolean;
}

export interface InspectionCriteria {
  id: string;
  name: string;
  specification: string;
  toleranceMin?: number;
  toleranceMax?: number;
  unit?: string;
  mandatory: boolean;
}

export interface QualityInspection {
  id: string;
  number: string;
  inspectionPlanId: string;
  type: 'reception' | 'process' | 'final';
  referenceType: string;
  referenceId: string;
  articleId: string;
  lotNumber?: string;
  sampleSize: number;
  inspectedQuantity: number;
  conformingQuantity: number;
  nonConformingQuantity: number;
  results: InspectionResult[];
  status: 'pending' | 'in_progress' | 'conforming' | 'non_conforming' | 'conditional';
  inspectorId: string;
  inspectionDate: string;
  notes: string;
}

export interface InspectionResult {
  criteriaId: string;
  measuredValue: number;
  specification: string;
  conforming: boolean;
}

export interface NonConformance {
  id: string;
  number: string;
  inspectionId?: string;
  articleId: string;
  description: string;
  severity: 'minor' | 'major' | 'critical';
  rootCause?: string;
  correctiveAction?: string;
  preventiveAction?: string;
  status: 'open' | 'investigating' | 'action_planned' | 'in_progress' | 'closed';
  openedBy: string;
  openedDate: string;
  closedDate?: string;
  cost: number;
}

// --- LOGISTICS ---
export interface ShipmentOrder {
  id: string;
  number: string;
  customerId: string;
  invoiceId?: string;
  status: 'pending' | 'reserved' | 'picking' | 'packed' | 'in_transit' | 'delivered' | 'returned';
  items: ShipmentItem[];
  carrierId?: string;
  trackingNumber?: string;
  plannedDate: string;
  actualDeliveryDate?: string;
  branchId: string;
  createdBy: string;
  createdAt: string;
}

export interface ShipmentItem {
  id: string;
  articleId: string;
  requestedQuantity: number;
  pickedQuantity: number;
  deliveredQuantity: number;
  lotNumber?: string;
}

export interface Carrier {
  id: string;
  name: string;
  contactName: string;
  phone: string;
  email: string;
  coverageZones: string[];
  active: boolean;
}

// --- CUSTOMERS ---
export interface Customer {
  id: string;
  name: string;
  taxId: string;
  email: string;
  phone: string;
  address: string;
  customerType: 'individual' | 'business' | 'government';
  taxRegime: string;
  paymentTerms: number;
  creditLimit: number;
  active: boolean;
  createdAt: string;
}

// --- INVOICING ---
export interface Invoice {
  id: string;
  number: string;
  series: string;
  customerId: string;
  branchId: string;
  status: 'draft' | 'pending_send' | 'sent' | 'accepted' | 'rejected' | 'error' | 'cancelled';
  items: InvoiceItem[];
  subtotal: number;
  taxAmount: number;
  total: number;
  currency: string;
  paymentMethod: string;
  dueDate: string;
  issueDate: string;
  electronicId?: string;
  electronicStatus?: string;
  xmlContent?: string;
  notes: string;
  createdBy: string;
  createdAt: string;
}

export interface InvoiceItem {
  id: string;
  articleId: string;
  description: string;
  quantity: number;
  unitPrice: number;
  discount: number;
  taxRate: number;
  taxAmount: number;
  total: number;
}

export interface CreditNote {
  id: string;
  number: string;
  invoiceId: string;
  customerId: string;
  reason: string;
  items: InvoiceItem[];
  total: number;
  status: 'draft' | 'sent' | 'accepted' | 'rejected';
  createdAt: string;
}

// --- ACCOUNTING ---
export interface ChartOfAccount {
  id: string;
  code: string;
  name: string;
  type: 'asset' | 'liability' | 'equity' | 'income' | 'expense';
  parentId?: string;
  level: number;
  active: boolean;
  allowsMovement: boolean;
}

export interface JournalEntry {
  id: string;
  number: string;
  date: string;
  reference: string;
  referenceType: string;
  referenceId: string;
  description: string;
  lines: JournalEntryLine[];
  status: 'draft' | 'posted' | 'reversed';
  periodId: string;
  createdBy: string;
  postedBy?: string;
  postedAt?: string;
  createdAt: string;
}

export interface JournalEntryLine {
  id: string;
  accountId: string;
  debit: number;
  credit: number;
  description: string;
  costCenterId?: string;
}

export interface AccountingPeriod {
  id: string;
  year: number;
  month: number;
  status: 'open' | 'closed' | 'locked';
  closedBy?: string;
  closedAt?: string;
}

export interface CostCenter {
  id: string;
  code: string;
  name: string;
  parentId?: string;
  active: boolean;
}

export interface AccountsReceivable {
  id: string;
  customerId: string;
  invoiceId: string;
  amount: number;
  paidAmount: number;
  dueDate: string;
  status: 'open' | 'partial' | 'paid' | 'overdue';
  currency: string;
}

export interface AccountsPayable {
  id: string;
  supplierId: string;
  invoiceId: string;
  amount: number;
  paidAmount: number;
  dueDate: string;
  status: 'open' | 'partial' | 'paid' | 'overdue';
  currency: string;
}

// --- BUDGETS & KPIs ---
export interface Budget {
  id: string;
  name: string;
  year: number;
  period: string;
  accountId?: string;
  costCenterId?: string;
  amount: number;
  currency: string;
  approvedBy?: string;
  status: 'draft' | 'approved' | 'active';
}

export interface KPI {
  id: string;
  name: string;
  description: string;
  formula: string;
  module: string;
  value?: number;
  target?: number;
  unit: string;
  frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly';
  alertThreshold?: number;
  warningThreshold?: number;
  status: 'good' | 'warning' | 'critical' | 'no_data';
  lastUpdated?: string;
  responsible?: string;
}

// --- IMPORT ---
export interface ImportBatch {
  id: string;
  fileName: string;
  module: string;
  totalRows: number;
  acceptedRows: number;
  rejectedRows: number;
  status: 'processing' | 'completed' | 'error';
  importedBy: string;
  importedAt: string;
  errors: ImportError[];
}

export interface ImportError {
  row: number;
  field: string;
  message: string;
  value: string;
}

// --- APP STATE ---
export interface AppState {
  currentUser: User | null;
  company: Company;
  branches: Branch[];
  isAuthenticated: boolean;
  sidebarCollapsed: boolean;
  currentModule: string;
}
