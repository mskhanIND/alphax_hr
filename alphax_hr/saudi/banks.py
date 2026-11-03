"""Banks licensed in Saudi Arabia with their abbreviation, SAMA IBAN bank code (IBAN digits 5-6) and SWIFT/BIC.
Seeded into ERPNext's Bank list; HR can add or correct banks there. IBAN codes are those published for SAMA's
IBAN scheme; verify a new or merged bank's code with the bank before relying on it."""

BANKS = [
	# name, abbr, iban code, swift, Arabic
	("Saudi National Bank", "SNB", "10", "NCBKSAJE", "البنك الأهلي السعودي"),
	("Al Rajhi Bank", "RJHI", "80", "RJHISARI", "مصرف الراجحي"),
	("Riyad Bank", "RIBL", "20", "RIBLSARI", "بنك الرياض"),
	("Saudi Awwal Bank", "SAB", "45", "SABBSARI", "البنك السعودي الأول"),
	("Banque Saudi Fransi", "BSF", "55", "BSFRSARI", "البنك السعودي الفرنسي"),
	("Arab National Bank", "ANB", "30", "ARNBSARI", "البنك العربي الوطني"),
	("Alinma Bank", "ALINMA", "05", "INMASARI", "مصرف الإنماء"),
	("Bank Albilad", "BILAD", "15", "ALBISARI", "بنك البلاد"),
	("Bank AlJazira", "BAJ", "60", "BJAZSAJE", "بنك الجزيرة"),
	("Saudi Investment Bank", "SAIB", "65", "SIBCSARI", "البنك السعودي للاستثمار"),
	("Gulf International Bank Saudi Arabia", "GIB", "90", "GULFSARI", "بنك الخليج الدولي - السعودية"),
	("Emirates NBD", "ENBD", "95", "EBILSARI", "بنك الإمارات دبي الوطني"),
	("National Bank of Bahrain", "NBB", "71", "NBOBSARI", "بنك البحرين الوطني"),
	("National Bank of Kuwait", "NBK", "75", "NBOKSAJE", "بنك الكويت الوطني"),
	("Bank Muscat", "BM", "76", "BMUSSARI", "بنك مسقط"),
	("Deutsche Bank", "DB", "81", "DEUTSARI", "دويتشه بنك"),
	("STC Bank", "STCB", "", "", "بنك إس تي سي"),
	("D360 Bank", "D360", "", "", "بنك دال ثلاثمائة وستون"),
	("Vision Bank", "VISION", "", "", "بنك فيجن"),
]


def by_iban(iban):
	"""The bank row for a Saudi IBAN, or None."""
	code = (iban or "").replace(" ", "").upper()[4:6]
	return next((b for b in BANKS if b[2] and b[2] == code), None) if len(code) == 2 else None
