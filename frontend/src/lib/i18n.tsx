import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, boot } from './api'

type Lang = 'en' | 'ar'

// English is the key. Arabic uses Saudi HR terminology.
const ar: Record<string, string> = {
  'Home': 'الرئيسية',
  'My Space': 'مساحتي',
  'My Leave': 'إجازاتي',
  'My Attendance': 'حضوري',
  'My Payslips': 'قسائم رواتبي',
  'My Profile': 'ملفي الشخصي',
  'Approvals': 'الموافقات',
  'Team Calendar': 'تقويم الفريق',
  'People': 'الموظفون',
  'Compliance': 'الامتثال',
  'Payroll': 'الرواتب',
  'GOSI Register': 'سجل التأمينات',
  'End of Service': 'مكافأة نهاية الخدمة',
  'HR Team': 'فريق الموارد البشرية',
  'Manager': 'المدير',
  'Sign out': 'تسجيل الخروج',
  'Good morning': 'صباح الخير',
  'Good afternoon': 'مساء الخير',
  'Good evening': 'مساء الخير',
  'Today': 'اليوم',
  'Check in': 'تسجيل الحضور',
  'Check out': 'تسجيل الانصراف',
  'Checked in at': 'سجلت الحضور الساعة',
  'Not checked in yet': 'لم تسجل الحضور بعد',
  'Shift': 'الوردية',
  'Leave balance': 'رصيد الإجازات',
  'Apply for leave': 'تقديم طلب إجازة',
  'Leave type': 'نوع الإجازة',
  'From': 'من',
  'To': 'إلى',
  'Half day': 'نصف يوم',
  'Reason': 'السبب',
  'Submit request': 'إرسال الطلب',
  'Cancel': 'إلغاء',
  'Withdraw': 'سحب',
  'Allocated': 'المخصص',
  'Taken': 'المستخدم',
  'Pending': 'قيد الاعتماد',
  'Balance': 'الرصيد',
  'days': 'أيام',
  'day': 'يوم',
  'My requests': 'طلباتي',
  'Status': 'الحالة',
  'Open': 'مفتوح',
  'Approved': 'معتمد',
  'Rejected': 'مرفوض',
  'Cancelled': 'ملغي',
  'Draft': 'مسودة',
  'Present': 'حاضر',
  'Absent': 'غائب',
  'On Leave': 'في إجازة',
  'Half Day': 'نصف يوم',
  'Work From Home': 'عمل عن بعد',
  'Late': 'متأخر',
  'Late entries': 'مرات التأخير',
  'Working hours': 'ساعات العمل',
  'Upcoming holidays': 'الإجازات الرسمية القادمة',
  'No holidays in the next 60 days': 'لا توجد إجازات رسمية خلال 60 يومًا',
  'Net pay': 'صافي الراتب',
  'Gross pay': 'إجمالي الراتب',
  'Deductions': 'الاستقطاعات',
  'Earnings': 'الاستحقاقات',
  'Download PDF': 'تحميل PDF',
  'Payment days': 'أيام الدفع',
  'No payslips yet': 'لا توجد قسائم رواتب بعد',
  'Pending approvals': 'طلبات بانتظار الموافقة',
  'Approve': 'اعتماد',
  'Reject': 'رفض',
  'Comment (optional)': 'تعليق (اختياري)',
  'All caught up': 'لا توجد طلبات معلقة',
  'Nothing is waiting for you.': 'لا يوجد شيء بانتظارك.',
  'Search people, ID or Iqama…': 'ابحث بالاسم أو الرقم أو الإقامة…',
  'Add employee': 'إضافة موظف',
  'Department': 'القسم',
  'Designation': 'المسمى الوظيفي',
  'Joined': 'تاريخ الالتحاق',
  'Saudi': 'سعودي',
  'Non-Saudi': 'غير سعودي',
  'All': 'الكل',
  'Active': 'نشط',
  'Left': 'غادر',
  'Inactive': 'غير نشط',
  'Previous': 'السابق',
  'Next': 'التالي',
  'Edit': 'تعديل',
  'Save': 'حفظ',
  'Saved': 'تم الحفظ',
  'Personal': 'البيانات الشخصية',
  'Job': 'البيانات الوظيفية',
  'Attendance & Leave': 'الحضور والإجازات',
  'Contact': 'بيانات التواصل',
  'Saudi compliance': 'الامتثال السعودي',
  'Exit': 'إنهاء الخدمة',
  'Documents': 'الوثائق',
  'Data issues': 'ملاحظات على البيانات',
  'Iqama': 'الإقامة',
  'Passport': 'جواز السفر',
  'Work permit': 'رخصة العمل',
  'Contract': 'العقد',
  'expired': 'منتهية',
  'within_30': 'خلال 30 يومًا',
  'within_60': 'خلال 60 يومًا',
  'within_90': 'خلال 90 يومًا',
  'valid': 'سارية',
  'missing': 'غير مسجلة',
  'Saudization (estimate)': 'نسبة السعودة (تقديرية)',
  'Saudis': 'السعوديون',
  'Weighted Saudis': 'السعوديون (موزون)',
  'Headcount': 'عدد الموظفين',
  'Target': 'المستهدف',
  'Saudis needed for target': 'عدد السعوديين المطلوب للوصول للمستهدف',
  'Data readiness': 'جاهزية البيانات',
  'Document expiry': 'انتهاء الوثائق',
  'Fix these so leave, payroll and compliance work correctly.': 'عالج هذه الملاحظات ليعمل نظام الإجازات والرواتب والامتثال بشكل صحيح.',
  'holiday_list_missing_or_outdated': 'قائمة العطلات غير محددة أو قديمة',
  'leave_approver_missing': 'لا يوجد معتمد للإجازات',
  'user_account_missing': 'لا يوجد حساب مستخدم',
  'gosi_registration_date_missing': 'تاريخ التسجيل الأول في التأمينات غير مسجل',
  'iqama_number_missing': 'رقم الإقامة غير مسجل',
  'iqama_expiry_missing': 'تاريخ انتهاء الإقامة غير مسجل',
  'no_salary_data': 'لا توجد بيانات راتب',
  'hr_user_restricted_to_own_record': 'مستخدمو الموارد البشرية مقيدون بسجلهم فقط',
  'saudi_flag_mismatch': 'الجنسية سعودية لكن الموظف غير مُعلَّم كسعودي',
  'no_holiday_list': 'لا توجد قائمة عطلات',
  'holiday_list_outdated': 'قائمة العطلات قديمة',
  'no_leave_approver': 'لا يوجد معتمد للإجازات',
  'no_user_account': 'لا يوجد حساب مستخدم',
  'iqama_missing': 'رقم الإقامة غير مسجل',
  'high': 'عالية',
  'medium': 'متوسطة',
  'employees': 'موظفين',
  'Company holiday list is outdated': 'قائمة العطلات الافتراضية للشركة قديمة',
  'Payroll runs': 'مسيرات الرواتب',
  'This month': 'هذا الشهر',
  'Slips': 'القسائم',
  'Submitted': 'معتمدة',
  'Active employees': 'الموظفون النشطون',
  'Month': 'الشهر',
  'Employee': 'الموظف',
  'System': 'النظام',
  'Contributory wage': 'الأجر الخاضع',
  'Employee share': 'حصة الموظف',
  'Employer share': 'حصة صاحب العمل',
  'Total': 'الإجمالي',
  'Needs attention': 'يحتاج مراجعة',
  'Legacy': 'النظام السابق',
  'New': 'النظام الجديد',
  'Unclassified': 'غير مصنف',
  'Calculate': 'احسب',
  'Exit date': 'تاريخ ترك العمل',
  'Monthly wage (optional)': 'الأجر الشهري (اختياري)',
  'Service': 'مدة الخدمة',
  'years': 'سنوات',
  'Gross award': 'المكافأة الكاملة',
  'Entitlement': 'نسبة الاستحقاق',
  'Award': 'المكافأة المستحقة',
  'First 5 years (½ month/year)': 'أول 5 سنوات (نصف شهر عن كل سنة)',
  'After 5 years (1 month/year)': 'بعد 5 سنوات (شهر عن كل سنة)',
  'Termination by employer': 'إنهاء من صاحب العمل',
  'End of fixed-term contract': 'انتهاء عقد محدد المدة',
  'Resignation': 'استقالة',
  'Resignation – Article 87 exception': 'استقالة – حالات المادة 87',
  'Dismissal under Article 80': 'فصل وفق المادة 80',
  'Loading…': 'جارٍ التحميل…',
  'Something went wrong': 'حدث خطأ',
  'Try again': 'حاول مرة أخرى',
  'Your user is not linked to an employee record.': 'حسابك غير مرتبط بسجل موظف.',
  'Request submitted': 'تم إرسال الطلب',
  'Done': 'تم',
  'Mobile': 'الجوال',
  'Personal email': 'البريد الشخصي',
  'Emergency contact': 'جهة الاتصال للطوارئ',
  'Reports to': 'المدير المباشر',
  'Annual leave entitlement': 'الاستحقاق السنوي للإجازة',
  'per year': 'سنويًا',
  'New employee': 'موظف جديد',
  'First name': 'الاسم الأول',
  'Last name': 'اسم العائلة',
  'Gender': 'الجنس',
  'Date of birth': 'تاريخ الميلاد',
  'Date of joining': 'تاريخ الالتحاق',
  'Company': 'الشركة',
  'Create': 'إنشاء',
  'Back': 'رجوع',
  'requests': 'طلبات',
  'Who is out': 'من في إجازة',
  'Expense Claim': 'مطالبة مصروفات',
  'Leave Application': 'طلب إجازة',
  'Attendance Request': 'طلب تصحيح حضور',
  'Shift Request': 'طلب وردية',
  'Compensatory Leave Request': 'طلب إجازة تعويضية',
  'Language': 'اللغة',
  'Basic details': 'البيانات الأساسية',
  'Required by your company': 'حقول إلزامية في إعدادات شركتك',
  'These fields are mandatory in your HR setup.': 'هذه الحقول إلزامية حسب إعدادات الموارد البشرية لديكم.',
  'Please fill in': 'يرجى تعبئة',
  'Required': 'مطلوب',
  'Also filled automatically': 'تُعبأ تلقائيًا أيضًا',
  'Saving this employee needs these mandatory fields first': 'لحفظ بيانات هذا الموظف يجب أولًا تعبئة الحقول الإلزامية التالية',
  'salary_slip': 'آخر قسيمة راتب',
  'salary_structure_assignment': 'الراتب الأساسي في هيكل الرواتب',
  'manual': 'مدخل يدويًا',
  'none': 'لا توجد بيانات راتب',
  'Emergency phone': 'هاتف الطوارئ',
  'Iqama expiry': 'تاريخ انتهاء الإقامة',
  'First GOSI registration date': 'تاريخ أول تسجيل في التأمينات',
  'Decides Legacy vs New GOSI system — not the hire date.': 'يحدد النظام السابق أو الجديد للتأمينات — وليس تاريخ التعيين.',
  'Warnings': 'تنبيهات',
  'wage_capped': 'تم تطبيق الحد الأعلى للأجر',
  'no_salary_slip_for_period': 'لا توجد قسيمة راتب للفترة',
  'component_mapping_missing': 'لم يتم ربط مكونات الراتب',
  'no_contributory_wage': 'لا يوجد أجر خاضع',
  'Employees overview': 'نظرة على الموظفين',
  'Joiners (30 days)': 'المنضمون (30 يومًا)',
  'Leavers (30 days)': 'المغادرون (30 يومًا)',
  'By department': 'حسب القسم',
  'Open compliance': 'فتح الامتثال',
  'Open inbox': 'فتح الطلبات',
}

// Machine keys returned by the API need readable English too.
const en: Record<string, string> = {
  expired: 'Expired', within_30: 'Within 30 days', within_60: 'Within 60 days', within_90: 'Within 90 days', valid: 'Valid', missing: 'Not recorded',
  holiday_list_missing_or_outdated: 'Holiday list missing or outdated',
  leave_approver_missing: 'No leave approver',
  user_account_missing: 'No user account (cannot use self-service)',
  gosi_registration_date_missing: 'First GOSI registration date missing (Saudis)',
  iqama_number_missing: 'Iqama number missing',
  iqama_expiry_missing: 'Iqama expiry date missing',
  no_salary_data: 'No salary data',
  saudi_flag_mismatch: 'Nationality is Saudi but not flagged as Saudi',
  hr_user_restricted_to_own_record: 'HR users restricted to their own employee record',
  no_holiday_list: 'No holiday list', holiday_list_outdated: 'Holiday list outdated', no_leave_approver: 'No leave approver',
  no_user_account: 'No user account', iqama_missing: 'Iqama number missing',
  wage_capped: 'Wage capped at GOSI maximum', no_salary_slip_for_period: 'No salary slip for this month',
  component_mapping_missing: 'Salary components not mapped', no_contributory_wage: 'No contributory wage',
  high: 'High', medium: 'Medium',
  salary_slip: 'last payslip', salary_structure_assignment: 'salary structure base', manual: 'entered manually', none: 'no salary data',
}

interface I18n {
  lang: Lang
  dir: 'ltr' | 'rtl'
  t: (s: string) => string
  setLang: (l: Lang) => void
}

const Ctx = createContext<I18n | null>(null)

function readStored(): Lang | null {
  try {
    const v = localStorage.getItem('alphax-lang')
    return v === 'ar' || v === 'en' ? v : null
  } catch {
    return null
  }
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readStored() ?? boot.lang ?? 'en')
  const dir = lang === 'ar' ? 'rtl' : 'ltr'
  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = dir
  }, [lang, dir])
  const t = useCallback((s: string) => (lang === 'ar' ? ar[s] ?? en[s] ?? s : en[s] ?? s), [lang])
  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try {
      localStorage.setItem('alphax-lang', l)
    } catch {
      /* storage unavailable */
    }
    api.setLanguage(l).catch(() => undefined)
  }, [])
  const value = useMemo(() => ({ lang, dir, t, setLang }), [lang, dir, t, setLang]) as I18n
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useI18n() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useI18n outside provider')
  return v
}

export const arabicKeys = Object.keys(ar)
