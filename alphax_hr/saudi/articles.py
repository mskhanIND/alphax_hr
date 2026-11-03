"""Standard help-centre articles on the Saudi Labor Law (summaries in plain words, English and Arabic).

Seeded once into AlphaX Knowledge Article under category "Saudi Labor Law"; HR can edit, unpublish or delete them.
They reflect the law as amended with effect from February 2025. They are summaries, not legal text: each ends with
a pointer to the official text published by the Ministry of Human Resources and Social Development (hrsd.gov.sa).
"""

CATEGORY = "Saudi Labor Law"
NOTE = "\n\nSummary for employees. The official text of the Saudi Labor Law (hrsd.gov.sa) and your contract prevail."
NOTE_AR = "\n\nملخص للموظفين. يُرجع إلى النص الرسمي لنظام العمل السعودي (hrsd.gov.sa) وإلى عقد العمل."

ARTICLES = [
	{
		"title": "Working hours, rest days and Ramadan",
		"title_ar": "ساعات العمل والراحة الأسبوعية ورمضان",
		"body": "- Normal working time is up to 8 hours a day or 48 hours a week (Art. 98).\n"
				"- In Ramadan, Muslim employees work up to 6 hours a day or 36 hours a week.\n"
				"- No more than 5 hours in a row without a break for prayer, rest and food of at least 30 minutes (Art. 101).\n"
				"- Every employee has at least one full paid rest day a week, normally Friday (Art. 104).\n"
				"- Your shift, rest day and any week-off changes are shown in My Attendance.",
		"body_ar": "- ساعات العمل العادية لا تزيد على 8 ساعات يومياً أو 48 ساعة أسبوعياً (المادة 98).\n"
				   "- في رمضان لا تزيد ساعات العمل للمسلمين على 6 ساعات يومياً أو 36 ساعة أسبوعياً.\n"
				   "- لا يعمل الموظف أكثر من 5 ساعات متتالية دون فترة للصلاة والراحة والطعام لا تقل عن 30 دقيقة (المادة 101).\n"
				   "- لكل موظف يوم راحة أسبوعية كامل مدفوع الأجر على الأقل، وهو الجمعة عادةً (المادة 104).\n"
				   "- تظهر ورديتك ويوم راحتك في صفحة حضوري.",
	},
	{
		"title": "Overtime pay",
		"title_ar": "أجر العمل الإضافي",
		"body": "- Work beyond the normal hours is overtime (Art. 107).\n"
				"- For each overtime hour you are paid the hourly wage plus 50% of the hourly basic wage.\n"
				"- Work on your rest day or a public holiday counts as overtime.\n"
				"- With your agreement, the company may give paid days off instead of overtime pay.\n"
				"- Overtime is recorded from your check-ins and added to payroll by HR.",
		"body_ar": "- العمل بعد ساعات العمل العادية عمل إضافي (المادة 107).\n"
				   "- يُدفع عن كل ساعة إضافية أجر الساعة مضافاً إليه 50% من أجر الساعة الأساسي.\n"
				   "- العمل في يوم الراحة أو العطلات الرسمية يُعد عملاً إضافياً.\n"
				   "- يجوز باتفاق الطرفين منح أيام إجازة مدفوعة بدلاً من أجر العمل الإضافي.\n"
				   "- يُحتسب العمل الإضافي من تسجيل الحضور وتضيفه الموارد البشرية إلى الرواتب.",
	},
	{
		"title": "Annual leave",
		"title_ar": "الإجازة السنوية",
		"body": "- At least 21 days of paid annual leave a year; at least 30 days after 5 years of continuous service (Art. 109).\n"
				"- Your contract or company policy may give more (for example 30 days for everyone).\n"
				"- The leave year follows your joining anniversary; HR sets the timing so work continues.\n"
				"- You may not give up your annual leave for money while you are employed; unused days are paid when the "
				"contract ends.\n"
				"- See your balance and request leave in My Leave.",
		"body_ar": "- للموظف إجازة سنوية مدفوعة لا تقل عن 21 يوماً، وتزيد إلى 30 يوماً بعد 5 سنوات خدمة متصلة (المادة 109).\n"
				   "- قد يمنح العقد أو سياسة الشركة أكثر من ذلك (مثل 30 يوماً للجميع).\n"
				   "- تُحتسب سنة الإجازة من تاريخ مباشرة العمل، وتحدد الإدارة توقيتها بما لا يعطل العمل.\n"
				   "- لا يجوز التنازل عن الإجازة السنوية مقابل مال أثناء الخدمة، ويُعوَّض الموظف عن الأيام غير المستخدمة عند انتهاء العقد.\n"
				   "- تجد رصيدك وتطلب الإجازة من صفحة إجازاتي.",
	},
	{
		"title": "Sick leave",
		"title_ar": "الإجازة المرضية",
		"body": "- With a medical report you may take up to 120 days of sick leave in one year, counted from the first sick day "
				"(Art. 117).\n"
				"- The first 30 days are on full pay, the next 60 days on 75% of the wage, and the last 30 days unpaid.\n"
				"- Attach the medical report to your sick leave request; HR approves it once the report is attached.",
		"body_ar": "- يحق للموظف بموجب تقرير طبي إجازة مرضية حتى 120 يوماً في السنة الواحدة تبدأ من أول إجازة مرضية (المادة 117).\n"
				   "- أول 30 يوماً بأجر كامل، ثم 60 يوماً بثلاثة أرباع الأجر، ثم 30 يوماً بدون أجر.\n"
				   "- أرفق التقرير الطبي بطلب الإجازة المرضية، وتعتمدها الموارد البشرية بعد إرفاقه.",
	},
	{
		"title": "Maternity, paternity, marriage and bereavement leave",
		"title_ar": "إجازة الوضع والأبوة والزواج والوفاة",
		"body": "- Maternity: 12 weeks on full pay; 6 weeks must be taken right after the birth, and the leave may start up to "
				"4 weeks before the expected date (Art. 151).\n"
				"- Paternity: 3 days on full pay, taken within 7 days of the birth (Art. 113).\n"
				"- Marriage: 5 days on full pay (Art. 113).\n"
				"- Death of a spouse, parent or child: 5 days on full pay; death of a brother or sister: 3 days (Art. 113).\n"
				"- A Muslim widow has 4 months and 10 days of Iddah leave on full pay; a non-Muslim widow 15 days (Art. 160).\n"
				"- HR may ask for a supporting document.",
		"body_ar": "- الوضع: 12 أسبوعاً بأجر كامل، منها 6 أسابيع إلزامية بعد الولادة، ويجوز أن تبدأ قبل الموعد المتوقع بأربعة أسابيع (المادة 151).\n"
				   "- الأبوة: 3 أيام بأجر كامل خلال 7 أيام من الولادة (المادة 113).\n"
				   "- الزواج: 5 أيام بأجر كامل (المادة 113).\n"
				   "- وفاة الزوج أو أحد الأصول أو الفروع: 5 أيام بأجر كامل، ووفاة الأخ أو الأخت: 3 أيام (المادة 113).\n"
				   "- للعاملة المسلمة المتوفى زوجها عدة 4 أشهر و10 أيام بأجر كامل، ولغير المسلمة 15 يوماً (المادة 160).\n"
				   "- قد تطلب الموارد البشرية مستنداً مؤيداً.",
	},
	{
		"title": "Hajj and exam leave",
		"title_ar": "إجازة الحج وإجازة الامتحانات",
		"body": "- Hajj: paid leave of at least 10 and at most 15 days including Eid al-Adha, once during your service, after 2 "
				"years of continuous service (Art. 114).\n"
				"- Exams: a student employee gets paid leave to sit exams of a recognised study they were allowed to join; "
				"the days are set by the law and the company may ask for proof (Art. 115).",
		"body_ar": "- الحج: إجازة مدفوعة لا تقل عن 10 أيام ولا تزيد على 15 يوماً بما فيها إجازة عيد الأضحى، مرة واحدة طوال الخدمة "
				   "بعد سنتين من الخدمة المتصلة (المادة 114).\n"
				   "- الامتحانات: يحق للموظف المنتسب لدراسة معترف بها إجازة مدفوعة لأداء الامتحان، وللشركة طلب ما يثبت ذلك (المادة 115).",
	},
	{
		"title": "Public holidays",
		"title_ar": "إجازات الأعياد والمناسبات الرسمية",
		"body": "- Paid public holidays include Eid al-Fitr, Eid al-Adha, Founding Day (22 February) and National Day "
				"(23 September), as set in the Executive Regulations (Art. 112).\n"
				"- Work on a public holiday is paid as overtime.\n"
				"- The holiday list for your company is shown in AlphaX; HR updates it every year.",
		"body_ar": "- الإجازات الرسمية المدفوعة تشمل عيد الفطر وعيد الأضحى ويوم التأسيس (22 فبراير) واليوم الوطني (23 سبتمبر) "
				   "وفق اللائحة التنفيذية (المادة 112).\n"
				   "- العمل في الإجازة الرسمية يُحتسب عملاً إضافياً.\n"
				   "- تظهر قائمة الإجازات الرسمية لشركتك في النظام وتحدثها الموارد البشرية سنوياً.",
	},
	{
		"title": "Probation period",
		"title_ar": "فترة التجربة",
		"body": "- The contract may set a probation period of up to 180 days; it must be written in the contract (Art. 53).\n"
				"- During probation either side may end the contract without an end-of-service award or compensation.\n"
				"- An employee cannot be put on probation twice with the same employer, except in a different job or after "
				"6 months away, with written agreement.",
		"body_ar": "- يجوز أن ينص العقد على فترة تجربة لا تزيد على 180 يوماً، ويجب أن تكون مكتوبة في العقد (المادة 53).\n"
				   "- يحق لكل من الطرفين إنهاء العقد خلال فترة التجربة دون مكافأة نهاية خدمة أو تعويض.\n"
				   "- لا يجوز وضع الموظف تحت التجربة أكثر من مرة لدى صاحب العمل نفسه إلا في مهنة مختلفة أو بعد 6 أشهر من انتهاء علاقته، وباتفاق مكتوب.",
	},
	{
		"title": "Resignation and notice period",
		"title_ar": "الاستقالة وفترة الإشعار",
		"body": "- For an open-ended contract, an employee who resigns gives at least 30 days' written notice; an employer who "
				"ends the contract for a valid reason gives at least 60 days' notice (Art. 75).\n"
				"- A resignation can be withdrawn within 7 days unless the employer has already accepted it.\n"
				"- Without the notice, the party that ends the contract pays the other the wage for the notice period.\n"
				"- Raise a Resignation request in Services; your last working day sets your final settlement.",
		"body_ar": "- في العقد غير محدد المدة يقدم الموظف المستقيل إشعاراً كتابياً قبل 30 يوماً على الأقل، ويقدم صاحب العمل الذي يُنهي العقد لسبب مشروع إشعاراً قبل 60 يوماً على الأقل (المادة 75).\n"
				   "- يجوز العدول عن الاستقالة خلال 7 أيام ما لم يقبلها صاحب العمل.\n"
				   "- إذا لم يُراعَ الإشعار التزم الطرف المنهي للعقد بأجر مدة الإشعار للطرف الآخر.\n"
				   "- قدّم طلب الاستقالة من الخدمات، ويُحدد آخر يوم عمل التسوية النهائية.",
	},
	{
		"title": "End-of-service award",
		"title_ar": "مكافأة نهاية الخدمة",
		"body": "- At the end of the contract you receive half a month's wage for each of the first 5 years and a full month's "
				"wage for each year after that, with part years counted pro rata (Art. 84). The wage used is the last wage.\n"
				"- If you resign: one third of the award after 2 to 5 years, two thirds after 5 to 10 years, the full award "
				"after 10 years; nothing before 2 years (Art. 85).\n"
				"- Women resigning within 6 months of marriage or 3 months of giving birth, and resignations for force "
				"majeure, get the full award (Art. 87).\n"
				"- Dismissal for a reason in Art. 80 removes the award.",
		"body_ar": "- عند انتهاء العقد يستحق الموظف أجر نصف شهر عن كل سنة من السنوات الخمس الأولى وأجر شهر عن كل سنة بعدها، وتُحتسب كسور السنة بنسبتها (المادة 84)، على أساس الأجر الأخير.\n"
				   "- عند الاستقالة: ثلث المكافأة بعد سنتين وأقل من 5 سنوات، وثلثاها بعد 5 وأقل من 10 سنوات، وكاملها بعد 10 سنوات، ولا شيء قبل سنتين (المادة 85).\n"
				   "- تستحق المرأة كامل المكافأة إذا استقالت خلال 6 أشهر من الزواج أو 3 أشهر من الوضع، وكذلك الاستقالة لقوة قاهرة (المادة 87).\n"
				   "- الفصل لسبب من أسباب المادة 80 يُسقط المكافأة.",
	},
	{
		"title": "Penalties and warnings at work",
		"title_ar": "الجزاءات والإنذارات",
		"body": "- Penalties follow the company's approved work regulation: warning, fine, deferring a raise or promotion, "
				"suspension without pay, and dismissal in the cases of Art. 80 (Art. 66).\n"
				"- You are told in writing and heard before a penalty; you may object within the period in the regulation.\n"
				"- A fine for one violation is at most 5 days' wage, and fines in one month are at most 5 days' wage.\n"
				"- No penalty for a violation discovered more than 30 days earlier, and none more than 30 days after the "
				"investigation ends.\n"
				"- Your warnings and penalties are in My warnings, where you can acknowledge or object.",
		"body_ar": "- تُطبق الجزاءات وفق لائحة تنظيم العمل المعتمدة: الإنذار، والغرامة، وتأجيل العلاوة أو الترقية، والإيقاف عن العمل دون أجر، والفصل في حالات المادة 80 (المادة 66).\n"
				   "- يُبلَّغ الموظف كتابة ويُستمع إليه قبل توقيع الجزاء، وله الاعتراض خلال المدة المحددة في اللائحة.\n"
				   "- لا تزيد الغرامة عن المخالفة الواحدة على أجر 5 أيام، ولا تزيد الغرامات في الشهر على أجر 5 أيام.\n"
				   "- لا يُوقَّع جزاء عن مخالفة مضى على كشفها أكثر من 30 يوماً، ولا بعد 30 يوماً من انتهاء التحقيق.\n"
				   "- تجد إنذاراتك وجزاءاتك في صفحة إنذاراتي، ويمكنك الإقرار أو الاعتراض.",
	},
	{
		"title": "What can be deducted from your salary",
		"title_ar": "ما يجوز حسمه من الراتب",
		"body": "Without your written consent only these can be deducted (Art. 92):\n"
				"- Repayment of a loan from the company - at most 10% of your wage a month.\n"
				"- GOSI and other contributions required by law.\n"
				"- Savings fund or housing scheme contributions you joined.\n"
				"- Fines for violations, and damage you caused - at most 5 days' wage a month for damage (Art. 91).\n"
				"- Debts ordered by a court - at most a quarter of the wage, unless for family maintenance.\n"
				"In all cases the total deducted in a month may not exceed half of your wage unless the labour court allows "
				"more (Art. 93). Anything else needs your written consent. AlphaX checks these limits before payroll.",
		"body_ar": "لا يجوز الحسم من الأجر دون موافقة كتابية إلا في الحالات الآتية (المادة 92):\n"
				   "- استرداد قروض صاحب العمل بما لا يزيد على 10% من الأجر شهرياً.\n"
				   "- اشتراكات التأمينات الاجتماعية وغيرها مما يقرره النظام.\n"
				   "- اشتراكات صندوق الادخار أو برامج الإسكان التي انضم إليها الموظف.\n"
				   "- الغرامات عن المخالفات، وما يقابل ما أتلفه الموظف بما لا يزيد على أجر 5 أيام في الشهر (المادة 91).\n"
				   "- الديون المحكوم بها قضائياً بما لا يزيد على ربع الأجر ما لم تكن نفقة.\n"
				   "وفي جميع الأحوال لا يجوز أن يزيد مجموع المحسوم في الشهر على نصف الأجر إلا بقرار من المحكمة العمالية (المادة 93). وأي حسم آخر يحتاج موافقتك الكتابية، ويتحقق النظام من هذه الحدود قبل الرواتب.",
	},
	{
		"title": "Loans and salary advances",
		"title_ar": "القروض والسلف",
		"body": "- Request a Loan or a Salary Advance in Services. Your manager and HR approve it, then HR pays it by cash or "
				"bank transfer.\n"
				"- A loan is repaid in monthly installments from your salary. Without your written consent an installment is "
				"at most 10% of your wage (Art. 92).\n"
				"- A salary advance is part of your salary paid early and is recovered from the next salary.\n"
				"- You can ask to postpone an installment (Loan Postponement request) or settle the rest at once by cash, "
				"bank transfer or from one salary.\n"
				"- Anything still owed when you leave is deducted from your final settlement.\n"
				"- See your schedule in My loans.",
		"body_ar": "- اطلب قرضاً أو سلفة على الراتب من الخدمات، ويعتمده مديرك والموارد البشرية، ثم تصرفه الموارد البشرية نقداً أو بتحويل بنكي.\n"
				   "- يُسدَّد القرض بأقساط شهرية من الراتب، ولا يزيد القسط دون موافقتك الكتابية على 10% من أجرك (المادة 92).\n"
				   "- السلفة جزء من راتبك يُصرف مبكراً ويُسترد من الراتب التالي.\n"
				   "- يمكنك طلب تأجيل قسط (طلب تأجيل قسط) أو سداد المتبقي دفعة واحدة نقداً أو بتحويل بنكي أو من راتب واحد.\n"
				   "- ما يتبقى عند انتهاء الخدمة يُخصم من التسوية النهائية.\n"
				   "- تجد جدول السداد في صفحة قروضي.",
	},
	{
		"title": "Payment of wages",
		"title_ar": "دفع الأجور",
		"body": "- Wages are paid in Saudi riyals, monthly for monthly-paid employees, into your bank account (Art. 90; "
				"Wage Protection System).\n"
				"- Keep your IBAN up to date: use My Profile → Request a change, with a bank letter.\n"
				"- Your payslip with every earning and deduction is in My payslips.",
		"body_ar": "- تُدفع الأجور بالريال السعودي شهرياً للموظفين بأجر شهري في حساب الموظف البنكي (المادة 90 ونظام حماية الأجور).\n"
				   "- حدّث رقم الآيبان من ملفي ← طلب تعديل مع خطاب من البنك.\n"
				   "- تجد قسيمة الراتب بكل الاستحقاقات والحسومات في صفحة رواتبي.",
	},
	{
		"title": "Dismissal without an award (Article 80)",
		"title_ar": "الفصل دون مكافأة (المادة 80)",
		"body": "The employer may end the contract without notice or award, after hearing the employee, in cases such as:\n"
				"- assault on the employer, a manager or colleague at work;\n"
				"- not performing essential duties or not following safety instructions after a written warning;\n"
				"- serious misconduct or a breach of honesty or integrity;\n"
				"- deliberately causing the employer a material loss, reported within 24 hours;\n"
				"- forging documents to get the job;\n"
				"- absence without a valid reason for more than 30 days in a year or more than 15 days in a row, after a "
				"written warning;\n"
				"- revealing industrial or commercial secrets.\n"
				"The employee is given the chance to object.",
		"body_ar": "يجوز لصاحب العمل فسخ العقد دون مكافأة أو إشعار بعد سماع أقوال الموظف في حالات منها:\n"
				   "- الاعتداء على صاحب العمل أو المدير أو أحد الزملاء أثناء العمل؛\n"
				   "- عدم أداء الالتزامات الجوهرية أو عدم اتباع تعليمات السلامة بعد إنذار كتابي؛\n"
				   "- سوء السلوك أو الإخلال بالأمانة والشرف؛\n"
				   "- التسبب عمداً في خسارة مادية لصاحب العمل بشرط الإبلاغ خلال 24 ساعة؛\n"
				   "- التزوير للحصول على العمل؛\n"
				   "- الغياب دون سبب مشروع أكثر من 30 يوماً في السنة أو أكثر من 15 يوماً متتالية بعد إنذار كتابي؛\n"
				   "- إفشاء الأسرار الصناعية أو التجارية.\n"
				   "مع إتاحة الفرصة للموظف للاعتراض.",
	},
	{
		"title": "GOSI social insurance",
		"title_ar": "التأمينات الاجتماعية",
		"body": "- Saudi employees and the company both contribute to GOSI pensions and occupational hazards; the employee "
				"share is deducted from salary. Rates depend on when you were first registered (legacy or new system).\n"
				"- Non-Saudi employees are covered for occupational hazards, paid by the company only.\n"
				"- Contributions are calculated on basic salary plus housing, within the GOSI wage limits.\n"
				"- Your GOSI deduction appears on your payslip.",
		"body_ar": "- يشترك الموظف السعودي والشركة في التأمينات الاجتماعية (المعاشات والأخطار المهنية)، وتُخصم حصة الموظف من الراتب، وتختلف النسب حسب تاريخ أول تسجيل (النظام السابق أو الجديد).\n"
				   "- الموظف غير السعودي مشمول بفرع الأخطار المهنية وتتحملها الشركة وحدها.\n"
				   "- تُحتسب الاشتراكات على الراتب الأساسي وبدل السكن ضمن حدود أجر الاشتراك.\n"
				   "- يظهر خصم التأمينات في قسيمة راتبك.",
	},
]


def seed(force=False):
	import frappe

	if not frappe.db.exists("DocType", "AlphaX Knowledge Article"):
		return 0
	made = 0
	for a in ARTICLES:
		if frappe.db.exists("AlphaX Knowledge Article", {"title": a["title"]}) and not force:
			continue
		frappe.get_doc({"doctype": "AlphaX Knowledge Article", "title": a["title"], "title_ar": a["title_ar"], "category": CATEGORY,
						"published": 1, "body": a["body"] + NOTE, "body_ar": a["body_ar"] + NOTE_AR}).insert(ignore_permissions=True)
		made += 1
	return made
